import pytest


@pytest.fixture
def agent():
    from naas_abi_core.engine.Engine import Engine
    from naas_abi_marketplace.applications.instagram.agents.InstagramAgent import (
        InstagramAgent,
    )

    engine = Engine()
    engine.load(module_names=["naas_abi_marketplace.applications.instagram"])

    return InstagramAgent.New()


def test_agent_name(agent):
    result = agent.invoke("What is your name?")

    assert result is not None, result
    assert "Instagram" in result, result


def test_agent_system_prompt(agent):
    result = agent.invoke("What can you help me with?")

    assert result is not None, result
    assert "instagram" in result.lower() or "social" in result.lower() or "content" in result.lower(), result
