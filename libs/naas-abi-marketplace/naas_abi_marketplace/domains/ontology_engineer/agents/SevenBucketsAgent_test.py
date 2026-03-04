import pytest
from naas_abi_marketplace.domains.ontology_engineer.agents.SevenBucketsAgent import (
    create_agent,
)


@pytest.fixture
def agent():
    from naas_abi_core.engine.Engine import Engine

    engine = Engine()
    engine.load(module_names=["naas_abi_marketplace.ai.chatgpt"])
    return create_agent()


def test_agent_role(agent):
    result = agent.invoke("What is your role?")
    assert result is not None, f"Result is None: {result}"
    assert "Ontology Engineer" in result, (
        f"Result does not contain 'Ontology Engineer': {result}"
    )


def test_agent_can_save_ontology(agent, tmp_path):
    # Test ontology Turtle string (without leading instruction)
    text = """Please save this ontology: ```turtle
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix owl: <http://www.w3.org/2002/07/owl#> .
@prefix skos: <http://www.w3.org/2004/02/skos/core#> .
@prefix bfo: <http://purl.obolibrary.org/obo/> .
@prefix abi: <http://ontology.naas.ai/abi/> .

abi:Abi a owl:Class ;
    rdfs:label "Abi"@en ;
    skos:definition "Abi is a material entity ."@en ;
    rdfs:subClassOf bfo:BFO_0000040 .
```"""

    result = agent.invoke(text)
    assert result is not None, f"Result is None: {result}"

    # The ontology should have been saved into the ontologies folder
    import os
    import re

    from naas_abi_marketplace.domains.ontology_engineer.agents import SevenBucketsAgent

    ONTOLOGIES_DIR = SevenBucketsAgent.ONTOLOGIES_DIR

    filepath = re.search(r"Saved (\w+)\.ttl \(triples=\d+\) to (.+)", result).group(2)
    assert os.path.exists(filepath), (
        f"File path does not exist: {filepath} in result: {result}"
    )
    assert ONTOLOGIES_DIR in filepath, (
        f"Ontology file is not saved in the ontologies folder: {filepath}"
    )

    # Clean up after test
    os.remove(filepath)
