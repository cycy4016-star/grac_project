# GRaC - Governance, Risk & Compliance Agent

**An AI-powered compliance assistant for cybersecurity and GRC professionals in Ghana.**

GRaC helps compliance professionals automate the boring 20-30% of their work—document review, gap analysis, policy drafting, and compliance reporting—while keeping lawyers and analysts in full control.

---

## What GRaC Does

### For Ethical Hackers & Security Analysts
Instead of writing 2-hour compliance reports after each engagement, describe your work to GRaC (voice or text) and get a professional, law-cited document in 5 minutes.

### For Company GRC Officers
Upload your company policies. GRaC compares them against Ghanaian laws and generates a gap analysis report with specific recommendations.

### For Compliance Teams
Ask compliance questions in plain English. GRaC searches Ghanaian law (Act 843, Act 1038, BoG CISD) and answers with exact citations.

---

## Architecture

GRaC uses **multi-agent orchestration**. Each agent has ONE job and does it well:

```
User Input
    ↓
Supervisor Agent (decides which agents to use)
    ├→ Ingestor Agent (PDF → Text)
    ├→ Parser Agent (Text → Hierarchy)
    ├→ Embedder Agent (Chunks → Vectors)
    ├→ Retriever Agent (Query → Relevant Laws)
    ├→ Analyzer Agent (Policy vs Laws → Gaps)
    ├→ Writer Agent (Gaps → Professional Document)
    ├→ Transcriber Agent (Audio → Text)
    └→ Scorer Agent (Policy → Compliance %)
    ↓
Professional Output (PDF Report, Answer, Score)
```

---

## Project Structure

```
grac/
├── config/              # Configuration & sector management
├── data/
│   └── laws/           # Laws organized by sector
│       ├── cybersecurity/
│       ├── fintech/
│       └── data_protection/
├── agents/             # All specialized agents
├── tools/              # Agent tools
├── skills/             # Document templates by sector
├── api/                # FastAPI endpoints
├── database/           # Data persistence
├── utils/              # Utilities
├── tests/              # Test suite
└── docs/               # Documentation
```

---

## Sector Organization

Laws are organized by sector. When you switch sectors, agents automatically work with the right laws:

```
data/laws/cybersecurity/
  ├── raw/              (Original PDFs)
  ├── parsed/           (Extracted text)
  ├── chunks/           (Parsed sections)
  └── registry.json

data/laws/fintech/
  ├── raw/
  ├── parsed/
  ├── chunks/
  └── registry.json
```

**MVP (July 1):** Single sector at a time  
**Future:** Multi-sector support (e.g., fintech + cybersecurity simultaneously)

---

## Quick Start

### 1. Setup Environment

```bash
# Clone repository
git clone <repo_url>
cd grac

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Create .env file
cp .env.example .env
# Edit .env with your API keys
```

### 2. Configure API Keys

Edit `.env`:
```
ANTHROPIC_API_KEY=your_key_here
OPENAI_API_KEY=your_key_here
ACTIVE_SECTOR=cybersecurity
```

### 3. Run Setup

```bash
python scripts/setup_environment.py
```

This:
- Creates all required directories
- Validates sector configuration
- Initializes logging
- Prepares vectorstore

### 4. Ingest Laws

```bash
# Download laws (manually from Ghana Laws Online)
# Place in data/laws/{sector}/raw/

# Run ingestion pipeline
python scripts/ingest_laws.py --sector cybersecurity
```

This:
- Extracts text from PDFs
- Parses hierarchical structure
- Creates embeddings
- Stores in ChromaDB

### 5. Start API Server

```bash
python api/main.py
```

Server runs on `http://localhost:8000`

---

## API Endpoints

### Analyze Policy for Gaps
```
POST /api/analyze-policy
Content-Type: application/json

{
  "sector": "cybersecurity",
  "policy": "PDF file or text",
  "output_format": "pdf"
}
```

### Ask Compliance Question
```
POST /api/ask-compliance
Content-Type: application/json

{
  "sector": "fintech",
  "question": "Can we store customer biometric data?",
  "return_sources": true
}
```

### Process Voice Input
```
POST /api/process-voice
Content-Type: multipart/form-data

{
  "sector": "cybersecurity",
  "audio_file": <file>,
  "document_type": "pentest_report"
}
```

### Calculate Compliance Score
```
POST /api/compliance-score
Content-Type: application/json

{
  "sector": "fintech",
  "policy": "policy text",
  "breakdown_by": "section"
}
```

---

## Development

### Running Tests

```bash
# All tests
pytest

# Specific test file
pytest tests/test_agents.py -v

# With coverage
pytest --cov=agents --cov=tools
```

### Testing Sector Switching

```bash
python scripts/test_sector_switch.py
```

### Adding a New Sector

1. Create folder structure:
```bash
mkdir -p data/laws/healthcare/{raw,parsed,chunks}
mkdir -p skills/healthcare
```

2. Update `config/sector_config.json`

3. Add sector config:
```json
{
  "id": "healthcare",
  "name": "Healthcare",
  "laws": [...],
  "enabled": true
}
```

4. Ingest laws:
```bash
python scripts/ingest_laws.py --sector healthcare
```

---

## Agent Details

### Ingestor Agent
**Job**: PDF → Text extraction  
**Tools**: pdfplumber, PyMuPDF  
**Output**: Extracted text with page info

### Parser Agent
**Job**: Text → Hierarchical structure  
**Tools**: Regex patterns, NLP  
**Output**: Chunks with Act/Part/Section/Subsection metadata

### Embedder Agent
**Job**: Chunks → Vectors → ChromaDB  
**Tools**: sentence-transformers, chromadb  
**Output**: Indexed, searchable law database

### Retriever Agent
**Job**: Query → Relevant law sections  
**Tools**: ChromaDB search, confidence scoring  
**Output**: Top 5 laws with citations

### Analyzer Agent
**Job**: Policy vs Laws → Gaps  
**Tools**: LLM, keyword matching, validation  
**Output**: Gap findings with severity levels

### Writer Agent
**Job**: Content → Professional document  
**Tools**: LLM, ReportLab, skills templates  
**Output**: PDF/DOCX reports with citations

### Transcriber Agent
**Job**: Audio → Text  
**Tools**: OpenAI Whisper  
**Output**: Transcript with confidence

### Scorer Agent
**Job**: Policy → Compliance score  
**Tools**: Scoring rules, metrics  
**Output**: Percentage score + breakdown

---

## Key Features

✅ **Law-Backed Answers** - Every response cites actual Ghanaian law  
✅ **Sector-Organized** - Laws organized by industry  
✅ **Multi-Agent** - Each agent specializes in one job  
✅ **Professional Output** - PDF reports ready for auditors  
✅ **Confidence Scoring** - Know when to trust the answer  
✅ **Audit Trail** - Track all inputs and outputs  
✅ **Future-Ready** - Foundation for multi-sector support  

---

## Limitations (MVP)

- Single sector at a time (Phase 1)
- Limited to 3 Ghanaian law sectors initially
- Voice input in English only
- Requires manual law PDF upload
- No database persistence (Phase 2)

---

## Roadmap

**Phase 1 (MVP - July 1):**
- Single-sector support
- 3 law sectors (cybersecurity, fintech, data protection)
- Core agents functional
- Competition ready

**Phase 2 (Post-Competition):**
- Multi-sector support
- Database persistence
- Dashboard UI
- Law update monitoring
- Mobile app

**Phase 3 (Scale):**
- Additional sectors (healthcare, telecom, etc)
- Multi-country support
- Advanced analytics
- Team collaboration features

---

## Support & Contribution

### Questions?
Check `docs/` folder for detailed documentation.

### Found a bug?
Open an issue with:
- Steps to reproduce
- Expected vs actual result
- Agent logs

### Want to contribute?
See `CONTRIBUTING.md` for guidelines.

---

## Legal Notice

**GRaC is a compliance assistant, not legal advice.**

- Always verify GRaC answers with legal counsel for critical decisions
- GRaC cites laws but doesn't interpret them for your specific situation
- Users are responsible for compliance with all applicable laws
- See full disclaimer in documentation

---

## Team

Built by Kwame and team for the Ghana National AI Innovation Challenge 2026.

Powered by:
- CrewAI for multi-agent orchestration
- LangChain for RAG pipeline
- Anthropic Claude for reasoning
- ChromaDB for vector search
- OpenAI Whisper for voice

---

## License

MIT License - See LICENSE file

---

**Let's automate compliance. Let's win this competition.**

🚀 Start with: `python scripts/setup_environment.py`
