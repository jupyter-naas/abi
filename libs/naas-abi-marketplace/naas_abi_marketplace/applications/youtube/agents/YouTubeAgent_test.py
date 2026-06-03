import pytest


@pytest.fixture
def agent():
    from naas_abi_core.engine.Engine import Engine
    from naas_abi_marketplace.applications.youtube.agents.YouTubeAgent import (
        YouTubeAgent,
    )

    engine = Engine()
    engine.load(module_names=["naas_abi_marketplace.applications.youtube"])

    return YouTubeAgent.New()


def test_agent_name(agent):
    result = agent.invoke("What is your name?")
    
    assert result is not None, result
    assert "YouTube" in result, result


def test_agent_system_prompt(agent):
    result = agent.invoke("What can you help me with?")
    
    assert result is not None, result
    assert "youtube" in result.lower() or "video" in result.lower() or "channel" in result.lower(), result

