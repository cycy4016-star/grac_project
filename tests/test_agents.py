"""Tests for all agent classes: BaseAgent, IngestorAgent, ParserAgent,
EmbedderAgent, RetrieverAgent, AnalyzerAgent, WriterAgent,
TranscriberAgent, ScorerAgent, SupervisorAgent."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from agents.base_agent import BaseAgent, MultiSectorAgent
from agents.supervisor import SupervisorAgent


# ======================================================================
# BaseAgent tests (abstract interface)
# ======================================================================

class TestBaseAgent:
    def test_cannot_instantiate_directly(self):
        with pytest.raises(TypeError):
            BaseAgent("test")


# ======================================================================
# SupervisorAgent
# ======================================================================

class TestSupervisorAgent:
    def setup_method(self):
        self.supervisor = SupervisorAgent(sector="cybersecurity")

    def test_initializes_with_registered_agents(self):
        assert "retriever" in self.supervisor.agent_registry
        assert "analyzer" in self.supervisor.agent_registry
        assert "writer" in self.supervisor.agent_registry
        assert "scorer" in self.supervisor.agent_registry
        assert "transcriber" in self.supervisor.agent_registry

    def test_validate_input_valid(self):
        assert self.supervisor.validate_input({"request_type": "pdf_analysis", "data": {}}) is True
        assert self.supervisor.validate_input({"request_type": "voice_input", "data": {}}) is True

    def test_validate_input_rejects_non_dict(self):
        assert self.supervisor.validate_input(None) is False
        assert self.supervisor.validate_input("string") is False
        assert self.supervisor.validate_input(123) is False

    def test_validate_input_rejects_missing_keys(self):
        assert self.supervisor.validate_input({}) is False
        assert self.supervisor.validate_input({"request_type": "pdf_analysis"}) is False
        assert self.supervisor.validate_input({"data": {}}) is False

    def test_register_custom_agent(self):
        mock_agent = MagicMock(spec=BaseAgent)
        self.supervisor.register_agent("custom", mock_agent)
        assert "custom" in self.supervisor.agent_registry

    def test_call_agent_forwards_input(self):
        mock_agent = MagicMock(spec=BaseAgent)
        mock_agent.run.return_value = {"status": "ok"}
        self.supervisor.register_agent("mock", mock_agent)
        result = self.supervisor.call_agent("mock", {"test": True})
        assert result["status"] == "ok"
        mock_agent.run.assert_called_once_with({"test": True})

    def test_format_output_has_expected_keys(self):
        result = self.supervisor.format_output({"key": "value"})
        assert "status" in result
        assert "timestamp" in result
        assert "agent" in result
        assert "sector" in result
        assert "result" in result

    @patch("agents.supervisor.SupervisorAgent._workflow_pdf_analysis")
    def test_routes_pdf_analysis(self, mock_wf):
        mock_wf.return_value = {"mocked": True}
        result = self.supervisor.execute({"request_type": "pdf_analysis", "data": {"policy": "test"}})
        mock_wf.assert_called_once()
        assert result == {"mocked": True}

    @patch("agents.supervisor.SupervisorAgent._workflow_voice_input")
    def test_routes_voice_input(self, mock_wf):
        mock_wf.return_value = {"mocked": True}
        result = self.supervisor.execute({"request_type": "voice_input", "data": {}})
        mock_wf.assert_called_once()

    @patch("agents.supervisor.SupervisorAgent._workflow_compliance_question")
    def test_routes_compliance_question(self, mock_wf):
        mock_wf.return_value = {"mocked": True}
        result = self.supervisor.execute({"request_type": "compliance_question", "data": {}})
        mock_wf.assert_called_once()

    @patch("agents.supervisor.SupervisorAgent._workflow_scoring")
    def test_routes_scoring(self, mock_wf):
        mock_wf.return_value = {"mocked": True}
        result = self.supervisor.execute({"request_type": "scoring", "data": {}})
        mock_wf.assert_called_once()

    def test_unknown_request_type_raises(self):
        with pytest.raises(ValueError, match="Unknown request type"):
            self.supervisor.execute({"request_type": "unknown", "data": {}})


# ======================================================================
# IngestorAgent
# ======================================================================

class TestIngestorAgent:
    def setup_method(self):
        from agents.ingestor import IngestorAgent
        self.agent = IngestorAgent(sector="cybersecurity")

    def test_validate_input_valid(self):
        assert self.agent.validate_input({"pdf_path": "test.pdf"}) is True

    def test_validate_input_rejects_non_dict(self):
        assert self.agent.validate_input("string") is False
        assert self.agent.validate_input(None) is False

    def test_validate_input_missing_path(self):
        assert self.agent.validate_input({}) is False
        assert self.agent.validate_input({"text": "hello"}) is False

    def test_validate_input_wrong_key(self):
        assert self.agent.validate_input({"path": "test.pdf"}) is False

    def test_format_output_has_expected_keys(self):
        result = {
            "text": "test",
            "source": "act_1038",
            "pages": 5,
            "method": "pdfplumber",
            "is_scanned": False,
        }
        output = self.agent.format_output(result)
        assert output["status"] == "success"
        assert output["extracted_text"] == "test"
        assert output["source"] == "act_1038"
        assert output["sector"] == "cybersecurity"


# ======================================================================
# ParserAgent
# ======================================================================

class TestParserAgent:
    def setup_method(self):
        from agents.parser import ParserAgent
        self.agent = ParserAgent(sector="cybersecurity")

    def test_validate_input_valid(self):
        assert self.agent.validate_input({"text": "Section 1 — Title", "law_name": "Act 1038"}) is True

    def test_validate_input_missing_keys(self):
        assert self.agent.validate_input({"text": "content"}) is False
        assert self.agent.validate_input({"law_name": "Act"}) is False
        assert self.agent.validate_input({}) is False

    def test_validate_input_rejects_non_dict(self):
        assert self.agent.validate_input("text") is False
        assert self.agent.validate_input(None) is False

    @patch("tools.parsing_tools.extract_metadata")
    @patch("tools.parsing_tools.parse_hierarchy")
    @patch("tools.parsing_tools.build_chunks")
    @patch("tools.parsing_tools.save_chunks")
    def test_execute_calls_tools(self, mock_save, mock_chunks, mock_hierarchy, mock_meta):
        mock_meta.return_value = {"law_number": "1038"}
        mock_hierarchy.return_value = {"law_name": "Act 1038", "parts": []}
        mock_chunks.return_value = [{"chunk_id": "c1", "text": "test"}]

        result = self.agent.execute({"text": "Section 1 — Title", "law_name": "Act 1038"})
        assert "chunks" in result
        assert "hierarchy" in result
        assert "metadata" in result

    def test_format_output_has_expected_keys(self):
        result = {"chunks": [], "hierarchy": {}, "metadata": {}, "chunk_count": 0}
        output = self.agent.format_output(result)
        assert output["status"] == "success"
        assert "chunks" in output
        assert "chunk_count" in output


# ======================================================================
# EmbedderAgent
# ======================================================================

class TestEmbedderAgent:
    def setup_method(self):
        from agents.embedder import EmbedderAgent
        self.agent = EmbedderAgent(sector="cybersecurity")

    def test_validate_input_valid(self):
        assert self.agent.validate_input({"chunks": [{"text": "test"}]}) is True

    def test_validate_input_missing_chunks(self):
        assert self.agent.validate_input({}) is False
        assert self.agent.validate_input({"data": []}) is False

    def test_validate_input_empty_chunks(self):
        assert self.agent.validate_input({"chunks": []}) is True

    def test_validate_input_rejects_non_dict(self):
        assert self.agent.validate_input(None) is False

    def test_format_output_has_expected_keys(self):
        result = {"collection_id": "test", "chunks_stored": 5, "collection_total": 10}
        output = self.agent.format_output(result)
        assert output["status"] == "success"
        assert output["chunks_stored"] == 5
        assert output["ready"] is True
        assert output["sector"] == "cybersecurity"


# ======================================================================
# RetrieverAgent (basic — detailed in test_retrieval.py)
# ======================================================================

class TestRetrieverAgentBasic:
    def setup_method(self):
        from agents.retriever import RetrieverAgent
        self.agent = RetrieverAgent(sector="cybersecurity")

    def test_sector_set(self):
        assert self.agent.sector == "cybersecurity"

    def test_name(self):
        assert self.agent.name == "RetrieverAgent"


# ======================================================================
# AnalyzerAgent
# ======================================================================

class TestAnalyzerAgent:
    def setup_method(self):
        from agents.analyzer import AnalyzerAgent
        self.agent = AnalyzerAgent(sector="cybersecurity")

    def test_validate_input_valid(self):
        assert self.agent.validate_input({"policy": "some policy text", "laws": [{"text": "law"}]}) is True

    def test_validate_input_missing_policy(self):
        assert self.agent.validate_input({"laws": []}) is False

    def test_validate_input_missing_laws(self):
        assert self.agent.validate_input({"policy": "text"}) is False

    def test_validate_input_empty_laws(self):
        assert self.agent.validate_input({"policy": "text", "laws": []}) is True

    def test_validate_input_rejects_non_dict(self):
        assert self.agent.validate_input("string") is False
        assert self.agent.validate_input(None) is False

    @patch("tools.llm_tools.parse_json_response")
    @patch("tools.llm_tools.build_gap_analysis_prompt")
    def test_execute_calls_llm(self, mock_build, mock_parse):
        mock_build.return_value = "analyze this"
        mock_parse.return_value = {"gaps": [], "summary": "ok"}

        result = self.agent.execute({"policy": "policy text", "laws": [{"text": "law"}]})
        assert "summary" in result

    def test_execute_with_empty_laws(self):
        result = self.agent.execute({"policy": "policy text", "laws": []})
        assert result["gaps"] == []

    def test_format_output_has_expected_keys(self):
        result = {"gaps": [], "findings": "", "severity": "low", "summary": "", "compliant_areas": [], "total_laws_checked": 0}
        output = self.agent.format_output(result)
        assert output["status"] == "success"
        assert "gaps" in output
        assert "summary" in output


# ======================================================================
# ScorerAgent
# ======================================================================

class TestScorerAgent:
    def setup_method(self):
        from agents.scorer import ScorerAgent
        self.agent = ScorerAgent(sector="cybersecurity")

    def test_validate_input_with_policy(self):
        assert self.agent.validate_input({"policy": "some text"}) is True

    def test_validate_input_with_gaps(self):
        assert self.agent.validate_input({"gaps": []}) is True

    def test_validate_input_with_both(self):
        assert self.agent.validate_input({"policy": "text", "gaps": []}) is True

    def test_validate_input_missing(self):
        assert self.agent.validate_input({}) is False
        assert self.agent.validate_input(None) is False

    @patch("tools.scoring_tools.calculate_score")
    @patch("tools.scoring_tools.build_score_record")
    @patch("tools.scoring_tools.load_score_history")
    @patch("tools.scoring_tools.build_trend")
    def test_execute_calculates_score(self, mock_trend, mock_history, mock_build, mock_calc):
        mock_calc.return_value = {"overall_score": 0.75, "percentage": 75, "grade": "B", "breakdown": {}, "penalty_points": 25.0}
        mock_build.return_value = {"overall_score": 0.75, "percentage": 75, "grade": "B", "breakdown": {}, "penalty_points": 25.0}
        mock_history.return_value = []
        mock_trend.return_value = []

        result = self.agent.execute({"gaps": [{"severity": "high"}], "policy": "text"})
        assert result["overall_score"] == 0.75

    def test_format_output(self):
        result = {
            "overall_score": 0.85, "percentage": 85, "grade": "B",
            "breakdown": {}, "trend": [], "policy_name": "test",
        }
        output = self.agent.format_output(result)
        assert output["status"] == "success"
        assert output["grade"] == "B"
        assert output["sector"] == "cybersecurity"


# ======================================================================
# WriterAgent
# ======================================================================

class TestWriterAgent:
    def setup_method(self):
        from agents.writer import WriterAgent
        self.agent = WriterAgent(sector="cybersecurity")

    def test_validate_input_valid(self):
        assert self.agent.validate_input({"type": "gap_analysis", "content": {"gaps": []}}) is True

    def test_validate_input_valid_incident(self):
        assert self.agent.validate_input({"type": "incident_report", "content": {}}) is True

    def test_validate_input_missing_type(self):
        assert self.agent.validate_input({"content": {}}) is False

    def test_validate_input_missing_content(self):
        assert self.agent.validate_input({"type": "gap_analysis"}) is False

    def test_validate_input_rejects_non_dict(self):
        assert self.agent.validate_input("string") is False
        assert self.agent.validate_input(None) is False

    @patch("tools.llm_tools.call_claude")
    @patch("tools.llm_tools.build_document_prompt")
    def test_execute_calls_llm(self, mock_build, mock_call):
        mock_build.return_value = "generate document"
        mock_call.return_value = "Generated document content."
        self.agent._get_api_key = MagicMock(return_value="fake_key")

        result = self.agent.execute({"type": "gap_analysis", "content": {"gaps": []}})
        assert "document" in result

    def test_format_output(self):
        result = {"document": "content", "format": "pdf", "path": "/tmp/doc.pdf", "title": "Report"}
        output = self.agent.format_output(result)
        assert output["status"] == "success"
        assert output["format"] == "pdf"


# ======================================================================
# TranscriberAgent
# ======================================================================

class TestTranscriberAgent:
    def setup_method(self):
        from agents.transcriber import TranscriberAgent
        self.agent = TranscriberAgent(sector="cybersecurity")

    def test_validate_input_with_audio_path(self):
        assert self.agent.validate_input({"audio_path": "test.mp3"}) is True

    def test_validate_input_with_audio_data(self):
        assert self.agent.validate_input({"audio_data": b"fakebytes"}) is True

    def test_validate_input_missing_audio(self):
        assert self.agent.validate_input({}) is False
        assert self.agent.validate_input({"text": "hello"}) is False

    def test_validate_input_rejects_non_dict(self):
        assert self.agent.validate_input(None) is False
        assert self.agent.validate_input("string") is False

    @patch("tools.audio_tools.transcribe_audio")
    @patch("tools.audio_tools.validate_audio_file")
    def test_execute_with_path(self, mock_validate, mock_transcribe):
        mock_validate.return_value = True
        mock_transcribe.return_value = {"transcript": "hello", "language": "en", "duration_seconds": 5.0}
        self.agent._get_api_key = MagicMock(return_value="fake_key")

        result = self.agent.execute({"audio_path": "test.mp3"})
        assert "transcript" in result

    @patch("tools.audio_tools.transcribe_audio_data")
    def test_execute_with_data(self, mock_transcribe):
        mock_transcribe.return_value = {"transcript": "hello", "language": "en", "duration_seconds": 5.0}
        self.agent._get_api_key = MagicMock(return_value="fake_key")

        result = self.agent.execute({"audio_data": b"fakebytes"})
        assert "transcript" in result

    def test_format_output(self):
        result = {"transcript": "hello", "confidence": 0.9, "language": "en", "duration_seconds": 5.0}
        output = self.agent.format_output(result)
        assert output["status"] == "success"
        assert output["transcript"] == "hello"
        assert output["sector"] == "cybersecurity"
