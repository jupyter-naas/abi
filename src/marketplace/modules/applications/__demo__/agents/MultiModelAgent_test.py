import pytest

from abi.services.agent.Agent import Agent
from src.marketplace.modules.applications.__demo__.agents.MultiModelAgent import create_agent

@pytest.fixture
def agent() -> Agent:
    return create_agent()

def test_multi_model_agent(agent: Agent):
    e = agent.invoke("What are the key differences between renewable and non-renewable energy sources?")
    assert "o3-mini" in e.lower(), e
    assert "gpt-4o-mini" in e.lower(), e
    assert "gpt-4-1" in e.lower(), e
    assert "comparison agent" in e.lower(), e
    assert "Python Code Execution Agent" not in e.lower(), e