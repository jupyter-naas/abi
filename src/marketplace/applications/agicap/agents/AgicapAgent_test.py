import pytest

from src.marketplace.applications.agicap.agents.AgicapAgent import create_agent

@pytest.fixture
def agent():
    return create_agent()

def test_agent(agent):
    response = agent.run("Quelles sont mes entreprises ?")
    assert response is not None
    assert "entreprises" in response.lower()

def test_agent_with_company(agent):
    response = agent.run("Quelles sont les entreprises de la société X ?")
    assert response is not None
    assert "entreprises" in response.lower()
    assert "société X" in response.lower()

def test_agent_with_account(agent):
    response = agent.run("Quels sont les comptes de la société X ?")
    assert response is not None
    assert "comptes" in response.lower()

def test_agent_with_transactions(agent):
    response = agent.run("Quels sont les transactions de la société X ?")
    assert response is not None
    assert "transactions" in response.lower()

def test_agent_with_balance(agent):
    response = agent.run("Quel est le solde de la société X ?")
    assert response is not None
    assert "solde" in response.lower()

def test_agent_with_debts(agent):
    response = agent.run("Quelles sont les dettes de la société X ?")
    assert response is not None
    assert "dettes" in response.lower()