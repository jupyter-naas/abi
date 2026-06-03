import pytest


@pytest.fixture
def agent():
    from naas_abi_core.engine.Engine import Engine
    from naas_abi_marketplace.applications.exchangeratesapi.agents.ExchangeRatesAPIAgent import (
        ExchangeRatesAPIAgent,
    )

    engine = Engine()
    engine.load(module_names=["naas_abi_marketplace.applications.exchangeratesapi"])

    return ExchangeRatesAPIAgent.New()


def test_agent_name(agent):
    result = agent.invoke("What is your name?")
    
    assert result is not None, result
    assert "ExchangeRatesAPI" in result or "Exchange Rates" in result, result


def test_agent_system_prompt(agent):
    result = agent.invoke("What can you help me with?")
    
    assert result is not None, result
    assert "exchange rate" in result.lower() or "currency" in result.lower(), result

