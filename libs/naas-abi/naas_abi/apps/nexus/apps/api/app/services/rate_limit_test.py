from __future__ import annotations

import pytest
import pytest_asyncio
from fastapi import HTTPException
from naas_abi.apps.nexus.apps.api.app.services import rate_limit
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine


@pytest_asyncio.fixture
async def engine(monkeypatch: pytest.MonkeyPatch):
    engine = create_async_engine("sqlite+aiosqlite://")
    async with engine.begin() as conn:
        await conn.execute(
            text(
                "CREATE TABLE rate_limit_events "
                "(id TEXT PRIMARY KEY, identifier TEXT, endpoint TEXT, created_at TIMESTAMP)"
            )
        )
    monkeypatch.setattr(rate_limit, "async_engine", engine)
    monkeypatch.setattr(rate_limit.settings, "rate_limit_enabled", True)
    yield engine
    await engine.dispose()


@pytest.mark.asyncio
async def test_the_limit_applies_to_recorded_attempts_only(engine) -> None:
    for _ in range(3):
        await rate_limit.ensure_under_limit("email:a@example.com", "/login", limit=3)
        await rate_limit.record_attempt("email:a@example.com", "/login")

    with pytest.raises(HTTPException) as exc_info:
        await rate_limit.ensure_under_limit("email:a@example.com", "/login", limit=3)

    assert exc_info.value.status_code == 429


@pytest.mark.asyncio
async def test_limits_are_per_identifier_and_endpoint(engine) -> None:
    for _ in range(3):
        await rate_limit.record_attempt("email:a@example.com", "/login")

    await rate_limit.ensure_under_limit("email:b@example.com", "/login", limit=3)
    await rate_limit.ensure_under_limit("email:a@example.com", "/otp", limit=3)


@pytest.mark.asyncio
async def test_check_rate_limit_counts_every_call(engine) -> None:
    await rate_limit.check_rate_limit("ip:1", "/register", limit=2)
    await rate_limit.check_rate_limit("ip:1", "/register", limit=2)

    with pytest.raises(HTTPException):
        await rate_limit.check_rate_limit("ip:1", "/register", limit=2)
