import pytest


@pytest.fixture
def agent():
    from naas_abi_core.engine.Engine import Engine
    from naas_abi_marketplace.applications.github.agents.GitHubAgent import (
        GitHubAgent,
    )

    engine = Engine()
    engine.load(module_names=["naas_abi_marketplace.applications.github"])

    return GitHubAgent.New()


def test_agent_name(agent):
    result = agent.invoke("What is your name?")
    assert result is not None, result
    assert "github" in result.lower(), result


def test_agent_system_prompt(agent):
    result = agent.invoke("What can you help me with?")
    assert result is not None, result
    lowered = result.lower()
    assert (
        "repository" in lowered
        or "issue" in lowered
        or "pull request" in lowered
        or "github" in lowered
    ), result
