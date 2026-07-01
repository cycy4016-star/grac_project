"""
Embedding Tools

Used by: EmbedderAgent
Responsibilities:
- Create vector embeddings (local sentence-transformers or API-based)
- Store/retrieve chunks in ChromaDB with metadata

Supports three embedding modes:
  - "local": sentence-transformers (offline, no API key needed)
  - "openai": OpenAI's text-embedding-ada-002 / text-embedding-3-small
  - "nvidia": NVIDIA's nv-embed-qa-4 via OpenAI-compatible API
  - "auto": picks the first available API provider, falls back to local
"""
from pathlib import Path
from typing import Optional


def get_collection_name(sector: str, prefix: str = "grac") -> str:
    """Return a consistent ChromaDB collection name for a sector."""
    return f"{prefix}_{sector}"


def get_chroma_client(db_path: str | Path):
    """
    Return a persistent ChromaDB client.

    Args:
        db_path: Path to the ChromaDB persistence directory
    """
    import chromadb

    db_path = Path(db_path)
    db_path.mkdir(parents=True, exist_ok=True)
    return chromadb.PersistentClient(path=str(db_path))


def get_or_create_collection(client, collection_name: str):
    """Get an existing collection or create it if it doesn't exist."""
    return client.get_or_create_collection(
        name=collection_name,
        metadata={"hnsw:space": "cosine"},
    )


# ---------------------------------------------------------------------------
# Embedding model loading
# ---------------------------------------------------------------------------

def load_embedding_model(model_name: str = "sentence-transformers/all-MiniLM-L6-v2"):
    """
    Load and return a local sentence-transformer model.

    Used only when EMBEDDING_PROVIDER is "local" or when no API key is available.
    """
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(model_name)


def _detect_embedding_provider() -> tuple[str, str, Optional[str]]:
    """
    Detect which embedding provider to use.

    Returns:
        (provider_name, model_name, base_url_for_api)
        provider_name is "local", "openai", or "nvidia"
    """
    from config.settings import settings

    preferred = settings.EMBEDDING_PROVIDER

    if preferred == "local":
        return "local", settings.EMBEDDING_MODEL, None

    if preferred == "openai":
        return "openai", settings.EMBEDDING_API_MODEL, None

    if preferred == "nvidia":
        return "nvidia", settings.EMBEDDING_API_MODEL, "https://integrate.api.nvidia.com/v1"

    # auto-detect: try NVIDIA first (free), then OpenAI, then local
    import os
    if os.getenv("NVIDIA_API_KEY"):
        return "nvidia", settings.EMBEDDING_API_MODEL, "https://integrate.api.nvidia.com/v1"
    if os.getenv("OPENAI_API_KEY"):
        return "openai", settings.EMBEDDING_API_MODEL, None

    return "local", settings.EMBEDDING_MODEL, None


def _get_api_embedding_client(base_url: Optional[str] = None):
    """
    Create an OpenAI-compatible client for API-based embeddings.

    Uses NVIDIA_API_KEY or OPENAI_API_KEY depending on the base_url.
    """
    from openai import OpenAI
    import os

    if base_url and "nvidia" in base_url:
        api_key = os.getenv("NVIDIA_API_KEY", "")
        if not api_key:
            raise RuntimeError("NVIDIA_API_KEY is not set for embeddings")
    else:
        api_key = os.getenv("OPENAI_API_KEY", "")
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY is not set for embeddings")

    return OpenAI(api_key=api_key, base_url=base_url, timeout=30)


def _embed_texts_api(texts: list[str], model: str, base_url: Optional[str] = None) -> list[list[float]]:
    """
    Embed a list of texts using the OpenAI-compatible API.

    Args:
        texts: List of text strings to embed
        model: Embedding model name
        base_url: Optional base URL for the API (NVIDIA uses a different one)

    Returns:
        List of embedding vectors
    """
    client = _get_api_embedding_client(base_url)

    response = client.embeddings.create(input=texts, model=model)
    return [r.embedding for r in response.data]


# ---------------------------------------------------------------------------
# Embed and store
# ---------------------------------------------------------------------------

def embed_chunks(
    chunks: list[dict],
    model,
    collection,
    batch_size: int = 64,
) -> int:
    """
    Embed a list of chunks and upsert them into a ChromaDB collection.

    Works with both local SentenceTransformer models and API-based
    embedding providers. If `model` is a string, it's treated as an
    API embedding model name.

    Args:
        chunks: List of chunk dicts with "id", "text", "metadata" keys
        model: SentenceTransformer model OR a string (API model name)
        collection: ChromaDB collection object
        batch_size: Number of chunks to embed per batch

    Returns:
        Number of chunks successfully stored
    """
    if not chunks:
        return 0

    is_api = isinstance(model, str)
    stored = 0

    for i in range(0, len(chunks), batch_size):
        batch = chunks[i: i + batch_size]

        texts = [c["text"] for c in batch]
        ids = [c["id"] for c in batch]
        metadatas = [c["metadata"] for c in batch]

        if is_api:
            provider_name, _, base_url = _detect_embedding_provider()
            embeddings = _embed_texts_api(texts, model, base_url)
        else:
            embeddings = model.encode(texts, show_progress_bar=False).tolist()

        collection.upsert(
            ids=ids,
            embeddings=embeddings,
            documents=texts,
            metadatas=metadatas,
        )
        stored += len(batch)

    return stored


# ---------------------------------------------------------------------------
# Query
# ---------------------------------------------------------------------------

def query_collection(
    query_text: str,
    model,
    collection,
    top_k: int = 5,
    where: Optional[dict] = None,
) -> list[dict]:
    """
    Query ChromaDB for the most relevant law chunks.

    Args:
        query_text: The user query or policy text snippet
        model: SentenceTransformer model OR a string (API model name)
        collection: ChromaDB collection object
        top_k: Number of results to return
        where: Optional metadata filter, e.g. {"section_number": "5"}

    Returns:
        List of result dicts with keys: id, text, metadata, distance, score
    """
    is_api = isinstance(model, str)

    if is_api:
        provider_name, _, base_url = _detect_embedding_provider()
        query_embedding = _embed_texts_api([query_text], model, base_url)
    else:
        query_embedding = model.encode([query_text], show_progress_bar=False).tolist()

    query_kwargs: dict = {
        "query_embeddings": query_embedding,
        "n_results": top_k,
        "include": ["documents", "metadatas", "distances"],
    }
    if where:
        query_kwargs["where"] = where

    results = collection.query(**query_kwargs)

    output = []
    ids = results.get("ids", [[]])[0]
    docs = results.get("documents", [[]])[0]
    metas = results.get("metadatas", [[]])[0]
    distances = results.get("distances", [[]])[0]

    for chunk_id, doc, meta, dist in zip(ids, docs, metas, distances):
        output.append(
            {
                "id": chunk_id,
                "text": doc,
                "metadata": meta,
                "distance": dist,
                "score": round(1 - dist, 4),
            }
        )

    return output


# ---------------------------------------------------------------------------
# Collection helpers
# ---------------------------------------------------------------------------

def collection_exists(client, collection_name: str) -> bool:
    """Return True if the named collection exists in ChromaDB."""
    existing = [c.name for c in client.list_collections()]
    return collection_name in existing


def get_collection_count(collection) -> int:
    """Return the number of chunks stored in a collection."""
    return collection.count()
