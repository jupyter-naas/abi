"""SendGrid sends mail only from the configured senders."""

from __future__ import annotations

import asyncio
import json

import httpx
import pytest
from naas_abi_apps.sendgrid import ABIModule
from naas_abi_apps.sendgrid.agents.SendGridAgent import tools_for
from naas_abi_apps.sendgrid.integrations.SendGridIntegration import (
    SendGridIntegrationConfiguration,
    as_tools,
)


def recording(sent: list[dict]) -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        sent.append(json.loads(request.content))
        return httpx.Response(202)

    return httpx.MockTransport(handler)


def send(configuration: SendGridIntegrationConfiguration, sender: str) -> None:
    tools = {t.name: t for t in as_tools(configuration)}
    asyncio.run(
        tools["sendgrid_send_email"].ainvoke(
            {
                "from_email": sender,
                "to_emails": ["someone@example.com"],
                "subject": "Hello",
                "html_content": "<p>Hello</p>",
            }
        )
    )


def test_sendgrid_keeps_to_configured_senders() -> None:
    sent: list[dict] = []
    configuration = SendGridIntegrationConfiguration(
        api_key="k", transport=recording(sent), allowed_senders=["Team@Example.com"]
    )

    send(configuration, "team@example.com")
    with pytest.raises(ValueError):
        send(configuration, "someone-else@example.com")

    assert [body["from"]["email"] for body in sent] == ["team@example.com"]


def test_sendgrid_sends_nothing_without_configured_senders() -> None:
    sent: list[dict] = []
    configuration = SendGridIntegrationConfiguration(
        api_key="k", transport=recording(sent)
    )

    with pytest.raises(ValueError):
        send(configuration, "team@example.com")

    assert sent == []


def test_sendgrid_agent_sends_only_from_the_module_senders() -> None:
    module_configuration = ABIModule.Configuration(
        allowed_senders=" team@example.com , ops@example.com "
    )
    assert module_configuration.sender_list() == [
        "team@example.com",
        "ops@example.com",
    ]
    (send_tool,) = [
        t
        for t in tools_for({"api_key": "k"}, module_configuration.sender_list())
        if t.name == "sendgrid_send_email"
    ]
    assert send_tool is not None
    assert ABIModule.Configuration().sender_list() == []
