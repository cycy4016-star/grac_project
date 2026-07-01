"""Shared fixtures and pytest configuration."""

from pathlib import Path
from unittest.mock import MagicMock, patch
import json

import pytest
import numpy as np


# ---------------------------------------------------------------------------
# Sample data constants
# ---------------------------------------------------------------------------

SAMPLE_LAW_TEXT = """
ACT 1038 — CYBERSECURITY ACT, 2020

Section 1 — Establishment of the Cybersecurity Authority
(1) There is established by this Act a body corporate known as the Cybersecurity Authority.
(2) The Authority shall be responsible for the regulation of cybersecurity activities in Ghana.

Section 5 — Data Protection Obligations
(1) A data controller shall implement appropriate technical and organisational measures.
(2) The measures shall ensure a level of security appropriate to the risk.

Section 12 — Breach Notification
(1) Where a data breach occurs, the data controller shall notify the Authority within 24 hours.
(2) The notification shall include the nature of the breach and the measures taken.

Section 48 — Offences and Penalties
(1) A person who contravenes this Act commits an offence.
(2) A person convicted under this Act is liable to a fine or imprisonment.
"""

SAMPLE_POLICY_TEXT = """
Our organisation is committed to protecting data. We have implemented firewalls
and access controls. Employees are required to use strong passwords.
We conduct annual security awareness training. Incident response procedures
are documented in our security handbook. We maintain backups of critical systems
and perform quarterly vulnerability scans. All third-party vendors must sign
non-disclosure agreements before accessing our systems.
"""


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def temp_dir(tmp_path: Path) -> Path:
    return tmp_path


@pytest.fixture
def sample_law_text() -> str:
    return SAMPLE_LAW_TEXT


@pytest.fixture
def sample_policy_text() -> str:
    return SAMPLE_POLICY_TEXT


@pytest.fixture
def sample_law_chunks() -> list[dict]:
    return [
        {
            "text": "Section 1: Establishment of the Cybersecurity Authority",
            "metadata": {
                "law_name": "Act 1038",
                "section_number": "1",
                "part_number": "I",
            },
        },
        {
            "text": "Section 5: Data protection obligations for data controllers",
            "metadata": {
                "law_name": "Act 1038",
                "section_number": "5",
                "part_number": "II",
            },
        },
    ]


@pytest.fixture
def sample_gaps() -> list[dict]:
    return [
        {
            "requirement": "Implement data encryption at rest",
            "law_reference": "Act 1038, s.5(1)",
            "policy_status": "missing",
            "severity": "high",
            "recommendation": "Implement AES-256 encryption for all stored data",
        },
        {
            "requirement": "Establish breach notification procedure",
            "law_reference": "Act 1038, s.12(1)",
            "policy_status": "inadequate",
            "severity": "critical",
            "recommendation": "Create 24-hour breach notification process",
        },
    ]


@pytest.fixture
def mock_chroma_collection():
    mock = MagicMock()
    mock.count.return_value = 5
    mock.name = "grac_cybersecurity"

    def fake_query(**kwargs):
        n_results = kwargs.get("n_results", 5)
        chunks = [
            ("chunk_1", 0.15, {"law_name": "Act 1038", "section_number": "5", "text": "Data protection obligations"},
             "Data controller shall implement appropriate technical measures."),
            ("chunk_2", 0.35, {"law_name": "Act 1038", "section_number": "12", "text": "Breach notification"},
             "Data controller shall notify Authority within 24 hours."),
        ][:n_results]
        return {
            "ids": [[c[0] for c in chunks]],
            "distances": [[c[1] for c in chunks]],
            "metadatas": [[c[2] for c in chunks]],
            "documents": [[c[3] for c in chunks]],
        }

    mock.query = fake_query
    return mock


@pytest.fixture
def mock_chroma_client(mock_chroma_collection):
    client = MagicMock()
    client.get_or_create_collection.return_value = mock_chroma_collection

    class FakeCollection:
        name = "grac_cybersecurity"

    client.list_collections.return_value = [FakeCollection()]
    return client


@pytest.fixture
def mock_embedding_model():
    model = MagicMock()
    model.encode.return_value = np.array([[0.1] * 384])
    model.get_sentence_embedding_dimension.return_value = 384
    return model


@pytest.fixture
def sample_analysis_record() -> dict:
    return {
        "id": 1,
        "sector": "cybersecurity",
        "policy_text": SAMPLE_POLICY_TEXT,
        "policy_summary": "Test summary",
        "compliant_areas": ["Access control"],
        "total_laws_checked": 5,
        "status": "completed",
        "created_at": None,
    }


@pytest.fixture(autouse=True)
def auto_patch_external_services():
    patches = [
        patch("tools.llm_tools.call_claude", return_value='{"result": "mocked"}'),
        patch("tools.llm_tools.call_llm", return_value='{"result": "mocked"}'),
        patch("tools.audio_tools.transcribe_audio", return_value={"transcript": "mocked", "language": "en", "duration_seconds": 10.0}),
        patch("tools.audio_tools.transcribe_audio_data", return_value={"transcript": "mocked", "language": "en", "duration_seconds": 10.0}),
    ]
    for p in patches:
        p.start()
    yield
    for p in patches:
        p.stop()
