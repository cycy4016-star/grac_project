# Agents Reference

All agents extend `BaseAgent(ABC)` which defines three abstract methods:

- `validate_input(input_data) -> bool`
- `execute(input_data, **kwargs) -> dict`
- `format_output(result) -> dict`

The base class provides logging, sector verification, checkpoint saving, and error wrapping via `run()`.

---

## BaseAgent

**File**: `agents/base_agent.py`

| Property | Type | Description |
|----------|------|-------------|
| `name` | str | Agent identifier |
| `sector` | str | Active sector |
| `logger` | Logger | Structured JSON logger |

**Key methods**:

| Method | Description |
|--------|-------------|
| `run(input_data)` | Validate → execute → format + log |
| `switch_sector(new_sector)` | Change sector (validates first) |
| `get_sector_path(subfolder)` | Path to sector's subdirectory |
| `_save_checkpoint(name, data)` | Write JSON checkpoint |

---

## SupervisorAgent

**File**: `agents/supervisor.py`  
**Purpose**: Orchestrates all other agents into workflows.

**Input**: `{"request_type": str, "data": any, "sector": str?, "options": dict?}`

**Workflows**:

### pdf_analysis

```
data: policy_text (str)
options: {output_format: "pdf"|"docx"}

1. RetrieverAgent — query law chunks
2. AnalyzerAgent — compare policy vs laws
3. WriterAgent — generate report document
4. ScorerAgent — calculate compliance score
```

### voice_input

```
data: {audio_path: str} or {audio_data: bytes}
options: {document_type: str, language: str}

1. TranscriberAgent — transcribe audio
2. RetrieverAgent — query law chunks
3. AnalyzerAgent — analyze transcript
4. WriterAgent — generate document
```

### compliance_question

```
data: question (str)
options: {top_k: int, return_sources: bool}

1. RetrieverAgent — find relevant laws
2. LLM (Claude) — generate answer with citations
```

### scoring

```
data: policy_text (str)
options: (none)

1. RetrieverAgent — query law chunks
2. AnalyzerAgent — analyze for gaps
3. ScorerAgent — calculate score
```

---

## IngestorAgent

**File**: `agents/ingestor.py`  
**Purpose**: Extract text from law PDFs.

| Aspect | Details |
|--------|---------|
| **Input** | `{"pdf_path": str}` |
| **Output** | `{text, source, pages, method, is_scanned}` |
| **Tools** | `pdf_tools.extract_text_from_pdf()`, `save_extracted_text()` |

**Notes**: Falls back from pdfplumber to PyMuPDF. Saves extracted text to `data/laws/{sector}/parsed/`.

---

## ParserAgent

**File**: `agents/parser.py`  
**Purpose**: Parse legal text into hierarchical chunks.

| Aspect | Details |
|--------|---------|
| **Input** | `{"text": str, "law_name": str}` |
| **Output** | `{chunks, hierarchy, metadata, chunk_count}` |
| **Tools** | `parsing_tools.extract_metadata()`, `parse_hierarchy()`, `build_chunks()` |

**Notes**: Regex-based parsing for Ghanaian legal format (PART, Section, Subsection). Configurable chunk size and overlap.

---

## EmbedderAgent

**File**: `agents/embedder.py`  
**Purpose**: Embed chunks and store in ChromaDB.

| Aspect | Details |
|--------|---------|
| **Input** | `{"chunks": list[dict]}` |
| **Output** | `{collection_id, chunks_stored, collection_total}` |
| **Tools** | `embedding_tools.get_chroma_client()`, `embed_chunks()` |

**Notes**: Lazy-loads SentenceTransformer model on first execute. Collection name: `grac_{sector}`.

---

## RetrieverAgent

**File**: `agents/retriever.py`  
**Purpose**: Retrieve relevant law chunks for a query.

| Aspect | Details |
|--------|---------|
| **Input** | `{"query": str, "top_k": int?, "min_score": float?}` |
| **Output** | `{results, confidence_scores, query}` |
| **Tools** | `embedding_tools.query_collection()`, `load_embedding_model()` |

**Notes**: Filters results by `min_score` (default 0.6). ChromaDB connection failures return empty results gracefully.

---

## AnalyzerAgent

**File**: `agents/analyzer.py`  
**Purpose**: Compare policy text against law chunks to find compliance gaps.

| Aspect | Details |
|--------|---------|
| **Input** | `{"policy": str, "laws": list[dict]}` |
| **Output** | `{gaps, findings, severity, summary, compliant_areas, total_laws_checked}` |
| **Tools** | `llm_tools.build_gap_analysis_prompt()`, `call_claude()`, `parse_json_response()` |

**Notes**: Empty law chunks return a no-op result (not an error). Requires `ANTHROPIC_API_KEY`.

---

## WriterAgent

**File**: `agents/writer.py`  
**Purpose**: Generate professional PDF/DOCX reports.

| Aspect | Details |
|--------|---------|
| **Input** | `{"type": str, "content": dict, "format": str}` |
| **Output** | `{document, format, path, title}` |
| **Tools** | `llm_tools.build_document_prompt()`, `call_claude()`, `document_tools.generate_pdf/docx` |

**Supported types**: `gap_analysis`, `incident_report`, `policy_draft`

---

## TranscriberAgent

**File**: `agents/transcriber.py`  
**Purpose**: Transcribe audio to text using OpenAI Whisper API.

| Aspect | Details |
|--------|---------|
| **Input** | `{"audio_path": str}` or `{"audio_data": bytes}` |
| **Output** | `{transcript, confidence, language, duration_seconds}` |
| **Tools** | `audio_tools.transcribe_audio()/transcribe_audio_data()`, `estimate_confidence()` |

**Notes**: Confidence is estimated heuristically from words-per-minute ratio. Requires `OPENAI_API_KEY`.

---

## ScorerAgent

**File**: `agents/scorer.py`  
**Purpose**: Calculate weighted compliance score from gap analysis.

| Aspect | Details |
|--------|---------|
| **Input** | `{"policy": str}` or `{"gaps": list[dict]}` |
| **Output** | `{overall_score, percentage, grade, breakdown, trend, policy_name}` |
| **Tools** | `scoring_tools.calculate_score()`, `build_score_record()`, `build_trend()` |

**Severity weights**: critical=1.0, high=0.6, medium=0.3, low=0.1  
**Grade scale**: A(90+), B(75-89), C(60-74), D(45-59), F(<45)
