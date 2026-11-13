"""SendGrid sends mail only from the configured senders."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest
from naas_abi_marketplace.applications.sendgrid.integrations import (
    SendGridIntegration as sendgrid_mod,
)
from naas_abi_marketplace.applications.sendgrid.integrations.SendGridIntegration import (
    SendGridIntegrationConfiguration,
    as_tools,
)


@pytest.fixture
def sent(monkeypatch: pytest.MonkeyPatch) -> list[dict]:
    bodies: list[dict] = []

    def request(method: str, url: str, **kwargs: Any) -> Any:
        bodies.append(kwargs.get("json") or {})
        return SimpleNamespace(content=b"", raise_for_status=lambda: None)

    monkeypatch.setattr(sendgrid_mod.requests, "request", request)
    return bodies


def send(configuration: SendGridIntegrationConfiguration, sender: str) -> None:
    tools = {t.name: t for t in as_tools(configuration)}
    tools["sendgrid_send_email"].invoke(
        {
            "from_email": sender,
            "to_emails": ["someone@example.com"],
            "subject": "Hello",
            "html_content": "<p>Hello</p>",
        }
    )


def test_sendgrid_keeps_to_configured_senders(sent: list[dict]) -> None:
    configuration = SendGridIntegrationConfiguration(
        api_key="k",
        base_url="https://sendgrid.test",
        allowed_senders=["Team@Example.com"],
    )

    send(configuration, "team@example.com")
    with pytest.raises(ValueError):
        send(configuration, "someone-else@example.com")

    assert [body["from"]["email"] for body in sent] == ["team@example.com"]


def test_sendgrid_sends_nothing_without_configured_senders(sent: list[dict]) -> None:
    configuration = SendGridIntegrationConfiguration(api_key="k")

    with pytest.raises(ValueError):
        send(configuration, "team@example.com")

    assert sent == []
