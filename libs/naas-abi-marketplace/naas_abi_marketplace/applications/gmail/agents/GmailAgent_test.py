import pytest


@pytest.fixture
def agent():
    from naas_abi_core.engine.Engine import Engine
    from naas_abi_marketplace.applications.gmail.agents.GmailAgent import (
        GmailAgent,
    )

    engine = Engine()
    engine.load(module_names=["naas_abi_marketplace.applications.gmail"])

    return GmailAgent.New()


def test_agent_name(agent):
    result = agent.invoke("What is your name?")

    assert result is not None, result
    assert "Gmail" in result, result


def test_agent_system_prompt(agent):
    result = agent.invoke("What can you help me with?")

    assert result is not None, result
    assert "email" in result.lower() or "gmail" in result.lower(), result
