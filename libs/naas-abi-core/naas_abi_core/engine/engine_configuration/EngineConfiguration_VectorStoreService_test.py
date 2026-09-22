from naas_abi_core.engine.engine_configuration.EngineConfiguration_VectorStoreService import (
    VectorStoreAdapterConfiguration,
    VectorStoreAdapterNATSConfiguration,
    VectorStoreAdapterQdrantConfiguration,
    VectorStoreServiceConfiguration,
)
from naas_abi_core.services.vector_store.adapters.secondary.VectorStoreSecondaryAdapterNATSClient import (
    VectorStoreSecondaryAdapterNATSClient,
)
from naas_abi_core.services.vector_store.IVectorStorePort import IVectorStorePort
from naas_abi_core.services.vector_store.VectorStoreService import VectorStoreService


def test_vector_store_service_configuration():
    from naas_abi_core.services.vector_store.adapters.QdrantAdapter import (
        QdrantAdapter,
    )

    qdrant_config = VectorStoreAdapterQdrantConfiguration()
    configuration = VectorStoreServiceConfiguration(
        vector_store_adapter=VectorStoreAdapterConfiguration(
            adapter="qdrant",
            config=qdrant_config.model_dump(),
        )
    )
    assert configuration.vector_store_adapter is not None

    vector_store_adapter = configuration.vector_store_adapter.load()

    assert vector_store_adapter is not None
    assert isinstance(vector_store_adapter, IVectorStorePort)
    assert isinstance(vector_store_adapter, QdrantAdapter)

    vector_store_service = configuration.load()

    assert vector_store_service is not None
    assert isinstance(vector_store_service, VectorStoreService)


def test_vector_store_service_configuration_qdrant_in_memory(tmp_path):
    from naas_abi_core.services.vector_store.adapters.QdrantInMemoryAdapter import (
        QdrantInMemoryAdapter,
    )

    configuration = VectorStoreServiceConfiguration(
        vector_store_adapter=VectorStoreAdapterConfiguration(
            adapter="qdrant_in_memory",
            config={"storage_path": str(tmp_path / "qdrant-local")},
        )
    )

    vector_store_adapter = configuration.vector_store_adapter.load()
    assert isinstance(vector_store_adapter, IVectorStorePort)
    assert isinstance(vector_store_adapter, QdrantInMemoryAdapter)


def test_vector_store_service_configuration_nats_rpc_is_lazy():
    """Loading the "nats_rpc" adapter must construct the client without any
    network I/O -- VectorStoreSecondaryAdapterNATSClient connects lazily on
    first use, so this must succeed with no live NATS server."""
    configuration = VectorStoreServiceConfiguration(
        vector_store_adapter=VectorStoreAdapterConfiguration(
            adapter="nats_rpc",
            # config is a plain dict here (not a VectorStoreAdapterNATSConfiguration
            # instance): VectorStoreAdapterConfiguration.config is typed dict | None,
            # not a typed Union, deliberately -- see that field's docstring.
            config=VectorStoreAdapterNATSConfiguration(
                nats_url="nats://127.0.0.1:4222",
                jwt_secret="test-shared-secret",
                service_identity="api",
            ).model_dump(),
        )
    )

    vector_store_adapter = configuration.vector_store_adapter.load()

    assert isinstance(vector_store_adapter, IVectorStorePort)
    assert isinstance(vector_store_adapter, VectorStoreSecondaryAdapterNATSClient)
