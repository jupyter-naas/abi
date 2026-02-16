import pytest
from naas_abi_marketplace.applications.aws.agents.AWSAgent import create_agent


@pytest.fixture
def agent():
    return create_agent()


def test_agent_name(agent):
    result = agent.invoke("What is your name?")

    assert result is not None, result
    assert "AWS" in result, result


def test_agent_system_prompt(agent):
    result = agent.invoke("What can you help me with?")

    assert result is not None, result
    assert (
        "aws" in result.lower()
        or "cloud" in result.lower()
        or "infrastructure" in result.lower()
    ), result
