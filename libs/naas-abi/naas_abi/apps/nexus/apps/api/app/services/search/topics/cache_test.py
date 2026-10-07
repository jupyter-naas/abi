"""Tests for the search topic response cache."""

from __future__ import annotations

from typing import Any

from naas_abi.apps.nexus.apps.api.app.services.search.topics.cache import SearchCache


class MemoryCache:
    """The two CacheService calls the search cache makes."""

    def __init__(self) -> None:
        self.values: dict[str, Any] = {}

    def get(self, key: str, ttl: Any = None) -> Any:
        if key not in self.values:
            raise KeyError(key)
        return self.values[key]

    def set_json(self, key: str, value: Any) -> None:
        self.values[key] = value


def key(cache: SearchCache, *, topic: dict | None = None, q: str = "edf") -> str:
    return cache.key(
        "ws-1",
        scope="scope-a",
        topic=topic or {"id": "person", "results_query": "SELECT 1"},
        request={"role": "results", "q": q},
    )


def test_a_stored_response_is_found_again() -> None:
    cache = SearchCache(MemoryCache())
    cache.store(key(cache), {"total": 10})
    assert cache.fetch(key(cache)) == {"total": 10}
    assert cache.fetch(key(cache, q="engie")) is None


def test_refresh_retires_every_response_of_the_workspace() -> None:
    cache = SearchCache(MemoryCache())
    cache.store(key(cache), {"total": 10})
    cache.refresh("ws-1")
    assert cache.fetch(key(cache)) is None


def test_editing_the_topic_is_a_new_entry() -> None:
    cache = SearchCache(MemoryCache())
    cache.store(key(cache), {"total": 10})
    edited = {"id": "person", "results_query": "SELECT 2"}
    assert cache.fetch(key(cache, topic=edited)) is None


def test_a_broken_cache_is_a_miss_not_an_error() -> None:
    class Broken:
        def get(self, *args: Any, **kwargs: Any) -> Any:
            raise RuntimeError("redis down")

        def set_json(self, *args: Any) -> None:
            raise RuntimeError("redis down")

    cache = SearchCache(Broken())
    cache.store(key(cache), {"total": 10})
    assert cache.fetch(key(cache)) is None
