#!/usr/bin/env python
"""
Ingest law PDFs into the GRaC system.

Scans a sector's data/laws/{sector}/raw/ directory for PDFs and runs the
full ingestion pipeline for each: IngestorAgent → ParserAgent → EmbedderAgent.

Usage:
    python scripts/ingest_laws.py --sector cybersecurity
    python scripts/ingest_laws.py --sector fintech --skip-embed
    python scripts/ingest_laws.py --all
    python scripts/ingest_laws.py --list-sectors
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

# Ensure project root is on sys.path
PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from config.settings import settings
from utils.sector_manager import sector_manager
from utils.logger import get_logger

logger = get_logger("scripts.ingest")


def list_available_sectors() -> None:
    """Print all configured sectors and their law counts."""
    print("\nAvailable sectors:")
    print("-" * 50)
    for sector in sector_manager.list_all_sectors():
        is_enabled = sector_manager.is_enabled(sector)
        status = "[OK]" if is_enabled else "[OFF]"
        config = sector_manager.get_sector_config(sector)
        laws = config.get("laws", [])
        raw_path = config.get("id") and (settings.get_sector_laws_path(sector) / "raw")
        pdf_count = len(list(raw_path.glob("*.pdf"))) if raw_path and raw_path.exists() else 0
        print(f"  {status} {sector:25s} {pdf_count} PDFs, {len(laws)} laws configured")
    print()


def ingest_sector(
    sector: str,
    skip_embed: bool = False,
    max_pdfs: int | None = None,
) -> int:
    """
    Run the full ingestion pipeline for a single sector.

    Args:
        sector: Sector ID (e.g. "cybersecurity").
        skip_embed: If True, skip the embedding step (parse only).
        max_pdfs: Maximum number of PDFs to process (None = all).

    Returns:
        Number of PDFs successfully processed.
    """
    from agents.ingestor import IngestorAgent
    from agents.parser import ParserAgent
    from agents.embedder import EmbedderAgent

    sector_manager.validate_sector(sector)
    raw_dir = sector_manager.get_raw_path(sector)

    if not raw_dir.exists():
        print(f"  [ERR] Raw directory not found: {raw_dir}")
        return 0

    pdfs = sorted(raw_dir.glob("*.pdf"))
    if not pdfs:
        print(f"  - No PDFs found in {raw_dir}")
        return 0

    if max_pdfs:
        pdfs = pdfs[:max_pdfs]

    print(f"\n  Found {len(pdfs)} PDF(s) to process")

    ingestor = IngestorAgent(sector)
    parser = ParserAgent(sector)
    embedder = EmbedderAgent(sector) if not skip_embed else None

    success_count = 0

    for i, pdf_path in enumerate(pdfs, 1):
        law_name = pdf_path.stem.replace("_", " ").title()
        print(f"\n  [{i}/{len(pdfs)}] {law_name}")
        print(f"         File: {pdf_path.name}")

        try:
            # Step 1: Extract text
            t0 = time.time()
            ingest_result = ingestor.run({"pdf_path": str(pdf_path)})
            if ingest_result.get("status") == "error":
                print(f"         [ERR] Ingestion failed: {ingest_result.get('error')}")
                continue
            text = ingest_result.get("extracted_text", "")
            t1 = time.time()
            print(f"         [OK] Extracted ({len(text)} chars, {ingest_result.get('pages', 0)} pages) [{t1-t0:.1f}s]")

            if not text.strip():
                print(f"         -- Skipping (no text extracted)")
                continue

            # Step 2: Parse hierarchy and build chunks
            t0 = time.time()
            parse_result = parser.run({"text": text, "law_name": law_name})
            if parse_result.get("status") == "error":
                print(f"         [ERR] Parsing failed: {parse_result.get('error')}")
                continue
            chunks = parse_result.get("chunks", [])
            t1 = time.time()
            print(f"         [OK] Parsed ({parse_result.get('chunk_count', 0)} chunks) [{t1-t0:.1f}s]")

            if not chunks:
                print(f"         -- Skipping embedding (no chunks generated)")
                success_count += 1
                continue

            # Step 3: Embed and store in ChromaDB
            if not skip_embed and embedder is not None:
                t0 = time.time()
                embed_result = embedder.run({"chunks": chunks})
                if embed_result.get("status") == "error":
                    print(f"         [ERR] Embedding failed: {embed_result.get('error')}")
                    continue
                t1 = time.time()
                stored = embed_result.get("chunks_stored", 0)
                total = embed_result.get("collection_total", 0)
                print(f"         [OK] Embedded ({stored} stored, {total} total in collection) [{t1-t0:.1f}s]")

            success_count += 1

        except Exception as e:
            print(f"         [ERR] Unexpected error: {e}")
            logger.error(f"Failed to process {pdf_path.name}", exc_info=True)
            continue

    return success_count


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Ingest law PDFs into the GRaC system",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="Examples:\n"
               "  %(prog)s --sector cybersecurity\n"
               "  %(prog)s --sector fintech --skip-embed\n"
               "  %(prog)s --all\n"
               "  %(prog)s --list-sectors",
    )
    parser.add_argument("--sector", help="Sector ID to ingest (e.g. cybersecurity)")
    parser.add_argument("--all", action="store_true", help="Ingest all enabled sectors")
    parser.add_argument("--skip-embed", action="store_true", help="Skip ChromaDB embedding step")
    parser.add_argument("--max-pdfs", type=int, help="Maximum PDFs to process per sector")
    parser.add_argument("--list-sectors", action="store_true", help="List available sectors and exit")

    args = parser.parse_args()

    print("=" * 60)
    print("GRaC Law Ingestion Pipeline")
    print("=" * 60)

    if args.list_sectors:
        list_available_sectors()
        return

    # Determine which sectors to process
    sectors_to_process = []
    if args.all:
        sectors_to_process = sector_manager.list_enabled_sectors()
    elif args.sector:
        sectors_to_process = [args.sector]
    else:
        sectors_to_process = [settings.ACTIVE_SECTOR]

    if not sectors_to_process:
        print("\nNo sectors to process. Use --sector, --all, or set ACTIVE_SECTOR in .env")
        sys.exit(1)

    total_processed = 0
    total_pdfs = 0

    for sector in sectors_to_process:
        print(f"\n{'=' * 50}")
        print(f"Sector: {sector}")
        print(f"{'=' * 50}")

        try:
            raw_dir = sector_manager.get_raw_path(sector)
            pdf_count = len(list(raw_dir.glob("*.pdf"))) if raw_dir.exists() else 0
            total_pdfs += pdf_count

            count = ingest_sector(sector, skip_embed=args.skip_embed, max_pdfs=args.max_pdfs)
            total_processed += count
        except ValueError as e:
            print(f"  [ERR] {e}")
        except Exception as e:
            print(f"  [ERR] Unexpected error processing sector '{sector}': {e}")
            logger.error(f"Sector {sector} failed", exc_info=True)

    print(f"\n{'=' * 60}")
    print(f"Summary: {total_processed}/{total_pdfs} PDFs processed successfully")
    if args.skip_embed:
        print("  (embedding skipped)")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
