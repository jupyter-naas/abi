import pytest


@pytest.fixture
def agent():
    from naas_abi_core.engine.Engine import Engine
    from naas_abi_marketplace.applications.naas.agents.NaasAgent import (
        NaasAgent,
    )

    engine = Engine()
    engine.load(module_names=["naas_abi_marketplace.applications.naas"])

    return NaasAgent.New()


def test_agent_presentation(agent):
    result = agent.run(input="What's your name?")

    assert result is not None, result
    assert "Naas" in result, result