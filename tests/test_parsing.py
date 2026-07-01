"""Tests for parsing_tools: hierarchy parsing, chunk building, metadata extraction."""

import json
from pathlib import Path

import pytest

from tools.parsing_tools import (
    extract_metadata,
    parse_hierarchy,
    build_chunks,
    save_chunks,
)


SAMPLE_LAW_TEXT_FOR_PARSING = """
ACT 1038 — CYBERSECURITY ACT, 2020

PART I — PRELIMINARY

1. Establishment of the Cybersecurity Authority
(1) There is established by this Act a body corporate known as the Cybersecurity Authority.
(2) The Authority shall be responsible for the regulation of cybersecurity activities in Ghana.

2. Objects of the Authority
(1) The object of the Authority is to regulate cybersecurity activities.
(2) The Authority shall promote the development of cybersecurity in Ghana.

PART II — DATA PROTECTION

5. Data Protection Obligations
(1) A data controller shall implement appropriate technical and organisational measures.
(2) The measures shall ensure a level of security appropriate to the risk.

12. Breach Notification
(1) Where a data breach occurs, the data controller shall notify the Authority within 24 hours.
(2) The notification shall include the nature of the breach and the measures taken.

PART III — ENFORCEMENT

48. Offences and Penalties
(1) A person who contravenes this Act commits an offence.
(2) A person convicted under this Act is liable to a fine or imprisonment.
"""


class TestExtractMetadata:
    def test_extracts_law_number(self):
        meta = extract_metadata(SAMPLE_LAW_TEXT_FOR_PARSING)
        assert meta["law_number"] == "1038"

    def test_extracts_year(self):
        meta = extract_metadata(SAMPLE_LAW_TEXT_FOR_PARSING)
        assert meta["year"] == "2020"

    def test_extracts_title(self):
        meta = extract_metadata(SAMPLE_LAW_TEXT_FOR_PARSING)
        assert meta["title"] is not None
        assert "cybersecurity" in meta["title"].lower()

    def test_empty_text_returns_defaults(self):
        meta = extract_metadata("")
        assert meta["law_number"] is None

    def test_malformed_text_does_not_crash(self):
        meta = extract_metadata("Just some random words without law structure.")
        assert isinstance(meta, dict)


class TestParseHierarchy:
    def test_parses_parts(self):
        hierarchy = parse_hierarchy(SAMPLE_LAW_TEXT_FOR_PARSING, "Act 1038")
        assert hierarchy["law_name"] == "Act 1038"
        assert len(hierarchy["parts"]) >= 1

    def test_parses_section_numbers(self):
        hierarchy = parse_hierarchy(SAMPLE_LAW_TEXT_FOR_PARSING, "Act 1038")
        sections = []
        for part in hierarchy["parts"]:
            sections.extend(part.get("sections", []))
        numbers = [s["number"] for s in sections]
        assert "1" in numbers
        assert "5" in numbers
        assert "12" in numbers
        assert "48" in numbers

    def test_parses_section_titles(self):
        hierarchy = parse_hierarchy(SAMPLE_LAW_TEXT_FOR_PARSING, "Act 1038")
        sections = []
        for part in hierarchy["parts"]:
            sections.extend(part.get("sections", []))
        titles = [s["title"].lower() for s in sections]
        assert "breach notification" in titles
        assert "data protection obligations" in titles
        assert "establishment of the cybersecurity authority" in titles

    def test_empty_text_returns_minimal_hierarchy(self):
        hierarchy = parse_hierarchy("", "Test Act")
        assert hierarchy["law_name"] == "Test Act"
        assert hierarchy["parts"] == []

    def test_malformed_text_returns_flat_structure(self):
        hierarchy = parse_hierarchy("No structure here at all.", "Test Act")
        assert hierarchy["law_name"] == "Test Act"
        assert isinstance(hierarchy["parts"], list)

    def test_schedules_defaults_to_empty(self):
        hierarchy = parse_hierarchy(SAMPLE_LAW_TEXT_FOR_PARSING, "Act 1038")
        assert isinstance(hierarchy.get("schedules", []), list)


class TestBuildChunks:
    def test_builds_chunks_from_hierarchy(self):
        hierarchy = parse_hierarchy(SAMPLE_LAW_TEXT_FOR_PARSING, "Act 1038")
        chunks = build_chunks(hierarchy, chunk_size=500, overlap=100)
        assert len(chunks) > 0

    def test_chunks_have_required_keys(self):
        hierarchy = parse_hierarchy(SAMPLE_LAW_TEXT_FOR_PARSING, "Act 1038")
        chunks = build_chunks(hierarchy)
        for chunk in chunks:
            assert "text" in chunk
            assert "metadata" in chunk
            assert "id" in chunk
            meta = chunk["metadata"]
            assert "law_name" in meta
            assert "section_number" in meta

    def test_empty_hierarchy_yields_no_chunks(self):
        hierarchy = {"law_name": "Empty Act", "parts": [], "schedules": []}
        chunks = build_chunks(hierarchy)
        assert chunks == []

    def test_chunks_reference_correct_law(self):
        hierarchy = parse_hierarchy(SAMPLE_LAW_TEXT_FOR_PARSING, "Act 1038")
        chunks = build_chunks(hierarchy)
        for chunk in chunks:
            assert chunk["metadata"]["law_name"] == "Act 1038"

    def test_zero_chunk_size_raises(self):
        hierarchy = parse_hierarchy(SAMPLE_LAW_TEXT_FOR_PARSING, "Act 1038")
        with pytest.raises(ValueError):
            build_chunks(hierarchy, chunk_size=0, overlap=0)


class TestSaveChunks:
    def test_saves_chunks_to_json(self, temp_dir):
        hierarchy = parse_hierarchy(SAMPLE_LAW_TEXT_FOR_PARSING, "Act 1038")
        chunks = build_chunks(hierarchy)
        out_path = save_chunks(chunks, temp_dir)
        assert out_path.exists()
        with open(out_path, encoding="utf-8") as f:
            loaded = json.load(f)
        assert len(loaded) == len(chunks)

    def test_saved_chunks_are_identical(self, temp_dir):
        hierarchy = parse_hierarchy(SAMPLE_LAW_TEXT_FOR_PARSING, "Act 1038")
        chunks = build_chunks(hierarchy)
        out_path = save_chunks(chunks, temp_dir)
        with open(out_path, encoding="utf-8") as f:
            loaded = json.load(f)
        assert loaded == chunks

    def test_empty_chunks_saves_empty_json_file(self, temp_dir):
        out_path = save_chunks([], temp_dir)
        assert out_path.exists()
        assert out_path.name == "empty.json"
        with open(out_path, encoding="utf-8") as f:
            loaded = json.load(f)
        assert loaded == []

    def test_creates_parent_directory(self, temp_dir):
        nested = temp_dir / "sub" / "nested"
        out_path = save_chunks([], nested)
        assert out_path.parent.exists()


class TestIntegrationParsingPipeline:
    def test_full_pipeline(self):
        meta = extract_metadata(SAMPLE_LAW_TEXT_FOR_PARSING)
        hierarchy = parse_hierarchy(SAMPLE_LAW_TEXT_FOR_PARSING, "Act 1038")
        chunks = build_chunks(hierarchy)
        assert isinstance(meta, dict)
        assert hierarchy["law_name"] == "Act 1038"
        assert len(chunks) > 0
        section_numbers = set()
        for part in hierarchy["parts"]:
            for s in part.get("sections", []):
                section_numbers.add(s["number"])
        assert "1" in section_numbers
        assert "5" in section_numbers

    def test_pipeline_does_not_modify_input(self):
        original = SAMPLE_LAW_TEXT_FOR_PARSING[:]
        extract_metadata(SAMPLE_LAW_TEXT_FOR_PARSING)
        hierarchy = parse_hierarchy(SAMPLE_LAW_TEXT_FOR_PARSING, "Act 1038")
        build_chunks(hierarchy)
        assert SAMPLE_LAW_TEXT_FOR_PARSING == original
