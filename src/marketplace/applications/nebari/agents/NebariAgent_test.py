import pytest

from src.marketplace.applications.nebari.agents.NebariAgent import create_agent

@pytest.fixture
def agent():
    return create_agent()

def test_agent_name(agent):
    result = agent.invoke("What is your name?")

    assert result is not None, result
    assert "Nebari" in result, result

def test_intent_favorite_color(agent):
    result = agent.invoke("What is your favorite color?")

    assert result is not None, result
    assert "blue" in result.lower(), result

def test_intent_favorite_animal(agent):
    result = agent.invoke("What is your favorite animal?")

    assert result is not None, result
    assert "dog" in result.lower(), result

def test_intent_favorite_food(agent):
    result = agent.invoke("What is your favorite food?")

    assert result is not None, result
    assert "pizza" in result.lower(), result