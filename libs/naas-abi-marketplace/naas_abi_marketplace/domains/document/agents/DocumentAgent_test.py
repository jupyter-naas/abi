"""Basic smoke tests for the DocumentAgent search tool builder."""

from __future__ import annotations

from typing import Any, Dict, List
from unittest.mock import MagicMock

import numpy as np
import pytest

from naas_abi_marketplace.domains.document.agents.DocumentAgent import (
    DocumentSearchInput,
    _build_search_tool,
)


class FakeSearchResult:
    def __init__(self, score: float, metadata: dict, payload: dict):
        self.score = score
        self.metadata = metadata
        self.payload = payload


class FakeVectorStore:
    def __init__(self, results: List[FakeSearchResult]):
        self._results = results

    def search_similar(self, collection_name, query_vector, k, include_metadata=True):
        return self._results[:k]


class FakeEmbeddingsModel:
    def embed_query(self, text: str) -> List[float]:
        return [0.1, 0.2, 0.3, 0.4]


class TestBuildSearchTool:
    def test_search_returns_formatted_results(self):
        fake_results = [
            FakeSearchResult(
                score=0.95,
                metadata={"file_path": "docs/guide.md", "chunk_index": 0},
                payload={"content": "This is the installation guide."},
            ),
            FakeSearchResult(
                score=0.88,
                metadata={"file_path": "docs/faq.md", "chunk_index": 2},
                payload={"content": "Frequently asked questions."},
            ),
        ]
        tool = _build_search_tool(FakeEmbeddingsModel(), FakeVectorStore(fake_results))
        result = tool.func(query="how to install", collection_name="documents", k=5)

        assert len(result) == 2
        assert result[0]["score"] == pytest.approx(0.95)
        assert result[0]["file_path"] == "docs/guide.md"
        assert result[0]["content"] == "This is the installation guide."
        assert result[1]["file_path"] == "docs/faq.md"

    def test_search_empty_query_returns_error(self):
        tool = _build_search_tool(FakeEmbeddingsModel(), FakeVectorStore([]))
        result = tool.func(query="", collection_name="documents", k=5)
        assert len(result) == 1
        assert "error" in result[0]

    def test_k_limits_results(self):
        fake_results = [
            FakeSearchResult(
                score=0.9 - i * 0.1,
                metadata={"file_path": f"doc{i}.md", "chunk_index": 0},
                payload={"content": f"Content {i}"},
            )
            for i in range(10)
        ]
        tool = _build_search_tool(FakeEmbeddingsModel(), FakeVectorStore(fake_results))
        result = tool.func(query="something", collection_name="documents", k=3)
        assert len(result) <= 3

    def test_search_handles_exception_gracefully(self):
        class BrokenVectorStore:
            def search_similar(self, **kwargs):
                raise RuntimeError("connection failed")

        tool = _build_search_tool(FakeEmbeddingsModel(), BrokenVectorStore())
        result = tool.func(query="test", collection_name="documents", k=5)
        assert len(result) == 1
        assert "error" in result[0]
        assert "connection failed" in result[0]["error"]


class TestDocumentSearchInput:
    def test_defaults(self):
        inp = DocumentSearchInput(query="hello")
        assert inp.collection_name == "documents"
        assert inp.k == 5

    def test_custom_values(self):
        inp = DocumentSearchInput(query="test", collection_name="my_collection", k=10)
        assert inp.collection_name == "my_collection"
        assert inp.k == 10

    def test_k_bounds(self):
        with pytest.raises(Exception):
            DocumentSearchInput(query="test", k=0)
        with pytest.raises(Exception):
            DocumentSearchInput(query="test", k=21)
