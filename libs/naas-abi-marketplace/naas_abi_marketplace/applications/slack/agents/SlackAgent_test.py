import pytest
from naas_abi_marketplace.applications.slack.agents.SlackAgent import create_agent


@pytest.fixture
def agent():
    return create_agent()


def test_agent_name(agent):
    result = agent.invoke("What is your name?")

    assert result is not None, result
    assert "Slack" in result, result


def test_agent_system_prompt(agent):
    result = agent.invoke("What can you help me with?")

    assert result is not None, result
    assert (
        "slack" in result.lower()
        or "channel" in result.lower()
        or "team" in result.lower()
        or "collaboration" in result.lower()
    ), result
