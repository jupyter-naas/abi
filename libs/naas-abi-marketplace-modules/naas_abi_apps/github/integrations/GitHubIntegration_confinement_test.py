"""What the GitHub tools reach with the one configured token."""

from __future__ import annotations

import asyncio

import httpx
import pytest
from naas_abi_apps.github.agents.GitHubAgent import tools_for
from naas_abi_apps.github.integrations.GitHubIntegration import (
    READ_TOOLS,
    GitHubIntegration,
    GitHubIntegrationConfiguration,
    as_tools,
    checked_endpoint,
)

DESTRUCTIVE = {
    "github_delete_organization_repository",
    "github_create_or_update_repository_secret",
    "github_delete_repository_secret",
}


def recorded(sent: list[tuple[str, str]]) -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        sent.append((request.method, str(request.url)))
        return httpx.Response(200, json={})

    return httpx.MockTransport(handler)


def tools(sent: list[tuple[str, str]], **configuration: object) -> dict:
    return {
        t.name: t
        for t in as_tools(
            GitHubIntegrationConfiguration(
                access_token="t",
                base_url="https://gh.test",
                transport=recorded(sent),
                **configuration,  # type: ignore[arg-type]
            )
        )
    }


def test_github_tools_keep_out_repository_deletes_and_secret_writes() -> None:
    names = set(tools([]))

    assert not names & DESTRUCTIVE
    assert READ_TOOLS <= names


@pytest.mark.parametrize(
    "endpoint",
    [
        "/repos/owner/repo/../../orgs/x",
        "/repos/owner/./repo",
        "/repos/owner/re po",
        "/repos/owner%2F../repo",
        "/repos//repo",
        "/repos/owner/repo?",
        "/repos/owner/repo/actions/secrets/NAME?",
        "/repos/owner/repo#x",
        "/repos/owner/repo/issues?state=open",
        "repos/owner/repo",
    ],
)
def test_github_endpoints_keep_to_plain_names(endpoint: str) -> None:
    with pytest.raises(ValueError):
        checked_endpoint(endpoint)


def test_github_endpoints_keep_to_configured_repositories() -> None:
    allowed = ["My-Org/app"]
    assert checked_endpoint("/repos/my-org/app/issues", allowed)
    for endpoint in ("/repos/my-org/other", "/orgs/my-org/repos", "/user/repos"):
        with pytest.raises(ValueError):
            checked_endpoint(endpoint, allowed)


def test_github_tools_keep_to_configured_repositories() -> None:
    sent: list[tuple[str, str]] = []
    by_name = tools(sent, repositories=["o/app"])
    get_issue = by_name["github_get_issue"]

    asyncio.run(get_issue.ainvoke({"repo_name": "o/app", "issue_id": "1"}))
    for repo_name in ("o/secret", "o/app/../../x"):
        with pytest.raises(ValueError):
            asyncio.run(get_issue.ainvoke({"repo_name": repo_name, "issue_id": "1"}))

    assert sent == [("GET", "https://gh.test/repos/o/app/issues/1")]


@pytest.mark.parametrize(
    "repo_name",
    ["o/app?", "o/app/actions/secrets/NAME?", "o/app#", "o/app/issues/1?x"],
)
def test_github_values_keep_to_their_own_endpoint(repo_name: str) -> None:
    sent: list[tuple[str, str]] = []
    delete_comment = tools(sent, repositories=["o/app"])["github_delete_issue_comment"]

    with pytest.raises(ValueError):
        asyncio.run(delete_comment.ainvoke({"repo_name": repo_name, "comment_id": 1}))

    assert sent == []


def test_github_query_values_go_as_parameters() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json=[])

    integration = GitHubIntegration(
        GitHubIntegrationConfiguration(
            access_token="t",
            base_url="https://gh.test",
            transport=httpx.MockTransport(handler),
        )
    )

    asyncio.run(integration.list_issues("o/app", labels="bug&x=1", limit=1))
    asyncio.run(integration.list_issue_comments("o/app", since="a&b=c"))

    assert seen[0].url.path == "/repos/o/app/issues"
    assert seen[0].url.params["labels"] == "bug&x=1"
    assert seen[1].url.path == "/repos/o/app/issues/comments"
    assert seen[1].url.params["since"] == "a&b=c"


def _agent_rest_tools(**kwargs: object) -> set[str]:
    return {
        t.name
        for t in tools_for("t", **kwargs)  # type: ignore[arg-type]
        if t.name.startswith("github_")
    }


def test_github_agent_keeps_to_read_tools_by_default() -> None:
    assert _agent_rest_tools() == set(READ_TOOLS)


def test_github_agent_writes_only_through_configured_tools() -> None:
    assert _agent_rest_tools(write_tools={"github_create_issue_comment"}) == set(
        READ_TOOLS
    ) | {"github_create_issue_comment"}
    # A destructive tool cannot be named back in: it is not a tool.
    assert not _agent_rest_tools(write_tools=DESTRUCTIVE) & DESTRUCTIVE
