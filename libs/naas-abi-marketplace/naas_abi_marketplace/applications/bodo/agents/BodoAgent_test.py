import pytest
from naas_abi_marketplace.applications.bodo.agents.BodoAgent import create_agent


@pytest.fixture
def agent():
    return create_agent()


def test_agent_name(agent):
    result = agent.invoke("What is your name?")
    
    assert result is not None, result
    assert "Bodo" in result or "BodoAgent" in result, result


def test_agent_system_prompt(agent):
    result = agent.invoke("What can you help me with?")
    
    assert result is not None, result
    assert "bodo" in result.lower() or "data" in result.lower() or "analysis" in result.lower() or "dataframe" in result.lower(), result

