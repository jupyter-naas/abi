"""The Naas agent tools act with one account key: they reveal no secret value
or storage credential, delete nothing and leave workspace membership alone."""

from __future__ import annotations

import asyncio
from typing import Any

import httpx
import pytest
from naas_abi_apps.naas.integrations.NaasIntegration import (
    NaasIntegrationConfiguration,
    as_tools,
    checked_endpoint,
)

WORKSPACE = "11111111-2222-3333-4444-555555555555"


def test_naas_tools_keep_secret_values_credentials_and_deletes_out() -> None:
    names = {t.name for t in as_tools(NaasIntegrationConfiguration(api_key="k"))}

    for name in names:
        assert not name.startswith("delete_"), name
    assert not names & {
        "get_secret",
        "list_secrets",
        "create_secret",
        "update_secret",
        "get_storage_credentials",
        "create_workspace_storage_credentials",
        "invite_workspace_user",
        "update_workspace_user",
    }
    assert {"list_secrets_names", "list_workspaces", "get_ontology"} <= names


def tools(sent: list[str]) -> dict[str, Any]:
    def handler(request: httpx.Request) -> httpx.Response:
        sent.append(str(request.url.copy_with(query=None)))
        return httpx.Response(200, json={"ok": True})

    configuration = NaasIntegrationConfiguration(
        api_key="k",
        base_url="https://naas.example.test",
        transport=httpx.MockTransport(handler),
    )
    return {t.name: t for t in as_tools(configuration)}


@pytest.mark.parametrize(
    ("tool", "arguments"),
    [
        ("get_ontology", {"workspace_id": WORKSPACE, "ontology_id": "../secret/X"}),
        ("get_ontology", {"workspace_id": WORKSPACE, "ontology_id": "../secret/"}),
        (
            "list_workspace_storage_objects",
            {
                "workspace_id": WORKSPACE,
                "storage_name": "../../../../secret/X",
                "prefix": "",
            },
        ),
        (
            "create_workspace_storage",
            {"workspace_id": WORKSPACE, "storage_name": "x/../../../secret"},
        ),
    ],
)
def test_naas_tools_keep_to_their_own_endpoints(tool: str, arguments: dict) -> None:
    sent: list[str] = []

    with pytest.raises(ValueError):
        asyncio.run(tools(sent)[tool].ainvoke(arguments))

    assert sent == []


@pytest.mark.parametrize(
    "endpoint",
    [
        "/ontology/../secret/X",
        "/workspace/./x",
        "/workspace/a?b",
        "/workspace/a#b",
        "/workspace/a%2F..",
        "/workspace//storage",
        "ontology/x",
    ],
)
def test_naas_endpoints_keep_to_plain_names(endpoint: str) -> None:
    with pytest.raises(ValueError):
        checked_endpoint(endpoint)


def test_naas_requests_reach_their_endpoint() -> None:
    sent: list[str] = []
    by_name = tools(sent)

    asyncio.run(
        by_name["get_ontology"].ainvoke(
            {"workspace_id": WORKSPACE, "ontology_id": WORKSPACE}
        )
    )
    asyncio.run(by_name["list_workspace_storage"].ainvoke({"workspace_id": WORKSPACE}))

    assert sent == [
        f"https://naas.example.test/ontology/{WORKSPACE}",
        f"https://naas.example.test/workspace/{WORKSPACE}/storage/",
    ]
