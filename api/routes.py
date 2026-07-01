from __future__ import annotations

import json
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, Form, UploadFile, HTTPException, Request

from agents.supervisor import SupervisorAgent
from pydantic import BaseModel, Field
from api.dependencies import get_supervisor
from api.models import (
    AnalyzePolicyRequest,
    AskComplianceRequest,
    ComplianceScoreRequest,
    ProcessVoiceRequest,
    DraftPolicyRequest,
    WebResearchRequest,
    FeedbackRequest,
    ApiResponse,
    ApiError,
    ErrorDetail,
)
from tools.document_tools import read_document
from config.settings import settings
from utils.logger import get_logger
from utils.validators import ValidationError


class GeneralQueryRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=8000, description="The user's message")
    history: str = Field("[]", description="JSON-encoded conversation history")

router = APIRouter(prefix="/api", tags=["compliance"])
logger = get_logger("api.routes")


def _build_response(data: dict, sector: str) -> ApiResponse:
    return ApiResponse(
        status="success",
        timestamp=datetime.now(timezone.utc).isoformat(),
        sector=sector,
        data=data,
    )


def _sector_or_default(sector: str | None) -> str:
    return (sector or settings.ACTIVE_SECTOR).strip().lower()


@router.post(
    "/analyze-policy",
    summary="Analyze a policy for compliance gaps",
    responses={
        200: {"model": ApiResponse},
        422: {"model": ApiError},
        500: {"model": ApiError},
    },
)
async def analyze_policy(
    body: AnalyzePolicyRequest,
    request: Request,
    supervisor: SupervisorAgent = Depends(get_supervisor),
):
    sector = _sector_or_default(body.sector)
    payload = {
        "request_type": "pdf_analysis",
        "data": body.policy,
        "sector": sector,
        "options": {"output_format": body.output_format},
    }
    result = supervisor.run(payload)
    if result.get("status") == "error":
        raise HTTPException(status_code=500, detail=result.get("error", "Analysis failed"))
    return _build_response(result.get("result", result), sector)


@router.post(
    "/analyze-document",
    summary="Upload and analyze a policy document (PDF, DOCX, TXT)",
    responses={
        200: {"model": ApiResponse},
        400: {"model": ApiError},
        422: {"model": ApiError},
        500: {"model": ApiError},
    },
)
async def analyze_document(
    file: UploadFile = File(...),
    sector: str = Form(None),
    output_format: str = Form("pdf"),
    supervisor: SupervisorAgent = Depends(get_supervisor),
):
    """Upload a policy document (PDF, DOCX, or TXT) and run full compliance gap analysis."""
    import tempfile, os
    from pathlib import Path

    resolved_sector = _sector_or_default(sector)
    ext = Path(file.filename).suffix.lower() if file.filename else ".txt"
    if ext not in {".pdf", ".docx", ".txt"}:
        raise HTTPException(status_code=400, detail=f"Unsupported file type: {ext}. Supported: .pdf, .docx, .txt")

    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Empty file")

    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=ext)
    try:
        tmp.write(content)
        tmp.close()
        doc = read_document(tmp.name)
    except Exception as e:
        os.unlink(tmp.name)
        raise HTTPException(status_code=422, detail=f"Failed to read document: {e}")
    finally:
        if os.path.exists(tmp.name):
            os.unlink(tmp.name)

    if not doc["text"] or len(doc["text"]) < 50:
        raise HTTPException(status_code=422, detail="Document has no readable text (may be scanned). Try a text-based PDF.")

    payload = {
        "request_type": "pdf_analysis",
        "data": doc["text"],
        "sector": resolved_sector,
        "options": {"output_format": output_format, "allow_web_fallback": True},
    }
    result = supervisor.run(payload)
    if result.get("status") == "error":
        raise HTTPException(status_code=500, detail=result.get("error", "Analysis failed"))
    return _build_response(result.get("result", result), resolved_sector)


@router.post(
    "/ask-compliance",
    summary="Ask a compliance question with law citations",
)
async def ask_compliance(
    body: AskComplianceRequest,
    request: Request,
    supervisor: SupervisorAgent = Depends(get_supervisor),
):
    sector = _sector_or_default(body.sector)
    payload = {
        "request_type": "compliance_question",
        "data": body.question,
        "sector": sector,
        "options": {"top_k": body.top_k, "return_sources": body.return_sources},
    }
    result = supervisor.run(payload)
    if result.get("status") == "error":
        raise HTTPException(status_code=500, detail=result.get("error", "Query failed"))
    return _build_response(result.get("result", result), sector)


@router.post(
    "/process-voice",
    summary="Process voice input and generate a compliance document",
)
async def process_voice(
    audio: UploadFile = File(...),
    sector: str = Form(None),
    document_type: str = Form("incident_report"),
    language: str = Form("en"),
    request: Request = None,
    supervisor: SupervisorAgent = Depends(get_supervisor),
):
    resolved_sector = _sector_or_default(sector)
    # Validate via ProcessVoiceRequest model
    voice_req = ProcessVoiceRequest(sector=resolved_sector, document_type=document_type, language=language)
    audio_bytes = await audio.read()
    payload = {
        "request_type": "voice_input",
        "data": {
            "audio_data": audio_bytes,
            "filename": audio.filename or "audio.mp3",
            "language": voice_req.language,
        },
        "sector": voice_req.sector,
        "options": {"document_type": voice_req.document_type},
    }
    result = supervisor.run(payload)
    if result.get("status") == "error":
        raise HTTPException(status_code=500, detail=result.get("error", "Voice processing failed"))
    return _build_response(result.get("result", result), resolved_sector)


@router.post(
    "/compliance-score",
    summary="Calculate a compliance score for a policy",
)
async def compliance_score(
    body: ComplianceScoreRequest,
    request: Request,
    supervisor: SupervisorAgent = Depends(get_supervisor),
):
    sector = _sector_or_default(body.sector)
    options = {}
    if body.total_requirements is not None:
        options["total_requirements"] = body.total_requirements
    payload = {
        "request_type": "scoring",
        "data": body.policy,
        "sector": sector,
        "options": options,
    }
    result = supervisor.run(payload)
    if result.get("status") == "error":
        raise HTTPException(status_code=500, detail=result.get("error", "Scoring failed"))
    return _build_response(result.get("result", result), sector)


@router.post(
    "/general",
    summary="General intelligence — handles any query with auto-sector detection, deep research, and orchestration",
)
async def general_query(
    body: GeneralQueryRequest,
    request: Request,
    supervisor: SupervisorAgent = Depends(get_supervisor),
):
    """Unified endpoint for all queries. Auto-detects sector, does deep research, orchestrates agents."""
    message = body.message.strip()
    if not message:
        raise HTTPException(status_code=422, detail=ErrorDetail(field="message", message="Message cannot be empty"))

    parsed_history = []
    try:
        parsed_history = json.loads(body.history) if body.history else []
    except (json.JSONDecodeError, TypeError):
        pass

    # Auto-detect sector from message
    detected = supervisor._detect_sector(message)
    current = settings.ACTIVE_SECTOR
    sector_switched = False
    if detected and detected != current:
        settings.set_active_sector(detected)
        supervisor.switch_sector(detected)
        sector_switched = True
        logger.info(f"Auto-switched sector from {current} to {detected}")
    sector = detected or current

    # Classify intent
    query_type = supervisor._classify_query(message)

    # Route to the right workflow
    result = supervisor.run({
        "request_type": "compliance_question" if query_type != "draft" else "draft_policy",
        "data": message,
        "sector": sector,
        "options": {
            "top_k": 5,
            "return_sources": True,
            "allow_web_fallback": True,
            "history": parsed_history,
            "sector": sector,
        },
    })

    response_data = result.get("result", result)
    response_data["query_type"] = query_type
    response_data["sector_detected"] = detected or current
    response_data["sector_switched"] = sector_switched
    if sector_switched:
        response_data["sector_switch_note"] = f"Switched from {current} to {detected} based on your query"

    if result.get("status") == "error":
        raise HTTPException(status_code=500, detail=result.get("error", "Query failed"))

    return _build_response(response_data, sector)


@router.post(
    "/draft-policy",
    summary="Generate a compliance policy PDF from a topic description",
    responses={
        200: {"model": ApiResponse},
        422: {"model": ApiError},
        500: {"model": ApiError},
    },
)
async def draft_policy(
    body: DraftPolicyRequest,
    supervisor: SupervisorAgent = Depends(get_supervisor),
):
    sector = _sector_or_default(body.sector)
    payload = {
        "request_type": "draft_policy",
        "data": body.topic,
        "sector": sector,
        "options": {"sector": sector},
    }
    result = supervisor.run(payload)
    if result.get("status") == "error":
        raise HTTPException(status_code=500, detail=result.get("error", "Draft failed"))
    return _build_response(result.get("result", result), sector)


@router.post(
    "/web-research",
    summary="Search the web for GRC laws and compliance information",
    responses={
        200: {"model": ApiResponse},
        422: {"model": ApiError},
        500: {"model": ApiError},
    },
)
async def web_research(
    body: WebResearchRequest,
    supervisor: SupervisorAgent = Depends(get_supervisor),
):
    sector = _sector_or_default(body.sector)
    payload = {
        "request_type": "web_research",
        "data": body.query,
        "sector": sector,
        "options": {"top_k": body.top_k, "summarize": body.summarize},
    }
    result = supervisor.run(payload)
    if result.get("status") == "error":
        raise HTTPException(status_code=500, detail=result.get("error", "Web research failed"))
    return _build_response(result.get("result", result), sector)


@router.get(
    "/health",
    summary="Health check endpoint",
    include_in_schema=True,
)
async def health():
    active_sectors = settings.get_active_sectors()
    return {
        "status": "ok",
        "service": "GRaC API",
        "version": "1.0.0",
        "active_sector": settings.ACTIVE_SECTOR,
        "active_sectors": active_sectors,
        "multi_sector_enabled": settings.ENABLE_MULTI_SECTOR,
        "sectors_available": [e["id"] for e in settings.SECTOR_CONFIG.get("sectors", []) if e.get("enabled")],
    }


@router.post("/export-report")
async def export_report(question: str = Form(...), answer: str = Form(...), sector: str = Form(None), sources: str = Form("[]")):
    """Generate a compliance report PDF from a Q&A pair and return download URL."""
    from pathlib import Path
    from datetime import datetime
    from tools.document_tools import generate_pdf
    import json, re

    resolved_sector = sector or settings.ACTIVE_SECTOR
    parsed_sources = []
    try:
        parsed_sources = json.loads(sources)
    except (json.JSONDecodeError, TypeError):
        pass

    # Build document content
    date_str = datetime.now().strftime("%d %B %Y")
    content_lines = [
        f"## Compliance Report — {resolved_sector.replace('_', ' ').title()}",
        f"Generated: {date_str}",
        "",
        "## Query",
        question,
        "",
        "## Analysis",
        answer,
    ]
    if parsed_sources:
        content_lines.append("")
        content_lines.append("## Sources Referenced")
        for i, src in enumerate(parsed_sources, 1):
            law = src.get("law_name", "Unknown")
            sec = src.get("section_number", "")
            text = (src.get("text", "") or "")[:300]
            content_lines.append(f"{i}. **{law}**{f' §{sec}' if sec else ''}")
            content_lines.append(f"   {text}")

    content_text = "\n".join(content_lines)
    safe_sector = re.sub(r"\s+", "_", resolved_sector.lower())
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"compliance_report_{safe_sector}_{ts}.pdf"
    output_dir = settings.PROJECT_ROOT / "data" / "output"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / filename

    title = f"Compliance Report — {resolved_sector.replace('_', ' ').title()}"
    generate_pdf(content_text, title, output_path, resolved_sector)

    return {"status": "ok", "filename": filename, "download_url": f"/api/download/{filename}"}


@router.post("/feedback")
async def submit_feedback(req: FeedbackRequest):
    """Store user feedback on an AI answer for continuous learning."""
    import json
    from pathlib import Path
    from datetime import datetime, timezone

    feedback_dir = settings.DATA_DIR / "feedback"
    feedback_dir.mkdir(parents=True, exist_ok=True)

    entry = {
        "message_id": req.message_id,
        "question": req.question,
        "answer": req.answer,
        "rating": req.rating,
        "correction": req.correction,
        "sector": req.sector or settings.ACTIVE_SECTOR,
        "sources": req.sources or [],
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    file_path = feedback_dir / "feedback.jsonl"
    with open(file_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")

    logger.info(f"Feedback stored: {req.message_id} rating={req.rating}")
    return {"status": "ok", "message_id": req.message_id, "rating": req.rating}


@router.get("/download/{filename}")
async def download_file(filename: str):
    """Serve a generated document from data/output."""
    from fastapi.responses import FileResponse
    from pathlib import Path
    safe_name = Path(filename).name
    file_path = settings.PROJECT_ROOT / "data" / "output" / safe_name
    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(status_code=404, detail=f"File not found: {safe_name}")
    return FileResponse(str(file_path), filename=file_path.name, media_type="application/octet-stream")
