import pytest

from src.core.modules.ontology.pipelines.RemoveIndividualPipeline import (
    RemoveIndividualPipeline,
    RemoveIndividualPipelineConfiguration,
    RemoveIndividualPipelineParameters,
)
from src import services

@pytest.fixture
def pipeline() -> RemoveIndividualPipeline:
    return RemoveIndividualPipeline(
        RemoveIndividualPipelineConfiguration(
            triple_store=services.triple_store_service
        )
    )

def test_remove_individual_pipeline(pipeline: RemoveIndividualPipeline):
    from src import services
    from rdflib import Graph, URIRef, RDFS, Literal, OWL, Namespace, RDF
    from uuid import uuid4
    import time
    from src.utils.SPARQL import get_subject_graph

    ABI = Namespace("http://ontology.naas.ai/abi/")

    graph = Graph()
    uri = ABI[str(uuid4())]
    graph.add((uri, RDF.type, URIRef("https://www.commoncoreontologies.org/ont00000443")))
    graph.add((uri, RDF.type, OWL.NamedIndividual))
    graph.add((uri, RDFS.label, Literal("Naas.ai")))
    graph.add((uri, ABI.logo, Literal("https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcQ9gXMaBLQZ39W6Pk53PRuzFjUvv_6lLRWPoQ&s")))
    services.triple_store_service.insert(graph)
    time.sleep(3)

    # Run pipeline to remove triples
    graph = pipeline.run(RemoveIndividualPipelineParameters(
        uris_to_remove=[str(uri)],
    ))
    assert graph is not None, graph.serialize(format="turtle")
    
    # Check if uri is removed in triplestore
    graph = get_subject_graph(str(uri), 1)
    assert len(graph) == 0, graph.serialize(format="turtle")