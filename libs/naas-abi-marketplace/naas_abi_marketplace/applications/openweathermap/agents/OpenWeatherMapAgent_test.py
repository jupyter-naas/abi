import pytest


@pytest.fixture
def agent():
    from naas_abi_core.engine.Engine import Engine
    from naas_abi_marketplace.applications.openweathermap.agents.OpenWeatherMapAgent import (
        OpenWeatherMapAgent,
    )

    engine = Engine()
    engine.load(module_names=["naas_abi_marketplace.applications.openweathermap"])

    return OpenWeatherMapAgent.New()


def test_agent_name(agent):
    result = agent.invoke("What is your name?")

    assert result is not None, result
    assert "OpenWeatherMap" in result or "Open Weather" in result or "Weather" in result, result


def test_agent_system_prompt(agent):
    result = agent.invoke("What can you help me with?")

    assert result is not None, result
    assert "weather" in result.lower() or "forecast" in result.lower() or "meteorological" in result.lower(), result
