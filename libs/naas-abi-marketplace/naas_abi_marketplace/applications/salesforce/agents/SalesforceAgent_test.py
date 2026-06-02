import pytest


@pytest.fixture
def agent():
    from naas_abi_core.engine.Engine import Engine
    from naas_abi_marketplace.applications.salesforce.agents.SalesforceAgent import (
        SalesforceAgent,
    )

    engine = Engine()
    engine.load(module_names=["naas_abi_marketplace.applications.salesforce"])

    return SalesforceAgent.New()


def test_agent_name(agent):
    result = agent.invoke("What is your name?")

    assert result is not None, result
    assert "Salesforce" in result, result


def test_agent_system_prompt(agent):
    result = agent.invoke("What can you help me with?")

    assert result is not None, result
    assert "salesforce" in result.lower() or "crm" in result.lower() or "sales" in result.lower() or "pipeline" in result.lower(), result
