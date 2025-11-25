import pytest

from src.marketplace.applications.nebari.agents.NebariAgent import create_agent
from abi.services.agent.IntentAgent import IntentType, IntentScope

@pytest.fixture
def agent():
    return create_agent()

def test_agent_name(agent):
    result = agent.invoke("What is your name?")

    assert result is not None, result
    assert "Nebari" in result, result

def test_intents(agent):
    if hasattr(agent, "intents"):
        intents = agent.intents

    for intent in intents:
        if intent.intent_type == IntentType.RAW and intent.intent_scope != IntentScope.DIRECT:
            result = agent.invoke(intent.intent_value)
            assert result is not None, f"Intent: {intent.intent_value} did not return a result."
            assert intent.intent_target in result, f"For intent '{intent.intent_value}', expected '{intent.intent_target}' in result: {result}"