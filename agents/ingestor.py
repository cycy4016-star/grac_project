"""
Ingestor Agent

Extracts text from law PDFs and prepares for parsing.

Input: {"pdf_path": "path/to/law.pdf"}
Output: {"text": "extracted_text", "source": "law_name", "pages": 50}
"""
from typing import Dict, Any
from pathlib import Path

from agents.base_agent import BaseAgent
from config.settings import settings


class IngestorAgent(BaseAgent):
    """Ingestor Agent - Extracts text from law PDFs."""

    def __init__(self, sector=None):
        super().__init__("IngestorAgent", sector)

    def validate_input(self, input_data: Any) -> bool:
        if not isinstance(input_data, dict):
            return False
        return "pdf_path" in input_data

    def execute(self, input_data: Dict[str, Any], **kwargs) -> Dict[str, Any]:
        from tools.pdf_tools import extract_text_from_pdf, save_extracted_text

        pdf_path = input_data["pdf_path"]
        self.logger.info(f"Extracting text from: {pdf_path}")

        result = extract_text_from_pdf(pdf_path)

        if result["pages"] == 0:
            raise ValueError(f"PDF has no pages: {pdf_path}")

        if result["is_scanned"]:
            self.logger.warning(f"PDF appears to be scanned — text extraction may be incomplete: {pdf_path}")

        if not result["text"]:
            self.logger.warning(f"No text extracted from: {pdf_path}")

        # Save to parsed/ directory
        parsed_dir = self.get_sector_path("parsed")
        saved_path = save_extracted_text(result["text"], result["source"], parsed_dir)
        self.logger.info(f"Saved extracted text to: {saved_path}")

        self._save_checkpoint("last_extraction", {
            "source": result["source"],
            "pages": result["pages"],
            "method": result["method"],
            "saved_path": str(saved_path),
        })

        return result

    def format_output(self, result: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "status": "success",
            "extracted_text": result.get("text", ""),
            "source": result.get("source", ""),
            "pages": result.get("pages", 0),
            "method": result.get("method", "unknown"),
            "is_scanned": result.get("is_scanned", False),
            "sector": self.sector,
        }
