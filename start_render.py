#!/usr/bin/env python
"""
Render deployment entry point.
Starts the FastAPI server immediately and runs law ingestion in the background.
"""
import os
import sys
import time
import threading
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))


def run_ingestion():
    time.sleep(10)
    try:
        from scripts.ingest_laws import ingest_sector
        from config.settings import settings
        from utils.sector_manager import sector_manager

        enabled = sector_manager.list_enabled_sectors()
        for sector in enabled:
            raw_dir = sector_manager.get_raw_path(sector)
            pdfs = list(raw_dir.glob("*.pdf")) if raw_dir.exists() else []
            if pdfs:
                print(f"[startup] Ingesting {sector} ({len(pdfs)} PDFs)...")
                ingest_sector(sector, skip_embed=False)
                print(f"[startup] {sector} ingestion complete")
    except Exception as e:
        print(f"[startup] Ingestion error (non-fatal): {e}")


def main():
    import uvicorn
    from api.main import app

    port = int(os.getenv("PORT", "8000"))
    host = os.getenv("HOST", "0.0.0.0")

    threading.Thread(target=run_ingestion, daemon=True).start()

    print(f"[startup] Server starting on {host}:{port}")
    uvicorn.run(app, host=host, port=port, log_level="warning")


if __name__ == "__main__":
    main()
