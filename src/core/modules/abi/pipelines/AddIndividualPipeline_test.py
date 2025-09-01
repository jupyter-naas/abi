import pytest

from src.core.modules.abi.pipelines.AddIndividualPipeline import (
    AddIndividualPipeline,
    AddIndividualPipelineConfiguration,
    AddIndividualPipelineParameters,
)
from src.core.modules.abi.workflows.SearchIndividualWorkflow import (
    SearchIndividualWorkflowConfiguration,
)
from src import services

@pytest.fixture
def pipeline() -> AddIndividualPipeline:
    search_individual_workflow_configuration = SearchIndividualWorkflowConfiguration(
        triple_store=services.triple_store_service
    )
    pipeline = AddIndividualPipeline(
        configuration=AddIndividualPipelineConfiguration(
            triple_store=services.triple_store_service,
            search_individual_configuration=search_individual_workflow_configuration
        )
    )
    return pipeline

def test_add_individual_pipeline(pipeline: AddIndividualPipeline):
    from rdflib import URIRef, RDFS, Literal, RDF, OWL
    from src.utils.SPARQL import results_to_list
    
    label = "Naas.ai"
    class_uri = "https://www.commoncoreontologies.org/ont00000443"
    graph = pipeline.run(AddIndividualPipelineParameters(individual_label=label, class_uri=class_uri))

    individual_uri = list(graph.triples((None, RDF.type, OWL.NamedIndividual)))[0][0]

    assert graph is not None, graph.serialize(format="turtle")
    assert len(list(graph.triples((None, RDFS.label, Literal(label))))) == 1, graph.serialize(format="turtle")
    assert len(list(graph.triples((None, RDF.type, URIRef(class_uri))))) == 1, graph.serialize(format="turtle")

    # Remove graph
    services.triple_store_service.remove(graph)

    # Check triples are removed from the triple store
    sparql_query = """
    PREFIX abi: <http://ontology.naas.ai/abi/>
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    PREFIX cco: <https://www.commoncoreontologies.org/>
    PREFIX owl: <http://www.w3.org/2002/07/owl#>

    SELECT ?s ?p ?o
    WHERE {
        ?s ?p ?o .
        FILTER(?s = <{{individual_uri}}>)
    }
    """
    sparql_query = sparql_query.replace("{{individual_uri}}", str(individual_uri))
    results = services.triple_store_service.query(sparql_query)
    results_list = results_to_list(results)
    assert results_list is None, results_list