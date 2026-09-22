"""Dataset search response cache."""

from naas_abi_marketplace.applications.x.apps.x_proxy.dataset.read_cache import (
    SEARCH_RESPONSE_CACHE,
    DatasetSearchResponseCache,
    _etag,
    cached_search_response,
    optional_module_kv,
)


class _KvDenied:
    class _Services:
        @property
        def kv(self):
            raise ValueError("no kv access")

    engine = type("Engine", (), {"services": _Services()})()


def test_optional_module_kv_returns_none_when_access_denied() -> None:
    assert optional_module_kv(_KvDenied()) is None


def test_cache_clears_when_generation_changes() -> None:
    cache = DatasetSearchResponseCache()
    cache.put("gen-a", ("posts", "", "0", "100"), b"{}")
    assert cache.get("gen-a", ("posts", "", "0", "100")) == b"{}"
    assert cache.get("gen-b", ("posts", "", "0", "100")) is None


def test_cached_search_reuses_body_and_supports_304() -> None:
    SEARCH_RESPONSE_CACHE._entries.clear()
    SEARCH_RESPONSE_CACHE._generation = None
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
