import pytest


@pytest.fixture
def agent():
    from naas_abi_core.engine.Engine import Engine
    from naas_abi_marketplace.applications.git.agents.GitAgent import (
        GitAgent,
    )

    engine = Engine()
    engine.load(module_names=["naas_abi_marketplace.applications.git"])

    return GitAgent.New()


def test_agent_name(agent):
    result = agent.invoke("What is your name?")
    assert result is not None, result
    assert "git" in result.lower() or "pull request" in result.lower(), result


def test_agent_system_prompt(agent):
    result = agent.invoke("What can you help me with?")
    assert result is not None, result
    lowered = result.lower()
    assert "commit" in lowered or "pull request" in lowered or "github" in lowered, (
        result
    )
