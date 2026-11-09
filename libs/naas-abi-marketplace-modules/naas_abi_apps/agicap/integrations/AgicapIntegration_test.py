"""Offline tests of the Agicap integration: the API is an httpx MockTransport."""

from __future__ import annotations

import asyncio
import json

import httpx
from naas_abi_apps.agicap.integrations.AgicapIntegration import (
    AgicapIntegration,
    AgicapIntegrationConfiguration,
    as_tools,
    flatten,
)


def configuration(handler, **credentials) -> AgicapIntegrationConfiguration:
    return AgicapIntegrationConfiguration(
        transport=httpx.MockTransport(handler), **credentials
    )


def test_the_bearer_token_is_fetched_once_from_username_and_password() -> None:
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.url.path)
        if request.url.path.endswith("/public/auth/v1/token"):
            form = dict(x.split("=") for x in request.content.decode().split("&"))
            assert form["username"] == "me" and form["grant_type"] == "password"
            return httpx.Response(200, json={"access_token": "fresh"})
        assert request.headers["Authorization"] == "Bearer fresh"
        assert request.headers["EntrepriseId"] == "c1"
        return httpx.Response(200, json={"Result": [{"Id": 1}]})

    integration = AgicapIntegration(
        configuration(handler, username="me", password="pw")
    )

    async def scenario():
        await integration.get_company_accounts("c1")
        return await integration.get_company_accounts("c1")

    assert asyncio.run(scenario()) == [{"Id": 1}]
    assert calls.count("/api/public/auth/v1/token") == 1


def test_transactions_page_and_flatten_up_to_the_limit() -> None:
    skips: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        skips.append(body["pagination"]["skip"])
        assert body["filters"]["bankAccountIds"] == ["a1"]
        return httpx.Response(
            200, json={"Result": [{"Amount": {"Value": i}} for i in range(3)]}
        )

    integration = AgicapIntegration(configuration(handler, bearer_token="b"))
    data = asyncio.run(integration.get_transactions("c1", "a1", limit=3))

    assert data == [{"Amount_Value": 0}, {"Amount_Value": 1}, {"Amount_Value": 2}]
    assert skips == [0]


def test_balance_without_account_is_consolidated() -> None:
    seen: list[httpx.URL] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.url)
        return httpx.Response(200, json={"balance": 1})

    integration = AgicapIntegration(configuration(handler, bearer_token="b"))
    asyncio.run(integration.get_balance("c1"))
    asyncio.run(integration.get_balance("c1", "a1"))

    assert seen[0].path == "/api/forecasting/v2/bank/cash-balances"
    assert seen[1].path == "/api/forecasting/v2/bank/a1/cash-balances"
    assert seen[0].params["frequency"] == "2"


def test_the_balance_tool_takes_no_account() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"balance": 1})

    tools = {t.name: t for t in as_tools(configuration(handler, bearer_token="b"))}

    assert set(tools) == {
        "agicap_list_companies",
        "agicap_get_company_accounts",
        "agicap_get_transactions",
        "agicap_get_balance",
        "agicap_get_debts",
    }
    # Required in the in-engine schema, so a consolidated balance was not reachable.
    assert asyncio.run(tools["agicap_get_balance"].ainvoke({"company_id": "c1"})) == {
        "balance": 1
    }


def test_flatten() -> None:
    assert flatten({"a": {"b": {"c": 1}}, "d": 2}) == {"a_b_c": 1, "d": 2}
