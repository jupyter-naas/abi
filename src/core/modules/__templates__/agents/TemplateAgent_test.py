import pytest

from src.core.modules.__templates__.agents.TemplateAgent import create_agent

@pytest.fixture
def agent():
    return create_agent()

def test_agent_name(agent):
    result = agent.invoke("What is your name?")

    assert result is not None, result
    assert "Template" in result, result