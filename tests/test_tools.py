"""Tests for all tool modules: pdf, scoring, audio, document, llm, embedding."""

from pathlib import Path
from unittest.mock import MagicMock, patch, mock_open

import pytest

from tools.scoring_tools import (
    calculate_score,
    build_score_record,
    save_score_record,
    load_score_history,
    build_trend,
    _percentage_to_grade,
)
from tools.audio_tools import (
    validate_audio_file,
    clean_transcript,
    estimate_confidence,
)
from tools.llm_tools import (
    build_gap_analysis_prompt,
    build_compliance_qa_prompt,
    build_document_prompt,
    parse_json_response,
)
from tools.document_tools import generate_pdf, generate_docx
from tools.pdf_tools import save_extracted_text, list_pdfs_in_directory


# ======================================================================
# Scoring Tools
# ======================================================================

class TestPercentageToGrade:
    def test_a_grade(self):
        assert _percentage_to_grade(95) == "A"
        assert _percentage_to_grade(90) == "A"
        assert _percentage_to_grade(100) == "A"

    def test_b_grade(self):
        assert _percentage_to_grade(89) == "B"
        assert _percentage_to_grade(75) == "B"

    def test_c_grade(self):
        assert _percentage_to_grade(74) == "C"
        assert _percentage_to_grade(60) == "C"

    def test_d_grade(self):
        assert _percentage_to_grade(59) == "D"
        assert _percentage_to_grade(45) == "D"

    def test_f_grade(self):
        assert _percentage_to_grade(44) == "F"
        assert _percentage_to_grade(0) == "F"
        assert _percentage_to_grade(-5) == "F"

    def test_boundary_values(self):
        assert _percentage_to_grade(90) == "A"
        assert _percentage_to_grade(89) == "B"
        assert _percentage_to_grade(75) == "B"
        assert _percentage_to_grade(74) == "C"
        assert _percentage_to_grade(60) == "C"
        assert _percentage_to_grade(59) == "D"
        assert _percentage_to_grade(45) == "D"
        assert _percentage_to_grade(44) == "F"


class TestCalculateScore:
    def test_perfect_compliance(self):
        result = calculate_score([], total_requirements=10)
        assert result["overall_score"] == 1.0
        assert result["percentage"] == 100
        assert result["grade"] == "A"
        assert result["penalty_points"] == 0.0

    def test_single_critical_gap(self):
        gaps = [{"severity": "critical", "requirement": "Encryption"}]
        result = calculate_score(gaps, total_requirements=10)
        assert result["percentage"] < 100
        assert result["penalty_points"] > 0
        assert result["breakdown"]["critical"]["count"] == 1

    def test_mixed_severity_gaps(self, sample_gaps):
        result = calculate_score(sample_gaps, total_requirements=10)
        assert result["breakdown"]["critical"]["count"] == 1
        assert result["breakdown"]["high"]["count"] == 1
        assert result["breakdown"]["medium"]["count"] == 0
        assert result["breakdown"]["low"]["count"] == 0

    def test_score_floored_at_zero(self):
        many_gaps = [{"severity": "critical"} for _ in range(200)]
        result = calculate_score(many_gaps, total_requirements=5)
        assert result["percentage"] == 0
        assert result["overall_score"] == 0.0
        assert result["grade"] == "F"

    def test_unknown_severity_falls_back_to_medium(self):
        gaps = [{"severity": "unknown_level"}]
        result = calculate_score(gaps, total_requirements=10)
        assert result["breakdown"]["medium"]["count"] == 1

    def test_zero_requirements_falls_back(self):
        result = calculate_score([{"severity": "high"}], total_requirements=0)
        assert result["percentage"] < 100

    def test_empty_gaps_list(self):
        result = calculate_score([], total_requirements=0)
        assert result["percentage"] == 100
        assert result["grade"] == "A"


class TestBuildScoreRecord:
    def test_includes_timestamp(self):
        result = calculate_score([], 10)
        record = build_score_record(result, "cybersecurity", "Test Policy")
        assert "timestamp" in record
        assert record["sector"] == "cybersecurity"
        assert record["policy_name"] == "Test Policy"

    def test_includes_all_score_fields(self):
        result = calculate_score([{"severity": "high"}], 10)
        record = build_score_record(result, "fintech")
        assert "overall_score" in record
        assert "percentage" in record
        assert "grade" in record
        assert "breakdown" in record


class TestSaveAndLoadScoreHistory:
    def test_round_trip(self, temp_dir):
        history_path = temp_dir / "scores.jsonl"
        result = calculate_score([], 10)
        record = build_score_record(result, "cybersecurity")
        save_score_record(record, history_path)
        loaded = load_score_history(history_path, "cybersecurity")
        assert len(loaded) == 1
        assert loaded[0]["sector"] == "cybersecurity"

    def test_filters_by_sector(self, temp_dir):
        path = temp_dir / "scores.jsonl"
        for sector in ["cybersecurity", "fintech"]:
            r = build_score_record(calculate_score([], 5), sector)
            save_score_record(r, path)
        cyb = load_score_history(path, "cybersecurity")
        fin = load_score_history(path, "fintech")
        assert len(cyb) == 1
        assert len(fin) == 1

    def test_missing_file_returns_empty(self, temp_dir):
        loaded = load_score_history(temp_dir / "nonexistent.jsonl", "cybersecurity")
        assert loaded == []

    def test_corrupted_line_skipped(self, temp_dir):
        path = temp_dir / "scores.jsonl"
        r = build_score_record(calculate_score([], 5), "cybersecurity")
        save_score_record(r, path)
        with open(path, "a") as f:
            f.write("not json\n")
        r2 = build_score_record(calculate_score([], 5), "cybersecurity")
        save_score_record(r2, path)
        loaded = load_score_history(path, "cybersecurity")
        assert len(loaded) == 2


class TestBuildTrend:
    def test_builds_trend_list(self):
        history = [
            {"timestamp": "2025-01-15T10:00:00", "percentage": 72, "grade": "C"},
            {"timestamp": "2025-02-15T10:00:00", "percentage": 85, "grade": "B"},
        ]
        trend = build_trend(history)
        assert len(trend) == 2
        assert trend[0]["date"] == "2025-01-15"
        assert trend[1]["percentage"] == 85

    def test_empty_history(self):
        assert build_trend([]) == []

    def test_preserves_input_order(self):
        history = [
            {"timestamp": "2025-03-01T00:00:00", "percentage": 91, "grade": "A"},
            {"timestamp": "2025-01-01T00:00:00", "percentage": 60, "grade": "D"},
        ]
        trend = build_trend(history)
        assert trend[0]["date"] == "2025-03-01"


# ======================================================================
# Audio Tools
# ======================================================================

class TestValidateAudioFile:
    def test_valid_mp3(self, temp_dir):
        f = temp_dir / "audio.mp3"
        f.write_text("dummy")
        assert validate_audio_file(f) is True

    def test_valid_wav(self, temp_dir):
        f = temp_dir / "audio.wav"
        f.write_text("dummy")
        assert validate_audio_file(f) is True

    def test_invalid_extension(self, temp_dir):
        f = temp_dir / "audio.txt"
        f.write_text("dummy")
        assert validate_audio_file(f) is False

    def test_nonexistent_file(self):
        assert validate_audio_file("C:/nonexistent/file.mp3") is False


class TestCleanTranscript:
    def test_collapses_whitespace(self):
        result = clean_transcript("Hello    world\n\n\nTest")
        assert result == "Hello world Test"

    def test_handles_empty_string(self):
        assert clean_transcript("") == ""

    def test_handles_leading_trailing_spaces(self):
        result = clean_transcript("  Hello world  ")
        assert result == "Hello world"


class TestEstimateConfidence:
    def test_high_confidence(self):
        # ratio 0.5-1.5 -> 0.9 (130 wpm expected, 65-195 words for 60s)
        transcript = " ".join(["word"] * 130)
        conf = estimate_confidence(transcript, duration_seconds=60.0)
        assert conf == 0.9

    def test_medium_confidence(self):
        # ratio 0.3-0.5 or 1.5-2.0 -> 0.7 (39-130 or 195-260 words for 60s)
        transcript = " ".join(["word"] * 40)
        conf = estimate_confidence(transcript, duration_seconds=60.0)
        assert conf == 0.7

    def test_low_confidence(self):
        # ratio < 0.3 or > 2.0 -> 0.5
        transcript = "word"
        conf = estimate_confidence(transcript, duration_seconds=60.0)
        assert conf == 0.5

    def test_no_duration_returns_default(self):
        transcript = "Hello world"
        conf = estimate_confidence(transcript, duration_seconds=None)
        assert conf == 0.5

    def test_zero_duration_handled(self):
        transcript = "Hello world"
        conf = estimate_confidence(transcript, duration_seconds=0)
        assert conf == 0.5


# ======================================================================
# LLM Tools
# ======================================================================

class TestBuildGapAnalysisPrompt:
    def test_includes_policy_and_laws(self, sample_policy_text, sample_law_chunks):
        prompt = build_gap_analysis_prompt(sample_policy_text, sample_law_chunks)
        assert "GAP ANALYSIS" in prompt.upper() or "gap" in prompt.lower()
        assert sample_policy_text[:20] in prompt

    def test_empty_law_chunks(self, sample_policy_text):
        prompt = build_gap_analysis_prompt(sample_policy_text, [])
        assert prompt is not None
        assert len(prompt) > 0

    def test_empty_policy(self):
        prompt = build_gap_analysis_prompt("", [])
        assert prompt is not None


class TestBuildComplianceQAPrompt:
    def test_includes_question_and_laws(self, sample_law_chunks):
        prompt = build_compliance_qa_prompt("What are data protection obligations?", sample_law_chunks)
        assert "COMPLIANCE" in prompt.upper() or "question" in prompt.lower()
        assert "data protection" in prompt.lower()

    def test_empty_chunks(self):
        prompt = build_compliance_qa_prompt("What does Act 1038 say?", [])
        assert prompt is not None


class TestBuildDocumentPrompt:
    def test_gap_analysis_type(self):
        prompt = build_document_prompt("gap_analysis", {"gaps": [], "summary": ""}, "cybersecurity")
        assert prompt is not None
        assert len(prompt) > 0

    def test_incident_report_type(self):
        prompt = build_document_prompt("incident_report", {"details": "test"}, "cybersecurity")
        assert prompt is not None

    def test_policy_draft_type(self):
        prompt = build_document_prompt("policy_draft", {"title": "Test"}, "cybersecurity")
        assert prompt is not None


class TestParseJsonResponse:
    def test_parses_plain_json(self):
        result = parse_json_response('{"key": "value"}')
        assert result == {"key": "value"}

    def test_strips_markdown_fences(self):
        result = parse_json_response('```json\n{"key": "value"}\n```')
        assert result == {"key": "value"}

    def test_strips_markdown_with_language(self):
        result = parse_json_response('```json\n{"nested": {"a": 1}}\n```')
        assert result == {"nested": {"a": 1}}

    def test_returns_error_dict_on_invalid(self):
        result = parse_json_response("not json at all")
        assert "error" in result
        assert "raw" in result

    def test_handles_empty_string(self):
        result = parse_json_response("")
        assert "error" in result

    def test_handles_nested_objects(self):
        result = parse_json_response('{"data": [1, 2, 3], "meta": {"count": 3}}')
        assert result["data"] == [1, 2, 3]
        assert result["meta"]["count"] == 3


# ======================================================================
# PDF Tools
# ======================================================================

class TestSaveExtractedText:
    def test_saves_text_to_file(self, temp_dir):
        path = save_extracted_text("Hello world", "test_source", temp_dir)
        assert path.exists()
        assert path.read_text(encoding="utf-8") == "Hello world"

    def test_creates_parent_directory(self, temp_dir):
        nested = temp_dir / "sub" / "output"
        path = save_extracted_text("content", "test", nested)
        assert path.parent.exists()

    def test_filename_based_on_source(self, temp_dir):
        path = save_extracted_text("content", "my_source", temp_dir)
        assert "my_source" in path.name


class TestListPdfsInDirectory:
    def test_returns_pdf_files(self, temp_dir):
        (temp_dir / "doc1.pdf").write_text("a")
        (temp_dir / "doc2.pdf").write_text("b")
        (temp_dir / "readme.txt").write_text("c")
        pdfs = list_pdfs_in_directory(temp_dir)
        assert len(pdfs) == 2
        assert all(p.suffix == ".pdf" for p in pdfs)

    def test_empty_directory(self, temp_dir):
        assert list_pdfs_in_directory(temp_dir) == []

    def test_nonexistent_directory(self, temp_dir):
        pdfs = list_pdfs_in_directory(temp_dir / "nonexistent")
        assert pdfs == []

    def test_sorts_alphabetically(self, temp_dir):
        (temp_dir / "b.pdf").write_text("b")
        (temp_dir / "a.pdf").write_text("a")
        (temp_dir / "c.pdf").write_text("c")
        pdfs = list_pdfs_in_directory(temp_dir)
        assert [p.name for p in pdfs] == ["a.pdf", "b.pdf", "c.pdf"]


# ======================================================================
# Document Tools (smoke tests — require reportlab/python-docx)
# ======================================================================

class TestGeneratePdf:
    def test_generates_pdf_file(self, temp_dir):
        out = temp_dir / "report.pdf"
        try:
            result = generate_pdf("Test content", "Test Report", out, sector="cybersecurity")
            assert result.exists()
            assert result.suffix == ".pdf"
            assert result.stat().st_size > 0
        except ImportError:
            pytest.skip("reportlab not installed")

    def test_generates_pdf_with_metadata(self, temp_dir):
        out = temp_dir / "report.pdf"
        try:
            result = generate_pdf("Content", "Report", out, metadata={"author": "tester"})
            assert result.exists()
        except ImportError:
            pytest.skip("reportlab not installed")


class TestGenerateDocx:
    def test_generates_docx_file(self, temp_dir):
        out = temp_dir / "report.docx"
        try:
            result = generate_docx("Test content", "Test Report", out, sector="cybersecurity")
            assert result.exists()
            assert result.suffix == ".docx"
            assert result.stat().st_size > 0
        except ImportError:
            pytest.skip("python-docx not installed")

    def test_generates_docx_with_empty_content(self, temp_dir):
        out = temp_dir / "empty.docx"
        try:
            result = generate_docx("", "Empty", out)
            assert result.exists()
        except ImportError:
            pytest.skip("python-docx not installed")
