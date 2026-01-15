import pytest
from naas_abi_marketplace.applications.spotify.agents.SpotifyAgent import create_agent


@pytest.fixture
def agent():
    return create_agent()


def test_agent_name(agent):
    result = agent.invoke("What is your name?")
    
    assert result is not None, result
    assert "Spotify" in result, result


def test_agent_system_prompt(agent):
    result = agent.invoke("What can you help me with?")
    
    assert result is not None, result
    assert "music" in result.lower() or "spotify" in result.lower() or "playlist" in result.lower(), result

