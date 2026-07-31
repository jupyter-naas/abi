from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
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
