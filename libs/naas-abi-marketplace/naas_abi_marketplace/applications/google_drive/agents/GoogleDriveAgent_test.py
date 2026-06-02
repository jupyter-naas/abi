import pytest


@pytest.fixture
def agent():
    from naas_abi_core.engine.Engine import Engine
    from naas_abi_marketplace.applications.google_drive.agents.GoogleDriveAgent import (
        GoogleDriveAgent,
    )

    engine = Engine()
    engine.load(module_names=["naas_abi_marketplace.applications.google_drive"])

    return GoogleDriveAgent.New()


def test_agent_name(agent):
    result = agent.invoke("What is your name?")

    assert result is not None, result
    assert "Google Drive" in result or "Drive" in result, result


def test_agent_system_prompt(agent):
    result = agent.invoke("What can you help me with?")

    assert result is not None, result
    assert "file" in result.lower() or "drive" in result.lower() or "storage" in result.lower(), result
