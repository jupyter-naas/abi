import pytest
from naas_abi_core import logger
from naas_abi_core.engine.Engine import Engine
from naas_abi_core.modules.triplestore_embeddings import ABIModule
from naas_abi_core.modules.triplestore_embeddings.pipelines.MergeIndividualsPipeline import (
    MergeIndividualsPipeline,
    MergeIndividualsPipelineConfiguration,
    MergeIndividualsPipelineParameters,
)
from naas_abi_core.utils.SPARQL import SPARQLUtils

engine = Engine()
engine.load(module_names=["naas_abi_core.modules.triplestore_embeddings"])
module: ABIModule = ABIModule.get_instance()

triple_store_service = engine.services.triple_store
object_storage_service = engine.services.object_storage
sparql_utils = SPARQLUtils(triple_store_service)


@pytest.fixture
def pipeline() -> MergeIndividualsPipeline:
    configuration = MergeIndividualsPipelineConfiguration(
        triple_store=triple_store_service,
        object_storage=object_storage_service,
        datastore_path="merged_individual_test",
    )
    return MergeIndividualsPipeline(configuration)


def test_merge_individuals_pipeline(pipeline: MergeIndividualsPipeline):
    import time
    from uuid import uuid4

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
