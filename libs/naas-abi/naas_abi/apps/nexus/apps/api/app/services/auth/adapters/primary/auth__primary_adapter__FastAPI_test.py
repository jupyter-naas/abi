from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException
from naas_abi.apps.nexus.apps.api.app.core.config import settings
from naas_abi.apps.nexus.apps.api.app.services.auth.adapters.primary import (
    auth__primary_adapter__FastAPI as auth_api,
)
from naas_abi.apps.nexus.apps.api.app.services.auth.service import MagicLinkChallenge


@pytest.mark.asyncio
async def test_request_magic_link_response_never_includes_secrets(monkeypatch) -> None:
    auth_service = AsyncMock()
    auth_service.request_magic_link = AsyncMock(
        return_value=MagicLinkChallenge(
            token="sensitive-magic-token",
            otp_code="123456",
            token_id="ml-1",
        )
    )
    fake_request = type(
        "Req", (), {"headers": {}, "client": type("Client", (), {"host": "127.0.0.1"})()}
    )()
    send_mock = AsyncMock()
    monkeypatch.setattr(auth_api, "_send_magic_link_email", send_mock)

    response = await auth_api.request_magic_link(
        request=fake_request,
        payload=auth_api.MagicLinkRequest(email="user@example.com"),
        auth_service=auth_service,
        email_service=SimpleNamespace(send=lambda **_: None),
    )

    assert response["status"] == "success"
    assert "sensitive-magic-token" not in str(response)
    assert "123456" not in str(response)
    send_mock.assert_awaited_once()
    auth_service.request_magic_link.assert_awaited_once_with("user@example.com")


@pytest.mark.asyncio
async def test_request_magic_link_revokes_challenge_when_email_fails(monkeypatch) -> None:
    auth_service = AsyncMock()
    auth_service.request_magic_link = AsyncMock(
        return_value=MagicLinkChallenge(
            token="sensitive-magic-token",
            otp_code="123456",
            token_id="ml-orphan",
        )
    )
    auth_service.invalidate_magic_link_challenge = AsyncMock()
    fake_request = type(
        "Req", (), {"headers": {}, "client": type("Client", (), {"host": "127.0.0.1"})()}
    )()

    async def _boom(*_args, **_kwargs):
        raise RuntimeError("smtp down")

    monkeypatch.setattr(auth_api, "_send_magic_link_email", _boom)

    with pytest.raises(RuntimeError, match="smtp down"):
        await auth_api.request_magic_link(
            request=fake_request,
            payload=auth_api.MagicLinkRequest(email="user@example.com"),
            auth_service=auth_service,
            email_service=SimpleNamespace(send=lambda **_: None),
        )

    auth_service.invalidate_magic_link_challenge.assert_awaited_once_with("ml-orphan")


@pytest.mark.asyncio
async def test_request_magic_link_unknown_user_does_not_send_email(monkeypatch) -> None:
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
        email_service=SimpleNamespace(send=lambda **_: None),
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
    monkeypatch.setattr(settings, "frontend_url", "https://platform.example.com")
    monkeypatch.setattr(settings, "magic_link_path", "/auth/magic-link")
    monkeypatch.setattr(settings, "magic_link_expire_minutes", 20)
    monkeypatch.setattr(settings, "magic_link_email_app_name", "ABI Platform")
    monkeypatch.setattr(
        settings,
        "magic_link_email_subject_template",
        "Login to {app_name}: {otp_code}",
    )
    monkeypatch.setattr(
        settings,
        "magic_link_email_text_template",
        "Code {otp_code}. Open this link for {app_name}: {magic_link_url} "
        "(expires in {expire_minutes} min)",
    )
    monkeypatch.setattr(
        settings,
        "magic_link_email_html_template",
        '<p>{app_name}</p><p>{otp_code}</p><a href="{magic_link_url}">open</a>'
        "<p>{expire_minutes}</p>",
    )
    monkeypatch.setattr(settings, "email_from_address", "no-reply@example.com")
    monkeypatch.setattr(settings, "email_from_name", "ABI")

    sent: dict = {}
    email_service = SimpleNamespace(send=lambda **kwargs: sent.update(kwargs))

    await auth_api._send_magic_link_email(
        "user@example.com", "token-123", "654321", email_service
    )

    assert sent["subject"] == "Login to ABI Platform: 654321"
    assert "654321" in sent["text_body"]
    assert "https://platform.example.com/auth/magic-link?token=token-123" in sent["text_body"]
    assert "ABI Platform" in sent["html_body"]
    assert sent["from_email"] == "no-reply@example.com"
    assert sent["from_name"] == "ABI"


@pytest.mark.asyncio
async def test_send_magic_link_email_logs_when_no_service(caplog, monkeypatch) -> None:
    import logging

    monkeypatch.setattr(settings, "log_otp_codes_when_email_unavailable", True)
    caplog.set_level(logging.INFO, logger=auth_api.logger.name)

    await auth_api._send_magic_link_email("user@example.com", "token-456", "111222", None)

    assert any(
        "Sign-in code for user@example.com" in record.message
        and "111222" in record.message
        and "token-456" in record.message
        for record in caplog.records
    )


# =============================================================================
# Dev auto-login exposure on /api/auth/config
# =============================================================================

@pytest.mark.asyncio
async def test_auth_config_omits_dev_credentials_by_default() -> None:
    """The default build must never hand credentials to an anonymous caller."""
    config = await auth_api.get_auth_config()

    assert "dev_autologin_email" not in config
    assert "dev_autologin_password" not in config


@pytest.mark.asyncio
async def test_auth_config_exposes_dev_credentials_when_enabled(monkeypatch) -> None:
    monkeypatch.setattr(settings, "dev_autologin_email", "admin@example.com")
    monkeypatch.setattr(settings, "dev_autologin_password", "generated-pw")

    config = await auth_api.get_auth_config()

    assert config["dev_autologin_email"] == "admin@example.com"
    assert config["dev_autologin_password"] == "generated-pw"


@pytest.mark.asyncio
async def test_auth_config_needs_both_halves(monkeypatch) -> None:
    """A half-configured pair must not produce a login the page can't complete."""
    monkeypatch.setattr(settings, "dev_autologin_email", "admin@example.com")
    monkeypatch.setattr(settings, "dev_autologin_password", "")

    config = await auth_api.get_auth_config()

    assert "dev_autologin_email" not in config
