import pytest
from naas_abi_core.services.tool_registry.adapters.secondary.VectorStoreToolIndexAdapter import (
    VectorStoreToolIndexAdapter,
)
from naas_abi_core.services.tool_registry.tests.tool_index__secondary_adapter__generic_test import (
    ToolIndexSecondaryAdapterContract,
)
from naas_abi_core.services.tool_registry.ToolRegistryPort import ToolIndexEntry
from naas_abi_core.services.vector_store.adapters.QdrantInMemoryAdapter import (
    QdrantInMemoryAdapter,
)
from naas_abi_core.services.vector_store.VectorStoreService import VectorStoreService


@pytest.fixture
def vector_store():
    service = VectorStoreService(adapter=QdrantInMemoryAdapter(storage_path=":memory:"))
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
