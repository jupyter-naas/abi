import pytest

from src.core.abi.workflows.SearchIndividualWorkflow import (
    SearchIndividualWorkflow,
    SearchIndividualWorkflowConfiguration,
    SearchIndividualWorkflowParameters,
)

@pytest.fixture
def search_individual_workflow() -> SearchIndividualWorkflow:
    from src import services
    
    # Configurations
    search_individual_workflow_configuration = SearchIndividualWorkflowConfiguration(
        triple_store=services.triple_store_service
    )

    # Workflow
    search_individual_workflow = SearchIndividualWorkflow(
        configuration=search_individual_workflow_configuration
    )
    
    return search_individual_workflow



def test_search_individual_workflow(search_individual_workflow: SearchIndividualWorkflow):
    from rdflib import Graph, URIRef, RDFS, Literal, OWL
    from abi.utils.Graph import TEST
    from uuid import uuid4
    from src import services
    
    graph = Graph()
    node_id = str(uuid4())
    graph.add((TEST[node_id], URIRef("http://www.w3.org/1999/02/22-rdf-syntax-ns#type"), URIRef("https://www.commoncoreontologies.org/ont00000443")))
    graph.add((TEST[node_id], URIRef("http://www.w3.org/1999/02/22-rdf-syntax-ns#type"), OWL.NamedIndividual))
    graph.add((TEST[node_id], RDFS.label, Literal(node_id)))
    
    services.triple_store_service.insert(graph)
    
    # Test
    result = search_individual_workflow.search_individual(
        SearchIndividualWorkflowParameters(
            search_label=node_id,
            class_uri="https://www.commoncoreontologies.org/ont00000443",
            limit=10,
            query=None
        )
    )
    
    assert isinstance(result, list), result
    assert len(result) == 1, result
    assert result[0]["label"] == node_id, result[0]
    
    services.triple_store_service.remove(graph)
    
    # Test
    result = search_individual_workflow.search_individual(
        SearchIndividualWorkflowParameters(
            search_label=node_id,
            class_uri="https://www.commoncoreontologies.org/ont00000443",
            limit=10,
            query=None
        )
    )
    
    assert len(result) == 0, result
    
    
def test_search_unexisting_individual(search_individual_workflow: SearchIndividualWorkflow):
    # Test
    result = search_individual_workflow.search_individual(
        SearchIndividualWorkflowParameters(
            search_label="kndfggkljkdfjgldfklgdkfgdfg_does_not_exist",
            class_uri="https://www.commoncoreontologies.org/ont00000443",
            limit=10,
            query=None
        )
    )
    
    assert isinstance(result, list), result
    assert len(result) == 0, result