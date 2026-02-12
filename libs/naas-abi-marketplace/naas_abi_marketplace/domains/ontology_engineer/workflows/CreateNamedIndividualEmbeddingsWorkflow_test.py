import pytest
from naas_abi_core.engine.Engine import Engine
from naas_abi_marketplace.domains.ontology_engineer import ABIModule
from naas_abi_marketplace.domains.ontology_engineer.workflows.CreateNamedIndividualEmbeddingsWorkflow import (
    CreateNamedIndividualEmbeddingsWorkflow,
    CreateNamedIndividualEmbeddingsWorkflowConfiguration,
    CreateNamedIndividualEmbeddingsWorkflowParameters,
)

engine = Engine()
engine.load(module_names=["naas_abi_marketplace.domains.ontology_engineer"])


@pytest.fixture
def workflow() -> CreateNamedIndividualEmbeddingsWorkflow:
    return CreateNamedIndividualEmbeddingsWorkflow(
        CreateNamedIndividualEmbeddingsWorkflowConfiguration(
            vector_store=ABIModule.get_instance().engine.services.vector_store,
        )
    )


def test_add_named_individuals_to_vector_store(
    workflow: CreateNamedIndividualEmbeddingsWorkflow,
):
    import uuid

    labels = ["John Doe", "Jane Doe"]
    uris = [
        f"https://www.example.com/{uuid.uuid4()}",
        f"https://www.example.com/{uuid.uuid4()}",
    ]
    metadata = [{"name": "John Doe"}, {"name": "Jane Doe"}]
    result = workflow.create_named_individual_embeddings(
        CreateNamedIndividualEmbeddingsWorkflowParameters(
            collection_name="TestPerson",
            labels=labels,
            uris=uris,
            metadata=metadata,
        )
    )
    assert result["status"] == "success", result
    assert result["entities_processed"] == len(labels), result


def test_add_named_individuals_from_class_to_vector_store(
    workflow: CreateNamedIndividualEmbeddingsWorkflow,
):
    labels, uris, metadata = workflow.get_individuals_from_class(
        class_uri="https://www.commoncoreontologies.org/ont00001262",
        triple_store_service=ABIModule.get_instance().engine.services.triple_store,
    )
    result = workflow.create_named_individual_embeddings(
        CreateNamedIndividualEmbeddingsWorkflowParameters(
            collection_name="Person",
            labels=labels,
            uris=uris,
            metadata=metadata,
        )
    )
    assert result["status"] == "success", result
    assert result["entities_processed"] > 0, result
    assert result["collection_name"] == "Person", result
