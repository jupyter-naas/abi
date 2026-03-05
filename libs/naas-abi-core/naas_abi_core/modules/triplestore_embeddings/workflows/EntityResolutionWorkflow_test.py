import os

import pytest
from langchain_openai import OpenAIEmbeddings
from naas_abi_core.engine.Engine import Engine
from naas_abi_core.modules.triplestore_embeddings import ABIModule
from naas_abi_core.modules.triplestore_embeddings.pipelines.MergeIndividualsPipeline import (
    MergeIndividualsPipelineConfiguration,
)
from naas_abi_core.modules.triplestore_embeddings.utils.Embeddings import (
    EmbeddingsUtils,
)
from naas_abi_core.modules.triplestore_embeddings.workflows.CreateTripleEmbeddingsWorkflow import (
    CreateTripleEmbeddingsWorkflowConfiguration,
)
from naas_abi_core.modules.triplestore_embeddings.workflows.EntityResolutionWorkflow import (
    EntityResolutionWorkflow,
    EntityResolutionWorkflowConfiguration,
)

# Set ENV=test to ensure test graph is used
os.environ["TEST"] = "true"

# Test graph name constant
TEST_GRAPH_NAME = "http://ontology.naas.ai/abi/test/"

engine = Engine()
engine.load(module_names=["naas_abi_core.modules.triplestore_embeddings"])

module: ABIModule = ABIModule.get_instance()
collection_name = module.configuration.collection_name + "_test"
datastore_path = module.configuration.datastore_path + "_test"
embeddings_dimensions = module.configuration.embeddings_dimensions
vector_store_service = module.engine.services.vector_store
triple_store_service = module.engine.services.triple_store
object_storage_service = module.engine.services.object_storage
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

# Remove collection from vector store
vector_store_service.delete_collection(collection_name)


@pytest.fixture
def workflow() -> EntityResolutionWorkflow:
    merge_pipeline_configuration = MergeIndividualsPipelineConfiguration(
        triple_store=triple_store_service,
        object_storage=object_storage_service,
        graph_name=TEST_GRAPH_NAME,
        datastore_path=datastore_path,
    )
    create_embeddings_workflow_configuration = (
        CreateTripleEmbeddingsWorkflowConfiguration(
            vector_store=vector_store_service,
            triple_store=triple_store_service,
            embeddings_model=embeddings_model,
            embeddings_dimensions=embeddings_dimensions,
            collection_name=collection_name,
            graph_name=TEST_GRAPH_NAME,
        )
    )
    configuration = EntityResolutionWorkflowConfiguration(
        merge_pipeline_configuration=merge_pipeline_configuration,
        create_embeddings_workflow_configuration=create_embeddings_workflow_configuration,
        vector_store=vector_store_service,
        triple_store=triple_store_service,
        embeddings_model=embeddings_model,
        embeddings_dimensions=embeddings_dimensions,
        collection_name=collection_name,
        graph_name=TEST_GRAPH_NAME,
    )
    workflow = EntityResolutionWorkflow(configuration)
    return workflow


def test_subscribe_resolvable_entity(workflow):
    import time
    import uuid

    from rdflib import OWL, RDF, RDFS, Graph, Literal, URIRef

    # Init
    graph = Graph()
    label = Literal("COO")
    class_uri = URIRef("http://purl.obolibrary.org/obo/BFO_0000023")
    owl_type = OWL.NamedIndividual
    vector = embeddings_utils.create_vector_embedding(label)

    # Create triples for CEO role (SPC)
    uri = "http://ontology.naas.ai/abi/test/" + str(uuid.uuid4())
    graph.add((URIRef(uri), RDF.type, owl_type))
    graph.add((URIRef(uri), RDF.type, class_uri))
    graph.add((URIRef(uri), RDFS.label, label))

    # Create same triples for CEO role (SPC) but with different URI
    uri2 = "http://ontology.naas.ai/abi/test/" + str(uuid.uuid4())
    graph.add((URIRef(uri2), RDF.type, owl_type))
    graph.add((URIRef(uri2), RDF.type, class_uri))
    graph.add((URIRef(uri2), RDFS.label, label))

    # Insert graph to triple store
    module.engine.services.triple_store.insert(
        graph, graph_name=URIRef(TEST_GRAPH_NAME)
    )
    time.sleep(10)

    # Check vector has been created
    search_results = vector_store_service.search_similar(
        collection_name=collection_name,
        query_vector=vector,
        k=10,
        filter={"uri": uri},
        include_metadata=True,
    )
    assert len(search_results) > 0, search_results

    # Check vector has not been created
    search_results = vector_store_service.search_similar(
        collection_name=collection_name,
        query_vector=vector,
        k=10,
        filter={"uri": uri2},
        include_metadata=True,
    )
    assert len(search_results) == 0, search_results

    # Delete graph from triple store
    module.engine.services.triple_store.remove(
        graph, graph_name=URIRef(TEST_GRAPH_NAME)
    )
    time.sleep(5)

    # Check vectors have been deleted
    search_results = vector_store_service.search_similar(
        collection_name=collection_name,
        query_vector=vector,
        k=10,
        filter={"uri": uri},
        include_metadata=True,
    )
    assert len(search_results) == 0, search_results


def test_subscribe_non_resolvable_entity(workflow):
    import time
    import uuid

    from rdflib import OWL, RDF, RDFS, Graph, Literal, URIRef

    # Init
    graph = Graph()
    label = Literal("CEO")
    label2 = Literal("Founder")
    class_uri = URIRef("http://purl.obolibrary.org/obo/BFO_0000019")  # quality
    owl_type = OWL.NamedIndividual
    vector = embeddings_utils.create_vector_embedding(label)
    vector2 = embeddings_utils.create_vector_embedding(label2)

    # Create triples for CEO role (SPC)
    uri = "http://ontology.naas.ai/abi/test/" + str(uuid.uuid4())
    graph.add((URIRef(uri), RDF.type, owl_type))
    graph.add((URIRef(uri), RDF.type, class_uri))
    graph.add((URIRef(uri), RDFS.label, label))

    # Create same triples for CEO role (SPC) but with different URI
    uri2 = "http://ontology.naas.ai/abi/test/" + str(uuid.uuid4())
    graph.add((URIRef(uri2), RDF.type, owl_type))
    graph.add((URIRef(uri2), RDF.type, class_uri))
    graph.add((URIRef(uri2), RDFS.label, label2))

    # Insert graph to triple store
    module.engine.services.triple_store.insert(
        graph, graph_name=URIRef(TEST_GRAPH_NAME)
    )
    time.sleep(5)

    # Check vector has been created
    search_results = vector_store_service.search_similar(
        collection_name=collection_name,
        query_vector=vector,
        k=10,
        filter={"uri": uri},
        include_metadata=True,
    )
    assert len(search_results) > 0, search_results

    # Check vector has been created
    search_results = vector_store_service.search_similar(
        collection_name=collection_name,
        query_vector=vector2,
        k=10,
        filter={"uri": uri2},
        include_metadata=True,
    )
    assert len(search_results) > 0, search_results

    # Delete graph from triple store
    module.engine.services.triple_store.remove(
        graph, graph_name=URIRef(TEST_GRAPH_NAME)
    )
    time.sleep(5)

    # Check vectors have been deleted
    search_results = vector_store_service.search_similar(
        collection_name=collection_name,
        query_vector=vector,
        k=10,
        filter={"uri": uri},
        include_metadata=True,
    )
    assert len(search_results) == 0, search_results

    search_results = vector_store_service.search_similar(
        collection_name=collection_name,
        query_vector=vector2,
        k=10,
        filter={"uri": uri2},
        include_metadata=True,
    )
    assert len(search_results) == 0, search_results


def test_subscribe_non_resolvable_entity_ic(workflow):
    import time
    import uuid

    from rdflib import OWL, RDF, RDFS, Graph, Literal, URIRef

    # Init
    graph = Graph()
    label = Literal("Jane Doe")
    class_uri = URIRef("http://purl.obolibrary.org/obo/BFO_0000040")  # material entity
    owl_type = OWL.NamedIndividual
    vector = embeddings_utils.create_vector_embedding(label)

    # Create triples for CEO role (SPC)
    uri = "http://ontology.naas.ai/abi/test/" + str(uuid.uuid4())
    graph.add((URIRef(uri), RDF.type, owl_type))
    graph.add((URIRef(uri), RDF.type, class_uri))
    graph.add((URIRef(uri), RDFS.label, label))

    # Create same triples for CEO role (SPC) but with different URI
    uri2 = "http://ontology.naas.ai/abi/test/" + str(uuid.uuid4())
    graph.add((URIRef(uri2), RDF.type, owl_type))
    graph.add((URIRef(uri2), RDF.type, class_uri))
    graph.add((URIRef(uri2), RDFS.label, label))

    # Insert graph to triple store
    module.engine.services.triple_store.insert(
        graph, graph_name=URIRef(TEST_GRAPH_NAME)
    )
    time.sleep(5)

    # Check vector has been created
    search_results = vector_store_service.search_similar(
        collection_name=collection_name,
        query_vector=vector,
        k=10,
        filter={"uri": uri},
        include_metadata=True,
    )
    assert len(search_results) > 0, search_results

    # Check vector has been created
    search_results = vector_store_service.search_similar(
        collection_name=collection_name,
        query_vector=vector,
        k=10,
        filter={"uri": uri2},
        include_metadata=True,
    )
    assert len(search_results) > 0, search_results

    # Delete graph from triple store
    module.engine.services.triple_store.remove(
        graph, graph_name=URIRef(TEST_GRAPH_NAME)
    )
    time.sleep(5)

    # Check vectors have been deleted
    search_results = vector_store_service.search_similar(
        collection_name=collection_name,
        query_vector=vector,
        k=10,
        filter={"uri": uri},
        include_metadata=True,
    )
    assert len(search_results) == 0, search_results

    search_results = vector_store_service.search_similar(
        collection_name=collection_name,
        query_vector=vector,
        k=10,
        filter={"uri": uri2},
        include_metadata=True,
    )
    assert len(search_results) == 0, search_results


def test_subscribe_resolvable_entity_ic(workflow):
    import time
    import uuid

    from rdflib import OWL, RDF, RDFS, Graph, Literal, URIRef

    # Init
    graph = Graph()
    label = Literal("Josh Smith")
    class_uri = URIRef(
        "https://www.commoncoreontologies.org/ont00001262"
    )  # material entity
    owl_type = OWL.NamedIndividual
    key_property = URIRef("http://ontology.naas.ai/abi/linkedin/isOwnerOf")
    vector = embeddings_utils.create_vector_embedding(label)

    # Create LinkedIn Profile Page
    linkedin_profile_page_uri = "http://ontology.naas.ai/abi/test/" + str(uuid.uuid4())
    linkedin_class_uri = URIRef("http://ontology.naas.ai/abi/linkedin/ProfilePage")
    graph.add((URIRef(linkedin_profile_page_uri), RDF.type, owl_type))
    graph.add((URIRef(linkedin_profile_page_uri), RDF.type, linkedin_class_uri))
    graph.add((URIRef(linkedin_profile_page_uri), RDFS.label, label))

    # Create triples for CEO role (SPC)
    uri = "http://ontology.naas.ai/abi/test/" + str(uuid.uuid4())
    graph.add((URIRef(uri), RDF.type, owl_type))
    graph.add((URIRef(uri), RDF.type, class_uri))
    graph.add((URIRef(uri), RDFS.label, label))
    graph.add((URIRef(uri), key_property, URIRef(linkedin_profile_page_uri)))

    # Create same triples for CEO role (SPC) but with different URI
    uri2 = "http://ontology.naas.ai/abi/test/" + str(uuid.uuid4())
    graph.add((URIRef(uri2), RDF.type, owl_type))
    graph.add((URIRef(uri2), RDF.type, class_uri))
    graph.add((URIRef(uri2), RDFS.label, label))
    graph.add((URIRef(uri2), key_property, URIRef(linkedin_profile_page_uri)))

    # Insert graph to triple store
    module.engine.services.triple_store.insert(
        graph, graph_name=URIRef(TEST_GRAPH_NAME)
    )
    time.sleep(5)

    # Check vector has been created
    search_results = vector_store_service.search_similar(
        collection_name=collection_name,
        query_vector=vector,
        k=10,
        filter={"uri": uri},
        include_metadata=True,
    )
    assert len(search_results) > 0, search_results

    # Check vector has not been created
    search_results = vector_store_service.search_similar(
        collection_name=collection_name,
        query_vector=vector,
        k=10,
        filter={"uri": uri2},
        include_metadata=True,
    )
    assert len(search_results) == 0, search_results

    # Delete graph from triple store
    module.engine.services.triple_store.remove(
        graph, graph_name=URIRef(TEST_GRAPH_NAME)
    )
    time.sleep(5)

    # Check vectors have been deleted
    search_results = vector_store_service.search_similar(
        collection_name=collection_name,
        query_vector=vector,
        k=10,
        filter={"uri": uri},
        include_metadata=True,
    )
    assert len(search_results) == 0, search_results
