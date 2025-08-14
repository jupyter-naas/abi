import pytest

from src.core.modules.gemma.agents.GemmaAgent import create_agent

@pytest.fixture
def agent():
    return create_agent()

def test_agent_name(agent):
    result = agent.invoke("what is your name")

    assert result is not None, result
    assert "Gemma" in result, result