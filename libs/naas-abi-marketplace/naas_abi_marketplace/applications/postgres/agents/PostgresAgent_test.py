import pytest


@pytest.fixture
def agent():
    from naas_abi_core.engine.Engine import Engine
    from naas_abi_marketplace.applications.postgres.agents.PostgresAgent import (
        PostgresAgent,
    )

    engine = Engine()
    engine.load(module_names=["naas_abi_marketplace.applications.postgres"])

    return PostgresAgent.New()


def test_agent_name(agent):
    result = agent.invoke("What is your name?")
    
    assert result is not None, result
    assert "PostgreSQL" in result or "Postgres" in result, result


def test_agent_system_prompt(agent):
    result = agent.invoke("What can you help me with?")
    
    assert result is not None, result
    assert "postgres" in result.lower() or "database" in result.lower() or "sql" in result.lower(), result

