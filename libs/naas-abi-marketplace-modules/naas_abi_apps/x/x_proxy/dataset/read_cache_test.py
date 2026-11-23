"""Dataset search response cache."""

import threading
import time
from types import SimpleNamespace

from naas_abi_apps.x.x_proxy.dataset.read_cache import (
    SEARCH_RESPONSE_CACHE,
    DatasetSearchResponseCache,
    _etag,
    cached_dataset_response,
    cached_search_response,
    publish_read_cache_generation,
    read_cache_generation,
)


class _Dataset:
    """Counts the generation reads; answers one commit."""

    def __init__(self) -> None:
        self.queries = 0

    def query(self, sql: str, *, namespace: str = "default"):
        self.queries += 1
        return SimpleNamespace(rows=[{"commit_id": "c1"}])


def test_generation_is_read_once_per_ttl_and_bumped_by_a_local_sync() -> None:
    dataset = _Dataset()
    assert read_cache_generation(dataset) == "c1"
    assert read_cache_generation(dataset) == "c1"
    assert dataset.queries == 1
    # The module's own sync bumps it at once, without a query.
    publish_read_cache_generation(None, "c2")
    assert read_cache_generation(dataset) == "c2"
    assert dataset.queries == 1


def test_cache_clears_when_generation_changes() -> None:
    cache = DatasetSearchResponseCache()
    cache.put("gen-a", ("posts", "", "0", "100"), b"{}")
    assert cache.get("gen-a", ("posts", "", "0", "100")) == b"{}"
    assert cache.get("gen-b", ("posts", "", "0", "100")) is None


def test_cached_search_reuses_body_and_supports_304() -> None:
    SEARCH_RESPONSE_CACHE._entries.clear()
    calls = {"n": 0}

    def compute() -> bytes:
        calls["n"] += 1
        return b'{"count":1}'

    gen = "commit-1"
    key_etag = _etag(gen, ("posts", "", "0", "100"))

    status, body, headers = cached_search_response(
        if_none_match=None,
        generation=gen,
        scope="posts",
        query="",
        page=0,
        per_page=100,
        compute_body=compute,
    )
    assert status == 200
    assert body == b'{"count":1}'
    assert calls["n"] == 1
    assert headers["ETag"] == key_etag

    status2, body2, _ = cached_search_response(
        if_none_match=headers["ETag"],
        generation=gen,
        scope="posts",
        query="",
        page=0,
        per_page=100,
        compute_body=compute,
    )
    assert status2 == 304
    assert body2 == b""
    assert calls["n"] == 1


def test_stale_generation_is_served_at_once_and_refreshed_in_background() -> None:
    cache = DatasetSearchResponseCache()
    key = ("users", "", "0", "100")
    cache.put("gen-1", key, b"old")
    refreshed = threading.Event()

    def compute() -> bytes:
        refreshed.set()
        return b"new"

    status, body, headers = cached_dataset_response(
        if_none_match=None,
        generation="gen-2",
        key=key,
        compute_body=compute,
        cache=cache,
    )
    assert (status, body) == (200, b"old")
    # The stale body keeps its own ETag, so the browser asks again later.
    assert headers["ETag"] == _etag("gen-1", key)
    assert refreshed.wait(5)
    for _ in range(100):
        if cache.get("gen-2", key) == b"new":
            break
        time.sleep(0.01)
    assert cache.get("gen-2", key) == b"new"


def test_concurrent_misses_share_one_computation() -> None:
    cache = DatasetSearchResponseCache()
    key = ("posts", "drone", "0", "100")
    calls = {"n": 0}
    gate = threading.Event()

    def compute() -> bytes:
        calls["n"] += 1
        gate.wait(5)
        return b"body"

    bodies: list[bytes] = []
    threads = [
        threading.Thread(
            target=lambda: bodies.append(cache.compute("gen", key, compute))
        )
        for _ in range(4)
    ]
    for thread in threads:
        thread.start()
    time.sleep(0.05)
    gate.set()
    for thread in threads:
        thread.join(5)
    assert bodies == [b"body"] * 4
    assert calls["n"] == 1


def test_cache_evicts_least_recently_used_beyond_capacity() -> None:
    cache = DatasetSearchResponseCache(max_entries=2)
    cache.put("g", ("a",), b"a")
    cache.put("g", ("b",), b"b")
    assert cache.get("g", ("a",)) == b"a"  # touch: ``b`` is now the oldest
    cache.put("g", ("c",), b"c")
    assert cache.get("g", ("b",)) is None
    assert cache.get("g", ("a",)) == b"a"
