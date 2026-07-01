"""Integration tests: end-to-end workflows through SupervisorAgent,
API health endpoint, and database CRUD pipeline."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from agents.supervisor import SupervisorAgent
from database.queries import (
    create_analysis,
    get_analysis,
    add_gaps,
    get_gaps_for_analysis,
    create_score,
    get_score_for_analysis,
    count_gaps_by_severity,
    log_audit_event,
    get_audit_logs,
)


# ======================================================================
# SupervisorAgent Workflow Integration
# ======================================================================

class TestSupervisorPdfAnalysisWorkflow:
    @patch("agents.retriever.RetrieverAgent.execute")
    @patch("agents.analyzer.AnalyzerAgent.execute")
    def test_pdf_analysis_workflow_chain(self, mock_analyzer, mock_retriever):
        mock_retriever.return_value = {
            "results": [{"text": "law content", "score": 0.9}],
            "confidence_scores": [0.9],
            "query": "policy",
        }
        mock_analyzer.return_value = {
            "gaps": [],
            "findings": "all compliant",
            "severity": "low",
            "summary": "Policy meets requirements",
            "compliant_areas": ["Encryption"],
            "total_laws_checked": 5,
        }

        supervisor = SupervisorAgent(sector="cybersecurity")
        input_data = {"request_type": "pdf_analysis", "data": "test policy text for analysis"}
        result = supervisor.run(input_data)
        assert result["status"] == "success"

    @patch("agents.retriever.RetrieverAgent.execute")
    def test_pdf_analysis_empty_laws(self, mock_retriever):
        mock_retriever.return_value = {
            "results": [],
            "confidence_scores": [],
            "query": "",
        }

        supervisor = SupervisorAgent(sector="cybersecurity")
        input_data = {"request_type": "pdf_analysis", "data": "test policy text for analysis"}
        result = supervisor.run(input_data)
        assert result["status"] == "success"


class TestSupervisorVoiceWorkflow:
    @patch("agents.transcriber.TranscriberAgent.execute")
    def test_voice_input_workflow(self, mock_transcriber):
        mock_transcriber.return_value = {
            "transcript": "This is a test transcription",
            "confidence": 0.95,
            "language": "en",
            "duration_seconds": 30.0,
        }

        supervisor = SupervisorAgent(sector="cybersecurity")
        input_data = {"request_type": "voice_input", "data": {"audio_data": b"fake"}}
        result = supervisor.run(input_data)
        assert result["status"] == "success"

    @patch("agents.transcriber.TranscriberAgent.execute")
    def test_voice_input_with_options(self, mock_transcriber):
        mock_transcriber.return_value = {
            "transcript": "test",
            "confidence": 0.8,
            "language": "en",
            "duration_seconds": 10.0,
        }

        supervisor = SupervisorAgent(sector="cybersecurity")
        input_data = {
            "request_type": "voice_input",
            "data": {"audio_data": b"fake", "language": "fr", "document_type": "incident_report"},
        }
        result = supervisor.run(input_data)
        assert result["status"] == "success"


class TestSupervisorComplianceQAWorkflow:
    @patch("agents.retriever.RetrieverAgent.execute")
    def test_compliance_question_workflow(self, mock_retrieve):
        mock_retrieve.return_value = {
            "results": [{"text": "law text", "score": 0.9}],
            "confidence_scores": [0.9],
            "query": "question",
        }

        supervisor = SupervisorAgent(sector="cybersecurity")
        input_data = {
            "request_type": "compliance_question",
            "data": "What does Act 1038 require for data protection?",
        }
        result = supervisor.run(input_data)
        assert result["status"] == "success"

    @patch("agents.retriever.RetrieverAgent.execute")
    def test_compliance_question_no_results(self, mock_retrieve):
        mock_retrieve.return_value = {
            "results": [],
            "confidence_scores": [],
            "query": "unknown",
        }

        supervisor = SupervisorAgent(sector="cybersecurity")
        input_data = {
            "request_type": "compliance_question",
            "data": "Some unknown question",
        }
        result = supervisor.run(input_data)
        assert result["status"] == "success"


class TestSupervisorScoringWorkflow:
    @patch("agents.retriever.RetrieverAgent.execute")
    @patch("agents.analyzer.AnalyzerAgent.execute")
    @patch("agents.scorer.ScorerAgent.execute")
    def test_scoring_workflow(self, mock_scorer, mock_analyzer, mock_retriever):
        mock_retriever.return_value = {
            "results": [{"text": "law content", "score": 0.9}],
            "confidence_scores": [0.9],
            "query": "policy",
        }
        mock_analyzer.return_value = {
            "gaps": [{"severity": "high", "requirement": "Encryption"}],
            "findings": "gaps found",
            "severity": "high",
            "summary": "Needs improvement",
            "compliant_areas": [],
            "total_laws_checked": 5,
        }
        mock_scorer.return_value = {
            "overall_score": 0.65,
            "percentage": 65,
            "grade": "D",
            "breakdown": {"critical": {"count": 0}, "high": {"count": 1}},
            "trend": [],
            "policy_name": "Policy",
        }

        supervisor = SupervisorAgent(sector="cybersecurity")
        input_data = {
            "request_type": "scoring",
            "data": "test policy text for analysis",
        }
        result = supervisor.run(input_data)
        assert result["status"] == "success"


# ======================================================================
# API Integration Tests
# ======================================================================

class TestAPIHealthEndpoint:
    def test_health_endpoint(self):
        from api.main import app
        from fastapi.testclient import TestClient

        client = TestClient(app)
        response = client.get("/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["service"] == "GRaC API"
        assert "version" in data
        assert "active_sector" in data

    def test_health_is_get_only(self):
        from api.main import app
        from fastapi.testclient import TestClient

        client = TestClient(app)
        response = client.post("/api/health")
        assert response.status_code == 405


class TestAPIAnalyzePolicy:
    def test_missing_policy_field(self):
        from api.main import app
        from fastapi.testclient import TestClient

        client = TestClient(app)
        response = client.post("/api/analyze-policy", json={})
        assert response.status_code == 422

    def test_policy_too_short(self):
        from api.main import app
        from fastapi.testclient import TestClient

        client = TestClient(app)
        response = client.post("/api/analyze-policy", json={"policy": "short"})
        assert response.status_code == 422


class TestAPIAskCompliance:
    def test_missing_question(self):
        from api.main import app
        from fastapi.testclient import TestClient

        client = TestClient(app)
        response = client.post("/api/ask-compliance", json={})
        assert response.status_code == 422

    def test_question_too_short(self):
        from api.main import app
        from fastapi.testclient import TestClient

        client = TestClient(app)
        response = client.post("/api/ask-compliance", json={"question": "ab"})
        assert response.status_code == 422


class TestAPIComplianceScore:
    def test_missing_policy(self):
        from api.main import app
        from fastapi.testclient import TestClient

        client = TestClient(app)
        response = client.post("/api/compliance-score", json={})
        assert response.status_code == 422

    def test_policy_too_short(self):
        from api.main import app
        from fastapi.testclient import TestClient

        client = TestClient(app)
        response = client.post("/api/compliance-score", json={"policy": "short"})
        assert response.status_code == 422


# ======================================================================
# Database CRUD Integration
# ======================================================================

class TestDatabaseCRUDPipeline:
    @pytest.fixture(autouse=True)
    def setup_db(self, tmp_path):
        import database.connection as conn
        from sqlalchemy import create_engine, orm

        self._db_path = tmp_path / "test_grac.db"
        test_url = f"sqlite:///{self._db_path}"
        test_engine = create_engine(test_url, echo=False)
        test_session = orm.sessionmaker(bind=test_engine)

        self._orig_get_engine = conn.get_engine
        self._orig_get_session = conn.get_session_local
        conn.get_engine = lambda: test_engine
        conn.get_session_local = lambda: test_session

        from database import init_db
        init_db()

        yield

        conn.get_engine = self._orig_get_engine
        conn.get_session_local = self._orig_get_session

    def test_full_crud_pipeline(self):
        a = create_analysis(
            "cybersecurity",
            "Policy text for testing database CRUD pipeline operations.",
            summary="Integration test",
            compliant_areas=["Access Control", "Encryption"],
            total_laws_checked=10,
        )
        assert a.id is not None
        assert a.sector == "cybersecurity"
        assert a.status == "completed"

        gaps = add_gaps(a.id, [
            {"requirement": "Implement MFA", "law_reference": "Act 1038 s.5", "policy_status": "missing", "severity": "critical", "recommendation": "Deploy MFA"},
            {"requirement": "Data backup", "law_reference": "Act 1038 s.12", "policy_status": "inadequate", "severity": "high", "recommendation": "Implement backups"},
        ])
        assert len(gaps) == 2

        s = create_score(a.id, 0.60, 60, "C", penalty_points=40.0, breakdown={"critical": {"count": 1}, "high": {"count": 1}}, total_requirements=10)
        assert s.analysis_id == a.id
        assert s.grade == "C"

        fetched = get_analysis(a.id)
        assert fetched is not None
        gaps_fetched = get_gaps_for_analysis(a.id)
        assert len(gaps_fetched) == 2
        score_fetched = get_score_for_analysis(a.id)
        assert score_fetched is not None
        assert score_fetched.grade == "C"

        counts = count_gaps_by_severity(a.id)
        assert counts.get("critical") == 1
        assert counts.get("high") == 1
        assert counts.get("medium", 0) == 0
        assert counts.get("low", 0) == 0

        assert len(fetched.gaps) == 2
        assert fetched.score is not None

    def test_audit_log_pipeline(self):
        entries = []
        for i in range(3):
            e = log_audit_event("TestAgent", f"event_{i}", sector="cybersecurity", status="success", duration_ms=i * 100)
            entries.append(e)
        assert len(entries) == 3

        loaded = get_audit_logs(agent_name="TestAgent", sector="cybersecurity")
        assert len(loaded) >= 3

    def test_concurrent_analyses(self):
        a1 = create_analysis("cybersecurity", "First policy text for concurrent testing of analysis creation.", summary="First")
        a2 = create_analysis("cybersecurity", "Second policy document for verifying separate analysis records.", summary="Second")
        assert a1.id != a2.id

    def test_analysis_with_zero_gaps(self):
        a = create_analysis("cybersecurity", "Policy text with no compliance gaps to verify empty state handling.", summary="No gaps")
        gaps = get_gaps_for_analysis(a.id)
        assert gaps == []
        counts = count_gaps_by_severity(a.id)
        assert len(counts) == 0
