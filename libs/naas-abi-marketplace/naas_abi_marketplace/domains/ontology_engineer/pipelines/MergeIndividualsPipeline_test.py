import pytest
from naas_abi_core.utils.SPARQL import SPARQLUtils
from naas_abi_marketplace.domains.ontology_engineer import ABIModule
from naas_abi_marketplace.domains.ontology_engineer.pipelines.MergeIndividualsPipeline import (
    MergeIndividualsPipeline,
    MergeIndividualsPipelineConfiguration,
    MergeIndividualsPipelineParameters,
)

triple_store_service = ABIModule.get_instance().engine.services.triple_store
object_storage_service = ABIModule.get_instance().engine.services.object_storage
sparql_utils = SPARQLUtils(triple_store_service)


@pytest.fixture
def pipeline() -> MergeIndividualsPipeline:
    return MergeIndividualsPipeline(
        MergeIndividualsPipelineConfiguration(
            triple_store=triple_store_service,
            object_storage=object_storage_service,
        )
    )


def test_merge_individuals_pipeline(pipeline: MergeIndividualsPipeline):
    import time
    from uuid import uuid4

    from naas_abi_core import logger
    from rdflib import OWL, RDF, RDFS, SKOS, Graph, Literal, Namespace, URIRef

    ABI = Namespace("http://ontology.naas.ai/abi/")

    graph = Graph()
    uri_to_keep = ABI[str(uuid4())]
    graph.add(
        (
            uri_to_keep,
            RDF.type,
            URIRef("https://www.commoncoreontologies.org/ont00000443"),
        )
    )
    graph.add((uri_to_keep, RDF.type, OWL.NamedIndividual))
    graph.add((uri_to_keep, RDFS.label, Literal("Naas.ai")))
    graph.add(
        (
            uri_to_keep,
            ABI.logo,
            Literal(
                "https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcQ9gXMaBLQZ39W6Pk53PRuzFjUvv_6lLRWPoQ&s"
            ),
        )
    )

    uri_to_merge = ABI[str(uuid4())]
    graph.add(
        (
            uri_to_merge,
            RDF.type,
            URIRef("https://www.commoncoreontologies.org/ont00000443"),
        )
    )
    graph.add((uri_to_merge, RDF.type, OWL.NamedIndividual))
    graph.add((uri_to_merge, RDFS.label, Literal("Naas.ai 2")))
    graph.add(
        (
            uri_to_merge,
            ABI.logo,
            Literal(
                "https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcQ9gXMaBLQZ39W6Pk53PRuzFjUvv_6lLRWPoQ&s"
            ),
        )
    )

    logger.info("Inserting triples to triplestore")
    triple_store_service.insert(graph)
    time.sleep(3)

    # Run pipeline to merge individuals
    graph_merged = pipeline.run(
        MergeIndividualsPipelineParameters(
            merge_pairs=[
                (uri_to_keep, uri_to_merge),
            ]
        )
    )
    assert graph_merged is not None, graph_merged.serialize(format="turtle")
    assert str(graph_merged.value(uri_to_keep, RDFS.label)) == "Naas.ai", (
        graph_merged.serialize(format="turtle")
    )
    assert str(graph_merged.value(uri_to_keep, SKOS.altLabel)) == "Naas.ai 2", (
        graph_merged.serialize(format="turtle")
    )
    assert len(list(graph_merged.triples((uri_to_keep, ABI.logo, None)))) == 1, (
        graph_merged.serialize(format="turtle")
    )

    # Check if uri_to_merge is removed in triplestore
    graph = sparql_utils.get_subject_graph(str(uri_to_merge), 1)
    assert len(graph) == 0, graph.serialize(format="turtle")

    # Remove graphs
    triple_store_service.remove(graph_merged)
    time.sleep(3)
