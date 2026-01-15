import pytest
from naas_abi_marketplace.applications.arxiv.agents.ArXivAgent import create_agent


@pytest.fixture
def agent():
    return create_agent()


def test_agent_name(agent):
    result = agent.invoke("What is your name?")
    
    assert result is not None, result
    assert "ArXiv" in result or "ArXivAgent" in result, result


def test_agent_system_prompt(agent):
    result = agent.invoke("What can you help me with?")
    
    assert result is not None, result
    assert "paper" in result.lower() or "arxiv" in result.lower() or "research" in result.lower(), result

