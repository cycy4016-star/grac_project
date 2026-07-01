"""
Analyzer Agent

Compares company policies against relevant laws to identify gaps.

Input: {"policy": "...", "laws": [...]} or {"policy": "...", "web_sources": "..."}
Output: {"gaps": [...], "findings": [...], "severity": [...]}
"""
from typing import Dict, Any
from agents.base_agent import BaseAgent


class AnalyzerAgent(BaseAgent):
    """Analyzer Agent - Identifies compliance gaps and issues."""

    def __init__(self, sector=None):
        super().__init__("AnalyzerAgent", sector)

    def validate_input(self, input_data: Any) -> bool:
        if not isinstance(input_data, dict):
            return False
        return "policy" in input_data and ("laws" in input_data or "web_sources" in input_data)

    def execute(self, input_data: Dict[str, Any], **kwargs) -> Dict[str, Any]:
        from tools.llm_tools import (
            build_gap_analysis_prompt, call_llm, parse_json_response
        )
        from config.settings import settings

        policy = input_data.get("policy", "")
        law_chunks = input_data.get("laws", [])
        web_sources = input_data.get("web_sources", "")

        self.logger.info(f"Analyzing policy ({len(policy)} chars) against {len(law_chunks)} law chunks")

        if not law_chunks and not web_sources:
            self.logger.warning("No law chunks or web sources provided — analysis will be empty")
            return {
                "gaps": [],
                "findings": [],
                "severity": [],
                "summary": "No relevant legal sources found to compare against.",
                "compliant_areas": [],
                "total_laws_checked": 0,
            }

        if web_sources and not law_chunks:
            prompt = _build_web_gap_analysis_prompt(policy, web_sources)
        else:
            prompt = build_gap_analysis_prompt(policy, law_chunks)

        raw_response = call_llm(
            prompt=prompt,
            model=settings.ANTHROPIC_MODEL,
            max_tokens=settings.LLM_MAX_TOKENS,
            temperature=settings.LLM_TEMPERATURE,
        )

        parsed = parse_json_response(raw_response)

        if "error" in parsed:
            self.logger.warning(f"LLM response parse failed — returning raw: {raw_response[:200]}")
            return {
                "gaps": [],
                "findings": [{"raw_analysis": raw_response}],
                "severity": [],
                "summary": raw_response[:500],
                "compliant_areas": [],
            }

        gaps = parsed.get("gaps", [])
        severities = [g.get("severity", "medium") for g in gaps]

        severity_counts = _count_severities(severities)
        if severity_counts:
            self.logger.info(f"Identified {len(gaps)} gaps: {dict(severity_counts)}")

        self._save_checkpoint("last_analysis", {
            "gap_count": len(gaps),
            "summary": parsed.get("summary", ""),
        })

        return {
            "gaps": gaps,
            "findings": gaps,
            "severity": severities,
            "summary": parsed.get("summary", ""),
            "compliant_areas": parsed.get("compliant_areas", []),
            "total_laws_checked": len(law_chunks) if law_chunks else 0,
        }

    def format_output(self, result: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "status": "success",
            "gaps": result.get("gaps", []),
            "findings": result.get("findings", []),
            "severity": result.get("severity", []),
            "summary": result.get("summary", ""),
            "compliant_areas": result.get("compliant_areas", []),
            "sector": self.sector,
        }


def _build_web_gap_analysis_prompt(policy_text: str, web_sources: str) -> str:
    """Build a gap analysis prompt using web search results as legal sources."""
    return f"""You are a Ghanaian compliance expert. Analyze the company policy against the relevant legal requirements found from web research below.

## Web Research Sources

{web_sources[:6000]}

## Company Policy

{policy_text[:8000]}

## Instructions

Identify compliance gaps — legal requirements the policy does not meet or inadequately addresses. Cite the web sources where possible.

Respond ONLY with a valid JSON object in this exact structure:
{{
  "gaps": [
    {{
      "requirement": "Brief description of the legal requirement",
      "law_reference": "e.g. Act 843, Section 5(1) — cited from [source URL]",
      "policy_status": "missing" | "inadequate" | "present",
      "severity": "critical" | "high" | "medium" | "low",
      "recommendation": "Specific action to remedy this gap"
    }}
  ],
  "summary": "2-3 sentence overall compliance summary",
  "compliant_areas": ["Area 1", "Area 2"]
}}"""


def _count_severities(severities: list) -> list[tuple]:
    """Return severity counts as (severity, count) pairs."""
    from collections import Counter
    return list(Counter(severities).items())
