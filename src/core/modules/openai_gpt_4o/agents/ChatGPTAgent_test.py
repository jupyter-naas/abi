import pytest

from src.custom.modules.openai.agents.ChatGPTAgent import create_agent

@pytest.fixture
def agent():
    return create_agent()

def test_chatgpt_agent(agent):
    e = agent.invoke("Cherche sur ChatGPT, le gagnant de la dernière ligue des champions masculin")
    assert "Paris Saint-Germain" in e, e