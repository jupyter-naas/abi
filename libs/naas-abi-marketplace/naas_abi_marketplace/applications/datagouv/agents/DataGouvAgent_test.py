import pytest
from naas_abi_marketplace.applications.datagouv.agents.DataGouvAgent import create_agent


@pytest.fixture
def agent():
    return create_agent()


def test_agent_name(agent):
    result = agent.invoke("What is your name?")
    
    assert result is not None, result
    assert "DataGouv" in result or "Data Gouv" in result, result


def test_agent_system_prompt(agent):
    result = agent.invoke("What can you help me with?")
    
    assert result is not None, result
    assert "data" in result.lower() or "datagouv" in result.lower() or "dataset" in result.lower() or "open data" in result.lower(), result

