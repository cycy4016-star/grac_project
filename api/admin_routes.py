"""
Admin API routes — hidden from client UI.
Sector management, PDF upload, ingestion trigger, test sandbox.
"""

import json
import time
from pathlib import Path
from datetime import datetime, timezone

from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from fastapi.responses import JSONResponse, FileResponse

from config.settings import settings
from utils.sector_manager import sector_manager
from utils.logger import get_logger
from tools.embedding_tools import collection_exists, get_chroma_client

logger = get_logger("api.admin")

router = APIRouter(prefix="/api/admin", tags=["admin"])


# ── Sectors ──

@router.get("/sectors")
async def list_sectors():
    """Return all sectors with their status, law count, collection info."""
    sectors = []
    for entry in settings.SECTOR_CONFIG["sectors"]:
        sid = entry["id"]
        raw_dir = sector_manager.get_raw_path(sid, require_enabled=False) if sector_manager.is_valid_sector(sid, require_enabled=False) else None
        pdfs = []
        if raw_dir and raw_dir.exists():
            pdfs = [{"name": p.name, "size": p.stat().st_size, "modified": datetime.fromtimestamp(p.stat().st_mtime, tz=timezone.utc).isoformat()} for p in sorted(raw_dir.glob("*.pdf"))]

        parsed_dir = sector_manager.get_parsed_path(sid, require_enabled=False) if sector_manager.is_valid_sector(sid, require_enabled=False) else None
        parsed_count = len(list(parsed_dir.glob("*.txt"))) if parsed_dir and parsed_dir.exists() else 0

        try:
            client = get_chroma_client(settings.VECTORSTORE_DIR)
            has_collection = collection_exists(client, f"grac_{sid}")
        except Exception:
            has_collection = False

        sectors.append({
            "id": sid,
            "name": entry.get("name", sid.title()),
            "description": entry.get("description", ""),
            "enabled": entry.get("enabled", False),
            "laws": entry.get("laws", []),
            "applicable_industries": entry.get("applicable_industries", []),
            "pdf_count": len(pdfs),
            "pdfs": pdfs,
            "parsed_count": parsed_count,
            "has_collection": has_collection,
        })
    return {"sectors": sectors}


@router.post("/sectors")
async def create_sector(body: dict):
    """Create a new sector in the config and on disk."""
    sector = body.get("sector", "").strip().lower().replace(" ", "_")
    name = body.get("name", "")
    description = body.get("description", "")
    laws = body.get("laws", [])
    applicable_industries = body.get("applicable_industries", [])

    if not sector:
        raise HTTPException(400, "sector field is required")
    if sector_manager.is_valid_sector(sector, require_enabled=False):
        raise HTTPException(400, f"Sector '{sector}' already exists.")

    config_path = settings.SECTOR_CONFIG_PATH
    config = settings.SECTOR_CONFIG
    config["sectors"].append({
        "id": sector,
        "name": name.strip() or sector.title(),
        "description": description.strip(),
        "laws": laws,
        "applicable_industries": applicable_industries,
        "enabled": True,
    })
    config_path.write_text(json.dumps(config, indent=2))
    sector_manager._ensure_sector_dirs(sector)
    logger.info(f"Created sector: {sector}")
    return {"status": "ok", "sector": sector}


@router.get("/sectors/{sector_id}")
async def get_sector(sector_id: str):
    """Return details for a single sector."""
    for entry in settings.SECTOR_CONFIG["sectors"]:
        if entry["id"] == sector_id:
            raw_dir = sector_manager.get_raw_path(sector_id, require_enabled=False)
            pdfs = []
            if raw_dir and raw_dir.exists():
                pdfs = [{"name": p.name, "size": p.stat().st_size} for p in sorted(raw_dir.glob("*.pdf"))]
            parsed_dir = sector_manager.get_parsed_path(sector_id, require_enabled=False)
            parsed_count = len(list(parsed_dir.glob("*.txt"))) if parsed_dir and parsed_dir.exists() else 0
            return {
                "id": entry["id"],
                "name": entry.get("name", ""),
                "description": entry.get("description", ""),
                "enabled": entry.get("enabled", False),
                "laws": entry.get("laws", []),
                "applicable_industries": entry.get("applicable_industries", []),
                "pdf_count": len(pdfs),
                "pdfs": pdfs,
                "parsed_count": parsed_count,
            }
    raise HTTPException(404, f"Sector '{sector_id}' not found.")


@router.put("/sectors/{sector_id}")
async def update_sector(sector_id: str, body: dict):
    """Update sector metadata (name, description, laws, applicable_industries)."""
    config_path = settings.SECTOR_CONFIG_PATH
    config = settings.SECTOR_CONFIG
    for entry in config["sectors"]:
        if entry["id"] == sector_id:
            if "name" in body:
                entry["name"] = body["name"]
            if "description" in body:
                entry["description"] = body["description"]
            if "laws" in body:
                entry["laws"] = body["laws"]
            if "applicable_industries" in body:
                entry["applicable_industries"] = body["applicable_industries"]
            config_path.write_text(json.dumps(config, indent=2))
            logger.info(f"Updated sector: {sector_id}")
            return {"status": "ok", "sector": sector_id, "updates": list(body.keys())}
    raise HTTPException(404, f"Sector '{sector_id}' not found.")


@router.delete("/sectors/{sector_id}")
async def delete_sector(sector_id: str):
    """Remove a sector from config and clean up disk artifacts."""
    config_path = settings.SECTOR_CONFIG_PATH
    config = settings.SECTOR_CONFIG
    before = len(config["sectors"])
    config["sectors"] = [e for e in config["sectors"] if e["id"] != sector_id]
    if len(config["sectors"]) == before:
        raise HTTPException(404, f"Sector '{sector_id}' not found.")
    config_path.write_text(json.dumps(config, indent=2))

    # Clean up disk artifacts
    import shutil
    sector_laws_dir = settings.PROJECT_ROOT / "data" / "laws" / sector_id
    if sector_laws_dir.exists():
        shutil.rmtree(sector_laws_dir)
        logger.info(f"Removed law files for sector: {sector_id}")

    # Remove ChromaDB collection
    try:
        from tools.embedding_tools import get_chroma_client, collection_exists
        client = get_chroma_client(settings.VECTORSTORE_DIR)
        collection_name = f"grac_{sector_id}"
        if collection_exists(client, collection_name):
            client.delete_collection(collection_name)
            logger.info(f"Removed ChromaDB collection: {collection_name}")
    except Exception as e:
        logger.warning(f"Could not remove ChromaDB collection for {sector_id}: {e}")

    logger.info(f"Deleted sector: {sector_id}")
    return {"status": "ok", "sector": sector_id}


@router.patch("/sectors/{sector_id}/toggle")
async def toggle_sector(sector_id: str):
    """Enable or disable a sector."""
    config_path = settings.SECTOR_CONFIG_PATH
    config = settings.SECTOR_CONFIG
    for entry in config["sectors"]:
        if entry["id"] == sector_id:
            entry["enabled"] = not entry.get("enabled", True)
            config_path.write_text(json.dumps(config, indent=2))
            logger.info(f"Toggled sector {sector_id}: enabled={entry['enabled']}")
            return {"status": "ok", "sector": sector_id, "enabled": entry["enabled"]}
    raise HTTPException(404, f"Sector '{sector_id}' not found.")


# ── Ingestion ──

@router.post("/sectors/{sector_id}/upload")
async def upload_pdf(sector_id: str, file: UploadFile = File(...)):
    """Upload a PDF to a sector's raw directory."""
    if not sector_manager.is_valid_sector(sector_id, require_enabled=False):
        raise HTTPException(404, f"Unknown sector: {sector_id}")

    raw_dir = sector_manager.get_raw_path(sector_id)
    raw_dir.mkdir(parents=True, exist_ok=True)

    dest = raw_dir / file.filename
    content = await file.read()
    if not content:
        raise HTTPException(400, "Empty file.")

    dest.write_bytes(content)
    logger.info(f"Uploaded {file.filename} to {sector_id} ({len(content)} bytes)")
    return {"status": "ok", "file": file.filename, "size": len(content)}


@router.post("/sectors/{sector_id}/ingest")
async def ingest_sector(sector_id: str):
    """Trigger full ingestion pipeline for a sector."""
    from scripts.ingest_laws import ingest_sector as run_ingest

    if not sector_manager.is_valid_sector(sector_id, require_enabled=False):
        raise HTTPException(404, f"Unknown sector: {sector_id}")

    try:
        t0 = time.time()
        count = run_ingest(sector_id, skip_embed=False)
        elapsed = time.time() - t0
        logger.info(f"Ingested {sector_id}: {count} PDF(s) in {elapsed:.1f}s")
        return {"status": "ok", "sector": sector_id, "pdfs_processed": count, "elapsed_seconds": round(elapsed, 1)}
    except Exception as e:
        logger.error(f"Ingestion failed for {sector_id}: {e}")
        raise HTTPException(500, f"Ingestion failed: {e}")


# ── Test sandbox ──

@router.post("/test")
async def test_query(question: str = Form(...), sector: str = Form(None), history: str = Form("[]")):
    """Run a compliance query and return the raw result (sandbox for admin)."""
    from api.dependencies import get_supervisor
    import json

    parsed_history = []
    try:
        parsed_history = json.loads(history)
    except (json.JSONDecodeError, TypeError):
        pass

    sup = get_supervisor()
    result = sup.run({
        "request_type": "compliance_question",
        "data": question,
        "sector": sector,
        "options": {"top_k": 5, "return_sources": True, "allow_web_fallback": True, "history": parsed_history},
    })
    return result


# ── PDF Management ──

@router.delete("/sectors/{sector_id}/pdfs/{filename}")
async def delete_pdf(sector_id: str, filename: str):
    """Delete a PDF from a sector's raw directory."""
    if not sector_manager.is_valid_sector(sector_id, require_enabled=False):
        raise HTTPException(404, f"Unknown sector: {sector_id}")

    raw_dir = sector_manager.get_raw_path(sector_id, require_enabled=False)
    from pathlib import Path
    safe_name = Path(filename).name
    file_path = raw_dir / safe_name

    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(404, f"File '{filename}' not found in sector '{sector_id}'")

    file_path.unlink()
    logger.info(f"Deleted {filename} from {sector_id}")
    return {"status": "ok", "file": filename, "sector": sector_id}


@router.delete("/sectors/{sector_id}/pdfs")
async def delete_all_pdfs(sector_id: str):
    """Delete all PDFs from a sector's raw directory."""
    if not sector_manager.is_valid_sector(sector_id, require_enabled=False):
        raise HTTPException(404, f"Unknown sector: {sector_id}")

    raw_dir = sector_manager.get_raw_path(sector_id, require_enabled=False)
    deleted = []
    for f in raw_dir.glob("*.pdf"):
        f.unlink()
        deleted.append(f.name)

    logger.info(f"Deleted {len(deleted)} PDF(s) from {sector_id}: {', '.join(deleted)}")
    return {"status": "ok", "deleted": deleted, "count": len(deleted)}


# ── Ingestion logs ──

@router.get("/sectors/{sector_id}/logs")
async def ingestion_logs(sector_id: str):
    """Return recent ingestion logs for a sector."""
    log_dir = settings.LOGS_DIR
    logs = []
    if log_dir.exists():
        for f in sorted(log_dir.glob("*.log"), reverse=True)[:10]:
            logs.append({"file": f.name, "size": f.stat().st_size})
    return {"logs": logs}


# ── Draft / Download ──

@router.get("/download/{filename}")
async def download_file(filename: str):
    """Serve a generated document from data/output."""
    from pathlib import Path
    safe_name = Path(filename).name
    file_path = settings.PROJECT_ROOT / "data" / "output" / safe_name
    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(404, f"File not found: {safe_name}")
    return FileResponse(str(file_path), filename=file_path.name, media_type="application/octet-stream")


@router.post("/draft")
async def draft_document(topic: str = Form(...), sector: str = Form(None), details: str = Form("")):
    """Generate a compliance policy draft as PDF using WriterAgent."""
    from agents.writer import WriterAgent
    from api.dependencies import get_supervisor
    from tools.llm_tools import call_llm

    sup = get_supervisor()
    resolved_sector = sector or sup.sector or "cybersecurity"

    # 1. Get law context via retriever
    law_context = ""
    try:
        retriever_out = sup.call_agent("retriever", {"query": topic, "top_k": 5, "sector": resolved_sector})
        chunks = retriever_out.get("results", [])
        if chunks:
            parts = []
            for c in chunks:
                meta = c.get("metadata", {})
                law_name = meta.get("law_name", "Unknown")
                sec = meta.get("section_number", "")
                text = (c.get("text", "") or "")[:400]
                parts.append(f"{law_name}{" §"+sec if sec else ""}:\n{text}")
            law_context = "\n\n".join(parts)
    except Exception as e:
        logger.warning(f"Draft law retrieval warning: {e}")

    # 2. Use LLM to extract findings and recommendations from topic + law context
    analysis_prompt = f"""You are a Ghanaian compliance analyst. Given the topic below, extract:
1. A 2-3 sentence summary of what this policy must cover
2. 3-5 key compliance findings/requirements (numbered, with law references)
3. 2-4 actionable recommendations

Topic: {topic}
{f"Sector: {resolved_sector}" if resolved_sector else ""}
{"Law Context:\n" + law_context if law_context else "No specific law context retrieved — use general Ghanaian regulatory knowledge."}

Output JSON with keys: summary, findings (list), recommendations (list)"""

    import json
    analysis_raw = call_llm(prompt=analysis_prompt)
    # Try to parse JSON from LLM output
    content = {"summary": "", "findings": [], "recommendations": []}
    try:
        # Find JSON in the response (handle markdown code blocks)
        json_str = analysis_raw.strip()
        if "```json" in json_str:
            json_str = json_str.split("```json")[1].split("```")[0].strip()
        elif "```" in json_str:
            json_str = json_str.split("```")[1].split("```")[0].strip()
        parsed = json.loads(json_str)
        content.update(parsed)
    except (json.JSONDecodeError, IndexError):
        # Fallback: use raw text as summary
        content["summary"] = analysis_raw[:500]

    # 3. Generate policy document via WriterAgent
    writer = WriterAgent(resolved_sector)
    writer_input = {
        "type": "policy_draft",
        "content": content,
        "format": "pdf",
        "metadata": {"author": "GRaC Compliance System", "company": "Ghana Regulatory Compliance (GRaC)"},
    }
    writer_out = writer.execute(writer_input)
    result = writer.format_output(writer_out)

    path = result.get("path", "")
    filename = Path(path).name if path else ""
    download_url = f"/api/admin/download/{filename}" if filename else ""

    return {"status": "ok", "path": path, "filename": filename, "download_url": download_url, "title": result.get("title", "")}
