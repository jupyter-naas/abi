import pytest


@pytest.fixture
def agent():
    from naas_abi_core.engine.Engine import Engine
    from naas_abi_marketplace.applications.hubspot.agents.HubSpotAgent import (
        HubSpotAgent,
    )

    engine = Engine()
    engine.load(module_names=["naas_abi_marketplace.applications.hubspot"])

    return HubSpotAgent.New()


def test_agent_name(agent):
    result = agent.invoke("What is your name?")

    assert result is not None, result
    assert "HubSpot" in result, result


def test_agent_system_prompt(agent):
    result = agent.invoke("What can you help me with?")

    assert result is not None, result
    assert "crm" in result.lower() or "hubspot" in result.lower() or "marketing" in result.lower(), result
