import pytest


@pytest.fixture
def agent():
    from naas_abi_core.engine.Engine import Engine
    from naas_abi_marketplace.applications.airtable.agents.AirtableAgent import (
        AirtableAgent,
    )

    engine = Engine()
    engine.load(module_names=["naas_abi_marketplace.applications.airtable"])

    return AirtableAgent.New()


def test_agent_name(agent):
    result = agent.invoke("What is your name?")

    assert result is not None, result
    assert "Airtable" in result, result


def test_agent_system_prompt(agent):
    result = agent.invoke("What can you help me with?")

    assert result is not None, result
    assert "database" in result.lower() or "airtable" in result.lower(), result
