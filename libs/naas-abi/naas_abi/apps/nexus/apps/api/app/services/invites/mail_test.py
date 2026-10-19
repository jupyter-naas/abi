from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from naas_abi.apps.nexus.apps.api.app.core.config import settings
from naas_abi.apps.nexus.apps.api.app.services.invites import mail
from naas_abi_core.engine.call_context import ANONYMOUS, current_call_context, use_call_context


def test_frontend_hostname_accepts_url_or_bare_host() -> None:
    assert mail.frontend_hostname("https://App.Dev.Example.com/path") == "app.dev.example.com"
    assert mail.frontend_hostname("app.dev.example.com") == "app.dev.example.com"
    assert mail.frontend_hostname("") == ""


def test_is_dev_frontend_from_hostname(monkeypatch) -> None:
    monkeypatch.setattr(settings, "nexus_env", "local")
    monkeypatch.setattr(settings, "frontend_url", "https://app.dev.example.com")
    assert mail.is_dev_frontend() is True

    monkeypatch.setattr(settings, "frontend_url", "https://app.example.dev")
    assert mail.is_dev_frontend() is True

    monkeypatch.setattr(settings, "frontend_url", "https://app.example.com")
    assert mail.is_dev_frontend() is False


def test_is_dev_frontend_from_nexus_env(monkeypatch) -> None:
    monkeypatch.setattr(settings, "frontend_url", "https://app.example.com")
    monkeypatch.setattr(settings, "nexus_env", "dev")
    assert mail.is_dev_frontend() is True

    monkeypatch.setattr(settings, "nexus_env", "local")
    assert mail.is_dev_frontend() is False


def test_apply_dev_subject_prefix_is_idempotent(monkeypatch) -> None:
    monkeypatch.setattr(settings, "frontend_url", "https://app.dev.example.com")
    monkeypatch.setattr(settings, "nexus_env", "local")
    assert mail.apply_dev_subject_prefix("Hello") == "[DEV] Hello"
    assert mail.apply_dev_subject_prefix("[DEV] Already marked") == "[DEV] Already marked"


def test_the_notice_says_who_added_you_where_and_where_to_sign_in(monkeypatch) -> None:
    monkeypatch.setattr(settings, "frontend_url", "https://app.example.com")
    monkeypatch.setattr(settings, "email_app_name", "ABI")

    subject, text, html = mail.render_added(
        inviter_name="Ada <script>",
        workspace_name="Research",
        workspace_role="viewer",
        organization_name="Acme",
        organization_role="member",
        to_email="bob+x@example.com",
    )

    assert subject == "You were added to Research on ABI"
    assert "a viewer of the workspace Research and a member of Acme" in text
    url = "https://app.example.com/auth/login?email=bob%2Bx%40example.com"
    assert url in text and url.replace("&", "&amp;") in html
    # No code, no token: signing in is the identity provider's.
    assert "code" not in text.lower() and "token" not in text.lower()
    assert "<script>" not in html and "&lt;script&gt;" in html


@pytest.mark.asyncio
async def test_the_notice_is_sent_as_nexus_for_no_workspace(monkeypatch) -> None:
    """The kept copy of a mail belongs to no workspace, whatever the request names."""
    monkeypatch.setattr(settings, "nexus_env", "local")
    monkeypatch.setattr(settings, "frontend_url", "https://app.example.com")
    seen = {}
    service = MagicMock()

    def send(**kwargs):
        context = current_call_context()
        seen.update(actor=context.principal.id, workspace=context.workspace_id, **kwargs)

    service.send.side_effect = send
    from dataclasses import replace

    with use_call_context(replace(ANONYMOUS, workspace_id="ws-from-the-request")):
        sent = await mail.send_added_notice(
            "bob@example.com", inviter_name="Ada", workspace_name="W", email_service=service
        )

    assert sent is True
    assert seen["actor"] == "api" and seen["workspace"] is None
    assert seen["to_email"] == "bob@example.com"


@pytest.mark.asyncio
async def test_without_an_email_service_nothing_is_sent(monkeypatch) -> None:
    monkeypatch.setattr(mail, "resolve_email_service", lambda: None)
    assert await mail.send_added_notice("bob@example.com", inviter_name=None) is False
