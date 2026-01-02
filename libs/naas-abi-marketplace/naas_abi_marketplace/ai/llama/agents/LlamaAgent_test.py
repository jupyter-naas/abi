import pytest
from naas_abi_marketplace.ai.llama.agents.LlamaAgent import create_agent


@pytest.fixture
def agent():
    return create_agent()


def test_agent_name(agent):
    result = agent.invoke("what is your name")

    assert result is not None, result
    assert "Llama" in result, result
