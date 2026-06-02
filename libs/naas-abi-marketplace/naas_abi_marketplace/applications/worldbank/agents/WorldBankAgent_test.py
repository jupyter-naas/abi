import pytest


@pytest.fixture
def agent():
    from naas_abi_core.engine.Engine import Engine
    from naas_abi_marketplace.applications.worldbank.agents.WorldBankAgent import (
        WorldBankAgent,
    )

    engine = Engine()
    engine.load(module_names=["naas_abi_marketplace.applications.worldbank"])

    return WorldBankAgent.New()


def test_agent_name(agent):
    result = agent.invoke("What is your name?")

    assert result is not None, result
    assert "World Bank" in result or "WorldBank" in result, result


def test_agent_system_prompt(agent):
    result = agent.invoke("What can you help me with?")

    assert result is not None, result
    assert "economic" in result.lower() or "world bank" in result.lower() or "development" in result.lower() or "indicator" in result.lower(), result
