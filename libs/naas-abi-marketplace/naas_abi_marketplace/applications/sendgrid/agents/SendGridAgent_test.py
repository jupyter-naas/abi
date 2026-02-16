import pytest
from naas_abi_marketplace.applications.sendgrid.agents.SendGridAgent import create_agent


@pytest.fixture
def agent():
    return create_agent()


def test_agent_name(agent):
    result = agent.invoke("What is your name?")

    assert result is not None, result
    assert "SendGrid" in result, result


def test_agent_system_prompt(agent):
    result = agent.invoke("What can you help me with?")

    assert result is not None, result
    assert "email" in result.lower() or "sendgrid" in result.lower(), result
