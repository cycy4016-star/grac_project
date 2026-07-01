from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String, Text, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.connection import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# Policy Analysis
# ---------------------------------------------------------------------------

class PolicyAnalysis(Base):
    __tablename__ = "policy_analyses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    sector: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    policy_text: Mapped[str] = mapped_column(Text, nullable=False)
    policy_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    compliant_areas: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    total_laws_checked: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="completed")
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )

    gaps: Mapped[list[GapFinding]] = relationship(
        "GapFinding", back_populates="analysis", cascade="all, delete-orphan",
        lazy="selectin",
    )
    score: Mapped[ComplianceScore | None] = relationship(
        "ComplianceScore", back_populates="analysis", uselist=False,
        cascade="all, delete-orphan", lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<PolicyAnalysis id={self.id} sector={self.sector} status={self.status}>"


# ---------------------------------------------------------------------------
# Gap Findings
# ---------------------------------------------------------------------------

class GapFinding(Base):
    __tablename__ = "gap_findings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    analysis_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("policy_analyses.id", ondelete="CASCADE"), nullable=False, index=True
    )
    requirement: Mapped[str] = mapped_column(Text, nullable=False)
    law_reference: Mapped[str] = mapped_column(String(255), nullable=False)
    policy_status: Mapped[str] = mapped_column(String(32), nullable=False)
    severity: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    recommendation: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )

    analysis: Mapped[PolicyAnalysis] = relationship("PolicyAnalysis", back_populates="gaps")

    def __repr__(self) -> str:
        return f"<GapFinding id={self.id} severity={self.severity} law={self.law_reference}>"


# ---------------------------------------------------------------------------
# Compliance Scores
# ---------------------------------------------------------------------------

class ComplianceScore(Base):
    __tablename__ = "compliance_scores"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    analysis_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("policy_analyses.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    overall_score: Mapped[float] = mapped_column(Float, nullable=False)
    percentage: Mapped[int] = mapped_column(Integer, nullable=False)
    grade: Mapped[str] = mapped_column(String(4), nullable=False)
    penalty_points: Mapped[float | None] = mapped_column(Float, nullable=True)
    breakdown: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    total_requirements: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )

    analysis: Mapped[PolicyAnalysis] = relationship("PolicyAnalysis", back_populates="score")

    def __repr__(self) -> str:
        return f"<ComplianceScore id={self.id} grade={self.grade} pct={self.percentage}>"


# ---------------------------------------------------------------------------
# Compliance Q&A
# ---------------------------------------------------------------------------

class ComplianceQuestion(Base):
    __tablename__ = "compliance_questions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    sector: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    question: Mapped[str] = mapped_column(Text, nullable=False)
    answer: Mapped[str | None] = mapped_column(Text, nullable=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    top_k: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )

    sources: Mapped[list[LawSource]] = relationship(
        "LawSource", back_populates="question", cascade="all, delete-orphan",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<ComplianceQuestion id={self.id} sector={self.sector}>"


class LawSource(Base):
    __tablename__ = "law_sources"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    question_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("compliance_questions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    law_name: Mapped[str] = mapped_column(String(255), nullable=False)
    section_number: Mapped[str | None] = mapped_column(String(32), nullable=True)
    section_title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    text_snippet: Mapped[str | None] = mapped_column(Text, nullable=True)
    score: Mapped[float | None] = mapped_column(Float, nullable=True)

    question: Mapped[ComplianceQuestion] = relationship("ComplianceQuestion", back_populates="sources")

    def __repr__(self) -> str:
        return f"<LawSource id={self.id} law={self.law_name} sec={self.section_number}>"


# ---------------------------------------------------------------------------
# Voice Transcription Log
# ---------------------------------------------------------------------------

class VoiceTranscription(Base):
    __tablename__ = "voice_transcriptions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    sector: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    transcript: Mapped[str | None] = mapped_column(Text, nullable=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    language: Mapped[str | None] = mapped_column(String(8), nullable=True)
    duration_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)
    document_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )

    def __repr__(self) -> str:
        return f"<VoiceTranscription id={self.id} lang={self.language}>"


# ---------------------------------------------------------------------------
# Audit Log
# ---------------------------------------------------------------------------

class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    agent_name: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    event: Mapped[str] = mapped_column(String(128), nullable=False)
    sector: Mapped[str | None] = mapped_column(String(64), nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="info")
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    details: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )

    def __repr__(self) -> str:
        return f"<AuditLog id={self.id} agent={self.agent_name} event={self.event}>"
