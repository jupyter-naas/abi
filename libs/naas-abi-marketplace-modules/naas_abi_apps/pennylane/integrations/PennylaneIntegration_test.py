"""Offline tests of the Pennylane integration: the API is an httpx MockTransport."""

from __future__ import annotations

import asyncio
import json

import httpx
import pytest
from naas_abi_apps.pennylane.integrations.PennylaneIntegration import (
    PennylaneIntegration,
    PennylaneIntegrationConfiguration,
    as_tools,
)
from naas_abi_sdk.integration import IntegrationConnectionError


class MemoryStorage:
    def __init__(self) -> None:
        self.objects: dict[tuple[str, str], bytes] = {}

    async def put_object(self, prefix: str, key: str, content: bytes) -> None:
        self.objects[(prefix, key)] = content


def integration_for(handler, storage=None) -> PennylaneIntegration:
    return PennylaneIntegration(
        PennylaneIntegrationConfiguration(
            api_key="token",
            storage=storage,
            transport=httpx.MockTransport(handler),
        )
    )


def test_lists_follow_the_cursor_and_are_archived() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        if "cursor" not in request.url.params:
            return httpx.Response(
                200, json={"items": [{"id": 1}], "has_more": True, "next_cursor": "c2"}
            )
        return httpx.Response(200, json={"items": [{"id": 2}], "has_more": False})

    storage = MemoryStorage()
    customers = asyncio.run(integration_for(handler, storage).list_customers())

    assert customers == [{"id": 1}, {"id": 2}]
    assert [r.url.params.get("cursor") for r in seen] == [None, "c2"]
    assert seen[0].url.path == "/api/external/v2/customers"
    assert seen[0].url.params["limit"] == "100" and seen[0].url.params["sort"] == "-id"
    assert seen[0].headers["Authorization"] == "Bearer token"
    stored = storage.objects[("pennylane/list_customers", "list_customers.json")]
    assert json.loads(stored) == customers


def test_invoice_filters_combine_customer_and_start_date() -> None:
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["filter"] = json.loads(request.url.params["filter"])
        captured["sort"] = request.url.params["sort"]
        return httpx.Response(200, json={"items": [], "has_more": False})

    asyncio.run(
        integration_for(handler).list_customer_invoices(
            customer_id="42", start_date="2026-01-01"
        )
    )

    assert captured["sort"] == "-date"
    assert captured["filter"] == [
        {"field": "customer_id", "operator": "match", "value": "42"},
        {"field": "date", "operator": "gteq", "value": "2026-01-01"},
    ]


def test_http_errors_raise_integration_connection_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"error": "unauthorized"})

    with pytest.raises(
        IntegrationConnectionError, match="Pennylane API request failed"
    ):
        asyncio.run(integration_for(handler).get_customer("1"))


def test_tools_keep_their_names_and_pass_keywords() -> None:
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["filter"] = json.loads(request.url.params.get("filter", "[]"))
        return httpx.Response(200, json={"items": [], "has_more": False})

    configuration = PennylaneIntegrationConfiguration(
        api_key="token", transport=httpx.MockTransport(handler)
    )
    tools = {tool.name: tool for tool in as_tools(configuration)}

    assert set(tools) == {
        "pennylane_list_customers",
        "pennylane_get_customer_details",
        "pennylane_list_customers_invoices",
        "pennylane_get_customer_invoice",
    }
    asyncio.run(
        tools["pennylane_list_customers_invoices"].ainvoke({"customer_id": "7"})
    )
    # The in-engine tool passed these positionally into (sort, filters).
    assert captured["filter"] == [
        {"field": "customer_id", "operator": "match", "value": "7"}
    ]
