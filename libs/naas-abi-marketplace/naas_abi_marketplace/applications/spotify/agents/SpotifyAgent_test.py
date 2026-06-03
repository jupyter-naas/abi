import pytest


@pytest.fixture
def agent():
    from naas_abi_core.engine.Engine import Engine
    from naas_abi_marketplace.applications.spotify.agents.SpotifyAgent import (
        SpotifyAgent,
    )

    engine = Engine()
    engine.load(module_names=["naas_abi_marketplace.applications.spotify"])

    return SpotifyAgent.New()


def test_agent_name(agent):
    result = agent.invoke("What is your name?")

    assert result is not None, result
    assert "Spotify" in result, result


def test_agent_system_prompt(agent):
    result = agent.invoke("What can you help me with?")

    assert result is not None, result
    assert "music" in result.lower() or "spotify" in result.lower() or "playlist" in result.lower(), result
