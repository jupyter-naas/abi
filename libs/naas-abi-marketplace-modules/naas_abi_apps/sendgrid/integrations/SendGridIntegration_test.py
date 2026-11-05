"""Offline tests of the SendGrid integration: an httpx MockTransport."""

from __future__ import annotations

import asyncio
import json

import httpx
from naas_abi_apps.sendgrid.integrations.SendGridIntegration import (
    SendGridIntegration,
    SendGridIntegrationConfiguration,
    as_tools,
)


def integration_for(handler, **kwargs) -> SendGridIntegration:
    return SendGridIntegration(
        SendGridIntegrationConfiguration(
            api_key="k", transport=httpx.MockTransport(handler), **kwargs
        )
    )


def test_send_email_puts_plain_text_first() -> None:
    bodies: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v3/mail/send"
        assert request.headers["Authorization"] == "Bearer k"
        bodies.append(json.loads(request.content))
        return httpx.Response(202)

    result = asyncio.run(
        integration_for(handler).send_email(
            "a@x.io", ["b@y.io"], "Hi", "<p>Hi</p>", "Hi"
        )
    )

    assert result == {}
    assert [c["type"] for c in bodies[0]["content"]] == ["text/plain", "text/html"]
    assert bodies[0]["personalizations"] == [{"to": [{"email": "b@y.io"}]}]


def test_contact_import_waits_only_when_asked() -> None:
    polls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "PUT":
            return httpx.Response(202, json={"job_id": "j1"})
        polls.append(request.url.path)
        status = "completed" if len(polls) == 2 else "pending"
        return httpx.Response(200, json={"status": status})

    integration = integration_for(handler, poll_interval=0)

    assert asyncio.run(integration.create_contacts([{"email": "a@x.io"}], ["l1"])) == {
        "job_id": "j1"
    }
    assert polls == []
    assert asyncio.run(integration.create_contacts([], ["l1"], wait=True)) == {
        "status": "completed"
    }
    assert polls == ["/v3/marketing/contacts/imports/j1"] * 2


def test_search_by_email_and_tool_names() -> None:
    bodies: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        bodies.append(json.loads(request.content))
        return httpx.Response(200, json={"result": []})

    tools = {t.name: t for t in as_tools(integration_for(handler).configuration)}
    assert set(tools) == {
        "sendgrid_create_contacts",
        "sendgrid_search_contacts",
        "sendgrid_get_lists",
        "sendgrid_get_unsubscribe_groups",
        "sendgrid_send_email",
    }
    # Both arguments were required by the in-engine tool's lambda.
    asyncio.run(tools["sendgrid_search_contacts"].ainvoke({"email": "a@x.io"}))
    assert bodies == [{"query": "email LIKE 'a@x.io'"}]
