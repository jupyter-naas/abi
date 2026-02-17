import os

import pytest
from langchain_openai import OpenAIEmbeddings
from naas_abi_core.engine.Engine import Engine
from naas_abi_core.modules.triplestore_embeddings import ABIModule
from naas_abi_core.modules.triplestore_embeddings.utils.Embeddings import (
    EmbeddingsUtils,
)
from naas_abi_core.modules.triplestore_embeddings.workflows.DeleteTripleEmbeddingsWorkflow import (
    DeleteTripleEmbeddingsWorkflow,
    DeleteTripleEmbeddingsWorkflowConfiguration,
)

# Set ENV=test to ensure test graph is used
os.environ["TEST"] = "true"

engine = Engine()
engine.load(module_names=["naas_abi_core.modules.triplestore_embeddings"])

module: ABIModule = ABIModule.get_instance()

collection_name = module.configuration.collection_name + "_test"
embeddings_dimensions = module.configuration.embeddings_dimensions
if module.configuration.embeddings_model_provider == "openai":
    embeddings_model = OpenAIEmbeddings(
        model=module.configuration.embeddings_model_name,
        dimensions=embeddings_dimensions,
    )
else:
    raise ValueError(
        f"Embeddings model provider {module.configuration.embeddings_model_provider} not supported"
    )

embeddings_utils = EmbeddingsUtils(embeddings_model=embeddings_model)

# Test graph name constant
TEST_GRAPH_NAME = "http://ontology.naas.ai/abi/test/"


@pytest.fixture
def workflow() -> DeleteTripleEmbeddingsWorkflow:
    configuration = DeleteTripleEmbeddingsWorkflowConfiguration(
        vector_store=module.engine.services.vector_store,
        embeddings_model=embeddings_model,
        embeddings_dimensions=embeddings_dimensions,
        collection_name=collection_name,
    )
    workflow = DeleteTripleEmbeddingsWorkflow(configuration)
    return workflow


def test_subscribe_delete_triple_embeddings(workflow):
    import time
    from uuid import uuid4

    from rdflib import OWL, RDF, RDFS, Graph, Literal, URIRef

    uri = "http://ontology.naas.ai/abi/test/" + str(uuid4())
    label = "Florent Ravenel"
    class_uri = URIRef("https://www.commoncoreontologies.org/ont00001262")
    owl_type = OWL.NamedIndividual

    graph = Graph()
    graph.add((URIRef(uri), RDF.type, owl_type))
    graph.add((URIRef(uri), RDF.type, class_uri))
    graph.add((URIRef(uri), RDFS.label, Literal(label)))

    triple_store_service = module.engine.services.triple_store
    triple_store_service.insert(graph, graph_name=URIRef(TEST_GRAPH_NAME))
    time.sleep(10)

    vector_store_service = module.engine.services.vector_store

    vector = embeddings_utils.create_vector_embedding(label)
    search_results = vector_store_service.search_similar(
        collection_name=collection_name,
        query_vector=vector,
        k=10,
        filter={"uri": uri},
        include_metadata=True,
    )
    assert len(search_results) > 0, search_results

    triple_store_service.remove(graph, graph_name=URIRef(TEST_GRAPH_NAME))
    time.sleep(10)

    search_results = vector_store_service.search_similar(
        collection_name=collection_name,
        query_vector=vector,
        k=10,
        filter={"uri": uri},
        include_metadata=True,
    )
    assert len(search_results) == 0, search_results
