from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException
from naas_abi.apps.nexus.apps.api.app.core.config import settings
from naas_abi.apps.nexus.apps.api.app.services.auth.adapters.primary import (
    auth__primary_adapter__FastAPI as auth_api,
)


@pytest.mark.asyncio
async def test_request_magic_link_never_logs_token(monkeypatch, caplog) -> None:
    monkeypatch.setattr(settings, "smtp_enabled", False)
    auth_service = AsyncMock()
    auth_service.request_magic_link = AsyncMock(return_value="sensitive-magic-token")
    fake_request = type(
        "Req", (), {"headers": {}, "client": type("Client", (), {"host": "127.0.0.1"})()}
    )()

    response = await auth_api.request_magic_link(
        request=fake_request,
        payload=auth_api.MagicLinkRequest(email="user@example.com"),
        auth_service=auth_service,
    )

    assert response["status"] == "success"
    assert "sensitive-magic-token" not in caplog.text
    auth_service.request_magic_link.assert_awaited_once_with("user@example.com")


@pytest.mark.asyncio
async def test_request_magic_link_unknown_user_does_not_send_email(monkeypatch) -> None:
    monkeypatch.setattr(settings, "smtp_enabled", True)
    auth_service = AsyncMock()
    auth_service.request_magic_link = AsyncMock(return_value=None)
    fake_request = type(
        "Req", (), {"headers": {}, "client": type("Client", (), {"host": "127.0.0.1"})()}
    )()

    send_mock = AsyncMock()
    monkeypatch.setattr(auth_api, "_send_magic_link_email", send_mock)

    response = await auth_api.request_magic_link(
        request=fake_request,
        payload=auth_api.MagicLinkRequest(email="unknown@example.com"),
        auth_service=auth_service,
    )

    assert response["status"] == "success"
    send_mock.assert_not_awaited()


@pytest.mark.asyncio
async def test_login_disabled_when_password_auth_off(monkeypatch) -> None:
    monkeypatch.setattr(settings, "auth_password_enabled", False)

    with pytest.raises(HTTPException) as exc_info:
        await auth_api.login(
            credentials=auth_api.UserLogin(email="user@example.com", password="password"),
            request=type("Req", (), {"headers": {}, "client": None})(),
            auth_service=AsyncMock(),
        )

    assert exc_info.value.status_code == 410
