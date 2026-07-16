from unittest.mock import MagicMock, patch

import numpy as np
import pytest
from naas_abi_core.services.secret.Secret import Secret
from naas_abi_core.services.triple_store.adaptors.secondary.TripleStoreService__SecondaryAdaptor__OxigraphEmbedded import (
    TripleStoreService__SecondaryAdaptor__OxigraphEmbedded,
)
from naas_abi_core.services.triple_store.TripleStoreService import TripleStoreService
from naas_abi_core.services.vector_store.adapters.QdrantInMemoryAdapter import (
    QdrantInMemoryAdapter,
)
from naas_abi_core.services.vector_store.VectorStoreService import VectorStoreService
from naas_abi_marketplace.domains.locations.pipelines.LocationsPipeline import (
    LocationSource,
    LocationsPipeline,
    LocationsPipelineConfiguration,
    LocationsPipelineParameters,
)
from naas_abi_marketplace.domains.locations.workflows.LocationsWorkflow import (
    LocationsSearchParameters,
    LocationsWorkflow,
    LocationsWorkflowConfiguration,
    LocationsWorkflowParameters,
)
from rdflib import URIRef

COLLECTION_NAME = "locations_test"
DIMENSION = 8


def _fake_embeddings_model() -> MagicMock:
    def embed_documents(texts):
        return [np.random.RandomState(abs(hash(t)) % (2**32)).rand(DIMENSION).tolist() for t in texts]

    def embed_query(text):
        return np.random.RandomState(abs(hash(text)) % (2**32)).rand(DIMENSION).tolist()

    model = MagicMock()
    model.embed_documents.side_effect = embed_documents
    model.embed_query.side_effect = embed_query
    return model


@pytest.fixture
def workflow(tmp_path) -> LocationsWorkflow:
    pgeocode_pipeline = LocationsPipeline(LocationsPipelineConfiguration(source=LocationSource.PGEOCODE))
    graph = pgeocode_pipeline.run(LocationsPipelineParameters(country_code="FR", postal_code="75001"))

    triple_store = TripleStoreService(
        TripleStoreService__SecondaryAdaptor__OxigraphEmbedded(store_path=str(tmp_path))
    )
    triple_store.insert(graph, graph_name=URIRef("http://ontology.naas.ai/graph/locations"))

    vector_store = VectorStoreService(QdrantInMemoryAdapter(storage_path=":memory:"))

    configuration = LocationsWorkflowConfiguration(
        triple_store=triple_store,
        vector_store=vector_store,
        secret=Secret([]),
        collection_name=COLLECTION_NAME,
        dimension=DIMENSION,
    )
    return LocationsWorkflow(configuration)


def test_fetch_individuals_builds_hierarchy(workflow: LocationsWorkflow):
    records = workflow._LocationsWorkflow__fetch_individuals()  # type: ignore[attr-defined]

    assert len(records) == 5
    types = {r["type"] for r in records}
    assert types == {"Country", "State", "Region", "City", "PostalCode"}

    country = next(r for r in records if r["type"] == "Country")
    assert country["country_code"] == "FR"

    city = next(r for r in records if r["type"] == "City")
    assert city["latitude"] is not None
    assert city["longitude"] is not None
    assert "Île-de-France" in city["parents"]


def test_run_and_search(workflow: LocationsWorkflow):
    with patch.object(
        LocationsWorkflow, "_LocationsWorkflow__embeddings_model", return_value=_fake_embeddings_model()
    ):
        result = workflow.run(LocationsWorkflowParameters())
        assert result == {"collection_name": COLLECTION_NAME, "count": 5}

        records = workflow._LocationsWorkflow__fetch_individuals()  # type: ignore[attr-defined]
        city_record = next(r for r in records if r["type"] == "City")
        city_text = workflow._LocationsWorkflow__build_text(city_record)  # type: ignore[attr-defined]

        matches = workflow.search(LocationsSearchParameters(query=city_text, k=3))

        assert len(matches) == 3
        assert matches[0]["uri"] == city_record["uri"]
        assert matches[0]["type"] == "City"
