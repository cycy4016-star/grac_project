"""
Writer Agent

Generates professional compliance documents.

Input: {"type": "gap_analysis"|"incident_report"|"policy_draft", "content": {...}}
Output: {"document": "...", "format": "pdf", "path": "..."}
"""
from typing import Dict, Any
from pathlib import Path
from agents.base_agent import BaseAgent


class WriterAgent(BaseAgent):
    """Writer Agent - Generates professional compliance documents."""

    def __init__(self, sector=None):
        super().__init__("WriterAgent", sector)

    def validate_input(self, input_data: Any) -> bool:
        if not isinstance(input_data, dict):
            return False
        return "type" in input_data and "content" in input_data

    def execute(self, input_data: Dict[str, Any], **kwargs) -> Dict[str, Any]:
        from tools.llm_tools import build_document_prompt
        from tools.document_tools import generate_pdf, generate_docx
        from config.settings import settings

        doc_type = input_data["type"]
        content = input_data["content"]
        output_format = input_data.get("format", "pdf")  # "pdf" | "docx"
        metadata = input_data.get("metadata", {})

        self.logger.info(f"Generating {doc_type} document ({output_format})")

        # 1. Load sector-specific skill context if available
        skill_context = self._load_skill_context(doc_type)
        if skill_context:
            content["_skill_context"] = skill_context

        # 2. Build prompt (with system awareness) and generate draft
        from tools.llm_tools import _system_knowledge_block
        from tools.llm_providers import call_llm
        prompt = f"{_system_knowledge_block()}\n\n---\n\n{build_document_prompt(doc_type, content, self.sector)}"
        document_text = call_llm(
            prompt=prompt,
            system="You are a professional compliance document writer for Ghanaian regulatory law. Produce clear, authoritative documents with proper legal citations.",
        )

        self.logger.info(f"Generated document draft ({len(document_text)} chars)")

        # 3. Render to file
        title = _doc_type_to_title(doc_type, self.sector)
        output_dir = settings.PROJECT_ROOT / "data" / "output"
        output_dir.mkdir(parents=True, exist_ok=True)

        import re
        from datetime import datetime
        safe_type = re.sub(r"\s+", "_", doc_type.lower())
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{safe_type}_{self.sector}_{timestamp}.{output_format}"
        output_path = output_dir / filename

        if output_format == "docx":
            generate_docx(document_text, title, output_path, self.sector, metadata)
        else:
            generate_pdf(document_text, title, output_path, self.sector, metadata)

        self.logger.info(f"Document saved to: {output_path}")

        self._save_checkpoint("last_document", {
            "doc_type": doc_type,
            "format": output_format,
            "path": str(output_path),
            "char_count": len(document_text),
        })

        return {
            "document": document_text,
            "format": output_format,
            "path": str(output_path),
            "title": title,
        }

    def format_output(self, result: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "status": "success",
            "document": result.get("document", ""),
            "format": result.get("format", "pdf"),
            "path": result.get("path", ""),
            "title": result.get("title", ""),
            "sector": self.sector,
        }

    def _load_skill_context(self, doc_type: str) -> str:
        """Load sector-specific skill template if it exists."""
        from config.settings import settings

        skill_file = settings.get_sector_skills_path(self.sector) / f"{doc_type}.md"
        if skill_file.exists():
            return skill_file.read_text(encoding="utf-8")
        return ""


def _doc_type_to_title(doc_type: str, sector: str) -> str:
    titles = {
        "gap_analysis": "Compliance Gap Analysis Report",
        "incident_report": "Cybersecurity Incident Report",
        "policy_draft": "Compliance Policy Document",
    }
    sector_label = sector.replace("_", " ").title()
    base = titles.get(doc_type, doc_type.replace("_", " ").title())
    return f"{base} — {sector_label}"
