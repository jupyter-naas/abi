import pytest

from naas_abi_marketplace.applications.naas.agents.NaasAgent import create_agent

@pytest.fixture
def naas_agent():
    return create_agent()

def test_agent_presentation(agent):
    result = agent.run(input="What's your name?")
    
    assert result is not None, result
    assert "Naas" in result, result