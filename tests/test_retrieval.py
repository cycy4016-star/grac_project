"""Tests for embedding_tools and RetrieverAgent."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from agents.retriever import RetrieverAgent
from tools.embedding_tools import (
    get_collection_name,
    collection_exists,
    get_collection_count,
    query_collection,
)


class TestGetCollectionName:
    def test_default_prefix(self):
        name = get_collection_name("cybersecurity")
        assert name == "grac_cybersecurity"

    def test_custom_prefix(self):
        name = get_collection_name("fintech", prefix="test")
        assert name == "test_fintech"

    def test_sectors_with_spaces(self):
        name = get_collection_name("data protection")
        assert name == "grac_data protection"

    def test_empty_sector(self):
        name = get_collection_name("")
        assert name == "grac_"


class TestCollectionExists:
    def test_returns_true_when_exists(self, mock_chroma_client):
        assert collection_exists(mock_chroma_client, "grac_cybersecurity") is True

    def test_returns_false_when_not_found(self, mock_chroma_client):
        assert collection_exists(mock_chroma_client, "nonexistent") is False

    def test_handles_exception(self, mock_chroma_client):
        mock_chroma_client.get_collection.side_effect = Exception("connection error")
        assert collection_exists(mock_chroma_client, "broken") is False


class TestGetCollectionCount:
    def test_returns_count(self, mock_chroma_collection):
        count = get_collection_count(mock_chroma_collection)
        assert count == 5

    def test_zero_count(self):
        mock = MagicMock()
        mock.count.return_value = 0
        assert get_collection_count(mock) == 0


class TestQueryCollection:
    def test_query_returns_results(self, mock_chroma_collection, mock_embedding_model):
        results = query_collection(
            query_text="data protection",
            model=mock_embedding_model,
            collection=mock_chroma_collection,
            top_k=2,
        )
        assert len(results) > 0
        for r in results:
            assert "id" in r
            assert "text" in r
            assert "metadata" in r
            assert "distance" in r
            assert "score" in r

    def test_query_results_have_scores(self, mock_chroma_collection, mock_embedding_model):
        results = query_collection(
            query_text="breach notification",
            model=mock_embedding_model,
            collection=mock_chroma_collection,
            top_k=2,
        )
        for r in results:
            assert 0.0 <= r["score"] <= 1.0

    def test_query_top_k_limits(self, mock_chroma_collection, mock_embedding_model):
        results = query_collection(
            query_text="test",
            model=mock_embedding_model,
            collection=mock_chroma_collection,
            top_k=1,
        )
        assert len(results) <= 1

    def test_query_returns_empty_for_no_results(self, mock_chroma_collection, mock_embedding_model):
        def empty_query(**kwargs):
            return {"ids": [[]], "distances": [[]], "metadatas": [[]], "documents": [[]]}
        mock_chroma_collection.query = empty_query
        mock_chroma_collection.query = empty_query
        results = query_collection(
            query_text="nonexistent",
            model=mock_embedding_model,
            collection=mock_chroma_collection,
            top_k=5,
        )
        assert results == []


class TestRetrieverAgentValidateInput:
    def setup_method(self):
        self.agent = RetrieverAgent(sector="cybersecurity")

    def test_valid_dict_with_query(self):
        assert self.agent.validate_input({"query": "data protection"}) is True

    def test_valid_dict_with_query_and_options(self):
        assert self.agent.validate_input({"query": "breach", "top_k": 5}) is True

    def test_rejects_non_dict(self):
        assert self.agent.validate_input("query") is False

    def test_rejects_empty_query(self):
        assert self.agent.validate_input({"query": ""}) is False

    def test_rejects_missing_query_key(self):
        assert self.agent.validate_input({"text": "something"}) is False

    def test_rejects_none(self):
        assert self.agent.validate_input(None) is False

    def test_rejects_empty_dict(self):
        assert self.agent.validate_input({}) is False


class TestRetrieverAgentFormatOutput:
    def setup_method(self):
        self.agent = RetrieverAgent(sector="cybersecurity")

    def test_returns_expected_keys(self):
        result = {
            "results": [{"id": "1", "text": "test", "score": 0.9}],
            "confidence_scores": [0.9],
            "query": "test query",
        }
        output = self.agent.format_output(result)
        assert output["status"] == "success"
        assert "results" in output
        assert "count" in output
        assert "confidence_scores" in output
        assert "query" in output
        assert output["sector"] == "cybersecurity"

    def test_empty_results(self):
        result = {"results": [], "confidence_scores": [], "query": ""}
        output = self.agent.format_output(result)
        assert output["count"] == 0
        assert output["status"] == "success"

    def test_none_results_handled(self):
        output = self.agent.format_output({"results": None, "confidence_scores": [], "query": ""})
        assert output["count"] == 0


class TestRetrieverAgentExecute:
    def setup_method(self):
        self.agent = RetrieverAgent(sector="cybersecurity")

    @patch("tools.embedding_tools.query_collection")
    @patch("tools.embedding_tools.load_embedding_model")
    @patch("tools.embedding_tools.get_chroma_client")
    def test_execute_returns_expected_structure(
        self, mock_get_client, mock_load_model, mock_query,
        mock_chroma_client, mock_embedding_model,
    ):
        mock_get_client.return_value = mock_chroma_client
        mock_load_model.return_value = mock_embedding_model
        mock_query.return_value = [
            {"id": "1", "text": "data protection", "metadata": {}, "distance": 0.15, "score": 0.85},
        ]

        result = self.agent.execute({"query": "data protection", "top_k": 3})
        assert "results" in result
        assert "confidence_scores" in result
        assert "query" in result
        assert len(result["results"]) > 0

    @patch("tools.embedding_tools.query_collection")
    @patch("tools.embedding_tools.load_embedding_model")
    @patch("tools.embedding_tools.get_chroma_client")
    def test_execute_empty_query_returns_empty(
        self, mock_get_client, mock_load_model, mock_query,
    ):
        result = self.agent.execute({"query": "", "top_k": 3})
        assert result["results"] == []

    def test_execute_handles_chroma_failure(self):
        result = self.agent.execute({"query": "test", "top_k": 3})
        assert result["results"] == []
        assert result["confidence_scores"] == []
