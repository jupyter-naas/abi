import pytest
from naas_abi_marketplace.applications.sharepoint.agents.SharePointAgent import create_agent


@pytest.fixture
def agent():
    return create_agent()


def test_agent_name(agent):
    result = agent.invoke("What is your name?")
    
    assert result is not None, result
    assert "SharePoint" in result, result


def test_agent_system_prompt(agent):
    result = agent.invoke("What can you help me with?")
    
    assert result is not None, result
    assert "document" in result.lower() or "sharepoint" in result.lower() or "collaboration" in result.lower(), result

