"""
AutoIngestor Service

Runs the LawMonitorAgent in a continuous loop, consciously detecting new law
content and triggering the full ingestion pipeline.

Modes:
  - daemon:  Runs forever, checking on a configurable interval
  - scan:    One-shot scan of all raw directories
  - web:     One-shot web check for new legislation
"""

import time
import signal
import sys
from datetime import datetime, timezone
from typing import Optional

from agents.law_monitor import LawMonitorAgent
from config.settings import settings
from utils.logger import get_logger

logger = get_logger("services.auto_ingestor")


class AutoIngestorService:
    """Background service that monitors for new laws and auto-ingests them."""

    def __init__(
        self,
        sector: Optional[str] = None,
        interval_seconds: int = 3600,
        web_check_interval: int = 86400,
    ):
        self.sector = sector or settings.ACTIVE_SECTOR
        self.interval = interval_seconds
        self.web_check_interval = web_check_interval
        self._running = False
        self._cycle_count = 0
        self._last_web_check = 0.0

    def run_daemon(self):
        """Run the monitor in an infinite loop (daemon mode)."""
        self._running = True
        signal.signal(signal.SIGINT, self._handle_signal)
        signal.signal(signal.SIGTERM, self._handle_signal)

        logger.info(
            f"AutoIngestor daemon started — sector={self.sector} "
            f"interval={self.interval}s web_interval={self.web_check_interval}s"
        )

        while self._running:
            self._cycle_count += 1
            logger.info(f"Monitor cycle #{self._cycle_count} starting...")

            self._run_filesystem_scan()

            now = time.time()
            if now - self._last_web_check >= self.web_check_interval:
                self._run_web_check()
                self._last_web_check = now

            if self._running:
                logger.info(f"Sleeping for {self.interval}s...")
                for _ in range(min(self.interval, 10)):
                    if not self._running:
                        break
                    time.sleep(1)

        logger.info("AutoIngestor daemon stopped.")

    def run_scan(self):
        """One-shot filesystem scan."""
        logger.info("Running one-shot filesystem scan...")
        result = self._run_filesystem_scan()
        self._print_result(result)
        return result

    def run_web_check(self):
        """One-shot web monitoring check."""
        logger.info("Running one-shot web check...")
        result = self._run_web_check()
        self._print_result(result)
        return result

    def stop(self):
        """Signal the daemon to stop."""
        self._running = False
        logger.info("Stop signal received.")

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _run_filesystem_scan(self) -> dict:
        agent = LawMonitorAgent(self.sector)
        result = agent.run({
            "mode": "filesystem",
            "report_only": False,
        })
        output = result if result.get("status") == "success" else result
        discoveries = output.get("discoveries", [])
        ingestion = output.get("ingestion_results", [])
        summary = output.get("summary", "")

        if discoveries:
            logger.info(f"Filesystem scan found {len(discoveries)} new item(s). {summary}")
            for d in discoveries:
                logger.info(f"  [{d.get('status')}] {d.get('name')} ({d.get('sector')})")
        else:
            logger.info("Filesystem scan: no new content.")

        return {
            "mode": "filesystem",
            "discoveries": discoveries,
            "ingestion_results": ingestion,
            "summary": summary,
        }

    def _run_web_check(self) -> dict:
        agent = LawMonitorAgent(self.sector)
        result = agent.run({
            "mode": "web",
            "report_only": True,
        })
        output = result if result.get("status") == "success" else result
        discoveries = output.get("discoveries", [])
        decision = output.get("decision", {})

        if discoveries:
            logger.info(f"Web check found {len(discoveries)} potential source(s).")
            for d in discoveries:
                logger.info(f"  [{d.get('web_source')}] {d.get('name')}")
                logger.info(f"    URL: {d.get('url')}")
        else:
            logger.info("Web check: no new legislation found.")

        return {
            "mode": "web",
            "discoveries": discoveries,
            "summary": decision.get("summary", ""),
        }

    def _print_result(self, result: dict):
        discoveries = result.get("discoveries", [])
        ingestion = result.get("ingestion_results", [])
        print(f"\n{'=' * 50}")
        print(f"AutoIngestor Result ({result.get('mode', 'unknown')})")
        print(f"{'=' * 50}")
        print(f"  Discoveries: {len(discoveries)}")
        for d in discoveries:
            status = d.get("status", "?")
            name = d.get("name", "?")
            sector = d.get("sector", d.get("web_source", "?"))
            print(f"    [{status}] {name} ({sector})")
        if ingestion:
            print(f"  Ingestion Results: {len(ingestion)}")
            for r in ingestion:
                print(f"    [{r.get('status')}] {r.get('name')}: {r.get('chunks_stored', 0)} chunks")
        print(f"  Summary: {result.get('summary', '')}")
        print(f"{'=' * 50}\n")

    def _handle_signal(self, signum, frame):
        logger.info(f"Received signal {signum}, shutting down...")
        self.stop()


def run_monitor_daemon(
    sector: Optional[str] = None,
    interval: int = 3600,
    web_interval: int = 86400,
):
    """Entry point for the daemon mode."""
    service = AutoIngestorService(
        sector=sector,
        interval_seconds=interval,
        web_check_interval=web_interval,
    )
    service.run_daemon()


def run_monitor_scan(sector: Optional[str] = None):
    """Entry point for one-shot scan."""
    service = AutoIngestorService(sector=sector)
    return service.run_scan()


def run_monitor_web(sector: Optional[str] = None):
    """Entry point for one-shot web check."""
    service = AutoIngestorService(sector=sector)
    return service.run_web_check()
