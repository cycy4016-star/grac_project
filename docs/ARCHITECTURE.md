# GRaC Architecture

## Overview

GRaC (Governance, Risk & Compliance Agent) uses a **multi-agent orchestration** architecture. Each agent specializes in a single task, and a Supervisor Agent coordinates them into workflows. The system is sector-aware — laws and templates are organized by industry (cybersecurity, fintech, data_protection).

## System Diagram

```
                         ┌──────────────────┐
                         │   User Input      │
                         │ (API / CLI / File)│
                         └────────┬─────────┘
                                  │
                         ┌────────▼─────────┐
                         │  SupervisorAgent  │
                         │  (Orchestrator)   │
                         │  Routes requests  │
                         │  to workflows     │
                         └───┬───┬───┬───┬──┘
                             │   │   │   │
            ┌────────────────┘   │   │   └──────────────────┐
            ▼                    ▼   ▼                       ▼
    ┌──────────────┐    ┌──────────────┐          ┌────────────────┐
    │ RetrieverAgent│    │ AnalyzerAgent│          │  ScorerAgent   │
    │ ChromaDB →    │    │ LLM → Gaps   │          │ Gaps → Score   │
    │ Law chunks    │    │ & Findings   │          │ & Grade        │
    └──────────────┘    └──────┬───────┘          └────────────────┘
                               │
                               ▼
                       ┌──────────────┐
                       │  WriterAgent  │
                       │ ReportLab →   │
                       │ PDF / DOCX    │
                       └──────────────┘

    ┌──────────────┐    ┌──────────────┐    ┌────────────────┐
    │ IngestorAgent│    │ ParserAgent   │    │ EmbedderAgent  │
    │ PDF → Text   │    │ Text → Chunks │    │ Chunks →       │
    │              │    │ w/ hierarchy  │    │ ChromaDB vecs  │
    └──────────────┘    └──────────────┘    └────────────────┘

    ┌──────────────────┐
    │ TranscriberAgent  │
    │ Audio → Text      │
    │ (Whisper API)     │
    └──────────────────┘
```

## Data Flow

### Ingestion Pipeline (one-time per law PDF)

```
PDF → IngestorAgent → ParserAgent → EmbedderAgent → ChromaDB
       (text)         (chunks)       (vectors)
```

### Compliance Analysis (on-demand)

```
Policy Text → RetrieverAgent ──┐
                │               │
                ▼               ▼
          ChromaDB        AnalyzerAgent ──→ WriterAgent ──→ PDF/DOCX
          (law chunks)    (gaps +        (report doc)
                          findings)
                               │
                               └──→ ScorerAgent ──→ Score + Grade
                                   (percentage)
```

### Voice Input

```
Audio File → TranscriberAgent → RetrieverAgent → AnalyzerAgent → WriterAgent
             (transcript)       (laws)           (gaps)          (report)
```

### Compliance Q&A

```
Question → RetrieverAgent → LLM (Claude) → Answer + Citations
           (law chunks)     (prompt)
```

## Sector Management

Each sector has its own law database (ChromaDB collection), skill templates, and file tree:

```
data/laws/{sector}/
  raw/       — Original PDFs
  parsed/    — Extracted text
  chunks/    — Parsed hierarchical chunks
skills/{sector}/
  *.md      — Document templates
```

Switching sectors (via `sector_manager.switch_sector()`) updates the active collection and template paths.

## Database (SQLAlchemy)

7 ORM models for persistence:

| Model | Table | Purpose |
|-------|-------|---------|
| `PolicyAnalysis` | policy_analyses | Analysis runs with metadata |
| `GapFinding` | gap_findings | Individual gaps per analysis |
| `ComplianceScore` | compliance_scores | Scored results linked to analyses |
| `ComplianceQuestion` | compliance_questions | Q&A history with sources |
| `LawSource` | law_sources | Source citations per question |
| `VoiceTranscription` | voice_transcriptions | Transcription log |
| `AuditLog` | audit_logs | Agent activity trail |

All queries support optional `db: Session` for both FastAPI dependency injection and standalone usage.

## Key Design Decisions

1. **Single-sector MVP** — Only one sector active at a time; multi-sector foundation exists but disabled
2. **ChromaDB for vector storage** — Each sector is a separate collection with cosine similarity search
3. **Anthropic Claude for reasoning** — All analysis and document generation uses Claude via direct API calls
4. **Step-level error resilience** — Workflow steps that fail don't crash the pipeline; empty results propagate
5. **SQLite default, PostgreSQL optional** — `DATABASE_URL` env overrides for production
6. **ASCII-only console output** — Avoids cp1252 encoding issues on Windows

## Configuration

All settings live in `config/settings.py`, loaded from `.env`:

- Sector configuration in `config/sector_config.json`
- API keys, model names, chunk sizes
- Path overrides via environment variables
