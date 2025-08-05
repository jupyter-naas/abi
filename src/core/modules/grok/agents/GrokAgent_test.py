import pytest

from src.core.modules.grok.agents.GrokAgent import create_agent

@pytest.fixture
def agent():
    return create_agent()

def test_ask_grok(agent):
    result = agent.invoke("what is your name")

    assert result is not None, result
    assert "Grok" in result, result