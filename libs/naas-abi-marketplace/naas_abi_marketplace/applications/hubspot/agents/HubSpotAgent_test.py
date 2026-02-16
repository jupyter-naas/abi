import pytest
from naas_abi_marketplace.applications.hubspot.agents.HubSpotAgent import create_agent


@pytest.fixture
def agent():
    return create_agent()


def test_agent_name(agent):
    result = agent.invoke("What is your name?")

    assert result is not None, result
    assert "HubSpot" in result, result


def test_agent_system_prompt(agent):
    result = agent.invoke("What can you help me with?")

    assert result is not None, result
    assert (
        "crm" in result.lower()
        or "hubspot" in result.lower()
        or "marketing" in result.lower()
    ), result
