import pytest

from src.core.modules.ontology.pipelines.InsertDataSPARQLPipeline import (
    InsertDataSPARQLPipeline,
    InsertDataSPARQLPipelineConfiguration,
    InsertDataSPARQLPipelineParameters,
)
from src import services
from abi import logger

@pytest.fixture
def pipeline() -> InsertDataSPARQLPipeline:
    pipeline = InsertDataSPARQLPipeline(
        configuration=InsertDataSPARQLPipelineConfiguration(
            triple_store=services.triple_store_service
        )
    )
    return pipeline

def test_insert_data_sparql_pipeline(pipeline: InsertDataSPARQLPipeline):
    from rdflib import Namespace, URIRef, Literal
    from src.utils.SPARQL import results_to_list
    sparql_statement = """
    PREFIX abi: <http://ontology.naas.ai/abi/>
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    PREFIX cco: <https://www.commoncoreontologies.org/>
    PREFIX owl: <http://www.w3.org/2002/07/owl#>

    INSERT DATA {
        abi:john a cco:ont00001262, owl:NamedIndividual ;
                    abi:name "John Doe" ;
                    abi:age 30 ;
                    abi:email "john.doe@example.com" .
        
        abi:jane a cco:ont00001262, owl:NamedIndividual ;
                    abi:name "Jane Smith" ;
                    abi:age 28 ;
                    abi:email "jane.smith@example.com" .
    }
    """
    graph = pipeline.run(InsertDataSPARQLPipelineParameters(sparql_statement=sparql_statement))
    ABI = Namespace("http://ontology.naas.ai/abi/")

    assert graph is not None, graph.serialize(format="turtle")
    assert len(list(graph.triples((URIRef(ABI.john), ABI.name, Literal("John Doe"))))) == 1, graph.serialize(format="turtle")
    assert len(list(graph.triples((URIRef(ABI.jane), ABI.name, Literal("Jane Smith"))))) == 1, graph.serialize(format="turtle")

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
        FILTER(?s = abi:john || ?s = abi:jane)
    }
    """
    results = services.triple_store_service.query(sparql_query)
    results_list = results_to_list(results)
    assert results_list is None, results_list