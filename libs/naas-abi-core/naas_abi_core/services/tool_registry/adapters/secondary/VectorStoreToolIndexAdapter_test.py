import pytest
from naas_abi_core.services.tool_registry.adapters.secondary.VectorStoreToolIndexAdapter import (
    VectorStoreToolIndexAdapter,
)
from naas_abi_core.services.tool_registry.tests.tool_index__secondary_adapter__generic_test import (
    ToolIndexSecondaryAdapterContract,
)
from naas_abi_core.services.tool_registry.ToolRegistryPort import ToolIndexEntry
from naas_abi_core.services.vector_store.adapters.QdrantAdapter import QdrantAdapter
from naas_abi_core.services.vector_store.adapters.QdrantInMemoryAdapter import (
    QdrantInMemoryAdapter,
)
from naas_abi_core.services.vector_store.adapters.SqliteVecAdapter import (
    SqliteVecAdapter,
)
from naas_abi_core.services.vector_store.VectorStoreService import VectorStoreService
from qdrant_client import QdrantClient


def _production_qdrant() -> QdrantAdapter:
    """The server adapter, pointed at a local client: it keeps point ids as
    given, so tool ids must reach it already encoded."""
    adapter = QdrantAdapter()
    adapter.client = QdrantClient(":memory:")
    return adapter


@pytest.fixture(params=["qdrant_in_memory", "qdrant", "sqlite_vec"])
def vector_store(request, tmp_path):
    adapters = {
        "qdrant_in_memory": lambda: QdrantInMemoryAdapter(storage_path=":memory:"),
        "qdrant": _production_qdrant,
        "sqlite_vec": lambda: SqliteVecAdapter(
            persistence_path=str(tmp_path / "vectors.sqlite3")
        ),
    }
    service = VectorStoreService(adapter=adapters[request.param]())
    yield service
    service.close()


class TestVectorStoreToolIndexAdapter(ToolIndexSecondaryAdapterContract):
    @pytest.fixture
    def index(self, vector_store):
        return VectorStoreToolIndexAdapter(vector_store, collection_prefix="tools")

    def test_entries_survive_a_new_adapter_on_the_same_store(self, vector_store):
        first = VectorStoreToolIndexAdapter(vector_store, collection_prefix="tools")
        first.prepare("model-a")
        first.upsert([ToolIndexEntry(id="ns/a@1", fingerprint="fp", vector=(1.0, 0.0))])

        second = VectorStoreToolIndexAdapter(vector_store, collection_prefix="tools")
        second.prepare("model-a")
        assert second.fingerprints(["ns/a@1"]) == {"ns/a@1": "fp"}
        # The dimension is recovered from storage, so a mismatch is still caught.
        with pytest.raises(ValueError):
            second.upsert(
                [ToolIndexEntry(id="ns/b@1", fingerprint="fp", vector=(1.0, 0.0, 0.0))]
            )

    def test_a_new_model_drops_the_previous_collection(self, vector_store):
        index = VectorStoreToolIndexAdapter(vector_store, collection_prefix="tools")
        index.prepare("model-a")
        index.upsert([ToolIndexEntry(id="ns/a@1", fingerprint="fp", vector=(1.0, 0.0))])
        index.prepare("model-b")
        assert [
            c for c in vector_store.list_collections() if c.startswith("tools__")
        ] == []

    def test_leaves_collections_of_other_prefixes_alone(self, vector_store):
        vector_store.ensure_collection("unrelated", dimension=2)
        other = VectorStoreToolIndexAdapter(vector_store, collection_prefix="other")
        other.prepare("model-a")
        other.upsert([ToolIndexEntry(id="ns/a@1", fingerprint="fp", vector=(1.0, 0.0))])

        index = VectorStoreToolIndexAdapter(vector_store, collection_prefix="tools")
        index.prepare("model-b")
        index.upsert([ToolIndexEntry(id="ns/a@1", fingerprint="fp", vector=(1.0, 0.0))])
        index.prepare("model-c")

        assert "unrelated" in vector_store.list_collections()
        assert other.size() == 1


def test_tool_ids_are_stored_as_valid_point_ids_on_the_server_adapter():
    store = VectorStoreService(adapter=_production_qdrant())
    index = VectorStoreToolIndexAdapter(store, collection_prefix="tools")
    index.prepare("model-a")
    index.upsert(
        [
            ToolIndexEntry(
                id="acme.github/create_issue@1", fingerprint="v1", vector=(1.0, 0.0)
            )
        ]
    )
    assert index.fingerprints(["acme.github/create_issue@1"]) == {
        "acme.github/create_issue@1": "v1"
    }
    (hit,) = index.search((1.0, 0.0), limit=1)
    assert hit.id == "acme.github/create_issue@1"
    index.delete(["acme.github/create_issue@1"])
    assert index.size() == 0


def test_min_score_keeps_an_exact_match_on_every_backend(vector_store):
    """Registry-level: min_score is a similarity threshold whatever the store."""
    from naas_abi_core.services.tool_registry.tests.concept_embeddings import (
        CountingConceptEmbedder,
    )
    from naas_abi_core.services.tool_registry.ToolRegistryPort import (
        PublishedTool,
        ToolDefinition,
    )
    from naas_abi_core.services.tool_registry.ToolRegistryService import (
        ToolRegistryService,
    )

    class _Binding:
        default_config: dict = {}

        def create(self, context, config):
            return object()

    registry = ToolRegistryService(
        embedder=CountingConceptEmbedder(),
        index=VectorStoreToolIndexAdapter(vector_store, collection_prefix="tools"),
    )
    registry.publish(
        "acme.weather",
        [
            PublishedTool(
                definition=ToolDefinition(
                    namespace="acme.weather",
                    name="get_forecast",
                    description="Get the weather forecast.",
                    module="acme.weather",
                ),
                binding=_Binding(),
            )
        ],
    )
    results = registry.search_tools("weather forecast", min_score=0.5)
    assert [r.name for r in results] == ["get_forecast"]
    assert results[0].score > 0.9
