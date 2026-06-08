import pytest


@pytest.fixture
def agent():
    from naas_abi_core.engine.Engine import Engine
    from naas_abi_marketplace.applications.twilio.agents.TwilioAgent import (
        TwilioAgent,
    )

    engine = Engine()
    engine.load(module_names=["naas_abi_marketplace.applications.twilio"])

    return TwilioAgent.New()


def test_agent_name(agent):
    result = agent.invoke("What is your name?")

    assert result is not None, result
    assert "Twilio" in result, result


def test_agent_system_prompt(agent):
    result = agent.invoke("What can you help me with?")

    assert result is not None, result
    assert "twilio" in result.lower() or "sms" in result.lower() or "messaging" in result.lower() or "communication" in result.lower(), result
