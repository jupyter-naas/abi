import pytest


@pytest.fixture
def agent():
    from naas_abi_core.engine.Engine import Engine
    from naas_abi_marketplace.applications.sendgrid.agents.SendGridAgent import (
        SendGridAgent,
    )

    engine = Engine()
    engine.load(module_names=["naas_abi_marketplace.applications.sendgrid"])

    return SendGridAgent.New()


def test_agent_name(agent):
    result = agent.invoke("What is your name?")
    
    assert result is not None, result
    assert "SendGrid" in result, result


def test_agent_system_prompt(agent):
    result = agent.invoke("What can you help me with?")
    
    assert result is not None, result
    assert "email" in result.lower() or "sendgrid" in result.lower(), result

