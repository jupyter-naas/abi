import pytest


@pytest.fixture
def agent():
    from naas_abi_core.engine.Engine import Engine
    from naas_abi_marketplace.applications.google_calendar.agents.GoogleCalendarAgent import (
        GoogleCalendarAgent,
    )

    engine = Engine()
    engine.load(module_names=["naas_abi_marketplace.applications.google_calendar"])

    return GoogleCalendarAgent.New()


def test_agent_name(agent):
    result = agent.invoke("What is your name?")

    assert result is not None, result
    assert "Google Calendar" in result or "Calendar" in result, result


def test_agent_system_prompt(agent):
    result = agent.invoke("What can you help me with?")

    assert result is not None, result
    assert "calendar" in result.lower() or "event" in result.lower() or "schedule" in result.lower(), result
