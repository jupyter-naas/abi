import pytest


@pytest.fixture
def agent():
    from naas_abi_core.engine.Engine import Engine
    from naas_abi_marketplace.applications.stripe.agents.StripeAgent import (
        StripeAgent,
    )

    engine = Engine()
    engine.load(module_names=["naas_abi_marketplace.applications.stripe"])

    return StripeAgent.New()


def test_agent_name(agent):
    result = agent.invoke("What is your name?")

    assert result is not None, result
    assert "Stripe" in result, result


def test_agent_system_prompt(agent):
    result = agent.invoke("What can you help me with?")

    assert result is not None, result
    assert "stripe" in result.lower() or "payment" in result.lower() or "subscription" in result.lower(), result
