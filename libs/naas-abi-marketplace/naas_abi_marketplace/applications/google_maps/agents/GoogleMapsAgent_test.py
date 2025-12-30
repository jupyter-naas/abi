import pytest
from naas_abi_marketplace.applications.google_maps.agents.GoogleMapsAgent import create_agent


@pytest.fixture
def agent():
    return create_agent()


def test_agent_name(agent):
    result = agent.invoke("What is your name?")
    
    assert result is not None, result
    assert "Google Maps" in result or "Maps" in result, result


def test_agent_system_prompt(agent):
    result = agent.invoke("What can you help me with?")
    
    assert result is not None, result
    assert "maps" in result.lower() or "location" in result.lower() or "geocoding" in result.lower(), result

