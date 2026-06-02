import pytest


@pytest.fixture
def agent():
    from naas_abi_core.engine.Engine import Engine
    from naas_abi_marketplace.applications.whatsapp_business.agents.WhatsAppBusinessAgent import (
        WhatsAppBusinessAgent,
    )

    engine = Engine()
    engine.load(module_names=["naas_abi_marketplace.applications.whatsapp_business"])

    return WhatsAppBusinessAgent.New()


def test_agent_name(agent):
    result = agent.invoke("What is your name?")

    assert result is not None, result
    assert "WhatsApp" in result or "Whatsapp" in result, result


def test_agent_system_prompt(agent):
    result = agent.invoke("What can you help me with?")

    assert result is not None, result
    assert "whatsapp" in result.lower() or "messaging" in result.lower() or "business" in result.lower() or "customer" in result.lower(), result
