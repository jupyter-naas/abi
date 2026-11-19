"""Offline tests of the exchangeratesapi integration: an httpx MockTransport."""

from __future__ import annotations

import asyncio

import httpx
from naas_abi_apps.exchangeratesapi.integrations.ExchangeratesapiIntegration import (
    ExchangeratesapiIntegration,
    ExchangeratesapiIntegrationConfiguration,
    as_tools,
)


def configuration(handler) -> ExchangeratesapiIntegrationConfiguration:
    return ExchangeratesapiIntegrationConfiguration(
        api_key="k", transport=httpx.MockTransport(handler)
    )


def test_rates_send_the_key_base_and_symbols() -> None:
    seen: list[httpx.URL] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.url)
        return httpx.Response(200, json={"rates": {"USD": 1.1}})

    integration = ExchangeratesapiIntegration(configuration(handler))
    rates = asyncio.run(
        integration.get_exchange_rates("2026-01-02", "EUR", ["USD", "GBP"])
    )

    assert rates == {"rates": {"USD": 1.1}}
    assert seen[0].path == "/v1/2026-01-02"
    assert dict(seen[0].params) == {
        "access_key": "k",
        "base": "EUR",
        "symbols": "USD,GBP",
    }


def test_symbols_are_read_once() -> None:
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.url.path)
        return httpx.Response(200, json={"symbols": {"EUR": "Euro"}})

    integration = ExchangeratesapiIntegration(configuration(handler))
    asyncio.run(integration.list_symbols())
    asyncio.run(integration.list_symbols())

    assert calls == ["/v1/symbols"]


def test_the_rates_tool_defaults_to_latest_eur() -> None:
    seen: list[httpx.URL] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.url)
        return httpx.Response(200, json={})

    tools = {t.name: t for t in as_tools(configuration(handler))}
    assert set(tools) == {
        "exchangeratesapi_get_exchange_rates",
        "exchangeratesapi_list_symbols",
    }
    # Every argument was required in the in-engine schema.
    asyncio.run(tools["exchangeratesapi_get_exchange_rates"].ainvoke({}))

    assert seen[0].path == "/v1/latest" and seen[0].params["base"] == "EUR"
