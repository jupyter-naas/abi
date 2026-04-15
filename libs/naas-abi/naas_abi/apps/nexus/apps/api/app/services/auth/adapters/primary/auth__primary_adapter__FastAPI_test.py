from __future__ import annotations

from types import SimpleNamespace
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


@pytest.mark.asyncio
async def test_send_magic_link_email_uses_configured_templates(monkeypatch) -> None:
    monkeypatch.setattr(settings, "smtp_enabled", True)
    monkeypatch.setattr(settings, "frontend_url", "https://platform.example.com")
    monkeypatch.setattr(settings, "magic_link_path", "/auth/magic-link")
    monkeypatch.setattr(settings, "magic_link_expire_minutes", 20)
    monkeypatch.setattr(settings, "magic_link_email_app_name", "ABI Platform")
    monkeypatch.setattr(settings, "magic_link_email_subject_template", "Login to {app_name}")
    monkeypatch.setattr(
        settings,
        "magic_link_email_text_template",
        "Open this link for {app_name}: {magic_link_url} (expires in {expire_minutes} min)",
    )
    monkeypatch.setattr(
        settings,
        "magic_link_email_html_template",
        '<p>{app_name}</p><a href="{magic_link_url}">open</a><p>{expire_minutes}</p>',
    )
    monkeypatch.setattr(settings, "smtp_host", "smtp.example.com")
    monkeypatch.setattr(settings, "smtp_port", 587)
    monkeypatch.setattr(settings, "smtp_username", "username")
    monkeypatch.setattr(settings, "smtp_password", "password")
    monkeypatch.setattr(settings, "smtp_use_tls", True)
    monkeypatch.setattr(settings, "smtp_use_ssl", False)
    monkeypatch.setattr(settings, "smtp_from_email", "no-reply@example.com")
    monkeypatch.setattr(settings, "smtp_from_name", "ABI")

    sent: dict = {}

    def _fake_factory(**_kwargs):
        return SimpleNamespace(send=lambda **kwargs: sent.update(kwargs))

    monkeypatch.setattr(auth_api.EmailFactory, "EmailServiceSMTP", _fake_factory)

    await auth_api._send_magic_link_email("user@example.com", "token-123")

    assert sent["subject"] == "Login to ABI Platform"
    assert "https://platform.example.com/auth/magic-link?token=token-123" in sent["text_body"]
    assert "ABI Platform" in sent["html_body"]
