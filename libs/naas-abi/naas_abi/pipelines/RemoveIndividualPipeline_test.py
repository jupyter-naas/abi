import pytest
from naas_abi import ABIModule
from naas_abi.pipelines.RemoveIndividualPipeline import (
    RemoveIndividualPipeline,
    RemoveIndividualPipelineConfiguration,
    RemoveIndividualPipelineParameters,
)
from naas_abi_core.utils.SPARQL import SPARQLUtils

triple_store_service = ABIModule.get_instance().engine.services.triple_store
sparql_utils = SPARQLUtils(triple_store_service)


@pytest.fixture
def pipeline() -> RemoveIndividualPipeline:
    return RemoveIndividualPipeline(
        RemoveIndividualPipelineConfiguration(triple_store=triple_store_service)
    )


def test_remove_individual_pipeline(pipeline: RemoveIndividualPipeline):
    import time
    from uuid import uuid4

    from rdflib import OWL, RDF, RDFS, Graph, Literal, Namespace, URIRef

    ABI = Namespace("http://ontology.naas.ai/abi/")

    graph = Graph()
    uri = ABI[str(uuid4())]
    graph.add(
        (uri, RDF.type, URIRef("https://www.commoncoreontologies.org/ont00000443"))
    )
    graph.add((uri, RDF.type, OWL.NamedIndividual))
    graph.add((uri, RDFS.label, Literal("Naas.ai")))
    graph.add(
        (
            uri,
            ABI.logo,
            Literal(
                "https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcQ9gXMaBLQZ39W6Pk53PRuzFjUvv_6lLRWPoQ&s"
            ),
        )
    )
    triple_store_service.insert(graph)
    time.sleep(3)

    # Run pipeline to remove triples
    graph = pipeline.run(
        RemoveIndividualPipelineParameters(
            uris_to_remove=[str(uri)],
        )
    )
    assert graph is not None, graph.serialize(format="turtle")

    # Check if uri is removed in triplestore
    graph = sparql_utils.get_subject_graph(str(uri), 1)
    assert len(graph) == 0, graph.serialize(format="turtle")
