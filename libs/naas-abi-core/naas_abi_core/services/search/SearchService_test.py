"""SearchService smoke tests.

Validates the federation shape: streaming order, error isolation,
read-only guard, cache hit. Adapters get tested separately under
`adaptors/secondary/`.
"""

from __future__ import annotations

import time
from typing import Any, Iterator

import pytest

from naas_abi_core.services.search.SearchPorts import (
    Exceptions,
    Hit,
    ISearchSource,
    SearchFinished,
    SearchHit,
    SearchStarted,
    SourceError,
    SourceFinished,
    SourceStarted,
)
from naas_abi_core.services.search.SearchService import SearchService


class _StaticSource(ISearchSource):
    def __init__(self, name: str, hits: list[SearchHit], delay: float = 0.0):
        self._n = name
        self._hits = hits
        self._delay = delay

    @property
    def name(self) -> str:
        return self._n

    def search(
        self, query: str, *, filters: dict[str, Any] | None = None, limit: int = 50
    ) -> Iterator[SearchHit]:
        if self._delay:
            time.sleep(self._delay)
        for h in self._hits[:limit]:
            yield h


class _BrokenSource(ISearchSource):
    @property
    def name(self) -> str:
        return "broken"

    def search(self, query: str, **_: Any) -> Iterator[SearchHit]:
        raise RuntimeError("boom")


def _hit(source: str, id_: str) -> SearchHit:
    return SearchHit(
        id=id_, source=source, kind="entity", title=id_, snippet=id_, score=1.0
    )


def test_streams_started_hits_finished_for_each_source():
    service = SearchService()
    service.register_source(_StaticSource("a", [_hit("a", "a1"), _hit("a", "a2")]))
    service.register_source(_StaticSource("b", [_hit("b", "b1")]))

    events = list(service.search("q"))

    assert isinstance(events[0], SearchStarted)
    assert events[0].sources == ["a", "b"]
    assert isinstance(events[-1], SearchFinished)
    assert events[-1].total_hits == 3

    starts = [e.source for e in events if isinstance(e, SourceStarted)]
    finishes = [e.source for e in events if isinstance(e, SourceFinished)]
    assert sorted(starts) == ["a", "b"]
    assert sorted(finishes) == ["a", "b"]


def test_broken_source_isolated_does_not_kill_others():
    service = SearchService()
    service.register_source(_StaticSource("ok", [_hit("ok", "1")]))
    service.register_source(_BrokenSource())

    events = list(service.search("q"))
    errors = [e for e in events if isinstance(e, SourceError)]
    hits = [e for e in events if isinstance(e, Hit)]

    assert len(errors) == 1 and errors[0].source == "broken"
    assert errors[0].error_type == "RuntimeError"
    assert len(hits) == 1 and hits[0].hit.source == "ok"


def test_unknown_source_raises():
    service = SearchService()
    service.register_source(_StaticSource("a", []))

    with pytest.raises(Exceptions.SourceNotFoundError):
        list(service.search("q", sources=["nope"]))


def test_reindex_on_readonly_source_raises():
    service = SearchService()
    service.register_source(_StaticSource("a", []))

    with pytest.raises(Exceptions.IndexingNotSupportedError):
        service.reindex("a")


def test_cache_hit_second_query_reuses_results():
    calls = {"n": 0}

    class _CountingSource(_StaticSource):
        def search(self, query: str, **kw: Any) -> Iterator[SearchHit]:
            calls["n"] += 1
            return super().search(query, **kw)

    service = SearchService(cache_ttl_seconds=60.0)
    service.register_source(_CountingSource("a", [_hit("a", "1")]))

    list(service.search("same"))
    list(service.search("same"))

    assert calls["n"] == 1


def test_bypass_cache_forces_refetch():
    calls = {"n": 0}

    class _CountingSource(_StaticSource):
        def search(self, query: str, **kw: Any) -> Iterator[SearchHit]:
            calls["n"] += 1
            return super().search(query, **kw)

    service = SearchService(cache_ttl_seconds=60.0)
    service.register_source(_CountingSource("a", [_hit("a", "1")]))

    list(service.search("same"))
    list(service.search("same", bypass_cache=True))

    assert calls["n"] == 2
