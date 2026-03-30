from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from naas_abi.apps.nexus.apps.api.app.services.search.search__schema import (
    PrivateSearchRequestData,
    WebSearchRequestData,
    WebSearchResultData,
)
from naas_abi.apps.nexus.apps.api.app.services.search.service import SearchService


@pytest.mark.asyncio
async def test_web_search_uses_wikipedia_engine() -> None:
    service = SearchService()
    expected = [WebSearchResultData(id="1", title="A", snippet="B")]
    service._search_wikipedia = AsyncMock(return_value=expected)  # type: ignore[method-assign]

    result = await service.web_search(
        WebSearchRequestData(query="naas", engine="wikipedia", limit=5)
    )

    assert result.results == expected
    service._search_wikipedia.assert_awaited_once_with(query="naas", limit=5)


@pytest.mark.asyncio
async def test_web_search_uses_duckduckgo_engine() -> None:
    service = SearchService()
    expected = [WebSearchResultData(id="1", title="A", snippet="B")]
    service._search_duckduckgo = AsyncMock(return_value=expected)  # type: ignore[method-assign]

    result = await service.web_search(
        WebSearchRequestData(query="naas", engine="duckduckgo", limit=3)
    )

    assert result.results == expected
    service._search_duckduckgo.assert_awaited_once_with(query="naas", limit=3)


@pytest.mark.asyncio
async def test_get_suggestions_returns_empty_on_failure() -> None:
    service = SearchService()

    class FailingClient:
        async def __aenter__(self):
            raise RuntimeError("boom")

        async def __aexit__(self, *_args):
            return False

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr("httpx.AsyncClient", lambda *args, **kwargs: FailingClient())
        suggestions = await service.get_suggestions(query="naas", limit=5)

    assert suggestions == []


@pytest.mark.asyncio
async def test_private_search_ontology_scores_results() -> None:
    rows = [
        SimpleNamespace(
            get=lambda key, _d=None: {
                "uri": "https://example.com/ontology/resource",
                "label": "Search Term",
                "definition": "Definition",
            }.get(key)
        )
    ]
    triple_store = SimpleNamespace(query=lambda _q: rows)
    service = SearchService(triple_store_getter=lambda: triple_store)

    response = await service.private_search(
        PrivateSearchRequestData(query="search term", source="ontology")
    )

    assert len(response.results) == 1
    assert response.results[0].id == "https://example.com/ontology/resource"
    assert response.results[0].relevance == 1.0


def test_build_duckduckgo_results_respects_limit() -> None:
    data = {
        "Abstract": "Abstract text",
        "Heading": "Heading",
        "RelatedTopics": [
            {"Text": "Topic A", "FirstURL": "https://example.com/a", "Icon": {"URL": ""}},
            {"Text": "Topic B", "FirstURL": "https://example.com/b", "Icon": {"URL": ""}},
        ],
    }

    results = SearchService._build_duckduckgo_results(data=data, query="q", limit=2)

    assert len(results) == 2
