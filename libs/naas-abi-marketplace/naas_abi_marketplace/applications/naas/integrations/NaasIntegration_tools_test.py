"""The Naas agent tools act with one account key: they reveal no secret value
or storage credential, delete nothing and leave workspace membership alone."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest
from naas_abi_marketplace.applications.naas.integrations import (
    NaasIntegration as naas_mod,
)
from naas_abi_marketplace.applications.naas.integrations.NaasIntegration import (
    NaasIntegrationConfiguration,
    as_tools,
    checked_endpoint,
)


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


WORKSPACE = "11111111-2222-3333-4444-555555555555"


@pytest.fixture
def sent(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    urls: list[str] = []

    def request(method: str, url: str, **kwargs: Any) -> Any:
        urls.append(url)
        return SimpleNamespace(raise_for_status=lambda: None, json=lambda: {"ok": True})

    monkeypatch.setattr(naas_mod.requests, "request", request)
    return urls


def tools() -> dict[str, Any]:
    configuration = NaasIntegrationConfiguration(
        api_key="k", base_url="https://naas.example.test"
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
def test_naas_tools_keep_to_their_own_endpoints(
    sent: list[str], tool: str, arguments: dict
) -> None:
    with pytest.raises(ValueError):
        tools()[tool].invoke(arguments)

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


def test_naas_requests_reach_their_endpoint(sent: list[str]) -> None:
    tools()["get_ontology"].invoke(
        {"workspace_id": WORKSPACE, "ontology_id": WORKSPACE}
    )
    tools()["list_workspace_storage"].invoke({"workspace_id": WORKSPACE})

    assert sent == [
        f"https://naas.example.test/ontology/{WORKSPACE}",
        f"https://naas.example.test/workspace/{WORKSPACE}/storage/",
    ]
