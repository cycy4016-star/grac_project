"""
Embedder Agent

Converts parsed law chunks into vector embeddings and stores in ChromaDB.

Input: {"chunks": [...], "metadata": {...}}
Output: {"collection_id": "...", "chunks_stored": 100, "ready": True}
"""
from typing import Dict, Any
from agents.base_agent import BaseAgent


class EmbedderAgent(BaseAgent):
    """Embedder Agent - Creates vectors and stores in ChromaDB."""

    def __init__(self, sector=None):
        super().__init__("EmbedderAgent", sector)
        self._model = None  # Lazy-loaded

    def validate_input(self, input_data: Any) -> bool:
        if not isinstance(input_data, dict):
            return False
        return "chunks" in input_data

    def _get_model(self):
        """Resolve the embedding model — string for API, object for local."""
        if self._model is None:
            from tools.embedding_tools import load_embedding_model, _detect_embedding_provider
            from config.settings import settings
            provider, model_name, _ = _detect_embedding_provider()
            if provider == "local":
                self.logger.info(f"Loading local embedding model: {model_name}")
                self._model = load_embedding_model(model_name)
            else:
                self.logger.info(f"Using API embedding model: {model_name} (provider: {provider})")
                self._model = model_name
        return self._model

    def execute(self, input_data: Dict[str, Any], **kwargs) -> Dict[str, Any]:
        from tools.embedding_tools import (
            get_chroma_client, get_or_create_collection,
            get_collection_name, embed_chunks, get_collection_count,
        )
        from config.settings import settings

        chunks = input_data["chunks"]
        self.logger.info(f"Embedding {len(chunks)} chunks for sector: {self.sector}")

        # 1. Connect to ChromaDB
        client = get_chroma_client(settings.CHROMA_DB_PATH)
        collection_name = get_collection_name(self.sector, settings.CHROMA_COLLECTION_PREFIX)
        collection = get_or_create_collection(client, collection_name)

        # 2. Load embedding model
        model = self._get_model()

        # 3. Embed and store
        stored_count = embed_chunks(chunks, model, collection)
        total_in_collection = get_collection_count(collection)

        self.logger.info(
            f"Stored {stored_count} chunks. Collection '{collection_name}' now has {total_in_collection} total."
        )

        self._save_checkpoint("last_embed", {
            "collection_name": collection_name,
            "chunks_stored": stored_count,
            "collection_total": total_in_collection,
        })

        return {
            "collection_id": collection_name,
            "chunks_stored": stored_count,
            "collection_total": total_in_collection,
        }

    def format_output(self, result: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "status": "success",
            "collection_id": result.get("collection_id"),
            "chunks_stored": result.get("chunks_stored", 0),
            "collection_total": result.get("collection_total", 0),
            "ready": True,
            "sector": self.sector,
        }
