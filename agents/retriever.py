"""
Retriever Agent

Searches law embeddings in ChromaDB to find relevant sections.

Input: {"query": "...", "sector": "...", "top_k": 5}
Output: {"results": [...], "confidence_scores": [...]}
"""
from typing import Dict, Any
from agents.base_agent import BaseAgent


class RetrieverAgent(BaseAgent):
    """Retriever Agent - Searches law database for relevant sections."""

    def __init__(self, sector=None):
        super().__init__("RetrieverAgent", sector)
        self._model = None

    def validate_input(self, input_data: Any) -> bool:
        if not isinstance(input_data, dict):
            return False
        query = input_data.get("query", "")
        return bool(query and query.strip())

    def _get_model(self):
        if self._model is None:
            from tools.embedding_tools import load_embedding_model, _detect_embedding_provider
            from config.settings import settings
            provider, model_name, _ = _detect_embedding_provider()
            if provider == "local":
                self._model = load_embedding_model(model_name)
            else:
                self._model = model_name
        return self._model

    def execute(self, input_data: Dict[str, Any], **kwargs) -> Dict[str, Any]:
        from tools.embedding_tools import (
            get_chroma_client, get_or_create_collection,
            get_collection_name, query_collection, collection_exists,
        )
        from config.settings import settings

        query = input_data["query"]
        top_k = input_data.get("top_k", 5)
        min_score = input_data.get("min_score", settings.MIN_RETRIEVAL_CONFIDENCE)
        sector = input_data.get("sector", self.sector)

        self.logger.info(f"Searching: '{query[:80]}...' (sector={sector}, top_k={top_k})")

        try:
            # 1. Connect to ChromaDB
            client = get_chroma_client(settings.CHROMA_DB_PATH)
            collection_name = get_collection_name(sector, settings.CHROMA_COLLECTION_PREFIX)

            if not collection_exists(client, collection_name):
                self.logger.warning(f"Collection '{collection_name}' not found — run IngestorAgent and EmbedderAgent first.")
                return {"results": [], "confidence_scores": [], "warning": "Collection not found"}

            collection = get_or_create_collection(client, collection_name)
            model = self._get_model()

            # 2. Query ChromaDB
            raw_results = query_collection(query, model, collection, top_k=top_k)
        except Exception as e:
            self.logger.error(f"Retrieval failed: {e}")
            return {"results": [], "confidence_scores": [], "warning": str(e)}

        # 3. Filter by minimum confidence
        results = [r for r in raw_results if r["score"] >= min_score]
        confidence_scores = [r["score"] for r in results]

        self.logger.info(f"Found {len(results)} results above confidence threshold {min_score}")

        return {
            "results": results,
            "confidence_scores": confidence_scores,
            "query": query,
        }

    def format_output(self, result: Dict[str, Any]) -> Dict[str, Any]:
        results = result.get("results") or []
        return {
            "status": "success",
            "results": results,
            "confidence_scores": result.get("confidence_scores", []),
            "count": len(results),
            "query": result.get("query", ""),
            "sector": self.sector,
        }
