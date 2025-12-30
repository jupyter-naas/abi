import pytest
from naas_abi_marketplace.applications.zoho.agents.ZohoAgent import create_agent


@pytest.fixture
def agent():
    return create_agent()


def test_agent_name(agent):
    result = agent.invoke("What is your name?")
    
    assert result is not None, result
    assert "Zoho" in result, result


def test_agent_system_prompt(agent):
    result = agent.invoke("What can you help me with?")
    
    assert result is not None, result
    assert "zoho" in result.lower() or "crm" in result.lower() or "business" in result.lower(), result

