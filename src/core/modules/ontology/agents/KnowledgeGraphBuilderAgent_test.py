import pytest

from abi.services.agent.Agent import Agent
from src.core.modules.ontology.agents.KnowledgeGraphBuilderAgent import create_agent

@pytest.fixture
def agent() -> Agent:
    return create_agent()

def test_search_company_found(agent: Agent):
    e = agent.invoke("Recherche la société Accor")
    assert "Accor" in e, e
    assert "http://ontology.naas.ai/abi/0fff1541-a93e-468d-a890-510d59525ee3" in e, e

def test_search_company_not_found(agent: Agent):
    e = agent.invoke("Recherche la société YDXZ")
    assert "Je suis désolé" in e, e