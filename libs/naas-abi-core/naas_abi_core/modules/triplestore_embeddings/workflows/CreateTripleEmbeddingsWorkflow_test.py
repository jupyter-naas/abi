import pytest
from langchain_openai import OpenAIEmbeddings
from naas_abi_core.engine.Engine import Engine
from naas_abi_core.modules.triplestore_embeddings import ABIModule
from naas_abi_core.modules.triplestore_embeddings.utils.Embeddings import (
    EmbeddingsUtils,
)
from naas_abi_core.modules.triplestore_embeddings.workflows.CreateTripleEmbeddingsWorkflow import (
    CreateTripleEmbeddingsWorkflow,
    CreateTripleEmbeddingsWorkflowConfiguration,
    CreateTripleEmbeddingsWorkflowParameters,
)

collection_name = "triple_embeddings_test"
embeddings_dimension = 3072
embeddings_model = OpenAIEmbeddings(
    model="text-embedding-3-large",
    dimensions=embeddings_dimension,
)
embeddings_utils = EmbeddingsUtils(embeddings_model=embeddings_model)

engine = Engine()
engine.load(module_names=["naas_abi_core.modules.triplestore_embeddings"])

module: ABIModule = ABIModule.get_instance()


@pytest.fixture
def workflow() -> CreateTripleEmbeddingsWorkflow:
    configuration = CreateTripleEmbeddingsWorkflowConfiguration(
        vector_store=module.engine.services.vector_store,
        triple_store=module.engine.services.triple_store,
        embeddings_model=embeddings_model,
        embeddings_dimension=embeddings_dimension,
        collection_name=collection_name,
    )
    workflow = CreateTripleEmbeddingsWorkflow(configuration)
    return workflow


def test_create_triple_embeddings(workflow):
    from rdflib import RDFS

    result = workflow.create_triple_embeddings(
        CreateTripleEmbeddingsWorkflowParameters(
            s="http://ontology.naas.ai/abi/9187f182-f84a-4dca-ab3b-7e39f73c901b",
            p=RDFS.label,
            o="Florent Ravenel",
        )
    )
    assert result["status"] == "success", result["message"]


def test_trigger_create_triple_embeddings(workflow):
    import time
    from uuid import uuid4

    from rdflib import OWL, RDF, RDFS, Graph, Literal, URIRef

    uri = "http://ontology.naas.ai/abi/test/" + str(uuid4())

    graph = Graph()
    graph.add(
        (
            URIRef(uri),
            RDF.type,
            URIRef("https://www.commoncoreontologies.org/ont00001262"),
        )
    )
    graph.add((URIRef(uri), RDF.type, OWL.NamedIndividual))
    graph.add((URIRef(uri), RDFS.label, Literal("Florent Ravenel")))

    triple_store_service = module.engine.services.triple_store
    triple_store_service.insert(graph)
    time.sleep(10)

    vector_store_service = module.engine.services.vector_store

    vector = embeddings_utils.create_vector_embedding("Florent Ravenel")
    search_results = vector_store_service.search_similar(
        collection_name=collection_name,
        query_vector=vector,
        k=10,
        filter={"uri": uri},
        include_metadata=True,
    )
    assert len(search_results) > 0, search_results

    triple_store_service.remove(graph)
