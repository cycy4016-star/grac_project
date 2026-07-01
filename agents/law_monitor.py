"""
Law Monitor Agent

Consciously watches for new law PDFs and decides when to trigger ingestion.

Detection modes:
  1. Filesystem watch — detects new/modified PDFs in raw directories
  2. Web monitor — periodically checks Parliament, CSA, BoG for new publications

When new content is found, the agent logs its decision and triggers
the full ingestion pipeline (IngestorAgent → ParserAgent → EmbedderAgent).
"""

import re
import time
import hashlib
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, Any, Optional

from agents.base_agent import BaseAgent
from config.settings import settings
from utils.sector_manager import sector_manager


class LawMonitorAgent(BaseAgent):
    """LawMonitorAgent — watches for new laws and consciously triggers ingestion."""

    def __init__(self, sector: Optional[str] = None):
        super().__init__("LawMonitorAgent", sector)
        self._known_files: dict[str, str] = {}  # path -> content hash
        self._load_checkpoint()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def validate_input(self, input_data: Any) -> bool:
        if not isinstance(input_data, dict):
            return False
        mode = input_data.get("mode", "filesystem")
        return mode in ("filesystem", "web", "scan")

    def execute(self, input_data: Dict[str, Any], **kwargs) -> Dict[str, Any]:
        mode = input_data.get("mode", "filesystem")
        report_only = input_data.get("report_only", False)

        discoveries = []

        if mode in ("filesystem", "scan"):
            discoveries += self._scan_raw_directories()

        if mode in ("web", "scan"):
            discoveries += self._check_web_sources()

        decision = self._decide(discoveries)

        if decision.get("should_ingest") and not report_only:
            results = self._execute_ingestion(decision["to_ingest"])
            decision["ingestion_results"] = results

        self._save_checkpoint("last_monitor_cycle", {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "discoveries": len(discoveries),
            "decision": decision.get("summary", ""),
        })

        return {
            "discoveries": discoveries,
            "decision": decision,
        }

    def format_output(self, result: Dict[str, Any]) -> Dict[str, Any]:
        discoveries = result.get("discoveries", [])
        decision = result.get("decision", {})
        return {
            "status": "success",
            "agent": self.name,
            "sector": self.sector,
            "new_files_found": len(discoveries),
            "should_ingest": decision.get("should_ingest", False),
            "summary": decision.get("summary", "No new content detected"),
            "ingestion_results": decision.get("ingestion_results", []),
            "discoveries": [
                {
                    "source": d.get("source"),
                    "name": d.get("name"),
                    "sector": d.get("sector"),
                    "size": d.get("size"),
                }
                for d in discoveries
            ],
        }

    # ------------------------------------------------------------------
    # Filesystem scanning
    # ------------------------------------------------------------------

    def _scan_raw_directories(self) -> list[dict]:
        discoveries = []
        sectors = sector_manager.list_enabled_sectors()

        for sector in sectors:
            raw_dir = sector_manager.get_raw_path(sector)
            if not raw_dir.exists():
                continue

            for pdf_path in sorted(raw_dir.glob("*.pdf")):
                file_hash = self._hash_file(pdf_path)
                prev_hash = self._known_files.get(str(pdf_path))

                if prev_hash is None:
                    status = "new"
                elif prev_hash != file_hash:
                    status = "modified"
                else:
                    continue

                discoveries.append({
                    "source": "filesystem",
                    "sector": sector,
                    "path": str(pdf_path),
                    "name": pdf_path.stem,
                    "size": pdf_path.stat().st_size,
                    "hash": file_hash,
                    "status": status,
                    "discovered_at": datetime.now(timezone.utc).isoformat(),
                })
                self._known_files[str(pdf_path)] = file_hash

        self._save_known_files()
        return discoveries

    # ------------------------------------------------------------------
    # Web source monitoring
    # ------------------------------------------------------------------

    def _check_web_sources(self) -> list[dict]:
        from tools.web_research_tools import search_web, fetch_page_text

        discoveries = []
        sources = [
            {
                "name": "Parliament of Ghana",
                "url": "https://repository.parliament.gh",
                "queries": ["site:repository.parliament.gh act 2025", "site:repository.parliament.gh act 2026"],
            },
            {
                "name": "Cyber Security Authority",
                "url": "https://www.csa.gov.gh",
                "queries": [
                    "site:csa.gov.gh cybersecurity act amendment 2025",
                    "site:csa.gov.gh cybersecurity act amendment 2026",
                    "site:csa.gov.gh new regulation",
                ],
            },
            {
                "name": "Bank of Ghana",
                "url": "https://www.bog.gov.gh",
                "queries": [
                    "site:bog.gov.gh new directive 2025",
                    "site:bog.gov.gh new directive 2026",
                    "site:bog.gov.gh payment regulation",
                ],
            },
            {
                "name": "Data Protection Commission",
                "url": "https://www.dataprotection.org.gh",
                "queries": [
                    "site:dataprotection.org.gh new regulation",
                    "site:dataprotection.org.gh guideline",
                ],
            },
        ]

        for source in sources:
            for query in source["queries"]:
                try:
                    results = search_web(query, max_results=3)
                    for r in results:
                        url = r.get("url", "")
                        title = r.get("title", "")
                        snippet = r.get("snippet", "")

                        discovery_key = hashlib.md5(url.encode()).hexdigest()
                        if discovery_key in {d.get("id") for d in discoveries}:
                            continue

                        is_pdf = url.lower().endswith(".pdf")
                        discoveries.append({
                            "id": discovery_key,
                            "source": "web",
                            "web_source": source["name"],
                            "name": title,
                            "url": url,
                            "snippet": snippet,
                            "is_pdf": is_pdf,
                            "status": "web_found",
                            "discovered_at": datetime.now(timezone.utc).isoformat(),
                        })
                except Exception:
                    continue

        return discoveries

    # ------------------------------------------------------------------
    # Conscious decision-making
    # ------------------------------------------------------------------

    def _decide(self, discoveries: list[dict]) -> Dict[str, Any]:
        if not discoveries:
            return {
                "should_ingest": False,
                "to_ingest": [],
                "summary": "No new content detected in any sector.",
            }

        to_ingest = []
        skipped = []

        for d in discoveries:
            if d["source"] == "filesystem":
                path = Path(d["path"])
                if path.stat().st_size < 1000:
                    skipped.append({**d, "reason": "File too small (< 1KB)"})
                    continue
                if d["status"] in ("new", "modified"):
                    to_ingest.append(d)
            elif d["source"] == "web":
                to_ingest.append(d)

        if not to_ingest:
            return {
                "should_ingest": False,
                "to_ingest": [],
                "summary": f"{len(discoveries)} item(s) found but none require ingestion.",
            }

        summary = (
            f"Found {len(to_ingest)} item(s) to ingest "
            f"({len([d for d in to_ingest if d['source'] == 'filesystem'])} filesystem, "
            f"{len([d for d in to_ingest if d['source'] == 'web'])} web). "
            f"{len(skipped)} skipped."
        )

        self.logger.info(f"Decision: {summary}")

        return {
            "should_ingest": True,
            "to_ingest": to_ingest,
            "skipped": skipped,
            "summary": summary,
        }

    # ------------------------------------------------------------------
    # Auto-ingestion
    # ------------------------------------------------------------------

    def _execute_ingestion(self, items: list[dict]) -> list[dict]:
        from agents.ingestor import IngestorAgent
        from agents.parser import ParserAgent
        from agents.embedder import EmbedderAgent

        results = []

        for item in items:
            sector = item.get("sector") or self.sector
            try:
                if item["source"] == "web":
                    result = self._ingest_from_web(item, sector)
                else:
                    result = self._ingest_from_filesystem(item, sector)
                results.append(result)
            except Exception as e:
                self.logger.error(f"Ingestion failed for {item.get('name')}: {e}")
                results.append({
                    "name": item.get("name"),
                    "status": "error",
                    "error": str(e),
                })

        return results

    def _ingest_from_filesystem(self, item: dict, sector: str) -> dict:
        from agents.ingestor import IngestorAgent
        from agents.parser import ParserAgent
        from agents.embedder import EmbedderAgent

        pdf_path = item["path"]
        law_name = item["name"].replace("_", " ").title()

        self.logger.info(f"Ingesting filesystem item: {law_name} ({sector})")

        ingestor = IngestorAgent(sector)
        parser = ParserAgent(sector)
        embedder = EmbedderAgent(sector)

        ingest_result = ingestor.run({"pdf_path": pdf_path})
        if ingest_result.get("status") == "error":
            return {"name": law_name, "status": "error", "error": ingest_result.get("error")}

        text = ingest_result.get("extracted_text", "")
        if not text.strip():
            return {"name": law_name, "status": "skipped", "reason": "No text extracted (scanned PDF?)"}

        parse_result = parser.run({"text": text, "law_name": law_name})
        if parse_result.get("status") == "error":
            return {"name": law_name, "status": "error", "error": parse_result.get("error")}

        chunks = parse_result.get("chunks", [])
        if not chunks:
            return {"name": law_name, "status": "skipped", "reason": "No chunks generated"}

        embed_result = embedder.run({"chunks": chunks})
        if embed_result.get("status") == "error":
            return {"name": law_name, "status": "error", "error": embed_result.get("error")}

        stored = embed_result.get("chunks_stored", 0)
        self.logger.info(f"Successfully ingested {law_name}: {stored} chunks stored")

        return {
            "name": law_name,
            "sector": sector,
            "status": "success",
            "chunks_stored": stored,
            "source": "filesystem",
        }

    def _ingest_from_web(self, item: dict, sector: str) -> dict:
        import requests
        from pathlib import Path

        url = item.get("url", "")
        name = item.get("name", "web_discovery")
        is_pdf = item.get("is_pdf", False)

        self.logger.info(f"Processing web discovery: {name} ({url})")

        if not is_pdf:
            return {
                "name": name,
                "status": "skipped",
                "reason": "Not a PDF — auto-ingestion only supports PDFs. URL logged for review.",
                "url": url,
            }

        pdf_response = requests.get(url, timeout=60, allow_redirects=True)
        if pdf_response.status_code != 200:
            return {"name": name, "status": "error", "error": f"HTTP {pdf_response.status_code}"}

        raw_dir = sector_manager.get_raw_path(sector)
        raw_dir.mkdir(parents=True, exist_ok=True)
        safe_name = re.sub(r"[^\w\-]", "_", Path(url).stem or name)
        pdf_path = raw_dir / f"{safe_name}.pdf"

        with open(pdf_path, "wb") as f:
            f.write(pdf_response.content)

        self.logger.info(f"Downloaded web PDF to: {pdf_path}")

        return self._ingest_from_filesystem({
            "path": str(pdf_path),
            "name": safe_name,
        }, sector)

    # ------------------------------------------------------------------
    # Persistent state
    # ------------------------------------------------------------------

    def _hash_file(self, path: Path) -> str:
        try:
            return hashlib.md5(path.read_bytes()).hexdigest()
        except Exception:
            return ""

    def _save_known_files(self):
        import json
        known_path = settings.CACHE_DIR / "law_monitor" / "known_files.json"
        known_path.parent.mkdir(parents=True, exist_ok=True)
        known_path.write_text(json.dumps(self._known_files, indent=2))

    def _load_checkpoint(self):
        import json
        known_path = settings.CACHE_DIR / "law_monitor" / "known_files.json"
        if known_path.exists():
            try:
                self._known_files = json.loads(known_path.read_text())
                self.logger.info(f"Loaded {len(self._known_files)} known files from checkpoint")
            except Exception:
                self._known_files = {}



