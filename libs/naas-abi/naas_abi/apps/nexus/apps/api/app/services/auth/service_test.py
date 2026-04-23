from __future__ import annotations

from datetime import datetime
from unittest.mock import AsyncMock

import pytest
from naas_abi.apps.nexus.apps.api.app.core.config import settings
from naas_abi.apps.nexus.apps.api.app.services.auth.port import AuthUserRecord
from naas_abi.apps.nexus.apps.api.app.services.auth.service import (
    AuthService,
    InvalidMagicLinkError,
    PasswordAuthenticationDisabledError,
)
from naas_abi.apps.nexus.apps.api.app.services.refresh_token import hash_token


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

    raw_token = await service.request_magic_link("USER@EXAMPLE.COM")

    assert raw_token
    adapter.mark_unused_magic_link_tokens_used.assert_awaited_once_with(
        "user-1",
        keep_latest_unused=4,
    )
    adapter.create_magic_link_token.assert_awaited_once()
    stored_token = adapter.create_magic_link_token.await_args.kwargs["token"]
    assert stored_token == hash_token(raw_token)
    assert stored_token != raw_token


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

    raw_token = await service.request_magic_link("user@example.com")

    assert raw_token
    adapter.mark_unused_magic_link_tokens_used.assert_awaited_once_with(
        "user-1",
        keep_latest_unused=0,
    )


@pytest.mark.asyncio
async def test_request_magic_link_for_unknown_user_does_not_create_account() -> None:
    adapter = AsyncMock()
    adapter.get_user_by_email.return_value = None
    service = AuthService(adapter=adapter)

    token = await service.request_magic_link("unknown@example.com")

    assert token is None
    adapter.create_user_with_personal_workspace.assert_not_called()
    adapter.create_magic_link_token.assert_not_called()
    adapter.commit.assert_not_called()


@pytest.mark.asyncio
async def test_request_magic_link_for_unknown_user_creates_account_when_enabled(
    monkeypatch,
) -> None:
    monkeypatch.setattr(settings, "magic_link_allow_signup", True)
    adapter = AsyncMock()
    adapter.get_user_by_email.return_value = None
    adapter.create_user_with_personal_workspace.return_value = AuthUserRecord(
        id="user-2",
        email="unknown@example.com",
        name="Unknown",
        hashed_password="hashed",
        created_at=datetime.utcnow(),
    )
    service = AuthService(adapter=adapter)

    token = await service.request_magic_link("unknown@example.com")

    assert token
    adapter.create_user_with_personal_workspace.assert_awaited_once()
    adapter.create_magic_link_token.assert_awaited_once()
    adapter.commit.assert_awaited_once()


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
