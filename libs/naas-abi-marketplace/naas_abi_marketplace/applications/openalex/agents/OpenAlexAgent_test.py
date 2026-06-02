import pytest


@pytest.fixture
def agent():
    from naas_abi_core.engine.Engine import Engine
    from naas_abi_marketplace.applications.openalex.agents.OpenAlexAgent import (
        OpenAlexAgent,
    )

    engine = Engine()
    engine.load(module_names=["naas_abi_marketplace.applications.openalex"])

    return OpenAlexAgent.New()


def test_agent_name(agent):
    result = agent.invoke("What is your name?")

    assert result is not None, result
    assert "OpenAlex" in result or "Open Alex" in result, result


def test_agent_system_prompt(agent):
    result = agent.invoke("What can you help me with?")

    assert result is not None, result
    assert "openalex" in result.lower() or "research" in result.lower() or "publication" in result.lower() or "academic" in result.lower(), result
