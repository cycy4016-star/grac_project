"""
System knowledge routes — tells the model what it knows so it can be self-aware.
"""

import json
from pathlib import Path

from fastapi import APIRouter

from config.settings import settings
from utils.sector_manager import sector_manager
from utils.logger import get_logger

logger = get_logger("api.system")

router = APIRouter(prefix="/api/system", tags=["system"])


CAPABILITIES = [
    {"id": "analyze_policy", "name": "Analyze Policy", "description": "Analyze a policy document against Ghanaian law to identify compliance gaps", "endpoint": "POST /api/analyze-policy"},
    {"id": "ask_compliance", "name": "Compliance Q&A", "description": "Answer compliance questions with citations from loaded laws and web research", "endpoint": "POST /api/ask-compliance"},
    {"id": "process_voice", "name": "Voice Input", "description": "Transcribe audio and generate a compliance document", "endpoint": "POST /api/process-voice"},
    {"id": "compliance_score", "name": "Compliance Score", "description": "Calculate a compliance score for a policy document", "endpoint": "POST /api/compliance-score"},
    {"id": "draft_policy", "name": "Draft Policy", "description": "Generate a professional compliance policy PDF from a topic description", "endpoint": "POST /api/draft-policy"},
    {"id": "export_report", "name": "Export Report", "description": "Export a compliance Q&A session as a downloadable PDF report", "endpoint": "POST /api/export-report"},
    {"id": "web_research", "name": "Web Research", "description": "Search the web for GRC laws, regulations, and compliance information", "endpoint": "POST /api/web-research"},
    {"id": "health_check", "name": "Health Check", "description": "Check if the API is operational", "endpoint": "GET /api/health"},
]


@router.get("/knowledge")
async def system_knowledge():
    """
    Return the system's full knowledge inventory.
    The LLM uses this to know what sectors/laws it has loaded.
    """
    sectors_knowledge = []

    for entry in settings.SECTOR_CONFIG["sectors"]:
        sid = entry["id"]
        if not entry.get("enabled", False):
            continue

        raw_dir = sector_manager.get_raw_path(sid)
        pdfs = []
        if raw_dir.exists():
            for p in sorted(raw_dir.glob("*.pdf")):
                pdfs.append(p.stem.replace("_", " ").title())

        parsed_dir = sector_manager.get_parsed_path(sid)
        parsed_files = list(parsed_dir.glob("*.txt")) if parsed_dir.exists() else []

        has_vector_knowledge = False
        try:
            from tools.embedding_tools import collection_exists, get_chroma_client
            client = get_chroma_client(settings.VECTORSTORE_DIR)
            has_vector_knowledge = collection_exists(client, f"grac_{sid}")
        except Exception:
            pass

        sectors_knowledge.append({
            "sector_id": sid,
            "sector_name": entry.get("name", sid.title()),
            "description": entry.get("description", ""),
            "loaded_laws": pdfs,
            "is_ingested": len(parsed_files) > 0 and has_vector_knowledge,
            "law_count": len(pdfs),
        })

    return {
        "system_name": "GRaC — Governance, Risk & Compliance Agent",
        "version": "1.0.0",
        "jurisdiction": "Ghana",
        "status": "operational",
        "sectors": sectors_knowledge,
        "capabilities": CAPABILITIES,
    }


@router.get("/capabilities")
async def system_capabilities():
    """Return the system's available capabilities and workflows."""
    return {"capabilities": CAPABILITIES}


@router.get("/knowledge/context")
async def system_knowledge_context():
    """Return a plain-text context block for LLM injection."""
    knowledge = await system_knowledge()
    lines = [
        f"You are GRaC, deployed as {knowledge['system_name']} (v{knowledge['version']}).",
        f"Jurisdiction: {knowledge['jurisdiction']}.",
        "",
        "Your loaded knowledge:",
    ]
    for s in knowledge["sectors"]:
        laws = ", ".join(s["loaded_laws"]) if s["loaded_laws"] else "No laws loaded yet"
        status = "READY" if s["is_ingested"] else "NOT INGESTED"
        lines.append(f"  [{status}] {s['sector_name']} ({s['sector_id']}): {laws}")

    lines.extend([
        "",
        "Your available capabilities:",
    ])
    for cap in CAPABILITIES:
        lines.append(f"  - {cap['name']}: {cap['description']} ({cap['endpoint']})")
    lines.extend([
        "",
        "Rules:",
        "  - If a user asks about a sector or law you have NOT loaded, say so honestly.",
        "  - Do NOT invent or hallucinate laws you do not have.",
        "  - If you have partial knowledge (law exists but not ingested), say so.",
        "  - You can answer general questions conversationally without citing laws.",
    ])
    return {"context": "\n".join(lines)}
