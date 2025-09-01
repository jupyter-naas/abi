import pytest

from abi.services.agent.Agent import Agent
from src.core.modules.abi.agents.KnowledgeGraphBuilderAgent import create_agent

@pytest.fixture
def agent() -> Agent:
    return create_agent()

def test_add_individual(agent: Agent):
    e = agent.invoke("Add individual Naas.ai as Organization")
    assert "We are going to add the following individual" in e, e
    assert "Individual label" in e, e
    assert "Class URI" in e, e
    assert "Are you sure you want to add this individual?" in e, e

def test_insert_data_sparql(agent: Agent):
    e = agent.invoke("""
    ```sparql
    INSERT DATA {
        <http://ontology.naas.ai/abi/test> <http://www.w3.org/2000/01/rdf-schema#label> "Test" .
    }
    ```
    """)
    assert "we are going to insert data from the following sparql statement" in e.lower() or "multiple individuals" in e.lower() or "multiple instances" in e.lower(), e
    if "multiple individuals" not in e.lower() and "multiple instances" not in e.lower():
        assert "Are you sure you want to insert this data?" in e or "please confirm" in e.lower(), e

def test_update_data_property(agent: Agent):
    e = agent.invoke("Update label of Naas.ai to Naas")
    assert "We are going to update the following data property" in e or "multiple individuals" in e.lower(), e
    if "multiple individuals" not in e.lower():
        assert "Individual URI" in e, e
        assert "Data property to update" in e, e 
        assert "Old value" in e, e
        assert "New value" in e, e
    assert "Are you sure you want to update this data property?" in e or "please confirm" in e.lower(), e

def test_merge_individuals(agent: Agent):
    e = agent.invoke("Merge duplicate Naas.ai instances")
    assert "We are going to merge the following individuals" in e or "multiple individuals" in e.lower() or "only one" in e.lower(), e
    if "multiple individuals" not in e.lower() and "only one" not in e.lower():
        assert "Instance to keep" in e, e
        assert "Instance to merge" in e, e
        assert "Are you sure you want to merge these individuals?" in e or "please confirm" in e.lower(), e

def test_remove_individual(agent: Agent):
    e = agent.invoke("Remove individual Naas.ai")
    assert "We are going to remove the following individual" in e or "multiple individuals" in e, e
    assert "Are you sure you want to remove this individual?" in e or "please confirm" in e.lower(), e