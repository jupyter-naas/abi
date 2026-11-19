"""What the GitHub tools reach with the one configured token."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest
from naas_abi_marketplace.domains.operations.modules.support.integrations import (
    GitHubIntegration as github_mod,
)
from naas_abi_marketplace.domains.operations.modules.support.integrations.GitHubIntegration import (
    READ_TOOLS,
    GitHubIntegrationConfiguration,
    as_tools,
    checked_endpoint,
)

DESTRUCTIVE = {
    "github_delete_organization_repository",
    "github_create_or_update_repository_secret",
    "github_delete_repository_secret",
}


@pytest.fixture
def sent(monkeypatch: pytest.MonkeyPatch) -> list[tuple[str, str]]:
    calls: list[tuple[str, str]] = []

    def request(method: str, url: str, **kwargs: Any) -> Any:
        calls.append((method, url))
        return SimpleNamespace(content=b"", raise_for_status=lambda: None)

    monkeypatch.setattr(github_mod.requests, "request", request)
    return calls


def test_github_tools_keep_out_repository_deletes_and_secret_writes() -> None:
    names = {t.name for t in as_tools(GitHubIntegrationConfiguration(access_token="t"))}

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


def test_github_tools_keep_to_configured_repositories(
    sent: list[tuple[str, str]],
) -> None:
    tools = {
        t.name: t
        for t in as_tools(
            GitHubIntegrationConfiguration(
                access_token="t", base_url="https://gh.test", repositories=["o/app"]
            )
        )
    }

    tools["github_get_issue"].invoke({"repo_name": "o/app", "issue_id": "1"})
    with pytest.raises(ValueError):
        tools["github_get_issue"].invoke({"repo_name": "o/secret", "issue_id": "1"})
    with pytest.raises(ValueError):
        tools["github_get_issue"].invoke(
            {"repo_name": "o/app/../../x", "issue_id": "1"}
        )

    assert sent == [("GET", "https://gh.test/repos/o/app/issues/1")]


@pytest.mark.parametrize(
    "repo_name",
    ["o/app?", "o/app/actions/secrets/NAME?", "o/app#", "o/app/issues/1?x"],
)
def test_github_values_keep_to_their_own_endpoint(
    sent: list[tuple[str, str]], repo_name: str
) -> None:
    tools = {
        t.name: t
        for t in as_tools(
            GitHubIntegrationConfiguration(
                access_token="t", base_url="https://gh.test", repositories=["o/app"]
            )
        )
    }

    with pytest.raises(ValueError):
        tools["github_delete_issue_comment"].invoke(
            {"repo_name": repo_name, "comment_id": 1}
        )

    assert sent == []


def test_github_query_values_go_as_parameters(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[str, dict | None]] = []

    def request(method: str, url: str, **kwargs: Any) -> Any:
        calls.append((url, kwargs.get("params")))
        return SimpleNamespace(content=b"[]", json=list, raise_for_status=lambda: None)

    monkeypatch.setattr(github_mod.requests, "request", request)
    integration = github_mod.GitHubIntegration(
        GitHubIntegrationConfiguration(access_token="t", base_url="https://gh.test")
    )

    integration.list_issues("o/app", labels="bug&x=1")

    url, params = calls[0]
    assert url == "https://gh.test/repos/o/app/issues"
    assert params is not None and params["labels"] == "bug&x=1"
