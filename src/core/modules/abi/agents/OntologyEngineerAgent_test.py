import pytest

from src.core.modules.abi.agents.OntologyEngineerAgent import create_agent

@pytest.fixture
def agent():
    return create_agent()

def test_question_about_bfo_ontology(agent):
    intent = "What's an Organization?"
    result = agent.invoke(intent)
    assert result is not None, result
    assert "BFO_0000040" or  "material entity" in result, result

def test_text_to_ontology_transformation(agent):
    intent = "Map to ontology: 'Florent Ravenel is working for Naas.ai'"
    result = agent.invoke(intent)
    assert result is not None, result
    assert "Florent Ravenel is working for Naas.ai" in result, result
    assert "```sparql" in result, result
    assert "INSERT DATA" in result, result

def test_add_to_triplestore_confirmation(agent):
    intent = """Add to triplestore the following SPARQL statement:
    ```sparql
    INSERT DATA {
    <http://ontology.naas.ai/abi/69a231b9-e87a-4503-8f80-a530ed8eaa4b> <http://www.w3.org/2000/01/rdf-schema#label> "Naas.ai" .
    }
    ```
    """
    result = agent.invoke(intent)
    assert result is not None, result
    assert "I am going to add the following SPARQL statement to the triplestore" in result, result
    assert "Are you sure you want to add this SPARQL statement to the triplestore?" in result, result