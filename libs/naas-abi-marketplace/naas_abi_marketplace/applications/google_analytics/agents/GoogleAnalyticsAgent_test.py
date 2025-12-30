import pytest
from naas_abi_marketplace.applications.google_analytics.agents.GoogleAnalyticsAgent import create_agent


@pytest.fixture
def agent():
    return create_agent()


def test_agent_name(agent):
    result = agent.invoke("What is your name?")
    
    assert result is not None, result
    assert "Google Analytics" in result or "Analytics" in result, result


def test_agent_system_prompt(agent):
    result = agent.invoke("What can you help me with?")
    
    assert result is not None, result
    assert "analytics" in result.lower() or "website" in result.lower() or "data" in result.lower() or "reporting" in result.lower(), result

