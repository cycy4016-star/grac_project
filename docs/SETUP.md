# Setup Guide

## Prerequisites

- **Python 3.11+** (tested on 3.12)
- **pip** (Python package manager)
- **API keys**: Anthropic (Claude) and/or OpenAI (Whisper)

## Installation

### 1. Clone and Enter the Project

```bash
git clone <repo-url>
cd grac_project
```

### 2. Create Virtual Environment

```bash
# Windows
python -m venv venv
venv\Scripts\activate

# macOS / Linux
python3 -m venv venv
source venv/bin/activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure Environment

```bash
cp .env.example .env
```

Edit `.env` with your values:

```ini
# Required: at least one API key
ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-...

# Sector (default: cybersecurity)
ACTIVE_SECTOR=cybersecurity

# Optional overrides
API_PORT=8000
DATABASE_URL=sqlite:///./data/grac.db
LOG_LEVEL=INFO
```

### 5. Run Setup Script

```bash
python scripts/setup_environment.py
```

This creates all required directories, validates the sector configuration, and initializes logging.

### 6. Ingest Law PDFs

Place PDFs in `data/laws/{sector}/raw/`, then:

```bash
# Ingest a specific sector
python scripts/ingest_laws.py --sector cybersecurity

# Ingest all enabled sectors
python scripts/ingest_laws.py --all

# List available sectors and their status
python scripts/ingest_laws.py --list-sectors
```

The ingestion pipeline: PDF → Text → Chunks → Embeddings → ChromaDB.

## Configuration Reference

All variables in `.env`:

| Variable | Default | Description |
|----------|---------|-------------|
| `ANTHROPIC_API_KEY` | — | Claude API key (required for analysis/QA) |
| `OPENAI_API_KEY` | — | OpenAI key (required for Whisper transcription) |
| `ACTIVE_SECTOR` | cybersecurity | Default sector on startup |
| `ENABLE_MULTI_SECTOR` | False | Enable multi-sector mode (future) |
| `API_HOST` | 127.0.0.1 | API server bind address |
| `API_PORT` | 8000 | API server port |
| `API_DEBUG` | False | Enable FastAPI debug mode |
| `ANTHROPIC_MODEL` | claude-3-sonnet-20240229 | Claude model to use |
| `LLM_TEMPERATURE` | 0.3 | LLM creativity (0.0-1.0) |
| `LLM_MAX_TOKENS` | 4096 | Max response tokens |
| `PDF_CHUNK_SIZE` | 500 | Words per chunk |
| `PDF_OVERLAP` | 100 | Overlap between chunks |
| `AGENT_TIMEOUT` | 300 | Agent execution timeout (seconds) |
| `AGENT_RETRY_ATTEMPTS` | 3 | Retry count on failure |
| `DATABASE_URL` | sqlite:///./data/grac.db | Database connection string |
| `LOG_LEVEL` | INFO | Logging verbosity |
| `MIN_RETRIEVAL_CONFIDENCE` | 0.6 | Minimum ChromaDB similarity score |
| `MIN_ANSWER_CONFIDENCE` | 0.7 | Minimum confidence to report answer |

## Running

### Start API Server

```bash
# Via main.py
python main.py api

# Directly via uvicorn
uvicorn api.main:app --reload --port 8000
```

### Run Tests

```bash
# All tests
pytest

# With coverage
pytest --cov=agents --cov=tools --cov=database

# Sector switch tests
python scripts/test_sector_switch.py
```

### Validate Project Structure

```bash
python scripts/validate_structure.py --verbose
```

## Adding a New Sector

```bash
# 1. Create directories
mkdir -p data/laws/healthcare/{raw,parsed,chunks}
mkdir -p skills/healthcare

# 2. Edit config/sector_config.json
#    Add a new sector entry with id, laws, applicable_industries

# 3. Ingest laws
python scripts/ingest_laws.py --sector healthcare

# 4. Create skill templates in skills/healthcare/
```

## Database

Default: SQLite at `data/grac.db`. For PostgreSQL:

```bash
# Install psycopg2 (included in requirements.txt)
# Set DATABASE_URL in .env:
DATABASE_URL=postgresql://user:pass@host:5432/grac
```

Tables are auto-created on first import via `database.init_db()`.
