import pytest
from naas_abi_core.services.agent.Agent import Agent
from naas_abi_marketplace.__demo__.agents.MultiModelAgent import create_agent


@pytest.fixture
def agent() -> Agent:
    return create_agent()


def test_multi_model_agent(agent: Agent):
    e = agent.invoke(
        "What are the key differences between renewable and non-renewable energy sources?"
    )
    assert "gpt-5.2" in e.lower(), e
    assert "gpt-5-mini" in e.lower(), e
    assert "gpt-5.5" in e.lower(), e
    assert "comparison agent" in e.lower(), e
    assert "Python Code Execution Agent" not in e.lower(), e
