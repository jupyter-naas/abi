import pytest


@pytest.fixture
def agent():
    from naas_abi_core.engine.Engine import Engine
    from naas_abi_marketplace.applications.pennylane.agents.PennylaneAgent import (
        PennylaneAgent,
    )

    engine = Engine()
    engine.load(module_names=["naas_abi_marketplace.applications.pennylane"])

    return PennylaneAgent.New()


def test_agent_name(agent):
    result = agent.invoke("What is your name?")
    
    assert result is not None, result
    assert "Pennylane" in result or "PennylaneAgent" in result, result


def test_agent_system_prompt(agent):
    result = agent.invoke("What can you help me with?")
    
    assert result is not None, result
    assert "pennylane" in result.lower() or "accounting" in result.lower() or "financial" in result.lower() or "comptable" in result.lower(), result

