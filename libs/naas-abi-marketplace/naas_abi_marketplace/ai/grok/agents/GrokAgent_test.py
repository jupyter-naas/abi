import pytest
from naas_abi_marketplace.ai.grok.agents.GrokAgent import create_agent


@pytest.fixture
def agent():
    return create_agent()


def test_agent_name(agent):
    result = agent.invoke("what is your name")

    assert result is not None, result
    assert "Grok" in result, result


def test_intent_can_do(agent):
    result = agent.invoke("what can you do")

    assert result is not None, result
    assert (
        "I excel at complex reasoning, scientific analysis, mathematical problems, truth-seeking, contrarian thinking, and real-time information synthesis. I have the highest measured intelligence globally (Intelligence Score: 73)."
        in result
    ), result
