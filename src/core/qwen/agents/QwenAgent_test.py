import pytest

from src.core.qwen.agents.QwenAgent import create_agent

@pytest.fixture
def agent():
    return create_agent()

def test_agent_name(agent):
    result = agent.invoke("what is your name")

    assert result is not None, result
    assert "Qwen" in result, result