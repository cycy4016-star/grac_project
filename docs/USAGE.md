# Usage Guide

## Modes

GRaC can be run in four modes via `python main.py <command>`:

| Command | Description |
|---------|-------------|
| `api` | Start FastAPI HTTP server (default) |
| `cli` | Interactive command-line mode (stub) |
| `test` | Run pytest suite |
| `setup` | Initialize directories and logging |

---

## API Usage

Start the server:

```bash
python main.py api
# or
uvicorn api.main:app --reload --port 8000
```

Health check:

```bash
curl http://localhost:8000/api/health
# {"status":"ok","service":"GRaC API","version":"1.0.0","active_sector":"cybersecurity"}
```

### Analyze Policy

```bash
curl -X POST http://localhost:8000/api/analyze-policy \
  -H "Content-Type: application/json" \
  -d '{
    "sector": "cybersecurity",
    "policy": "Our organisation encrypts all customer data at rest...",
    "output_format": "pdf"
  }'
```

### Ask Compliance Question

```bash
curl -X POST http://localhost:8000/api/ask-compliance \
  -H "Content-Type: application/json" \
  -d '{
    "sector": "cybersecurity",
    "question": "What are the breach notification requirements under Act 1038?",
    "top_k": 5,
    "return_sources": true
  }'
```

### Process Voice Input

```bash
curl -X POST http://localhost:8000/api/process-voice \
  -F "audio_file=@recording.mp3" \
  -F "sector=cybersecurity" \
  -F "document_type=incident_report"
```

### Calculate Compliance Score

```bash
curl -X POST http://localhost:8000/api/compliance-score \
  -H "Content-Type: application/json" \
  -d '{
    "sector": "cybersecurity",
    "policy": "We have implemented firewalls and access controls...",
    "total_requirements": 10
  }'
```

---

## CLI Mode

```bash
python main.py cli
```

Interactive commands (stub — under development):

```
ask <question>          Ask compliance question
analyze <policy_file>   Analyze policy for gaps
score <policy_file>     Calculate compliance score
switch <sector>         Switch active sector
exit                    Exit
```

---

## Scripts

### Law Ingestion

```bash
# Ingest a single sector's PDFs
python scripts/ingest_laws.py --sector cybersecurity

# Ingest all enabled sectors
python scripts/ingest_laws.py --all

# Skip the embedding step (re-parse only)
python scripts/ingest_laws.py --sector cybersecurity --skip-embed

# List available sectors
python scripts/ingest_laws.py --list-sectors
```

The pipeline processes every PDF in `data/laws/{sector}/raw/` through three stages:

1. **IngestorAgent** — Extract text with pdfplumber/PyMuPDF
2. **ParserAgent** — Parse into hierarchical chunks (PART → Section → Subsection)
3. **EmbedderAgent** — Embed with sentence-transformers, store in ChromaDB

### Structure Validation

```bash
# Check all required paths and files exist
python scripts/validate_structure.py

# Verbose output with details
python scripts/validate_structure.py --verbose

# Auto-create missing directories
python scripts/validate_structure.py --fix
```

### Sector Switch Tests

```bash
python scripts/test_sector_switch.py
# verbose:
python scripts/test_sector_switch.py --verbose
```

---

## Sector Management

Switch the active sector:

```python
from utils.sector_manager import sector_manager

# Switch
sector_manager.switch_sector("fintech")

# Check current
current = sector_manager.active_sector  # "fintech"

# Validate without switching
sector_manager.validate_sector("cybersecurity")
```

Sectors are defined in `config/sector_config.json`. Only enabled sectors can be activated. Disabled sectors (e.g., `healthcare`, `telecom`) are recognized but blocked.

---

## Database Queries

Direct database access for custom queries:

```python
from database import init_db, get_db_session
from database.queries import (
    create_analysis, get_analysis, list_analyses,
    add_gaps, get_gaps_for_analysis,
    create_score, get_score_history,
    create_question, search_questions,
    log_audit_event,
)

init_db()

# Create an analysis
a = create_analysis("cybersecurity", "Policy text...", summary="My analysis")

# Add gaps
gaps = add_gaps(a.id, [
    {"requirement": "Encrypt data", "law_reference": "Act 843 s.28",
     "policy_status": "missing", "severity": "high"},
])

# Score it
s = create_score(a.id, 0.75, 75, "B", penalty_points=25.0)

# Read back with relationships
analysis = get_analysis(a.id)
print(analysis.gaps, analysis.score.grade)
```

---

## Skill Templates

Document templates live in `skills/{sector}/*.md` and are used by the WriterAgent for report generation. Each template uses `{placeholder}` variables that get filled at generation time.

To add a template:

```bash
# Create a markdown file
echo "# {title}\n\n{body}" > skills/cybersecurity/my_template.md
```

Existing templates (11 total):

| Sector | Templates |
|--------|-----------|
| cybersecurity | pentest_report, incident_response, policy_draft, risk_assessment, compliance_checklist |
| fintech | vendor_assessment, regulatory_response, audit_report |
| data_protection | dpia_template, breach_notice, gap_analysis |
