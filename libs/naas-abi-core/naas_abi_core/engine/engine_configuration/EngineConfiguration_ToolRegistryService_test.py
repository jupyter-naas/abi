import pytest
from naas_abi_core.engine.engine_configuration.EngineConfiguration_ToolRegistryService import (
    ToolRegistryServiceConfiguration,
)
from naas_abi_core.engine.IEngine import IEngine
from naas_abi_core.services.model_registry.ModelRegistryService import (
    ModelRegistryService,
)
from naas_abi_core.services.tool_registry.adapters.secondary.InMemoryToolIndexAdapter import (
    InMemoryToolIndexAdapter,
)
from naas_abi_core.services.tool_registry.adapters.secondary.VectorStoreToolIndexAdapter import (
    VectorStoreToolIndexAdapter,
)
from naas_abi_core.services.tool_registry.ToolRegistryService import (
    ToolRegistryService,
)
from naas_abi_core.services.vector_store.adapters.QdrantInMemoryAdapter import (
    QdrantInMemoryAdapter,
)
from naas_abi_core.services.vector_store.VectorStoreService import VectorStoreService


def _wired(configuration, vector_store=None) -> ToolRegistryService:
    service = configuration.load()
    services = IEngine.Services(
        model_registry=ModelRegistryService(),
        vector_store=vector_store,
        tool_registry=service,
    )
    configuration.wire(service, services)
    return service


def test_defaults_to_an_in_memory_index():
    service = _wired(ToolRegistryServiceConfiguration())
    assert isinstance(service, ToolRegistryService)
    assert service.search_available
    assert isinstance(service._index, InMemoryToolIndexAdapter)


def test_auto_uses_the_vector_store_when_the_engine_loaded_one():
    store = VectorStoreService(adapter=QdrantInMemoryAdapter(storage_path=":memory:"))
    service = _wired(ToolRegistryServiceConfiguration(), vector_store=store)
    assert isinstance(service._index, VectorStoreToolIndexAdapter)


def test_explicit_vector_store_without_one_is_a_configuration_error():
    with pytest.raises(ValueError, match="vector_store"):
        _wired(ToolRegistryServiceConfiguration(index="vector_store"))


def test_memory_can_be_forced():
    store = VectorStoreService(adapter=QdrantInMemoryAdapter(storage_path=":memory:"))
    service = _wired(
        ToolRegistryServiceConfiguration(index="memory"), vector_store=store
    )
    assert isinstance(service._index, InMemoryToolIndexAdapter)


def test_search_can_be_disabled():
    service = _wired(ToolRegistryServiceConfiguration(search_enabled=False))
    assert not service.search_available


def test_rejects_unknown_options():
    with pytest.raises(ValueError):
        ToolRegistryServiceConfiguration(unknown=True)
