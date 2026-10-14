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
    from naas_abi.apps.nexus.apps.api.app.core import database

    monkeypatch.setattr(database, "async_engine", engine)  # read at call time there
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


@pytest.mark.asyncio
async def test_a_logout_outlives_the_cleanup_of_its_session_token(
    engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Review round 1: device B's grant (valid 30 min) must stay ended after the
    cleanup job removes the row of device A's logged-out token (valid 2 min)."""
    from naas_abi.apps.nexus.apps.api.app.services.auth import service as auth_service

    monkeypatch.setattr(auth_service.settings, "secret_key", "s" * 32)
    device_b_grant = datetime.now(UTC)
    token, _ = auth_service.create_access_token({"sub": "u-1"}, timedelta(minutes=2))

    await auth_service.AuthService(adapter=None).logout_user("u-1", token)

    async with engine.begin() as conn:  # the cleanup job, 3 minutes later
        await conn.execute(
            text("DELETE FROM revoked_tokens WHERE expires_at < :later"),
            {"later": datetime.now(UTC).replace(tzinfo=None) + timedelta(minutes=3)},
        )
    revocation._latest.clear()
    assert await revocation.grant_revoked("u-1", device_b_grant)


@pytest.mark.asyncio
async def test_a_credential_issued_before_a_logout_or_revoked_mints_nothing(
    engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    from naas_abi.apps.nexus.apps.api.app.services.auth import service as auth_service

    monkeypatch.setattr(auth_service.settings, "secret_key", "s" * 32)
    older, _ = auth_service.create_access_token({"sub": "u-1"})
    claims = auth_service.decode_token(older)
    assert isinstance(claims["iat"], float)
    assert not await revocation.credential_revoked("u-1", claims)

    await revocation.revoke_remote_app_grants("u-1")  # a logout elsewhere
    assert await revocation.credential_revoked("u-1", claims)
    newer, _ = auth_service.create_access_token({"sub": "u-1"})
    assert not await revocation.credential_revoked("u-1", auth_service.decode_token(newer))

    await refresh_token.revoke_access_token(
        "jti-x", "u-2", datetime.now(UTC) + timedelta(minutes=5)
    )
    revocation._latest.clear()
    # The revoked token itself, even without an iat (minted before it existed).
    assert await revocation.credential_revoked("u-3", {"sub": "u-3", "jti": "jti-x"})
    assert not await revocation.credential_revoked("u-3", {"sub": "u-3", "jti": "jti-y"})
