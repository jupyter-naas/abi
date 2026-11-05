"""Offline tests of the Algolia integration: a fake v4 SearchClient."""

from __future__ import annotations

import asyncio
from typing import Any, Self

import pytest
from naas_abi_apps.algolia.integrations.AlgoliaIntegration import (
    AlgoliaIntegration,
    AlgoliaIntegrationConfiguration,
    as_tools,
)
from naas_abi_sdk.integration import IntegrationConnectionError


class Model:
    def __init__(self, data: dict[str, Any]) -> None:
        self.data = data

    def to_dict(self) -> dict[str, Any]:
        return self.data


class FakeClient:
    calls: list[tuple[str, dict[str, Any]]] = []
    opened: list[tuple[str, str]] = []

    def __init__(self, app_id: str, api_key: str) -> None:
        FakeClient.opened.append((app_id, api_key))

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, *exc: object) -> None:
        return None

    def __getattr__(self, method: str):
        async def call(**kwargs: Any) -> Model:
            if method == "delete_index" and kwargs["index_name"] == "boom":
                raise RuntimeError("index locked")
            FakeClient.calls.append((method, kwargs))
            return Model({"method": method})

        return call


@pytest.fixture
def integration() -> AlgoliaIntegration:
    FakeClient.calls, FakeClient.opened = [], []
    return AlgoliaIntegration(
        AlgoliaIntegrationConfiguration(
            app_id="app", api_key="key", client_factory=FakeClient
        )
    )


def test_search_builds_one_request_and_returns_plain_data(integration) -> None:
    result = asyncio.run(integration.search("books", "dune", filters="price < 10"))

    assert result == {"method": "search"}
    assert FakeClient.opened == [("app", "key")]
    ((method, kwargs),) = FakeClient.calls
    assert method == "search"
    assert kwargs["search_method_params"]["requests"] == [
        {
            "indexName": "books",
            "query": "dune",
            "hitsPerPage": 50,
            "filters": "price < 10",
        }
    ]


def test_create_index_sets_then_reads_settings(integration) -> None:
    result = asyncio.run(
        integration.create_index("books", {"searchableAttributes": ["title"]})
    )

    assert [m for m, _ in FakeClient.calls] == ["set_settings", "get_settings"]
    assert FakeClient.calls[0][1]["index_settings"] == {
        "searchableAttributes": ["title"]
    }
    assert result["name"] == "books"


def test_sdk_errors_become_integration_connection_errors(integration) -> None:
    with pytest.raises(IntegrationConnectionError, match="index locked"):
        asyncio.run(integration.delete_index("boom"))


def test_tools_keep_their_names_and_run_async(integration) -> None:
    tools = {t.name: t for t in as_tools(integration.configuration)}

    assert set(tools) == {
        "algolia_search_index",
        "algolia_create_index",
        "algolia_list_indexes",
        "algolia_delete_index",
        "algolia_update_records",
        "algolia_delete_all_records",
    }
    asyncio.run(
        tools["algolia_update_records"].ainvoke(
            {"index_name": "b", "records": [{"a": 1}, {"a": 2}]}
        )
    )
    assert [m for m, _ in FakeClient.calls] == ["save_object", "save_object"]
