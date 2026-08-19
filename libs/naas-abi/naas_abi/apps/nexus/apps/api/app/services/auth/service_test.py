from __future__ import annotations

from datetime import datetime
from unittest.mock import AsyncMock

import pytest
from naas_abi.apps.nexus.apps.api.app.core.config import settings
from naas_abi.apps.nexus.apps.api.app.services.auth.port import (
    AuthUserRecord,
    MagicLinkTokenRecord,
)
from naas_abi.apps.nexus.apps.api.app.services.auth.service import (
    AuthService,
    InvalidMagicLinkError,
    InvalidOtpError,
    PasswordAuthenticationDisabledError,
)
from naas_abi.apps.nexus.apps.api.app.services.refresh_token import hash_otp_code, hash_token


@pytest.mark.asyncio
async def test_forgot_password_stores_hashed_token(monkeypatch) -> None:
    monkeypatch.setattr(settings, "auth_password_enabled", True)
    adapter = AsyncMock()
    adapter.get_user_by_email.return_value = AuthUserRecord(
        id="user-1",
        email="user@example.com",
        name="User",
        hashed_password="hashed",
        created_at=datetime.utcnow(),
    )

    service = AuthService(adapter=adapter)
    raw_token = await service.forgot_password("USER@EXAMPLE.COM")

    assert raw_token is not None
    assert raw_token != ""
    adapter.create_password_reset_token.assert_awaited_once()
    stored_token = adapter.create_password_reset_token.await_args.kwargs["token"]
    assert stored_token == hash_token(raw_token)
    assert stored_token != raw_token


@pytest.mark.asyncio
async def test_forgot_password_for_unknown_user_does_not_store_token(monkeypatch) -> None:
    monkeypatch.setattr(settings, "auth_password_enabled", True)
    adapter = AsyncMock()
    adapter.get_user_by_email.return_value = None
    service = AuthService(adapter=adapter)

    token = await service.forgot_password("unknown@example.com")

    assert token is None
    adapter.create_password_reset_token.assert_not_called()
    adapter.commit.assert_not_called()


@pytest.mark.asyncio
async def test_request_magic_link_stores_hashed_token(monkeypatch) -> None:
    monkeypatch.setattr(settings, "magic_link_max_active", 5)
    adapter = AsyncMock()
    adapter.get_user_by_email.return_value = AuthUserRecord(
        id="user-1",
        email="user@example.com",
        name="User",
        hashed_password="hashed",
        created_at=datetime.utcnow(),
    )
    service = AuthService(adapter=adapter)

    challenge = await service.request_magic_link("USER@EXAMPLE.COM")

    assert challenge
    assert len(challenge.otp_code) == settings.otp_code_length
    adapter.mark_unused_magic_link_tokens_used.assert_awaited_once_with(
        "user-1",
        keep_latest_unused=4,
    )
    adapter.create_magic_link_token.assert_awaited_once()
    stored_token = adapter.create_magic_link_token.await_args.kwargs["token"]
    assert stored_token == hash_token(challenge.token)
    assert stored_token != challenge.token
    stored_otp = adapter.create_magic_link_token.await_args.kwargs["otp_code_hash"]
    assert stored_otp == hash_otp_code(challenge.otp_code)
    assert stored_otp != challenge.otp_code


@pytest.mark.asyncio
async def test_request_magic_link_with_non_positive_max_active_invalidates_all(monkeypatch) -> None:
    monkeypatch.setattr(settings, "magic_link_max_active", 0)
    adapter = AsyncMock()
    adapter.get_user_by_email.return_value = AuthUserRecord(
        id="user-1",
        email="user@example.com",
        name="User",
        hashed_password="hashed",
        created_at=datetime.utcnow(),
    )
    service = AuthService(adapter=adapter)

    challenge = await service.request_magic_link("user@example.com")

    assert challenge
    adapter.mark_unused_magic_link_tokens_used.assert_awaited_once_with(
        "user-1",
        keep_latest_unused=0,
    )


@pytest.mark.asyncio
async def test_request_magic_link_for_unknown_user_does_not_create_account(
    monkeypatch,
) -> None:
    monkeypatch.setattr(settings, "magic_link_allow_signup", False)
    adapter = AsyncMock()
    adapter.get_user_by_email.return_value = None
    service = AuthService(adapter=adapter)

    challenge = await service.request_magic_link("unknown@example.com")

    assert challenge is None
    adapter.create_user.assert_not_called()
    adapter.create_user_with_default_workspace.assert_not_called()
    adapter.create_magic_link_token.assert_not_called()
    adapter.commit.assert_not_called()


@pytest.mark.asyncio
async def test_ensure_user_for_invite_creates_user_without_workspace() -> None:
    adapter = AsyncMock()
    adapter.get_user_by_email.return_value = None
    adapter.create_user.return_value = AuthUserRecord(
        id="user-new",
        email="new@example.com",
        name="New",
        hashed_password="hashed",
        created_at=datetime.utcnow(),
    )
    service = AuthService(adapter=adapter)

    user, created = await service.ensure_user_for_invite(
        "NEW@example.com", name="Emma Petit"
    )

    assert created is True
    assert user.id == "user-new"
    adapter.create_user.assert_awaited_once()
    assert adapter.create_user.await_args.kwargs["name"] == "Emma Petit"
    adapter.create_user_with_default_workspace.assert_not_called()
    adapter.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_ensure_user_for_invite_returns_existing_account() -> None:
    adapter = AsyncMock()
    adapter.get_user_by_email.return_value = AuthUserRecord(
        id="user-1",
        email="user@example.com",
        name="User",
        hashed_password="hashed",
        created_at=datetime.utcnow(),
    )
    service = AuthService(adapter=adapter)

    user, created = await service.ensure_user_for_invite("user@example.com")

    assert created is False
    assert user.id == "user-1"
    adapter.create_user.assert_not_called()
    adapter.create_user_with_default_workspace.assert_not_called()


@pytest.mark.asyncio
async def test_request_magic_link_public_signup_creates_default_workspace(
    monkeypatch,
) -> None:
    monkeypatch.setattr(settings, "magic_link_allow_signup", True)
    adapter = AsyncMock()
    adapter.get_user_by_email.return_value = None
    adapter.create_user_with_default_workspace.return_value = AuthUserRecord(
        id="user-2",
        email="unknown@example.com",
        name="Unknown",
        hashed_password="hashed",
        created_at=datetime.utcnow(),
    )
    service = AuthService(adapter=adapter)

    challenge = await service.request_magic_link("unknown@example.com")

    assert challenge
    adapter.create_user_with_default_workspace.assert_awaited_once()
    assert (
        adapter.create_user_with_default_workspace.await_args.kwargs["name"] == "Unknown"
    )
    adapter.create_user.assert_not_called()
    adapter.create_magic_link_token.assert_awaited_once()
    adapter.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_request_magic_link_create_if_missing_true_skips_workspace(
    monkeypatch,
) -> None:
    monkeypatch.setattr(settings, "magic_link_allow_signup", False)
    adapter = AsyncMock()
    adapter.get_user_by_email.return_value = None
    adapter.create_user.return_value = AuthUserRecord(
        id="user-3",
        email="invitee@example.com",
        name="Invitee",
        hashed_password="hashed",
        created_at=datetime.utcnow(),
    )
    service = AuthService(adapter=adapter)

    challenge = await service.request_magic_link(
        "invitee@example.com", create_if_missing=True
    )

    assert challenge
    adapter.create_user.assert_awaited_once()
    adapter.create_user_with_default_workspace.assert_not_called()
    adapter.create_magic_link_token.assert_awaited_once()


@pytest.mark.asyncio
async def test_verify_magic_link_rejects_unknown_token() -> None:
    adapter = AsyncMock()
    adapter.get_magic_link_token.return_value = None
    service = AuthService(adapter=adapter)

    with pytest.raises(InvalidMagicLinkError):
        await service.verify_magic_link("token", user_agent=None, ip_address=None)


@pytest.mark.asyncio
async def test_password_login_disabled(monkeypatch) -> None:
    monkeypatch.setattr(settings, "auth_password_enabled", False)
    adapter = AsyncMock()
    service = AuthService(adapter=adapter)

    with pytest.raises(PasswordAuthenticationDisabledError):
        await service.login_user("user@example.com", "pass", None, None)


@pytest.mark.asyncio
async def test_verify_otp_accepts_valid_code(monkeypatch) -> None:
    monkeypatch.setattr(settings, "otp_code_length", 6)
    monkeypatch.setattr(settings, "otp_max_attempts", 5)
    code = "482913"
    adapter = AsyncMock()
    adapter.get_user_by_email.return_value = AuthUserRecord(
        id="user-1",
        email="user@example.com",
        name="User",
        hashed_password="hashed",
        created_at=datetime.utcnow(),
    )
    adapter.list_unused_magic_links_for_user.return_value = [
        MagicLinkTokenRecord(
            id="ml-1",
            user_id="user-1",
            token="link-hash",
            expires_at=datetime.utcnow().replace(year=2099),
            used=False,
            created_at=datetime.utcnow(),
            otp_code_hash=hash_otp_code(code),
            otp_attempts=0,
        )
    ]
    monkeypatch.setattr(
        "naas_abi.apps.nexus.apps.api.app.services.auth.service.create_refresh_token",
        AsyncMock(return_value="refresh"),
    )
    monkeypatch.setattr(
        "naas_abi.apps.nexus.apps.api.app.services.auth.service.create_access_token",
        lambda data, expires_delta=None: ("access", "jti"),
    )
    service = AuthService(adapter=adapter)

    user, tokens = await service.verify_otp(
        email="USER@example.com",
        code=code,
        user_agent=None,
        ip_address=None,
    )

    assert user.id == "user-1"
    assert tokens.access_token == "access"
    adapter.mark_magic_link_token_used.assert_awaited_with("ml-1")


@pytest.mark.asyncio
async def test_verify_otp_matches_older_challenge_when_newer_unused_exists(
    monkeypatch,
) -> None:
    """Recreate/retry can leave a newer unused row that shadows the emailed OTP."""
    monkeypatch.setattr(settings, "otp_code_length", 6)
    monkeypatch.setattr(settings, "otp_max_attempts", 5)
    emailed_code = "926740"
    adapter = AsyncMock()
    adapter.get_user_by_email.return_value = AuthUserRecord(
        id="user-1",
        email="user@example.com",
        name="User",
        hashed_password="hashed",
        created_at=datetime.utcnow(),
    )
    adapter.list_unused_magic_links_for_user.return_value = [
        MagicLinkTokenRecord(
            id="ml-newer",
            user_id="user-1",
            token="newer-hash",
            expires_at=datetime.utcnow().replace(year=2099),
            used=False,
            created_at=datetime.utcnow(),
            otp_code_hash=hash_otp_code("111111"),
            otp_attempts=0,
        ),
        MagicLinkTokenRecord(
            id="ml-emailed",
            user_id="user-1",
            token="emailed-hash",
            expires_at=datetime.utcnow().replace(year=2099),
            used=False,
            created_at=datetime.utcnow(),
            otp_code_hash=hash_otp_code(emailed_code),
            otp_attempts=0,
        ),
    ]
    monkeypatch.setattr(
        "naas_abi.apps.nexus.apps.api.app.services.auth.service.create_refresh_token",
        AsyncMock(return_value="refresh"),
    )
    monkeypatch.setattr(
        "naas_abi.apps.nexus.apps.api.app.services.auth.service.create_access_token",
        lambda data, expires_delta=None: ("access", "jti"),
    )
    service = AuthService(adapter=adapter)

    user, tokens = await service.verify_otp(
        email="user@example.com",
        code=emailed_code,
        user_agent=None,
        ip_address=None,
    )

    assert user.id == "user-1"
    assert tokens.access_token == "access"
    adapter.mark_magic_link_token_used.assert_awaited_with("ml-emailed")
    adapter.increment_magic_link_otp_attempts.assert_not_awaited()


@pytest.mark.asyncio
async def test_verify_otp_rejects_wrong_code_and_increments(monkeypatch) -> None:
    monkeypatch.setattr(settings, "otp_code_length", 6)
    monkeypatch.setattr(settings, "otp_max_attempts", 5)
    adapter = AsyncMock()
    adapter.get_user_by_email.return_value = AuthUserRecord(
        id="user-1",
        email="user@example.com",
        name="User",
        hashed_password="hashed",
        created_at=datetime.utcnow(),
    )
    adapter.list_unused_magic_links_for_user.return_value = [
        MagicLinkTokenRecord(
            id="ml-1",
            user_id="user-1",
            token="link-hash",
            expires_at=datetime.utcnow().replace(year=2099),
            used=False,
            created_at=datetime.utcnow(),
            otp_code_hash=hash_otp_code("111111"),
            otp_attempts=0,
        )
    ]
    adapter.increment_magic_link_otp_attempts.return_value = 1
    service = AuthService(adapter=adapter)

    with pytest.raises(InvalidOtpError):
        await service.verify_otp(
            email="user@example.com",
            code="000000",
            user_agent=None,
            ip_address=None,
        )

    adapter.increment_magic_link_otp_attempts.assert_awaited_once_with("ml-1")
    adapter.mark_magic_link_token_used.assert_not_awaited()
