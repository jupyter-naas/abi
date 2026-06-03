import pytest


@pytest.fixture
def agent():
    from naas_abi_core.engine.Engine import Engine
    from naas_abi_marketplace.applications.yahoofinance.agents.YfinanceAgent import (
        YfinanceAgent,
    )

    engine = Engine()
    engine.load(module_names=["naas_abi_marketplace.applications.yahoofinance"])

    return YfinanceAgent.New()


def test_agent_name(agent):
    result = agent.invoke("What is your name?")
    
    assert result is not None, result
    assert "YahooFinance" in result or "Yahoo Finance" in result, result


def test_agent_system_prompt(agent):
    result = agent.invoke("What can you help me with?")
    
    assert result is not None, result
    assert "finance" in result.lower() or "stock" in result.lower() or "yahoo" in result.lower() or "financial" in result.lower(), result

