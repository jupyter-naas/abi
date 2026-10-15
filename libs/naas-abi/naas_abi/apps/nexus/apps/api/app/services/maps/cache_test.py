from __future__ import annotations

import asyncio
import datetime

from naas_abi.apps.nexus.apps.api.app.services.maps.cache import MapsCache
from naas_abi_core.services.cache.adapters.secondary.CacheFSAdapter import CacheFSAdapter
from naas_abi_core.services.cache.CacheService import TIER_COLD, TIER_HOT, CacheService

TTL = datetime.timedelta(seconds=30)


def _engine_cache(tmp_path) -> CacheService:
    return CacheService(
        adapters=[
            (TIER_HOT, CacheFSAdapter(str(tmp_path / "hot"))),
            (TIER_COLD, CacheFSAdapter(str(tmp_path / "cold"))),
        ]
    )


def test_values_live_in_the_engine_hot_tier(tmp_path) -> None:
    engine = _engine_cache(tmp_path)
    cache = MapsCache(engine)
    cache.set_json("k", {"a": 1})
    assert cache.get_json("k", TTL) == {"a": 1}
    assert engine.hot.get("k") == {"a": 1}
    assert not engine.cold.exists("k")  # the cold tier is object storage: never used here
    cache.set_binary("b", b"\x00bytes")
    assert cache.get_binary("b", TTL) == b"\x00bytes"
    cache.delete("k")
    assert cache.get_json("k", TTL) is None


def test_expired_and_missing_entries_are_misses(tmp_path) -> None:
    cache = MapsCache(_engine_cache(tmp_path))
    cache.set_json("k", {"a": 1})
    assert cache.get_json("k", datetime.timedelta(seconds=-1)) is None
    assert cache.get_json("absent", TTL) is None


def test_without_a_hot_tier_nothing_is_cached(tmp_path) -> None:
    cold_only = CacheService(adapters=[(TIER_COLD, CacheFSAdapter(str(tmp_path)))])
    for cache in (MapsCache(cold_only), MapsCache(None)):
        cache.set_json("k", {"a": 1})
        assert cache.get_json("k", TTL) is None


def test_concurrent_misses_share_one_load(tmp_path) -> None:
    cache = MapsCache(_engine_cache(tmp_path))
    calls = 0

    async def load() -> dict:
        nonlocal calls
        calls += 1
        await asyncio.sleep(0.01)
        return {"role": "member"}

    async def run() -> list[dict]:
        return await asyncio.gather(*(cache.json_or_load("k", TTL, load) for _ in range(30)))

    assert asyncio.run(run()) == [{"role": "member"}] * 30
    assert calls == 1
    # Then served from the engine cache.
    assert asyncio.run(cache.json_or_load("k", TTL, load)) == {"role": "member"}
    assert calls == 1


def test_failed_loads_are_not_kept(tmp_path) -> None:
    cache = MapsCache(_engine_cache(tmp_path))

    async def fail() -> dict:
        raise LookupError("nope")

    async def ok() -> dict:
        return {"v": 1}

    import pytest

    with pytest.raises(LookupError):
        asyncio.run(cache.json_or_load("k", TTL, fail))
    assert asyncio.run(cache.json_or_load("k", TTL, ok)) == {"v": 1}


def test_membership_is_checked_once_per_user_and_workspace(tmp_path) -> None:
    cache = MapsCache(_engine_cache(tmp_path))
    calls = 0

    async def check() -> str:
        nonlocal calls
        calls += 1
        return "member"

    async def run() -> None:
        await asyncio.gather(*(cache.member("u-1", "ws-1", check) for _ in range(10)))
        await cache.member("u-1", "ws-1", check)

    asyncio.run(run())
    assert calls == 1
