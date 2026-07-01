"""
Parser Agent

Identifies hierarchical structure in extracted text (Act → Part → Section → Subsection).

Input: {"text": "extracted_text", "law_name": "Act 843"}
Output: {"chunks": [...], "hierarchy": {...}, "metadata": {...}}
"""
from typing import Dict, Any
from agents.base_agent import BaseAgent


class ParserAgent(BaseAgent):
    """Parser Agent - Identifies legal document hierarchy."""

    def __init__(self, sector=None):
        super().__init__("ParserAgent", sector)

    def validate_input(self, input_data: Any) -> bool:
        if not isinstance(input_data, dict):
            return False
        return "text" in input_data and "law_name" in input_data

    def execute(self, input_data: Dict[str, Any], **kwargs) -> Dict[str, Any]:
        from tools.parsing_tools import parse_hierarchy, build_chunks, extract_metadata, save_chunks
        from config.settings import settings

        text = input_data["text"]
        law_name = input_data["law_name"]

        self.logger.info(f"Parsing: {law_name} ({len(text)} characters)")

        # 1. Extract top-level metadata
        metadata = extract_metadata(text)
        metadata["law_name"] = law_name

        # 2. Build hierarchy tree
        hierarchy = parse_hierarchy(text, law_name)

        # 3. Create overlapping chunks with metadata
        chunks = build_chunks(
            hierarchy,
            chunk_size=settings.PDF_CHUNK_SIZE,
            overlap=settings.PDF_OVERLAP,
        )

        self.logger.info(f"Created {len(chunks)} chunks from {law_name}")

        # 4. Save chunks to disk
        chunks_dir = self.get_sector_path("chunks")
        saved_path = save_chunks(chunks, chunks_dir)
        self.logger.info(f"Saved chunks to: {saved_path}")

        self._save_checkpoint("last_parse", {
            "law_name": law_name,
            "chunk_count": len(chunks),
            "parts": len(hierarchy.get("parts", [])),
        })

        return {
            "chunks": chunks,
            "hierarchy": hierarchy,
            "metadata": metadata,
        }

    def format_output(self, result: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "status": "success",
            "chunks": result.get("chunks", []),
            "hierarchy": result.get("hierarchy", {}),
            "metadata": result.get("metadata", {}),
            "chunk_count": len(result.get("chunks", [])),
            "sector": self.sector,
        }
