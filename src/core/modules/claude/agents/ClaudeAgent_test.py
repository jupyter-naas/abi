import pytest

from src.core.modules.claude.agents.ClaudeAgent import create_agent

@pytest.fixture
def agent():
    return create_agent()

def test_agent_name(agent):
    result = agent.invoke("what is your name")

    assert result is not None, result
    assert "Claude" in result, result

def test_intent_can_do(agent):
    result = agent.invoke("what can you do")

    assert result is not None, result
    assert "I can help with complex reasoning, critical thinking, analysis, creative writing, technical explanations, research, and providing balanced perspectives on various topics." in result, result
