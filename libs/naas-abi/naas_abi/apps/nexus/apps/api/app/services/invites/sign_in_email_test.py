from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from naas_abi.apps.nexus.apps.api.app.core.config import settings
from naas_abi.apps.nexus.apps.api.app.services.auth.service import MagicLinkChallenge
from naas_abi.apps.nexus.apps.api.app.services.invites import sign_in_email
from naas_abi.apps.nexus.apps.api.app.services.invites.sign_in_email import (
    ensure_user_and_send_invite_email,
    issue_and_send_invite_sign_in,
)

CHALLENGE = MagicLinkChallenge(token="tok", otp_code="123456", token_id="tid-1")


def _auth_service() -> AsyncMock:
    auth = AsyncMock()
    auth.request_magic_link.return_value = CHALLENGE
    return auth


@pytest.mark.asyncio
async def test_successful_send_keeps_the_challenge(monkeypatch) -> None:
    monkeypatch.setattr(sign_in_email, "send_invite_sign_in_email", AsyncMock(return_value=True))
    auth = _auth_service()

    sent = await issue_and_send_invite_sign_in(auth, "User@Example.com", email_service=MagicMock())

    assert sent is True
    auth.invalidate_magic_link_challenge.assert_not_called()


@pytest.mark.asyncio
async def test_raising_send_invalidates_the_undelivered_challenge(monkeypatch) -> None:
    monkeypatch.setattr(
        sign_in_email,
        "send_invite_sign_in_email",
        AsyncMock(side_effect=RuntimeError("smtp down")),
    )
    auth = _auth_service()

    with pytest.raises(RuntimeError):
        await issue_and_send_invite_sign_in(auth, "user@example.com", email_service=MagicMock())

    auth.invalidate_magic_link_challenge.assert_awaited_once_with("tid-1")


@pytest.mark.asyncio
async def test_undelivered_send_invalidates_the_challenge(monkeypatch) -> None:
    """No email transport: the code was never delivered, so it must not stay live."""
    monkeypatch.setattr(sign_in_email, "send_invite_sign_in_email", AsyncMock(return_value=False))
    auth = _auth_service()

    sent = await issue_and_send_invite_sign_in(auth, "user@example.com", email_service=None)

    assert sent is False
    auth.invalidate_magic_link_challenge.assert_awaited_once_with("tid-1")


@pytest.mark.asyncio
async def test_no_challenge_issued_reports_not_sent(monkeypatch) -> None:
    send = AsyncMock(return_value=True)
    monkeypatch.setattr(sign_in_email, "send_invite_sign_in_email", send)
    auth = _auth_service()
    auth.request_magic_link.return_value = None

    sent = await issue_and_send_invite_sign_in(auth, "user@example.com")

    assert sent is False
    send.assert_not_called()
    auth.invalidate_magic_link_challenge.assert_not_called()


@pytest.mark.asyncio
async def test_ensure_user_and_send_invite_email_reuses_the_guarded_path(monkeypatch) -> None:
    monkeypatch.setattr(sign_in_email, "send_invite_sign_in_email", AsyncMock(return_value=False))
    auth = _auth_service()
    auth.ensure_user_for_invite.return_value = (object(), True)

    result = await ensure_user_and_send_invite_email(
        auth, "user@example.com", name="User", email_service=MagicMock()
    )

    assert result == {"user_created": True, "sign_in_email_sent": False}
    auth.invalidate_magic_link_challenge.assert_awaited_once_with("tid-1")


def test_render_sign_in_email_embeds_private_host_logo_as_cid(monkeypatch, tmp_path) -> None:
    """*.localhost logo URLs are unreachable from mail clients — embed as cid:."""
    from naas_abi.apps.nexus.apps.api.app.core.config import TenantConfig

    seal = tmp_path / "Seal_of_U.S._Customs_and_Border_Protection.png"
    seal.write_bytes(b"\x89PNG\r\n\x1a\n" + b"fake-png-bytes")

    monkeypatch.setattr(
        settings,
        "tenant",
        TenantConfig(
            tab_title="AXI AI",
            logo_url=f"https://api.localhost/modules/report/assets/public/{seal.name}",
            primary_color="#00416A",
            accent_color="#1460AA",
        ),
    )
    monkeypatch.setattr(settings, "magic_link_email_app_name", "AXI AI")
    monkeypatch.setattr(
        settings,
        "magic_link_email_html_template",
        "<div>{logo_html}</div><a href=\"{magic_link_url}\">Sign in</a>",
    )
    monkeypatch.setattr(
        sign_in_email,
        "_try_load_seal_from_disk",
        lambda _url: seal.read_bytes(),
    )

    _subject, _text, html, attachments = sign_in_email.render_sign_in_email(
        magic_link_url="https://nexus.example/auth/magic-link?token=abc",
        otp_code="123456",
    )

    assert 'src="cid:sign-in-logo"' in html
    assert "api.localhost" not in html
    assert len(attachments) == 1
    assert attachments[0].is_inline is True
    assert attachments[0].content_id == "sign-in-logo"
    assert attachments[0].content.startswith(b"\x89PNG")
