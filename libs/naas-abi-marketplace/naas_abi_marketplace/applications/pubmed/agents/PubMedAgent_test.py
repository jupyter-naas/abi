import pytest


@pytest.fixture
def agent():
    from naas_abi_core.engine.Engine import Engine
    from naas_abi_marketplace.applications.pubmed.agents.PubMedAgent import (
        PubMedAgent,
    )

    engine = Engine()
    engine.load(module_names=["naas_abi_marketplace.applications.pubmed"])

    return PubMedAgent.New()


def test_agent_name(agent):
    result = agent.invoke("What is your name?")
    
    assert result is not None, result
    assert "PubMed" in result or "PubMedAgent" in result, result


def test_agent_system_prompt(agent):
    result = agent.invoke("What can you help me with?")
    
    assert result is not None, result
    assert "pubmed" in result.lower() or "paper" in result.lower() or "search" in result.lower(), result

