"""Tests for the DocumentAgent hybrid search tool."""

from __future__ import annotations

from typing import Any, List
from unittest.mock import MagicMock

import pytest

from naas_abi_marketplace.domains.document.agents.DocumentAgent import (
    DocumentSearchInput,
    _build_search_tool,
    _normalize_text,
)


class FakeSearchResult:
    def __init__(self, score: float, metadata: dict, payload: dict):
        self.score = score
        self.metadata = metadata
        self.payload = payload


class FakeVectorStore:
    def __init__(self, results: List[FakeSearchResult]):
        self._results = results
        self.last_k: int | None = None

    def search_similar(self, collection_name, query_vector, k, include_metadata=True):
        self.last_k = k
        return self._results[:k]


class FakeEmbeddingsModel:
    def embed_query(self, text: str) -> List[float]:
        return [0.1, 0.2, 0.3, 0.4]


class FakeTripleStore:
    """Returns object-attr rows (mimics rdflib's bindings access)."""

    def __init__(self, rows: list[dict]):
        self._rows = rows
        self.last_query: str | None = None

    def query(self, query: str):
        self.last_query = query
        out = []
        for row in self._rows:
            obj = MagicMock()
            obj.file_path = row["file_path"]
            obj.chunk_index = row["chunk_index"]
            obj.content = row["content"]
            out.append(obj)
        return out


class TestNormalizeText:
    def test_lowercases(self):
        assert _normalize_text("Hello") == "hello"

    def test_strips_french_accents(self):
        assert _normalize_text("Épée") == "epee"
        assert _normalize_text("château") == "chateau"
        assert _normalize_text("Noël") == "noel"

    def test_strips_mixed_accents(self):
        assert _normalize_text("Crème Brûlée") == "creme brulee"

    def test_empty(self):
        assert _normalize_text("") == ""


class TestBuildSearchTool:
    def test_vector_search_returns_formatted_results(self):
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
        assert result[0]["match_type"] == "vector"

    def test_empty_query_and_keywords_returns_error(self):
        tool = _build_search_tool(FakeEmbeddingsModel(), FakeVectorStore([]))
        result = tool.func(query="", keywords=[], collection_name="documents", k=5)
        assert len(result) == 1
        assert "error" in result[0]

    def test_k_limits_vector_results(self):
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

    def test_keyword_search_matches_all_terms_accent_insensitive(self):
        triple = FakeTripleStore(
            [
                {
                    "file_path": "docs/a.md",
                    "chunk_index": 0,
                    "content": "Le château de l'épée brille.",
                },
                {
                    "file_path": "docs/b.md",
                    "chunk_index": 1,
                    "content": "Just a guide with no special terms.",
                },
                {
                    "file_path": "docs/c.md",
                    "chunk_index": 2,
                    "content": "Une épée sans forteresse.",
                },
            ]
        )
        tool = _build_search_tool(
            FakeEmbeddingsModel(),
            FakeVectorStore([]),
            triple_store_service=triple,
        )
        # No vector query — keyword-only search must match all terms.
        result = tool.func(
            query="",
            keywords=["EPEE", "Chateau"],
            collection_name="documents",
            k=10,
        )

        paths = [r["file_path"] for r in result]
        assert "docs/a.md" in paths
        assert "docs/c.md" not in paths  # missing one of the keywords
        assert "docs/b.md" not in paths
        for r in result:
            assert r["match_type"] == "keyword"

    def test_hybrid_search_dedupes_results(self):
        fake_results = [
            FakeSearchResult(
                score=0.95,
                metadata={"file_path": "docs/a.md", "chunk_index": 0},
                payload={"content": "Le château de l'épée brille."},
            ),
        ]
        triple = FakeTripleStore(
            [
                {
                    "file_path": "docs/a.md",
                    "chunk_index": 0,
                    "content": "Le château de l'épée brille.",
                },
            ]
        )
        tool = _build_search_tool(
            FakeEmbeddingsModel(),
            FakeVectorStore(fake_results),
            triple_store_service=triple,
        )
        result = tool.func(
            query="forteresse médiévale",
            keywords=["chateau", "epee"],
            collection_name="documents",
            k=5,
        )
        assert len(result) == 1
        assert result[0]["match_type"] == "vector"

    def test_vector_results_filtered_by_keywords(self):
        fake_results = [
            FakeSearchResult(
                score=0.95,
                metadata={"file_path": "docs/match.md", "chunk_index": 0},
                payload={"content": "Le château et l'épée."},
            ),
            FakeSearchResult(
                score=0.90,
                metadata={"file_path": "docs/skip.md", "chunk_index": 1},
                payload={"content": "Unrelated content."},
            ),
        ]
        tool = _build_search_tool(
            FakeEmbeddingsModel(),
            FakeVectorStore(fake_results),
            triple_store_service=FakeTripleStore([]),
        )
        result = tool.func(
            query="anything",
            keywords=["chateau", "epee"],
            collection_name="documents",
            k=5,
        )
        paths = [r["file_path"] for r in result]
        assert "docs/match.md" in paths
        assert "docs/skip.md" not in paths

    def test_vector_search_fetches_wider_net_when_keywords_present(self):
        store = FakeVectorStore([])
        tool = _build_search_tool(
            FakeEmbeddingsModel(),
            store,
            triple_store_service=FakeTripleStore([]),
        )
        tool.func(query="hi", keywords=["foo"], collection_name="documents", k=3)
        # widened to k*4 so keyword filtering doesn't starve the result set.
        assert store.last_k == 12

    def test_keyword_search_without_triple_store_is_skipped(self):
        tool = _build_search_tool(FakeEmbeddingsModel(), FakeVectorStore([]))
        result = tool.func(query="", keywords=["foo"], collection_name="documents", k=5)
        # No vector results, no triple store → empty (not error).
        assert result == []


class TestDocumentSearchInput:
    def test_defaults(self):
        inp = DocumentSearchInput(query="hello")
        assert inp.collection_name == "documents"
        assert inp.k == 5
        assert inp.keywords == []

    def test_custom_values(self):
        inp = DocumentSearchInput(
            query="test",
            keywords=["a", "b"],
            collection_name="my_collection",
            k=10,
        )
        assert inp.collection_name == "my_collection"
        assert inp.k == 10
        assert inp.keywords == ["a", "b"]

    def test_k_bounds(self):
        with pytest.raises(Exception):
            DocumentSearchInput(query="test", k=0)
        with pytest.raises(Exception):
            DocumentSearchInput(query="test", k=21)
