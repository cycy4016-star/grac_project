# API Reference

Base URL: `http://localhost:8000/api`

All endpoints return JSON. Errors return 422 (validation) or 500 (server error).

---

## Health Check

```
GET /api/health
```

**Response** `200`:

```json
{
  "status": "ok",
  "service": "GRaC API",
  "version": "1.0.0",
  "active_sector": "cybersecurity"
}
```

---

## Analyze Policy

```
POST /api/analyze-policy
```

Analyze a policy document for compliance gaps against sector laws.

### Request Body

```json
{
  "sector": "cybersecurity",
  "policy": "Full policy text describing security measures, access controls, data handling procedures, incident response plans, and third-party risk management...",
  "output_format": "pdf"
}
```

| Field | Type | Required | Default | Constraints |
|-------|------|----------|---------|-------------|
| `sector` | string | No | active sector | Valid sector ID |
| `policy` | string | Yes | — | min 50 characters |
| `output_format` | string | No | "pdf" | "pdf" or "docx" |

### Response `200`

```json
{
  "status": "success",
  "timestamp": "2026-06-15T10:30:00+00:00",
  "sector": "cybersecurity",
  "data": {
    "workflow": "pdf_analysis",
    "steps": {
      "retrieval": {"status": "success", "results": [...], "count": 5},
      "analysis": {"status": "success", "gaps": [...], "summary": "..."},
      "document": {"status": "success", "format": "pdf"},
      "score": {"status": "success", "grade": "C", "percentage": 65}
    }
  }
}
```

### Error `422`

```json
{
  "status": "error",
  "error": {"field": "policy", "message": "Policy text must be at least 50 characters"}
}
```

---

## Ask Compliance Question

```
POST /api/ask-compliance
```

Ask a compliance question and get an answer with law citations.

### Request Body

```json
{
  "sector": "cybersecurity",
  "question": "What are the data protection obligations for data controllers under Act 1038?",
  "top_k": 5,
  "return_sources": true
}
```

| Field | Type | Required | Default | Constraints |
|-------|------|----------|---------|-------------|
| `sector` | string | No | active sector | Valid sector ID |
| `question` | string | Yes | — | 5-4000 characters |
| `top_k` | integer | No | 5 | 1-20 |
| `return_sources` | boolean | No | true | — |

### Response `200`

```json
{
  "status": "success",
  "timestamp": "2026-06-15T10:30:00+00:00",
  "sector": "cybersecurity",
  "data": {
    "workflow": "compliance_question",
    "answer": "Under Act 1038, Section 5, data controllers must implement appropriate technical and organisational measures to ensure a level of security appropriate to the risk...",
    "sources": [
      {
        "law_name": "Act 1038",
        "section_number": "5",
        "section_title": "Data Protection Obligations",
        "text": "A data controller shall implement appropriate technical and organisational measures...",
        "score": 0.92
      }
    ],
    "confidence": 0.92
  }
}
```

---

## Process Voice Input

```
POST /api/process-voice
```

Transcribe audio and generate a compliance document.

### Request (multipart/form-data)

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `audio_file` | file | Yes | — | Audio file (mp3, wav, m4a, ogg, flac) |
| `sector` | string | No | active sector | Valid sector ID |
| `document_type` | string | No | "incident_report" | "incident_report", "gap_analysis", "policy_draft" |
| `language` | string | No | "en" | Language code |

### Response `200`

```json
{
  "status": "success",
  "timestamp": "2026-06-15T10:30:00+00:00",
  "sector": "cybersecurity",
  "data": {
    "workflow": "voice_input",
    "transcript": {"transcript": "During our security audit we found...", "confidence": 0.95},
    "analysis": {"gaps": [...], "summary": "..."},
    "document": {"format": "pdf", "path": "/output/report.pdf"}
  }
}
```

---

## Calculate Compliance Score

```
POST /api/compliance-score
```

Calculate a weighted compliance score for a policy document.

### Request Body

```json
{
  "sector": "cybersecurity",
  "policy": "Full policy text describing security controls, data protection measures, incident response procedures, access management, and vendor risk management...",
  "total_requirements": 10
}
```

| Field | Type | Required | Default | Constraints |
|-------|------|----------|---------|-------------|
| `sector` | string | No | active sector | Valid sector ID |
| `policy` | string | Yes | — | min 50 characters |
| `total_requirements` | integer | No | auto | Number of compliance requirements checked |

### Response `200`

```json
{
  "status": "success",
  "timestamp": "2026-06-15T10:30:00+00:00",
  "sector": "cybersecurity",
  "data": {
    "workflow": "scoring",
    "overall_score": 0.65,
    "percentage": 65,
    "grade": "D",
    "breakdown": {
      "critical": {"count": 1, "penalty": 10.0},
      "high": {"count": 2, "penalty": 12.0},
      "medium": {"count": 1, "penalty": 3.0},
      "low": {"count": 0, "penalty": 0.0}
    },
    "trend": [
      {"date": "2026-06-01", "percentage": 55, "grade": "D"},
      {"date": "2026-06-15", "percentage": 65, "grade": "D"}
    ],
    "policy_name": "security_policy_2026"
  }
}
```

### Grade Scale

| Range | Grade |
|-------|-------|
| 90-100 | A |
| 75-89 | B |
| 60-74 | C |
| 45-59 | D |
| 0-44 | F |

### Score Calculation

Score starts at 100%. Each gap deducts based on severity weight and total requirements:

```
penalty = (severity_weight / total_requirements) * 100
```

| Severity | Weight |
|----------|--------|
| critical | 1.0 |
| high | 0.6 |
| medium | 0.3 |
| low | 0.1 |

---

## Error Responses

### Validation Error `422`

```json
{
  "status": "error",
  "error": {
    "field": "question",
    "message": "Question must be between 5 and 4000 characters"
  }
}
```

### Server Error `500`

```json
{
  "status": "error",
  "error": {
    "field": null,
    "message": "Analysis failed: No relevant legal sources found"
  }
}
```

---

## Data Models

### ApiResponse (all successful responses)

| Field | Type | Description |
|-------|------|-------------|
| `status` | string | Always "success" |
| `timestamp` | string | ISO 8601 UTC |
| `sector` | string | Active sector |
| `data` | object | Endpoint-specific payload |

### ApiError (all error responses)

| Field | Type | Description |
|-------|------|-------------|
| `status` | string | Always "error" |
| `error` | object | `{field: string?, message: string}` |
