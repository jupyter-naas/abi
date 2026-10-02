from naas_abi_core.services.model_registry.ModelRegistryService import (
    ModelRegistryService,
)
from naas_abi_core.services.tool_registry.tests.concept_embeddings import (
    concept_embedding_model,
)
from naas_abi_core.services.tool_registry.ToolRegistryFactory import ToolRegistryFactory
from naas_abi_core.services.vector_store.adapters.QdrantInMemoryAdapter import (
    QdrantInMemoryAdapter,
)
from naas_abi_core.services.vector_store.VectorStoreService import VectorStoreService


def _models() -> ModelRegistryService:
    registry = ModelRegistryService(default_embedding_model="concepts")
    registry.register("concepts", concept_embedding_model())
    return registry


def test_in_memory_without_models_has_no_search():
    assert not ToolRegistryFactory.InMemory().search_available


def test_in_memory_with_models_can_search():
    registry = ToolRegistryFactory.InMemory(_models())
    assert registry.search_available
    assert registry.search_tools("anything") == []


def test_vector_store_registry_can_search():
    store = VectorStoreService(adapter=QdrantInMemoryAdapter(storage_path=":memory:"))
    registry = ToolRegistryFactory.VectorStore(store, _models())
    assert registry.search_available
    assert registry.search_tools("anything") == []
