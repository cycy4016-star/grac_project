"""
LLM Tools

Used by: AnalyzerAgent, WriterAgent, RetrieverAgent
Responsibilities:
- Call LLM API for gap analysis, document generation, Q&A
- Format prompts with retrieved law context
- Parse structured responses

Now uses the multi-provider abstraction (llm_providers.py).
"""
import json
import re
from typing import Optional
from tools.llm_providers import call_llm


def _system_knowledge_block() -> str:
    """Return a text block describing what the system knows (for self-awareness).

    Single source of truth used by all agents and prompts.
    """
    try:
        from config.settings import settings as s
        from utils.sector_manager import sector_manager as sm

        lines = [
            "## Personality",
            "You are GRaC — a friendly GRC companion for Ghanaian law. You speak like a knowledgeable colleague who genuinely",
            "enjoys helping with compliance. You're professional but warm, precise but conversational. You can geek out about",
            "regulatory frameworks, then switch to casual chat without missing a beat. Use phrases like 'Let me look into that',",
            "'Here's what I found', 'Great question!' — sound human, not like a report generator.",
            "",
            "You're chatting with a compliance professional. Match their energy: if they're formal, be formal; if they're casual,",
            "be casual. Never start by saying 'I don't have enough information' — instead say what you *can* help with.",
            "",
            "## Loaded Knowledge (sectors + laws you have ingested):",
        ]
        for entry in s.SECTOR_CONFIG.get("sectors", []):
            if not entry.get("enabled"):
                continue
            sid = entry["id"]
            raw_dir = sm.get_raw_path(sid)
            laws = []
            if raw_dir.exists():
                laws = [p.stem.replace("_", " ").title() for p in sorted(raw_dir.glob("*.pdf"))]
            parsed_dir = sm.get_parsed_path(sid)
            ingested = len(list(parsed_dir.glob("*.txt"))) if parsed_dir.exists() else 0
            law_list = ", ".join(laws) if laws else "No laws loaded"
            lines.append(f"  [{sid}] {entry.get('name', sid.title())}: {law_list} ({ingested} documents ingested)")
        lines.append("")
        lines.append("You have real-time web research capability and automatically search the web for every question.")
        lines.append("You use both loaded law context and web search results together to answer.")
        lines.append("")
        lines.append("You can GENERATE PROFESSIONAL PDF DOCUMENTS of compliance policies.")
        lines.append("If the user asks you to 'draft', 'write', 'create', or 'generate' a policy document, policy draft, or compliance report —")
        lines.append("tell them you can produce a professional PDF with full law citations.")
        lines.append("After you provide your answer, let them know you can export it as a downloadable PDF if they want.")
        lines.append("")
        lines.append("## Hallucination Guardrails (MANDATORY)")
        lines.append("  - NEVER invent a law name, section number, or regulatory body.")
        lines.append("  - If you don't know the answer, say: 'I don't have that information in my loaded laws. Let me search the web for you.'")
        lines.append("  - If the user asks about a sector or law you do NOT have, say so immediately.")
        lines.append("  - For EVERY factual claim about a law, provide the specific Act name and section number.")
        lines.append("  - If you cannot cite the source of a claim, do not make the claim.")
        lines.append("  - If you have the law but it is not yet ingested/vectorized, say 'This law is loaded but not yet searchable'.")
        lines.append("  - Just chat casually if that's what the user is doing — no need to cite laws for every sentence.")
        lines.append("  - When asked to draft a policy and you lack law context, use web research results as your law references and cite them clearly.")
        return "\n".join(lines)
    except Exception:
        return ""


def build_gap_analysis_prompt(policy_text: str, law_chunks: list[dict]) -> str:
    """
    Build the prompt for the AnalyzerAgent's gap analysis.

    Args:
        policy_text: The company policy document text
        law_chunks: Retrieved law sections (from embedding_tools.query_collection)

    Returns:
        Formatted prompt string
    """
    law_context = _format_law_chunks(law_chunks)

    system_knowledge = _system_knowledge_block()

    return f"""{system_knowledge}

---

You are a Ghanaian compliance expert. Analyze the company policy against the relevant legal requirements below.

## Relevant Legal Requirements

{law_context}

## Company Policy

{policy_text[:8000]}

## Instructions

Identify compliance gaps — legal requirements the policy does not meet or inadequately addresses.

Respond ONLY with a valid JSON object in this exact structure:
{{
  "gaps": [
    {{
      "requirement": "Brief description of the legal requirement",
      "law_reference": "e.g. Act 843, Section 5(1)",
      "policy_status": "missing" | "inadequate" | "present",
      "severity": "critical" | "high" | "medium" | "low",
      "recommendation": "Specific action to remedy this gap"
    }}
  ],
  "summary": "2-3 sentence overall compliance summary",
  "compliant_areas": ["Area 1", "Area 2"]
}}"""


def build_compliance_qa_prompt(question: str, law_chunks: list[dict]) -> str:
    """
    Build the prompt for answering a compliance question with citations.

    Args:
        question: User's compliance question
        law_chunks: Retrieved relevant law sections

    Returns:
        Formatted prompt string
    """
    law_context = _format_law_chunks(law_chunks)
    system_knowledge = _system_knowledge_block()

    return f"""{system_knowledge}

---

## Possible Legal Sources

{law_context}

## Question from user

{question}

Speak like a colleague helping a peer. If the legal sources are relevant, cite them naturally
(e.g. "Under Section 5(1) of Act 843 you'd need to..."). If they aren't relevant, just answer
conversationally from your own knowledge — no need to force citations.

Be warm, clear, and direct. Imagine the user is sitting next to you asking for advice."""


def _ensure_aware(prompt: str) -> str:
    return f"{_system_knowledge_block()}\n\n---\n\n{prompt}"


def build_document_prompt(doc_type: str, content: dict, sector: str) -> str:
    """
    Build the prompt for WriterAgent document generation.

    Args:
        doc_type: "gap_analysis" | "incident_report" | "policy_draft"
        content: Structured content dict from AnalyzerAgent / AnalyzerAgent
        sector: Active sector (for tone/context)

    Returns:
        Formatted prompt string
    """
    sector_label = sector.replace("_", " ").title()

    if doc_type == "gap_analysis":
        gaps_text = json.dumps(content.get("gaps", []), indent=2)
        return f"""You are a professional compliance consultant specializing in {sector_label} in Ghana.

Write a formal Gap Analysis Report based on the findings below.

## Findings

{gaps_text}

## Summary
{content.get("summary", "")}

## Requirements

- Professional tone suitable for board/management presentation
- Structure: Executive Summary → Findings → Recommendations → Next Steps
- Reference specific Ghanaian laws by name and section
- Prioritize critical and high severity gaps first
- Keep recommendations actionable and time-bound
- Length: 600-900 words"""

    elif doc_type == "incident_report":
        return f"""You are a cybersecurity compliance officer in Ghana.

Write a formal Incident Report based on the information below.

## Incident Details

{json.dumps(content, indent=2)}

## Requirements

- Professional tone for regulatory submission
- Structure: Incident Summary → Timeline → Impact Assessment → Response Actions → Recommendations
- Reference applicable sections of the Cybersecurity Act 2020 (Act 1038) where relevant
- Length: 400-600 words"""

    elif doc_type == "policy_draft":
        return f"""You are a Ghanaian compliance expert drafting a new company policy.

Draft a {sector_label} compliance policy based on the requirements below.

## Requirements and Context

{json.dumps(content, indent=2)}

## Instructions

- Professional and clear language
- Structure with numbered sections
- Cite specific Ghanaian laws where applicable
- Include: Purpose, Scope, Definitions, Requirements, Responsibilities, Review Period
- Length: 800-1200 words"""

    else:
        return f"Generate a professional {doc_type} document based on: {json.dumps(content)}"


def call_claude(
    prompt: str,
    api_key: str = "",
    model: str = "",
    max_tokens: int = 0,
    temperature: float = 0.0,
    system: Optional[str] = None,
    timeout_seconds: int = 120,
) -> str:
    """
    Call the Claude API and return the response text.

    Delegates to the multi-provider call_llm() for actual execution.
    The api_key, model, max_tokens, temperature params are optional -
    if not provided (or zero/empty), settings defaults are used.

    Args:
        prompt: User message prompt
        api_key: Anthropic API key (uses env var if empty)
        model: Claude model string (uses settings default if empty)
        max_tokens: Maximum tokens in response
        temperature: Sampling temperature
        system: Optional system prompt override
        timeout_seconds: Request timeout in seconds (default 120)

    Returns:
        Response text from Claude

    Raises:
        RuntimeError: If the API call fails or times out
    """
    return call_llm(
        prompt=prompt,
        provider_name="anthropic",
        model=model or None,
        max_tokens=max_tokens or None,
        temperature=temperature or None,
        system=system,
        timeout_seconds=timeout_seconds,
    )


def call_openai(
    prompt: str,
    api_key: str = "",
    model: str = "",
    max_tokens: int = 0,
    temperature: float = 0.0,
    system: Optional[str] = None,
    timeout_seconds: int = 120,
) -> str:
    """
    Call the OpenAI API and return the response text.

    Delegates to the multi-provider call_llm() for actual execution.
    The api_key, model, max_tokens, temperature params are optional -
    if not provided (or zero/empty), settings defaults are used.

    Args:
        prompt: User message prompt
        api_key: OpenAI API key (uses env var if empty)
        model: OpenAI model string (uses settings default if empty)
        max_tokens: Maximum tokens in response
        temperature: Sampling temperature
        system: Optional system prompt override
        timeout_seconds: Request timeout in seconds (default 120)

    Returns:
        Response text from OpenAI

    Raises:
        RuntimeError: If the API call fails or times out
    """
    return call_llm(
        prompt=prompt,
        provider_name="openai",
        model=model or None,
        max_tokens=max_tokens or None,
        temperature=temperature or None,
        system=system,
        timeout_seconds=timeout_seconds,
    )


def parse_json_response(response_text: str) -> dict:
    """
    Safely parse a JSON response from the LLM.

    Strips markdown code fences if present.

    Returns:
        Parsed dict, or {"error": "parse_failed", "raw": response_text} on failure
    """
    # Strip markdown fences
    cleaned = re.sub(r"```(?:json)?", "", response_text).strip().rstrip("```").strip()

    # Find the first { or [ to handle leading prose
    start = min(
        (cleaned.find("{") if "{" in cleaned else len(cleaned)),
        (cleaned.find("[") if "[" in cleaned else len(cleaned)),
    )
    cleaned = cleaned[start:]

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        return {"error": "parse_failed", "raw": response_text}


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _format_law_chunks(chunks: list[dict]) -> str:
    """Format retrieved law chunks into a readable context block."""
    if not chunks:
        return "No relevant legal sources found."

    lines = []
    for i, chunk in enumerate(chunks, 1):
        meta = chunk.get("metadata", {})
        law = meta.get("law_name", "Unknown Law")
        section = meta.get("section_number", "?")
        section_title = meta.get("section_title", "")
        score = chunk.get("score", 0)

        lines.append(
            f"[{i}] {law} — Section {section}: {section_title} (relevance: {score:.0%})\n"
            f"{chunk.get('text', '').strip()}\n"
        )

    return "\n".join(lines)
