import pytest


@pytest.fixture
def agent():
    from naas_abi_core.engine.Engine import Engine
    from naas_abi_marketplace.applications.openrouter.agents.OpenRouterAgent import (
        OpenRouterAgent,
    )

    engine = Engine()
    engine.load(module_names=["naas_abi_marketplace.applications.openrouter"])

    return OpenRouterAgent.New()


def test_agent_name(agent):
    result = agent.invoke("What is your name?")
    
    assert result is not None, result
    assert "OpenRouter" in result, result


def test_agent_system_prompt(agent):
    result = agent.invoke("What can you help me with?")
    
    assert result is not None, result
    assert "ai model" in result.lower() or "openrouter" in result.lower() or "routing" in result.lower(), result

