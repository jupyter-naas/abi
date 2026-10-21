import pytest
from naas_abi_core.engine.engine_configuration.EngineConfiguration_ToolRegistryService import (
    ToolIndexRole,
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


def _wired(
    configuration, vector_store=None, role=ToolIndexRole.PEER
) -> ToolRegistryService:
    service = configuration.load()
    services = IEngine.Services(
        model_registry=ModelRegistryService(),
        vector_store=vector_store,
        tool_registry=service,
    )
    configuration.wire(service, services, role)
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


@pytest.mark.parametrize(
    ("role", "shared", "collects"),
    [
        (ToolIndexRole.SOLE_WRITER, True, True),
        (ToolIndexRole.PEER, True, False),
        (ToolIndexRole.LOCAL, False, True),
    ],
)
def test_the_role_decides_which_index_a_process_writes(role, shared, collects):
    """Only the serving engine, or an engine without NATS, writes the shared
    store; a standby or client engine keeps its own, in memory. Cleaning leftovers
    out is for the one writer, or for an index no one else sees."""
    store = VectorStoreService(adapter=QdrantInMemoryAdapter(storage_path=":memory:"))
    service = _wired(ToolRegistryServiceConfiguration(), vector_store=store, role=role)
    assert isinstance(
        service._index,
        VectorStoreToolIndexAdapter if shared else InMemoryToolIndexAdapter,
    )
    assert service._collect_leftovers is collects


def test_a_local_role_ignores_an_explicit_vector_store_index():
    store = VectorStoreService(adapter=QdrantInMemoryAdapter(storage_path=":memory:"))
    service = _wired(
        ToolRegistryServiceConfiguration(index="vector_store"),
        vector_store=store,
        role=ToolIndexRole.LOCAL,
    )
    assert isinstance(service._index, InMemoryToolIndexAdapter)
