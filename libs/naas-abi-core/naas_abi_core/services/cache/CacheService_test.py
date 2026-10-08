# mypy: disable-error-code="arg-type,misc"
"""Tests for the multi-tier CacheService."""

from __future__ import annotations

import datetime
import pickle
import time

import pytest
from naas_abi_core.services.cache.CachePort import (
    CachedData,
    CacheKeyPage,
    CacheNotFoundError,
    DataType,
    ICacheAdapter,
    paginate_keys,
)
from naas_abi_core.services.cache.CacheService import TIER_COLD, TIER_HOT, CacheService
from naas_abi_core.services.cache.ontologies.modules.CacheEventOntology import (
    CacheDeleted,
    CacheError,
    CacheSet,
)

# ---------------------------------------------------------------------------
# In-memory test adapter
# ---------------------------------------------------------------------------


class CacheMemoryAdapter(ICacheAdapter):
    def __init__(self) -> None:
        self.store: dict[str, CachedData] = {}

    def get(self, key: str) -> CachedData:
        if key not in self.store:
            raise CacheNotFoundError(f"Cache not found: {key}")
        return self.store[key]

    def set(self, key: str, value: CachedData) -> None:
        self.store[key] = value

    def set_if_absent(self, key: str, value: CachedData) -> bool:
        if key in self.store:
            return False
        self.store[key] = value
        return True

    def delete(self, key: str) -> None:
        if key not in self.store:
            raise CacheNotFoundError(f"Cache not found: {key}")
        del self.store[key]

    def exists(self, key: str) -> bool:
        return key in self.store

    def list_keys(
        self, prefix: str = "", *, limit: int = 100, after: str | None = None
    ) -> CacheKeyPage:
        return paginate_keys(self.store, prefix, limit, after)


def _single_cold() -> CacheService:
    """Convenience: single cold-tier service."""
    return CacheService(adapters=[(TIER_COLD, CacheMemoryAdapter())])


def _hot_cold() -> tuple[CacheMemoryAdapter, CacheMemoryAdapter, CacheService]:
    """Convenience: hot + cold two-tier service."""
    hot_adapter = CacheMemoryAdapter()
    cold_adapter = CacheMemoryAdapter()
    svc = CacheService(
        adapters=[(TIER_HOT, hot_adapter), (TIER_COLD, cold_adapter)]
    )
    return hot_adapter, cold_adapter, svc


# ---------------------------------------------------------------------------
# Single-tier baseline (backward-compat behaviour)
# ---------------------------------------------------------------------------


def test_single_tier_basic_ops() -> None:
    cache = _single_cold()

    assert cache.exists("k") is False

    cache.set_json("k", {"v": 1})
    assert cache.exists("k") is True
    assert cache.get("k") == {"v": 1}

    cache.delete("k")
    assert cache.exists("k") is False


def test_single_tier_set_if_absent() -> None:
    cache = _single_cold()

    assert cache.set_json_if_absent("k", {"v": 1}) is True
    assert cache.set_json_if_absent("k", {"v": 2}) is False
    assert cache.get("k") == {"v": 1}


def test_single_tier_cold_property() -> None:
    cache = _single_cold()
    cache.cold.set_json("k", {"x": 42})
    assert cache.cold.get("k") == {"x": 42}


def test_single_tier_hot_unavailable_raises() -> None:
    cache = _single_cold()
    try:
        _ = cache.hot
        assert False, "Expected ValueError"
    except ValueError as exc:
        assert "hot" in str(exc).lower()


# ---------------------------------------------------------------------------
# Two-tier (hot + cold) semantics
# ---------------------------------------------------------------------------


def test_two_tier_read_through_hot_miss_falls_to_cold() -> None:
    hot, cold, cache = _hot_cold()

    # Write to cold only (default top-level write)
    cache.set_json("k", {"data": "from_cold"})

    assert hot.exists("k") is False   # hot is empty
    assert cold.exists("k") is True   # cold has it

    # Top-level get does hot → cold read-through
    assert cache.get("k") == {"data": "from_cold"}


def test_two_tier_read_through_hot_hit_skips_cold() -> None:
    _hot, _cold, cache = _hot_cold()

    # Write different values to each tier directly
    cache.hot.set_json("k", {"from": "hot"})
    cache.cold.set_json("k", {"from": "cold"})

    # Top-level get finds hot first
    assert cache.get("k") == {"from": "hot"}


def test_two_tier_no_promotion_on_cold_hit() -> None:
    """A cold-tier hit must NOT automatically populate the hot tier."""
    hot, _cold, cache = _hot_cold()

    cache.cold.set_json("k", {"data": "cold_only"})

    result = cache.get("k")  # read-through: cold hit
    assert result == {"data": "cold_only"}

    # Hot tier must remain empty — no automatic promotion
    assert hot.exists("k") is False


def test_two_tier_explicit_hot_write() -> None:
    _, _, cache = _hot_cold()

    cache.hot.set_json("session", {"token": "abc"})
    assert cache.hot.exists("session") is True
    assert cache.cold.exists("session") is False  # cold untouched


def test_two_tier_explicit_promotion_by_caller() -> None:
    """Caller is responsible for promoting cold → hot when desired."""
    hot, _cold, cache = _hot_cold()

    cache.cold.set_json("k", {"expensive": "data"})

    # Caller reads cold and explicitly promotes to hot
    value = cache.cold.get("k")
    cache.hot.set_json("k", value)

    assert hot.exists("k") is True
    assert cache.get("k") == {"expensive": "data"}  # now served from hot


def test_two_tier_default_write_targets_cold_only() -> None:
    hot, cold, cache = _hot_cold()

    cache.set_json("k", {"v": 1})

    assert cold.exists("k") is True
    assert hot.exists("k") is False


def test_two_tier_exists_checks_all_tiers() -> None:
    _, _, cache = _hot_cold()

    # Key only in hot
    cache.hot.set_json("hot_key", {})
    assert cache.exists("hot_key") is True

    # Key only in cold
    cache.cold.set_json("cold_key", {})
    assert cache.exists("cold_key") is True

    # Missing everywhere
    assert cache.exists("missing") is False


def test_two_tier_delete_removes_from_all_tiers() -> None:
    _, _, cache = _hot_cold()

    cache.hot.set_json("k", {"v": 1})
    cache.cold.set_json("k", {"v": 1})

    cache.delete("k")

    assert cache.exists("k") is False
    assert cache.hot.exists("k") is False
    assert cache.cold.exists("k") is False


def test_two_tier_get_raises_if_absent_everywhere() -> None:
    _, _, cache = _hot_cold()

    try:
        cache.get("no_such_key")
        assert False, "Expected CacheNotFoundError"
    except CacheNotFoundError:
        pass


# ---------------------------------------------------------------------------
# Hot-tier resilience — errors degrade gracefully to cold
# ---------------------------------------------------------------------------


class _BrokenAdapter(ICacheAdapter):
    """Adapter that always raises a connection-style error."""

    def get(self, key: str) -> CachedData:
        raise OSError("Redis connection refused")

    def set(self, key: str, value: CachedData) -> None:
        raise OSError("Redis connection refused")

    def set_if_absent(self, key: str, value: CachedData) -> bool:
        raise OSError("Redis connection refused")

    def delete(self, key: str) -> None:
        raise OSError("Redis connection refused")

    def exists(self, key: str) -> bool:
        raise OSError("Redis connection refused")

    def list_keys(
        self, prefix: str = "", *, limit: int = 100, after: str | None = None
    ) -> CacheKeyPage:
        raise OSError("Redis connection refused")


def _broken_hot_cold() -> tuple[CacheMemoryAdapter, CacheService]:
    """Hot tier always raises; cold tier is a normal memory adapter."""
    cold_adapter = CacheMemoryAdapter()
    svc = CacheService(
        adapters=[(TIER_HOT, _BrokenAdapter()), (TIER_COLD, cold_adapter)]
    )
    return cold_adapter, svc


def test_broken_hot_get_falls_through_to_cold() -> None:
    cold, cache = _broken_hot_cold()

    cold.set("k", CachedData(key="k", data='{"v": 1}', data_type=DataType.JSON))

    # Hot raises OSError → should fall through silently to cold
    result = cache.get("k")
    assert result == {"v": 1}


def test_broken_hot_exists_falls_through_to_cold() -> None:
    cold, cache = _broken_hot_cold()

    assert cache.exists("k") is False  # cold empty

    cold.set("k", CachedData(key="k", data="x", data_type=DataType.TEXT))
    assert cache.exists("k") is True   # found in cold despite hot being broken


def test_broken_hot_get_raises_not_found_when_cold_also_misses() -> None:
    _, cache = _broken_hot_cold()

    try:
        cache.get("missing")
        assert False, "Expected CacheNotFoundError"
    except CacheNotFoundError:
        pass


# ---------------------------------------------------------------------------
# Decorator (cache.__call__)
# ---------------------------------------------------------------------------


def test_decorator_targets_cold_by_default() -> None:
    hot, cold, cache = _hot_cold()
    salt = "good"

    @cache(lambda x: f"key_{x}", cache_type=DataType.TEXT, ttl=datetime.timedelta(seconds=2))
    def compute(x: str) -> str:
        return f"{x}_{salt}"

    assert compute("a") == "a_good"

    salt = "bad"
    assert compute("a") == "a_good"   # served from cold cache

    assert cold.exists("key_a") is True
    assert hot.exists("key_a") is False   # hot not touched


def test_decorator_hot_tier() -> None:
    _, cold, cache = _hot_cold()
    calls = 0

    @cache.hot(lambda x: f"key_{x}", cache_type=DataType.JSON)
    def fast_lookup(x: str) -> dict:
        nonlocal calls
        calls += 1
        return {"v": x}

    assert fast_lookup("a") == {"v": "a"}
    assert calls == 1

    assert fast_lookup("a") == {"v": "a"}
    assert calls == 1  # served from hot cache

    assert cold.exists("key_a") is False  # cold not touched


def test_decorator_ttl_expiry() -> None:
    cache = _single_cold()
    salt = "good"

    @cache(lambda x: f"key_{x}", cache_type=DataType.TEXT, ttl=datetime.timedelta(seconds=1))
    def get_text(x: str) -> str:
        return f"data_{x}_{salt}"

    assert get_text("test") == "data_test_good"

    salt = "bad"
    assert get_text("test") == "data_test_good"  # still cached

    time.sleep(1)
    assert get_text("test") == "data_test_bad"   # expired, recomputed


def test_ttl_accepts_naive_created_at() -> None:
    """Older cache files stored naive ISO timestamps; TTL must still compare."""
    cache = _single_cold()
    cache.set_text("k", "v")
    adapter = cache.cold.adapter
    cached = adapter.get("k")
    adapter.set(
        "k",
        CachedData(
            key="k",
            data=cached.data,
            data_type=cached.data_type,
            created_at=datetime.datetime.now(datetime.UTC)
            .replace(tzinfo=None)
            .isoformat(),
        ),
    )
    assert cache.get("k", ttl=datetime.timedelta(days=1)) == "v"


def test_decorator_force_refresh() -> None:
    cache = _single_cold()
    counter = [0]

    @cache(lambda x: f"key_{x}", cache_type=DataType.JSON)
    def compute(x: str) -> dict:
        counter[0] += 1
        return {"count": counter[0]}

    assert compute("a") == {"count": 1}
    assert compute("a") == {"count": 1}           # from cache
    assert compute("a", force_cache_refresh=True) == {"count": 2}


def test_decorator_non_matching_key_builder_args() -> None:
    cache = _single_cold()

    @cache(lambda x, z: f"key_{x}_{z}", cache_type=DataType.TEXT)
    def fn(x: str, y: str, z: str = "toto") -> str:
        return f"{x}_{y}_{z}"

    assert fn("test", "test", "tati") == "test_test_tati"
    assert fn(x="test", y="tata", z="tutu") == "test_tata_tutu"
    assert fn(x="test", y="toto") == "test_toto_toto"
    # Cached (same x + z)
    assert fn(x="test", y="yolo") == "test_toto_toto"
    assert fn(x="test", y="yolo", force_cache_refresh=True) == "test_yolo_toto"


# ---------------------------------------------------------------------------
# Event emission
# ---------------------------------------------------------------------------


class _FakeEventService:
    def __init__(self) -> None:
        self.published: list = []

    def publish(self, event) -> None:
        self.published.append(event)


class _FakeServices:
    """Minimal stand-in for IEngine.Services exposing only what CacheService uses."""

    def __init__(self, events: _FakeEventService | None = None) -> None:
        self._events = events

    def events_available(self) -> bool:
        return self._events is not None

    @property
    def events(self) -> _FakeEventService:
        assert self._events is not None
        return self._events


def _wired_hot_cold():
    hot_adapter = CacheMemoryAdapter()
    cold_adapter = CacheMemoryAdapter()
    svc = CacheService(
        adapters=[(TIER_HOT, hot_adapter), (TIER_COLD, cold_adapter)]
    )
    events = _FakeEventService()
    svc.set_services(_FakeServices(events))
    return hot_adapter, cold_adapter, svc, events


def test_events_not_emitted_when_unwired() -> None:
    """No services attached → no exceptions, no events, normal operation."""
    cache = _single_cold()
    cache.set_json("k", {"v": 1})
    cache.delete("k")  # no crash even though no events service


def test_events_not_emitted_when_events_unavailable() -> None:
    cache = _single_cold()
    cache.set_services(_FakeServices(events=None))  # services wired but no events
    cache.set_json("k", {"v": 1})
    cache.delete("k")  # must not raise


def test_set_emits_cache_set_on_default_tier() -> None:
    _, _, cache, events = _wired_hot_cold()
    cache.set_json("k", {"v": 1})

    assert len(events.published) == 1
    evt = events.published[0]
    assert isinstance(evt, CacheSet)
    assert evt.key == "k"
    assert evt.tier == TIER_COLD
    assert evt.data_type == DataType.JSON.value
    assert evt.size_bytes == len('{"v": 1}')


def test_set_hot_emits_cache_set_with_hot_tier() -> None:
    _, _, cache, events = _wired_hot_cold()
    cache.hot.set_text("session", "abc")

    assert len(events.published) == 1
    evt = events.published[0]
    assert isinstance(evt, CacheSet)
    assert evt.tier == TIER_HOT
    assert evt.data_type == DataType.TEXT.value


def test_delete_emits_cache_deleted_per_tier_holding_the_key() -> None:
    _, _, cache, events = _wired_hot_cold()
    cache.hot.set_text("k", "x")
    cache.cold.set_text("k", "x")
    events.published.clear()

    cache.delete("k")

    deleted = [e for e in events.published if isinstance(e, CacheDeleted)]
    assert len(deleted) == 2
    assert {e.tier for e in deleted} == {TIER_HOT, TIER_COLD}


def test_delete_missing_does_not_emit() -> None:
    _, _, cache, events = _wired_hot_cold()
    cache.delete("never_set")

    assert events.published == []


def test_set_if_absent_only_emits_when_wrote() -> None:
    _, _, cache, events = _wired_hot_cold()

    assert cache.set_json_if_absent("k", {"v": 1}) is True
    events_after_first = list(events.published)
    assert len(events_after_first) == 1
    assert isinstance(events_after_first[0], CacheSet)

    assert cache.set_json_if_absent("k", {"v": 2}) is False
    # Still only the first event — no CacheSet emitted on the no-op
    assert len(events.published) == 1


def test_adapter_failure_emits_cache_error_and_reraises() -> None:
    cold_adapter = CacheMemoryAdapter()
    svc = CacheService(
        adapters=[(TIER_HOT, _BrokenAdapter()), (TIER_COLD, cold_adapter)]
    )
    events = _FakeEventService()
    svc.set_services(_FakeServices(events))

    # set on hot raises; CacheError must fire for the hot tier
    try:
        svc.hot.set_text("k", "v")
        assert False, "expected OSError"
    except OSError:
        pass

    errors = [e for e in events.published if isinstance(e, CacheError)]
    assert len(errors) == 1
    err = errors[0]
    assert err.tier == TIER_HOT
    assert err.operation == "set"
    assert err.key == "k"
    assert "Redis" in (err.message or "")


def test_publisher_exception_does_not_break_mutation() -> None:
    """If the EventService blows up, the cache write must still succeed."""

    class _ExplodingEvents:
        def publish(self, event):
            raise RuntimeError("event bus down")

    cache = _single_cold()
    cache.set_services(_FakeServices(events=_ExplodingEvents()))

    # Must not raise — cache write is authoritative, event publication is best-effort
    cache.set_json("k", {"v": 1})
    assert cache.get("k") == {"v": 1}


# ---------------------------------------------------------------------------
# Administration: listing, raw entries, named tiers
# ---------------------------------------------------------------------------


def _text(key: str) -> CachedData:
    return CachedData(key=key, data=f"value of {key}", data_type=DataType.TEXT)


def test_list_keys_merges_tiers_without_duplicates():
    hot, cold, svc = _hot_cold()
    for key in ("b", "d", "shared"):
        hot.set(key, _text(key))
    for key in ("a", "c", "shared", "e"):
        cold.set(key, _text(key))

    seen, after = [], None
    for _ in range(10):
        page = svc.list_keys(limit=2, after=after)
        seen += page.keys
        after = page.next_after
        if after is None:
            break

    assert seen == ["a", "b", "c", "d", "e", "shared"]
    assert svc.list_keys("s", limit=10).keys == ("shared",)


def test_list_keys_skips_an_unavailable_tier_but_not_all():
    cold, svc = _broken_hot_cold()
    cold.set("k", _text("k"))

    assert svc.list_keys(limit=10).keys == ("k",)

    with pytest.raises(OSError):
        CacheService(adapters=[(TIER_COLD, _BrokenAdapter())]).list_keys()


def test_get_entry_returns_the_stored_entry_and_its_tier_without_deserializing():
    class Explodes:
        def __reduce__(self):
            return (_never_called, ())

    hot, cold, svc = _hot_cold()
    cold.set("p", CachedData(key="p", data="", data_type=DataType.TEXT))
    svc.cold.set_pickle("p", Explodes())
    hot.set("h", _text("h"))
    cold.set("h", CachedData(key="h", data="stale", data_type=DataType.TEXT))

    pickled = svc.get_entry("p")
    hot_first = svc.get_entry("h")

    assert (pickled.tier, pickled.cached.data_type) == (TIER_COLD, DataType.PICKLE)
    assert isinstance(pickled.cached.data, str)  # still base64 text
    assert (hot_first.tier, hot_first.cached.data) == (TIER_HOT, "value of h")
    with pytest.raises(CacheNotFoundError):
        svc.get_entry("missing")


def _never_called():
    raise AssertionError("an admin read must never unpickle")


def test_named_tiers():
    _, _, svc = _hot_cold()

    assert svc.tier_names == (TIER_HOT, TIER_COLD)
    svc.tier(TIER_HOT).set_text("k", "v")
    assert svc.tier(TIER_HOT).get_entry("k").tier == TIER_HOT
    assert svc.tier(TIER_HOT).list_keys().keys == ("k",)
    with pytest.raises(ValueError):
        svc.tier("lukewarm")


def test_pickle_payload_is_valid_base64_of_a_pickle():
    # Guards the assumption above: set_pickle stores base64 text, decoded only by get().
    _, _, svc = _hot_cold()
    svc.cold.set_pickle("n", 42)
    import base64

    assert pickle.loads(base64.b64decode(svc.get_entry("n").cached.data)) == 42
