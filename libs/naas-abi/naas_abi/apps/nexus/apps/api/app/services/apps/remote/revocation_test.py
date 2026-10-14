from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
import pytest_asyncio
from naas_abi.apps.nexus.apps.api.app.services import refresh_token
from naas_abi.apps.nexus.apps.api.app.services.apps.remote import revocation
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine


@pytest_asyncio.fixture
async def engine(monkeypatch: pytest.MonkeyPatch):
    engine = create_async_engine("sqlite+aiosqlite://")
    async with engine.begin() as conn:
        await conn.execute(
            text(
                "CREATE TABLE revoked_tokens (jti TEXT PRIMARY KEY, user_id TEXT, "
                "revoked_at TIMESTAMP, revoked_reason TEXT, expires_at TIMESTAMP)"
            )
        )
        await conn.execute(
            text(
                "CREATE TABLE refresh_tokens (id TEXT PRIMARY KEY, user_id TEXT, "
                "revoked_at TIMESTAMP, revoked_reason TEXT)"
            )
        )
    monkeypatch.setattr(revocation, "async_engine", engine)
    monkeypatch.setattr(refresh_token, "async_engine", engine)
    monkeypatch.setattr(revocation, "_latest", {})
    yield engine
    await engine.dispose()


@pytest.mark.asyncio
async def test_a_logout_ends_the_grants_issued_before_it(engine) -> None:
    before = datetime.now(UTC)
    assert not await revocation.grant_revoked("u-1", before)

    await refresh_token.revoke_access_token(
        "jti-1", "u-1", datetime.now(UTC) + timedelta(minutes=30), reason="logout"
    )
    revocation._latest.clear()  # past the cache

    assert await revocation.grant_revoked("u-1", before)
    assert not await revocation.grant_revoked("u-1", datetime.now(UTC))
    assert not await revocation.grant_revoked("u-2", before)


@pytest.mark.asyncio
async def test_a_user_can_end_every_grant_at_once(engine) -> None:
    before = datetime.now(UTC)

    await revocation.revoke_remote_app_grants("u-1")

    assert await revocation.grant_revoked("u-1", before)
    async with engine.begin() as conn:
        row = (
            await conn.execute(text("SELECT revoked_reason, expires_at FROM revoked_tokens"))
        ).one()
    assert row[0] == revocation.REASON
    # The cleanup job keeps it as long as a grant lives, then removes it.
    expires = datetime.fromisoformat(row[1]) if isinstance(row[1], str) else row[1]
    assert expires - datetime.now(UTC).replace(tzinfo=None) > timedelta(hours=23)


@pytest.mark.asyncio
async def test_a_password_change_ends_the_grants_too(engine) -> None:
    before = datetime.now(UTC)

    await refresh_token.revoke_all_user_tokens("u-1", reason="password_change")

    assert await revocation.grant_revoked("u-1", before)


@pytest.mark.asyncio
async def test_answers_are_cached_briefly(engine, monkeypatch: pytest.MonkeyPatch) -> None:
    before = datetime.now(UTC)
    assert not await revocation.grant_revoked("u-1", before)
    async with engine.begin() as conn:
        await conn.execute(
            text("INSERT INTO revoked_tokens VALUES ('jti-2', 'u-1', :now, 'logout', :now)"),
            {"now": datetime.now(UTC).replace(tzinfo=None)},
        )

    assert not await revocation.grant_revoked("u-1", before)  # within CACHE_SECONDS
    monkeypatch.setattr(revocation, "CACHE_SECONDS", 0.0)
    assert await revocation.grant_revoked("u-1", before)
