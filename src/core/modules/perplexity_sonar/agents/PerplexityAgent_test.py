import pytest

from src.custom.modules.perplexity.agents.PerplexityAgent import create_agent

@pytest.fixture
def agent():
    return create_agent()

def test_perplexity_agent(agent):
    e = agent.invoke("Cherche sur Perplexity, le gagnant de la dernière ligue des champions masculin")
    assert "Paris Saint-Germain" in e, e