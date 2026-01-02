from naas_abi_core.engine.engine_configuration.EngineConfiguration_VectorStoreService import (
    VectorStoreAdapterConfiguration,
    VectorStoreAdapterQdrantConfiguration,
    VectorStoreServiceConfiguration,
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
