import pytest
from naas_abi_marketplace.applications.youtube.agents.YouTubeAgent import create_agent


@pytest.fixture
def agent():
    return create_agent()


def test_agent_name(agent):
    result = agent.invoke("What is your name?")
    
    assert result is not None, result
    assert "YouTube" in result, result


def test_agent_system_prompt(agent):
    result = agent.invoke("What can you help me with?")
    
    assert result is not None, result
    assert "youtube" in result.lower() or "video" in result.lower() or "channel" in result.lower(), result

