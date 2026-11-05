"""Offline tests of the GitHub integrations: an httpx MockTransport."""

from __future__ import annotations

import asyncio
import json
from base64 import b64encode

import httpx
import pytest
from naas_abi_apps.github.integrations.GitHubGraphqlIntegration import (
    GitHubGraphqlIntegration,
    GitHubGraphqlIntegrationConfiguration,
)
from naas_abi_apps.github.integrations.GitHubGraphqlIntegration import (
    as_tools as graphql_tools,
)
from naas_abi_apps.github.integrations.GitHubIntegration import (
    GitHubIntegration,
    GitHubIntegrationConfiguration,
    as_tools,
)
from naas_abi_sdk.integration import IntegrationConnectionError


def rest(handler) -> GitHubIntegration:
    return GitHubIntegration(
        GitHubIntegrationConfiguration(
            access_token="t", transport=httpx.MockTransport(handler)
        )
    )


def test_requests_carry_the_token_and_errors_raise() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["Authorization"] == "Bearer t"
        if request.url.path == "/users/ghost":
            return httpx.Response(404, json={"message": "Not Found"})
        return httpx.Response(200, json={"login": "ada"})

    integration = rest(handler)

    assert asyncio.run(integration.get_user_details("ada")) == {"login": "ada"}
    with pytest.raises(IntegrationConnectionError):
        asyncio.run(integration.get_user_details("ghost"))


def test_list_issues_pages_until_empty_or_limit() -> None:
    pages: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        page = int(request.url.params["page"])
        pages.append(request.url.params["page"])
        assert request.url.params["labels"] == "bug"
        return httpx.Response(
            200, json=[{"number": page * 10 + i} for i in range(2)] if page < 3 else []
        )

    integration = rest(handler)

    assert len(asyncio.run(integration.list_issues("o/r", labels="bug"))) == 4
    assert pages == ["1", "2", "3"]
    assert [
        i["number"]
        for i in asyncio.run(integration.list_issues("o/r", labels="bug", limit=3))
    ] == [10, 11, 20]


def test_check_assignee_is_true_on_204_false_on_404() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(204 if request.url.path.endswith("/ada") else 404)

    integration = rest(handler)

    assert asyncio.run(integration.check_assignee("o/r", "ada")) is True
    assert asyncio.run(integration.check_assignee("o/r", "bob")) is False


def test_repository_secrets_are_sealed_with_the_repository_key() -> None:
    from nacl.public import PrivateKey, SealedBox

    private = PrivateKey.generate()
    sent: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/public-key"):
            return httpx.Response(
                200,
                json={
                    "key_id": "k1",
                    "key": b64encode(bytes(private.public_key)).decode(),
                },
            )
        sent.update(json.loads(request.content))
        return httpx.Response(201)

    asyncio.run(
        rest(handler).create_or_update_repository_secret("o/r", "TOKEN", "s3cret")
    )

    from base64 import b64decode

    assert sent["key_id"] == "k1"
    assert SealedBox(private).decrypt(b64decode(sent["encrypted_value"])) == b"s3cret"


def test_tools_call_the_async_methods() -> None:
    params: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/issues"):
            params.append(dict(request.url.params))
            return httpx.Response(200, json=[])
        return httpx.Response(200, json=[{"name": "a", "full_name": "o/a", "id": 1}])

    tools = {
        t.name: t for t in as_tools(rest(handler)._GitHubIntegration__configuration)
    }

    assert len(tools) == 27
    arguments = {
        "repo_name": "o/r",
        "filter": "all",
        "state": "closed",
        "sort": "created",
        "direction": "desc",
        "limit": 5,
        "since": "2026-01-01T00:00:00Z",
        "labels": "bug",
    }
    assert asyncio.run(tools["github_list_issues"].ainvoke(arguments)) == []
    assert params[0]["state"] == "closed" and params[0]["labels"] == "bug"
    repos = asyncio.run(
        rest(handler).list_organization_repositories("o", return_list=True)
    )
    assert repos == [{"name": "a", "full_name": "o/a"}]
    json.dumps(repos)


def test_graphql_returns_errors_and_builds_variables() -> None:
    seen: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        seen.append(body)
        if body["variables"]["number"] == 0:
            return httpx.Response(200, json={"errors": [{"message": "no project"}]})
        return httpx.Response(
            200, json={"data": {"organization": {"projectV2": {"id": "P1"}}}}
        )

    configuration = GitHubGraphqlIntegrationConfiguration(
        access_token="t", transport=httpx.MockTransport(handler)
    )
    integration = GitHubGraphqlIntegration(configuration)

    assert (
        asyncio.run(integration.get_project_node_id("acme", "3"))["data"][
            "organization"
        ]["projectV2"]["id"]
        == "P1"
    )
    assert seen[0]["variables"] == {"org": "acme", "number": 3}
    assert asyncio.run(integration.get_project_node_id("acme", 0)) == {
        "error": [{"message": "no project"}]
    }
    assert {t.name for t in graphql_tools(configuration)} == {
        "githubgraphql_get_project_node_id",
        "githubgraphql_get_project_details",
        "githubgraphql_list_priorities",
    }
