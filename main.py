#!/usr/bin/env python
"""
GRaC Main Entry Point

This is the starting point for the application.
Can be run in different modes:
- API server
- CLI interaction
- Agent testing
"""
import os
import sys
import argparse
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))

from config import settings


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="GRaC - Governance, Risk & Compliance Agent"
    )
    
    parser.add_argument(
        "command",
        nargs="?",
        default="api",
        choices=["api", "cli", "monitor", "test", "setup"],
        help="Command to run"
    )
    
    parser.add_argument(
        "--sector",
        default=settings.ACTIVE_SECTOR,
        help=f"Sector to use (default: {settings.ACTIVE_SECTOR})"
    )
    
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug mode"
    )
    
    # Monitor-specific args
    parser.add_argument(
        "--mode",
        choices=["daemon", "scan", "web"],
        default="scan",
        help="Monitor mode (default: scan)"
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=3600,
        help="Daemon check interval in seconds (default: 3600)"
    )
    parser.add_argument(
        "--web-interval",
        type=int,
        default=86400,
        help="Web check interval in seconds (default: 86400)"
    )
    
    args = parser.parse_args()
    
    # Set sector if provided
    if args.sector != settings.ACTIVE_SECTOR:
        settings.set_active_sector(args.sector)
    
    if args.command == "api":
        run_api_server()
    elif args.command == "cli":
        run_cli()
    elif args.command == "monitor":
        run_monitor(args.mode, args.interval, args.web_interval)
    elif args.command == "test":
        run_tests()
    elif args.command == "setup":
        run_setup()


def run_api_server():
    """Start FastAPI server with optional auto-ingestor."""
    print("Starting GRaC API Server...")
    print(f"Active Sector: {settings.ACTIVE_SECTOR}")
    print(f"Debug Mode: {settings.API_DEBUG}")
    
    monitor = None
    if os.getenv("MONITOR_ENABLED", "False").lower() == "true":
        from services.auto_ingestor import AutoIngestorService
        import threading
        interval = int(os.getenv("MONITOR_INTERVAL", "3600"))
        web_interval = int(os.getenv("MONITOR_WEB_INTERVAL", "86400"))
        monitor = AutoIngestorService(
            sector=settings.ACTIVE_SECTOR,
            interval_seconds=interval,
            web_check_interval=web_interval,
        )
        t = threading.Thread(target=monitor.run_daemon, daemon=True)
        t.start()
        print(f"Auto-ingestor daemon started (interval={interval}s, web_interval={web_interval}s)")
    
    try:
        import uvicorn
        from api.main import app
        
        uvicorn.run(
            app,
            host=settings.API_HOST,
            port=settings.API_PORT,
            log_level="info" if settings.API_DEBUG else "warning"
        )
    except Exception as e:
        print(f"Error starting API server: {e}")
        if monitor:
            monitor.stop()
        sys.exit(1)


def run_cli():
    """Run CLI mode for interactive compliance queries."""
    import readline  # improves input editing on Unix; harmless on Windows

    from agents.supervisor import SupervisorAgent

    print()
    print("  " + "=" * 56)
    print("   GRaC — Governance, Risk & Compliance Agent")
    print("  " + "=" * 56)
    print(f"   Sector: {settings.ACTIVE_SECTOR}")
    print(f"   LLM:    {settings.LLM_PROVIDER}")
    print()
    print("   Commands:")
    print("     ask <question>        Ask a compliance question")
    print("     analyze <text>        Analyze policy text for gaps")
    print("     score <text>          Calculate compliance score")
    print("     switch <sector>       Switch sector")
    print("     ingest                Ingest laws for current sector")
    print("     monitor               Run one-shot filesystem scan")
    print("     help                  Show this help")
    print("     exit / quit           Exit")
    print()

    supervisor = SupervisorAgent(settings.ACTIVE_SECTOR)

    while True:
        try:
            raw = input(f"grac/{settings.ACTIVE_SECTOR}> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break

        if not raw:
            continue

        parts = raw.split(maxsplit=1)
        cmd = parts[0].lower()
        arg = parts[1] if len(parts) > 1 else ""

        if cmd in ("exit", "quit"):
            print("Goodbye.")
            break

        elif cmd == "help":
            print("  Commands:")
            print("    ask <question>        Ask a compliance question")
            print("    analyze <text>        Analyze policy text for gaps")
            print("    score <text>          Calculate compliance score")
            print("    switch <sector>       Switch sector")
            print("    ingest                Ingest laws for current sector")
            print("    monitor               Run one-shot filesystem scan")
            print("    help                  Show this help")
            print("    exit / quit           Exit")

        elif cmd == "switch":
            if not arg:
                print("Usage: switch <sector>")
                continue
            try:
                settings.set_active_sector(arg)
                supervisor.switch_sector(arg)
                print(f"Switched to sector: {arg}")
            except ValueError as e:
                print(f"Error: {e}")

        elif cmd == "ask":
            if not arg:
                print("Usage: ask <question>")
                continue
            print("  Querying laws...", end=" ", flush=True)
            result = supervisor.run({
                "request_type": "compliance_question",
                "data": arg,
                "sector": settings.ACTIVE_SECTOR,
                "options": {"top_k": 5, "return_sources": True},
            })
            if result.get("status") == "error":
                print(f"\n  Error: {result.get('error')}")
                continue
            data = result.get("result", {})
            print("done.\n")
            answer = data.get("answer", data.get("response", ""))
            if answer:
                print(f"  {answer}\n")
            sources = data.get("sources", [])
            if sources:
                print(f"  Sources ({len(sources)}):")
                for s in sources[:3]:
                    law = s.get("law_name", "")
                    sec = s.get("section_number", "")
                    text = (s.get("text", "") or "")[:120]
                    print(f"    - {law} §{sec}: {text}")
                print()

        elif cmd == "analyze":
            if not arg:
                print("Usage: analyze <policy_text>")
                continue
            print("  Analyzing policy...", end=" ", flush=True)
            result = supervisor.run({
                "request_type": "pdf_analysis",
                "data": arg,
                "sector": settings.ACTIVE_SECTOR,
                "options": {"output_format": "text", "allow_web_fallback": False},
            })
            if result.get("status") == "error":
                print(f"\n  Error: {result.get('error')}")
                continue
            print("done.\n")
            analysis = (result.get("result", {}) or {}).get("analysis", {})
            gaps = analysis.get("gaps", [])
            if gaps:
                for g in gaps[:5]:
                    sev = g.get("severity", "").upper()
                    print(f"  [{sev}] {g.get('requirement', '')}")
                    print(f"        Law: {g.get('law_reference', '')}")
                    print(f"        Status: {g.get('policy_status', '')}")
                    print()
            summary = analysis.get("summary", "")
            if summary:
                print(f"  Summary: {summary}\n")

        elif cmd == "score":
            if not arg:
                print("Usage: score <policy_text>")
                continue
            print("  Scoring...", end=" ", flush=True)
            result = supervisor.run({
                "request_type": "scoring",
                "data": arg,
                "sector": settings.ACTIVE_SECTOR,
                "options": {},
            })
            if result.get("status") == "error":
                print(f"\n  Error: {result.get('error')}")
                continue
            print("done.\n")
            score_data = (result.get("result", {}) or {}).get("score", {})
            if score_data:
                pct = score_data.get("compliance_percentage", score_data.get("score", 0))
                total = score_data.get("total_requirements", 0)
                met = score_data.get("met_requirements", 0)
                print(f"  Compliance Score: {pct}%")
                print(f"  Requirements met: {met}/{total}")
            else:
                print("  No score data returned.")

        elif cmd == "ingest":
            print("  Ingesting laws...")
            from scripts.ingest_laws import ingest_sector
            try:
                count = ingest_sector(settings.ACTIVE_SECTOR, skip_embed=False)
                print(f"  Done — {count} PDF(s) processed.")
            except Exception as e:
                print(f"  Error: {e}")

        elif cmd == "monitor":
            print("  Scanning for new laws...")
            from agents.law_monitor import LawMonitorAgent
            agent = LawMonitorAgent(settings.ACTIVE_SECTOR)
            result = agent.run({"mode": "filesystem", "report_only": False})
            output = result if result.get("status") == "success" else result
            discoveries = output.get("discoveries", [])
            ingestion = output.get("ingestion_results", [])
            if discoveries:
                print(f"  Found {len(discoveries)} new item(s):")
                for d in discoveries:
                    print(f"    - {d.get('name')} ({d.get('sector')})")
            else:
                print("  No new content found.")
            if ingestion:
                for r in ingestion:
                    st = r.get("status", "?")
                    print(f"    [{st}] {r.get('name')}")

        else:
            print(f"Unknown command: {cmd}. Type 'help' for available commands.")


def run_tests():
    """Run test suite."""
    print("Running GRaC Tests...")
    
    try:
        import pytest
        
        result = pytest.main([
            "tests/",
            "-v",
            "--tb=short"
        ])
        
        sys.exit(result)
    except Exception as e:
        print(f"Error running tests: {e}")
        sys.exit(1)


def run_setup():
    """Run setup script."""
    print("Setting up GRaC...")
    
    try:
        from scripts.setup_environment import setup
        setup()
        print("✓ Setup complete!")
    except Exception as e:
        print(f"Error during setup: {e}")
        sys.exit(1)


def run_monitor(mode: str = "scan", interval: int = 3600, web_interval: int = 86400):
    """Run the auto-ingestion monitor."""
    from services.auto_ingestor import run_monitor_daemon, run_monitor_scan, run_monitor_web
    
    print("=" * 60)
    print("GRaC Law Monitor — Conscious Auto-Ingestion")
    print("=" * 60)
    print(f"Mode: {mode}")
    print(f"Sector: {settings.ACTIVE_SECTOR}")
    print()
    
    if mode == "daemon":
        print(f"Starting daemon (interval={interval}s, web_interval={web_interval}s)...")
        print("Press Ctrl+C to stop.\n")
        run_monitor_daemon(
            sector=settings.ACTIVE_SECTOR,
            interval=interval,
            web_interval=web_interval,
        )
    elif mode == "web":
        result = run_monitor_web(sector=settings.ACTIVE_SECTOR)
        print("Done.")
    else:
        result = run_monitor_scan(sector=settings.ACTIVE_SECTOR)
        print("Done.")


if __name__ == "__main__":
    main()
