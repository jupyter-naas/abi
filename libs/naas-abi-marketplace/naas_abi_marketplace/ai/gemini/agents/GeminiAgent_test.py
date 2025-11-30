import pytest
from naas_abi.core.gemini.agents.GeminiAgent import create_agent


@pytest.fixture
def agent():
    return create_agent()


def test_agent_name(agent):
    result = agent.invoke("what is your name")

    assert result is not None, result
    assert "Gemini" in result, result


def test_intent_can_do(agent):
    result = agent.invoke("what can you do")

    assert result is not None, result
    assert (
        "I can help with advanced reasoning, code analysis, mathematical computations, creative writing, research, and multimodal understanding of text, images, audio, and video."
        in result
    ), result
