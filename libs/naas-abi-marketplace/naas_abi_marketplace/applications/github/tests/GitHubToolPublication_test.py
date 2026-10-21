"""The GitHub module publishes its integration tools without building its agent."""

from types import SimpleNamespace

import pytest
from naas_abi_core.services.tool_registry.adapters.primary.LangChainToolPublisher import (
    ToolPublisher,
)
from naas_abi_core.services.tool_registry.ToolRegistryPort import ToolContext
from naas_abi_core.services.tool_registry.ToolRegistryService import (
    ToolRegistryService,
)
from naas_abi_marketplace.applications.github import ABIModule

MODULE = "naas_abi_marketplace.applications.github"


def _module(token: str) -> ABIModule:
    # A module instance without an engine: publication only reads the
    # module configuration, so no agent, engine or network is involved.
    module = ABIModule.__new__(ABIModule)
    module._configuration = SimpleNamespace(github_access_token=token)
    return module


@pytest.fixture
def registry() -> ToolRegistryService:
    registry = ToolRegistryService()
    publisher = ToolPublisher(MODULE)
    _module("module-token").publish_tools(publisher)
    publisher.publish_to(registry)
    return registry


def test_publishes_the_rest_and_graphql_tools(registry):
    names = {d.name for d in registry.list_definitions()}
    assert {
        "github_create_issue",
        "github_list_issues",
        "githubgraphql_list_priorities",
    } <= names
    assert len(names) >= 30


def test_definitions_carry_the_contract_and_never_the_token(registry):
    definition = registry.get_definition(f"{MODULE}/github_create_issue")
    assert str(definition.id) == f"{MODULE}/github_create_issue@1"
    assert "repo_name" in definition.input_schema["properties"]
    assert definition.required_config_keys() == ("access_token",)
    assert "module-token" not in definition.model_dump_json()


@pytest.fixture
def sent(monkeypatch) -> list[dict]:
    """Capture GitHub API requests instead of sending them."""
    from naas_abi_marketplace.applications.github.integrations.GitHubIntegration import (
        GitHubIntegration,
    )

    requests: list[dict] = []

    def _capture(self, method, endpoint, data=None, params=None, headers=None):
        requests.append(
            {
                "method": method,
                "endpoint": endpoint,
                "auth": self.headers["Authorization"],
            }
        )
        return {"ok": True}

    monkeypatch.setattr(GitHubIntegration, "_make_request", _capture)
    return requests


def _create_issue(tool) -> None:
    tool.invoke(
        {
            "repo_name": "o/r",
            "title": "Crash",
            "body": "It crashed.",
            "labels": [],
            "assignees": [],
        }
    )


def test_resolution_uses_the_module_token_by_default(registry, sent):
    _create_issue(registry.resolve(f"{MODULE}/github_create_issue", ToolContext()))
    assert sent == [
        {
            "method": "POST",
            "endpoint": "/repos/o/r/issues",
            "auth": "Bearer module-token",
        }
    ]


def test_a_caller_token_replaces_the_module_token(registry, sent):
    tool = registry.resolve(
        f"{MODULE}/github_create_issue", ToolContext(), config={"access_token": "mine"}
    )
    _create_issue(tool)
    assert sent[0]["auth"] == "Bearer mine"


def test_publication_does_not_construct_the_agent(monkeypatch):
    from naas_abi_marketplace.applications.github.agents.GitHubAgent import GitHubAgent

    def _fail(*args, **kwargs):
        raise AssertionError("GitHubAgent.New must not run to publish tools")

    monkeypatch.setattr(GitHubAgent, "New", classmethod(_fail))
    publisher = ToolPublisher(MODULE)
    _module("t").publish_tools(publisher)
    assert publisher.tools
