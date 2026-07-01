from __future__ import annotations

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class AnalyzePolicyRequest(BaseModel):
    sector: Optional[str] = Field(None, description="Sector ID (defaults to active sector)")
    policy: str = Field(..., min_length=50, description="Policy document text")
    output_format: str = Field("pdf", pattern=r"^(pdf|docx)$")


class AskComplianceRequest(BaseModel):
    sector: Optional[str] = Field(None, description="Sector ID (defaults to active sector)")
    question: str = Field(..., min_length=5, max_length=4000)
    top_k: int = Field(5, ge=1, le=20, description="Number of law sections to retrieve")
    return_sources: bool = Field(True, description="Include source citations in response")


class ProcessVoiceRequest(BaseModel):
    sector: Optional[str] = Field(None, description="Sector ID (defaults to active sector)")
    document_type: str = Field("incident_report", pattern=r"^(incident_report|gap_analysis|policy_draft)$")
    language: str = Field("en", pattern=r"^(en)$", description="ISO-639-1 language code")


class ComplianceScoreRequest(BaseModel):
    sector: Optional[str] = Field(None, description="Sector ID (defaults to active sector)")
    policy: str = Field(..., min_length=50, description="Policy document text")
    total_requirements: Optional[int] = Field(None, ge=1, description="Total requirements to check against")


class GapItem(BaseModel):
    requirement: str
    law_reference: str
    policy_status: str
    severity: str
    recommendation: str


class GapAnalysisResult(BaseModel):
    summary: str
    gaps: list[GapItem]
    compliant_areas: list[str]
    total_laws_checked: int


class ScoreBreakdown(BaseModel):
    critical: dict
    high: dict
    medium: dict
    low: dict


class ScoreResult(BaseModel):
    overall_score: float
    percentage: int
    grade: str
    breakdown: ScoreBreakdown


class LawSource(BaseModel):
    law_name: str
    section_number: str
    section_title: str
    text: str
    score: float


class ComplianceAnswer(BaseModel):
    answer: str
    sources: list[LawSource]
    confidence: float


class DraftPolicyRequest(BaseModel):
    topic: str = Field(..., min_length=10, description="Policy topic description")
    sector: Optional[str] = Field(None, description="Sector ID (defaults to active sector)")


class WebResearchRequest(BaseModel):
    query: str = Field(..., min_length=5, description="Search query for web research")
    sector: Optional[str] = Field(None, description="Sector ID (defaults to active sector)")
    top_k: int = Field(5, ge=1, le=20, description="Number of results to return")
    summarize: bool = Field(False, description="Generate an LLM summary of results")


class ApiResponse(BaseModel):
    status: str
    timestamp: str
    sector: str
    data: Any


class ErrorDetail(BaseModel):
    field: Optional[str] = None
    message: str


class ApiError(BaseModel):
    status: str = "error"
    error: ErrorDetail


class Capability(BaseModel):
    id: str
    name: str
    description: str
    endpoint: str


class SystemKnowledgeResponse(BaseModel):
    system_name: str
    version: str
    jurisdiction: str
    status: str
    sectors: list[dict]
    capabilities: list[Capability]


class FeedbackRequest(BaseModel):
    message_id: str = Field(..., description="Message identifier")
    question: str = Field(..., description="Original user question")
    answer: str = Field(..., description="The AI's answer")
    rating: int = Field(..., ge=1, le=2, description="1=thumbs down, 2=thumbs up")
    correction: Optional[str] = Field(None, description="Optional corrected answer text")
    sector: Optional[str] = Field(None, description="Active sector when answer was given")
    sources: Optional[list[dict]] = Field(None, description="Sources cited in the answer")
