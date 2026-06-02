import pytest


@pytest.fixture
def agent():
    from naas_abi_core.engine.Engine import Engine
    from naas_abi_marketplace.applications.qonto.agents.QontoAgent import (
        QontoAgent,
    )

    engine = Engine()
    engine.load(module_names=["naas_abi_marketplace.applications.qonto"])

    return QontoAgent.New()


def test_agent_name(agent):
    result = agent.invoke("What is your name?")

    assert result is not None, result
    assert "Qonto" in result, result


def test_agent_system_prompt(agent):
    result = agent.invoke("What can you help me with?")

    assert result is not None, result
    assert "qonto" in result.lower() or "banking" in result.lower() or "financial" in result.lower() or "business" in result.lower(), result
