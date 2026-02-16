import pytest
from naas_abi_marketplace.applications.qonto.agents.QontoAgent import create_agent


@pytest.fixture
def agent():
    return create_agent()


def test_agent_name(agent):
    result = agent.invoke("What is your name?")

    assert result is not None, result
    assert "Qonto" in result, result


def test_agent_system_prompt(agent):
    result = agent.invoke("What can you help me with?")

    assert result is not None, result
    assert (
        "qonto" in result.lower()
        or "banking" in result.lower()
        or "financial" in result.lower()
        or "business" in result.lower()
    ), result
