"""The Git agents act on the engine's working directory only on a developer's
machine: the git module's ``single_user_development`` flag."""

from __future__ import annotations

from types import SimpleNamespace

import naas_abi_marketplace.applications.git as git_pkg
import pytest
from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel
from langchain_core.messages import AIMessage
from naas_abi_core.module.ModuleAgentLoader import ModuleAgentLoader
from naas_abi_core.services.agent.Agent import Agent
from naas_abi_marketplace.applications.git.agents.GitAgent import GitAgent
from naas_abi_marketplace.applications.git.agents.PullRequestDescriptionAgent import (
    PullRequestDescriptionAgent,
)

ACTING_TOOLS = {
    "make_check",
    "make_fix",
    "git_add",
    "git_restore",
    "git_commit",
    "git_push",
    "gh_pr_create",
    "gh_pr_edit",
    "git_diff",
}


def use_module(monkeypatch: pytest.MonkeyPatch, configuration: object) -> None:
    chat = FakeMessagesListChatModel(responses=[AIMessage(content="ok")])
    module = SimpleNamespace(
        configuration=configuration,
        engine=SimpleNamespace(
            services=SimpleNamespace(
                model_registry=SimpleNamespace(get_default_chat_model=lambda: chat),
                object_storage=None,
            )
        ),
    )
    monkeypatch.setattr(
        git_pkg.ABIModule, "get_instance", classmethod(lambda cls: module)
    )


def tool_names(agent: Agent) -> set[str]:
    return {t.name for t in agent.tools if hasattr(t, "name")}


@pytest.mark.parametrize(
    "configured", [False, True], ids=["no configuration", "flag unset"]
)
def test_git_agents_keep_off_the_engine_checkout_by_default(
    monkeypatch: pytest.MonkeyPatch, configured: bool
) -> None:
    monkeypatch.delenv(git_pkg.SINGLE_USER_DEVELOPMENT_ENV, raising=False)
    configuration = (
        git_pkg.ABIModule.Configuration.model_construct() if configured else None
    )
    use_module(monkeypatch, configuration)

    assert not tool_names(GitAgent.New()) & ACTING_TOOLS
    assert not tool_names(PullRequestDescriptionAgent.New()) & ACTING_TOOLS

    loaded = ModuleAgentLoader.load_agents(git_pkg.ABIModule, configuration)
    assert GitAgent not in loaded
    assert PullRequestDescriptionAgent not in loaded


def test_git_agents_act_on_a_single_developer_checkout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    configuration = git_pkg.ABIModule.Configuration.model_construct(
        single_user_development=True
    )
    use_module(monkeypatch, configuration)

    assert {"make_check", "git_commit", "git_push"} <= tool_names(GitAgent.New())
    assert "git_diff" in tool_names(PullRequestDescriptionAgent.New())

    loaded = ModuleAgentLoader.load_agents(git_pkg.ABIModule, configuration)
    assert GitAgent in loaded
    assert PullRequestDescriptionAgent in loaded


@pytest.mark.parametrize(("value", "on"), [("1", True), ("", False), ("true", False)])
def test_git_agents_act_only_with_the_explicit_environment_flag(
    monkeypatch: pytest.MonkeyPatch, value: str, on: bool
) -> None:
    monkeypatch.setenv(git_pkg.SINGLE_USER_DEVELOPMENT_ENV, value)
    configuration = git_pkg.ABIModule.Configuration.model_construct()
    use_module(monkeypatch, configuration)

    assert ("make_check" in tool_names(GitAgent.New())) is on
    assert (
        GitAgent in ModuleAgentLoader.load_agents(git_pkg.ABIModule, configuration)
    ) is on
