from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import desc, func
from sqlalchemy.orm import Session

from database.connection import get_db_session
from database.models import (
    AuditLog,
    ComplianceQuestion,
    ComplianceScore,
    GapFinding,
    LawSource,
    PolicyAnalysis,
    VoiceTranscription,
)


# ======================================================================
# Policy Analysis
# ======================================================================

def create_analysis(
    sector: str,
    policy_text: str,
    *,
    summary: str | None = None,
    compliant_areas: list[str] | None = None,
    total_laws_checked: int | None = None,
    status: str = "completed",
    error_message: str | None = None,
    db: Session | None = None,
) -> PolicyAnalysis:
    """Create a new policy analysis record."""
    if db is None:
        db = get_db_session()
        close = True
    else:
        close = False

    try:
        analysis = PolicyAnalysis(
            sector=sector,
            policy_text=policy_text,
            policy_summary=summary,
            compliant_areas=compliant_areas,
            total_laws_checked=total_laws_checked,
            status=status,
            error_message=error_message,
        )
        db.add(analysis)
        db.commit()
        db.refresh(analysis)
        return analysis
    finally:
        if close:
            db.close()


def get_analysis(analysis_id: int, db: Session | None = None) -> PolicyAnalysis | None:
    """Fetch a policy analysis by ID."""
    s = db or get_db_session()
    try:
        return s.get(PolicyAnalysis, analysis_id)
    finally:
        if db is None:
            s.close()


def list_analyses(
    sector: str | None = None,
    limit: int = 20,
    offset: int = 0,
    db: Session | None = None,
) -> list[PolicyAnalysis]:
    """List policy analyses, newest first."""
    s = db or get_db_session()
    try:
        query = s.query(PolicyAnalysis)
        if sector:
            query = query.filter(PolicyAnalysis.sector == sector)
        return (
            query.order_by(desc(PolicyAnalysis.created_at))
            .limit(limit)
            .offset(offset)
            .all()
        )
    finally:
        if db is None:
            s.close()


def count_analyses(sector: str | None = None, db: Session | None = None) -> int:
    """Count policy analyses, optionally filtered by sector."""
    s = db or get_db_session()
    try:
        query = s.query(func.count(PolicyAnalysis.id))
        if sector:
            query = query.filter(PolicyAnalysis.sector == sector)
        return query.scalar() or 0
    finally:
        if db is None:
            s.close()


# ======================================================================
# Gap Findings
# ======================================================================

def add_gaps(analysis_id: int, gaps: list[dict], db: Session | None = None) -> list[GapFinding]:
    """Bulk-add gap findings for an analysis."""
    s = db or get_db_session()
    close = db is None

    try:
        created = []
        for g in gaps:
            finding = GapFinding(
                analysis_id=analysis_id,
                requirement=g.get("requirement", ""),
                law_reference=g.get("law_reference", ""),
                policy_status=g.get("policy_status", "missing"),
                severity=g.get("severity", "medium"),
                recommendation=g.get("recommendation"),
            )
            s.add(finding)
            created.append(finding)
        s.commit()
        for f in created:
            s.refresh(f)
        return created
    finally:
        if close:
            s.close()


def get_gaps_for_analysis(
    analysis_id: int, db: Session | None = None
) -> list[GapFinding]:
    """Return all gap findings for a given analysis."""
    s = db or get_db_session()
    try:
        return (
            s.query(GapFinding)
            .filter(GapFinding.analysis_id == analysis_id)
            .order_by(GapFinding.severity)
            .all()
        )
    finally:
        if db is None:
            s.close()


def count_gaps_by_severity(
    analysis_id: int, db: Session | None = None
) -> dict[str, int]:
    """Return gap counts grouped by severity for an analysis."""
    s = db or get_db_session()
    try:
        rows = (
            s.query(GapFinding.severity, func.count(GapFinding.id))
            .filter(GapFinding.analysis_id == analysis_id)
            .group_by(GapFinding.severity)
            .all()
        )
        return {sev: count for sev, count in rows}
    finally:
        if db is None:
            s.close()


# ======================================================================
# Compliance Scores
# ======================================================================

def create_score(
    analysis_id: int,
    overall_score: float,
    percentage: int,
    grade: str,
    *,
    penalty_points: float | None = None,
    breakdown: dict | None = None,
    total_requirements: int | None = None,
    db: Session | None = None,
) -> ComplianceScore:
    """Create a compliance score record linked to an analysis."""
    s = db or get_db_session()
    close = db is None

    try:
        score = ComplianceScore(
            analysis_id=analysis_id,
            overall_score=overall_score,
            percentage=percentage,
            grade=grade,
            penalty_points=penalty_points,
            breakdown=breakdown,
            total_requirements=total_requirements,
        )
        s.add(score)
        s.commit()
        s.refresh(score)
        return score
    finally:
        if close:
            s.close()


def get_score_for_analysis(
    analysis_id: int, db: Session | None = None
) -> ComplianceScore | None:
    """Get the compliance score for a given analysis."""
    s = db or get_db_session()
    try:
        return (
            s.query(ComplianceScore)
            .filter(ComplianceScore.analysis_id == analysis_id)
            .first()
        )
    finally:
        if db is None:
            s.close()


def get_score_history(
    sector: str, limit: int = 20, db: Session | None = None
) -> list[dict]:
    """Return score trend data for a sector (latest first)."""
    s = db or get_db_session()
    try:
        rows = (
            s.query(
                PolicyAnalysis.created_at,
                ComplianceScore.percentage,
                ComplianceScore.grade,
                ComplianceScore.overall_score,
            )
            .join(ComplianceScore, PolicyAnalysis.id == ComplianceScore.analysis_id)
            .filter(PolicyAnalysis.sector == sector)
            .order_by(desc(PolicyAnalysis.created_at))
            .limit(limit)
            .all()
        )
        return [
            {
                "date": row.created_at.isoformat() if row.created_at else "",
                "percentage": row.percentage,
                "grade": row.grade,
            }
            for row in rows
        ]
    finally:
        if db is None:
            s.close()


# ======================================================================
# Compliance Q&A
# ======================================================================

def create_question(
    sector: str,
    question: str,
    answer: str | None = None,
    confidence: float | None = None,
    top_k: int | None = None,
    sources: list[dict] | None = None,
    db: Session | None = None,
) -> ComplianceQuestion:
    """Record a compliance question, answer, and source citations."""
    s = db or get_db_session()
    close = db is None

    try:
        q = ComplianceQuestion(
            sector=sector,
            question=question,
            answer=answer,
            confidence=confidence,
            top_k=top_k,
        )
        s.add(q)
        s.flush()

        if sources:
            for src in sources:
                law_src = LawSource(
                    question_id=q.id,
                    law_name=src.get("law_name", "Unknown"),
                    section_number=src.get("section_number"),
                    section_title=src.get("section_title"),
                    text_snippet=src.get("text", src.get("text_snippet", ""))[:500],
                    score=src.get("score"),
                )
                s.add(law_src)

        s.commit()
        s.refresh(q)
        return q
    finally:
        if close:
            s.close()


def get_question(question_id: int, db: Session | None = None) -> ComplianceQuestion | None:
    """Fetch a compliance question by ID with its sources."""
    s = db or get_db_session()
    try:
        return s.get(ComplianceQuestion, question_id)
    finally:
        if db is None:
            s.close()


def search_questions(
    sector: str | None = None,
    query: str | None = None,
    limit: int = 20,
    db: Session | None = None,
) -> list[ComplianceQuestion]:
    """Search previously asked compliance questions."""
    s = db or get_db_session()
    try:
        q = s.query(ComplianceQuestion)
        if sector:
            q = q.filter(ComplianceQuestion.sector == sector)
        if query:
            q = q.filter(ComplianceQuestion.question.ilike(f"%{query}%"))
        return q.order_by(desc(ComplianceQuestion.created_at)).limit(limit).all()
    finally:
        if db is None:
            s.close()


# ======================================================================
# Voice Transcriptions
# ======================================================================

def create_transcription_log(
    sector: str,
    transcript: str,
    confidence: float | None = None,
    language: str | None = "en",
    duration_seconds: float | None = None,
    filename: str | None = None,
    document_type: str | None = None,
    db: Session | None = None,
) -> VoiceTranscription:
    """Log a voice transcription event."""
    s = db or get_db_session()
    close = db is None

    try:
        record = VoiceTranscription(
            sector=sector,
            filename=filename,
            transcript=transcript,
            confidence=confidence,
            language=language,
            duration_seconds=duration_seconds,
            document_type=document_type,
        )
        s.add(record)
        s.commit()
        s.refresh(record)
        return record
    finally:
        if close:
            s.close()


# ======================================================================
# Audit Log
# ======================================================================

def log_audit_event(
    agent_name: str,
    event: str,
    sector: str | None = None,
    status: str = "info",
    duration_ms: int | None = None,
    details: dict | None = None,
    db: Session | None = None,
) -> AuditLog:
    """Persist an audit/execution event."""
    s = db or get_db_session()
    close = db is None

    try:
        entry = AuditLog(
            agent_name=agent_name,
            event=event,
            sector=sector,
            status=status,
            duration_ms=duration_ms,
            details=details,
        )
        s.add(entry)
        s.commit()
        s.refresh(entry)
        return entry
    finally:
        if close:
            s.close()


def get_audit_logs(
    agent_name: str | None = None,
    sector: str | None = None,
    limit: int = 50,
    db: Session | None = None,
) -> list[AuditLog]:
    """Fetch audit log entries, newest first."""
    s = db or get_db_session()
    try:
        q = s.query(AuditLog)
        if agent_name:
            q = q.filter(AuditLog.agent_name == agent_name)
        if sector:
            q = q.filter(AuditLog.sector == sector)
        return q.order_by(desc(AuditLog.created_at)).limit(limit).all()
    finally:
        if db is None:
            s.close()
