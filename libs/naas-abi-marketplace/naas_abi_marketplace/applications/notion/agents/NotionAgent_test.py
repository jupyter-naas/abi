import pytest
from naas_abi_marketplace.applications.notion.agents.NotionAgent import create_agent


@pytest.fixture
def agent():
    return create_agent()


def test_agent_name(agent):
    result = agent.invoke("What is your name?")
    
    assert result is not None, result
    assert "Notion" in result, result


def test_agent_system_prompt(agent):
    result = agent.invoke("What can you help me with?")
    
    assert result is not None, result
    assert "workspace" in result.lower() or "notion" in result.lower() or "page" in result.lower(), result

