from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import datetime, timedelta

import pytest
import pytest_asyncio
from fastapi import HTTPException
from naas_abi.apps.nexus.apps.api.app.services import rate_limit
from naas_abi.apps.nexus.apps.api.app.services.rate_limit.adapters.secondary.memory import (
    MemoryRateLimitStore,
)
from naas_abi.apps.nexus.apps.api.app.services.rate_limit.adapters.secondary.sql import (
    SqlRateLimitStore,
)
from naas_abi.apps.nexus.apps.api.app.services.rate_limit.port import RateLimitStorePort
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

NOW = datetime(2026, 11, 17, 12, 0, 0)


@pytest_asyncio.fixture(params=["sql", "memory"])
async def store(request: pytest.FixtureRequest) -> AsyncIterator[RateLimitStorePort]:
    """Each adapter of the port: the SQL one on the migration's table, and memory."""
    if request.param == "memory":
        yield MemoryRateLimitStore()
        return
    engine = create_async_engine("sqlite+aiosqlite://")
    async with engine.begin() as conn:
        await conn.execute(
            text(
                "CREATE TABLE rate_limit_events "
                "(id TEXT PRIMARY KEY, identifier TEXT, endpoint TEXT, created_at TIMESTAMP)"
            )
        )
    yield SqlRateLimitStore(engine)
    await engine.dispose()


@pytest.fixture
def enabled(store: RateLimitStorePort, monkeypatch: pytest.MonkeyPatch) -> RateLimitStorePort:
    monkeypatch.setattr(rate_limit, "_store", store)
    monkeypatch.setattr(rate_limit.settings, "rate_limit_enabled", True)
    return store


# -- the port's contract --------------------------------------------------------


@pytest.mark.asyncio
async def test_counts_attempts_at_or_after_the_start_of_the_window(store) -> None:
    await store.record("ip:1", "/login", NOW - timedelta(minutes=10))
    await store.record("ip:1", "/login", NOW - timedelta(minutes=5))
    await store.record("ip:1", "/login", NOW)

    assert await store.count_since("ip:1", "/login", NOW - timedelta(minutes=5)) == 2
    assert await store.count_since("ip:1", "/login", NOW + timedelta(seconds=1)) == 0


@pytest.mark.asyncio
async def test_counts_per_identifier_and_endpoint(store) -> None:
    await store.record("ip:1", "/login", NOW)
    await store.record("ip:2", "/login", NOW)
    await store.record("ip:1", "/otp", NOW)

    assert await store.count_since("ip:1", "/login", NOW) == 1


@pytest.mark.asyncio
async def test_prune_forgets_only_older_attempts(store) -> None:
    await store.record("ip:1", "/login", NOW - timedelta(days=2))
    await store.record("ip:1", "/login", NOW)

    await store.prune(NOW - timedelta(days=1))

    assert await store.count_since("ip:1", "/login", NOW - timedelta(days=3)) == 1


# -- the service ----------------------------------------------------------------


@pytest.mark.asyncio
async def test_the_limit_applies_to_recorded_attempts_only(enabled) -> None:
    for _ in range(3):
        await rate_limit.ensure_under_limit("email:a@example.com", "/login", limit=3)
        await rate_limit.record_attempt("email:a@example.com", "/login")

    with pytest.raises(HTTPException) as exc_info:
        await rate_limit.ensure_under_limit("email:a@example.com", "/login", limit=3)

    assert exc_info.value.status_code == 429


@pytest.mark.asyncio
async def test_limits_are_per_identifier_and_endpoint(enabled) -> None:
    for _ in range(3):
        await rate_limit.record_attempt("email:a@example.com", "/login")

    await rate_limit.ensure_under_limit("email:b@example.com", "/login", limit=3)
    await rate_limit.ensure_under_limit("email:a@example.com", "/otp", limit=3)


@pytest.mark.asyncio
async def test_check_rate_limit_counts_every_call(enabled) -> None:
    await rate_limit.check_rate_limit("ip:1", "/register", limit=2)
    await rate_limit.check_rate_limit("ip:1", "/register", limit=2)

    with pytest.raises(HTTPException):
        await rate_limit.check_rate_limit("ip:1", "/register", limit=2)


@pytest.mark.asyncio
async def test_nothing_is_counted_when_rate_limiting_is_off(store, monkeypatch) -> None:
    monkeypatch.setattr(rate_limit, "_store", store)
    monkeypatch.setattr(rate_limit.settings, "rate_limit_enabled", False)

    await rate_limit.check_rate_limit("ip:1", "/register", limit=1)
    await rate_limit.check_rate_limit("ip:1", "/register", limit=1)

    assert await store.count_since("ip:1", "/register", NOW - timedelta(days=3650)) == 0
