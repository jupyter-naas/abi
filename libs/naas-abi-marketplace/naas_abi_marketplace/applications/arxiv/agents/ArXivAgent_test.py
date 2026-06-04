import pytest


@pytest.fixture
def agent():
    from naas_abi_core.engine.Engine import Engine
    from naas_abi_marketplace.applications.arxiv.agents.ArXivAgent import (
        ArXivAgent,
    )

    engine = Engine()
    engine.load(module_names=["naas_abi_marketplace.applications.arxiv"])

    return ArXivAgent.New()


def test_agent_name(agent):
    result = agent.invoke("What is your name?")
    
    assert result is not None, result
    assert "ArXiv" in result or "ArXivAgent" in result, result


def test_agent_system_prompt(agent):
    result = agent.invoke("What can you help me with?")
    
    assert result is not None, result
    assert "paper" in result.lower() or "arxiv" in result.lower() or "research" in result.lower(), result

