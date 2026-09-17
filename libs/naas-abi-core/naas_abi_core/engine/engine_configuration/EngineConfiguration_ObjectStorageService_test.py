from naas_abi_core.engine.engine_configuration.EngineConfiguration_ObjectStorageService import (
    ObjectStorageAdapterConfiguration,
    ObjectStorageAdapterFSConfiguration,
    ObjectStorageAdapterNATSConfiguration,
    ObjectStorageServiceConfiguration,
)
from naas_abi_core.services.object_storage.adapters.secondary.ObjectStorageSecondaryAdapterFS import (
    ObjectStorageSecondaryAdapterFS,
)
from naas_abi_core.services.object_storage.adapters.secondary.ObjectStorageSecondaryAdapterNATSClient import (
    ObjectStorageSecondaryAdapterNATSClient,
)
from naas_abi_core.services.object_storage.ObjectStoragePort import (
    IObjectStorageAdapter,
)


def test_object_storage_service_configuration():
    configuration = ObjectStorageServiceConfiguration(
        object_storage_adapter=ObjectStorageAdapterConfiguration(
            adapter="fs", config=ObjectStorageAdapterFSConfiguration(base_path="test")
        )
    )
    assert configuration.object_storage_adapter is not None

    object_storage_adapter = configuration.object_storage_adapter.load()

    assert object_storage_adapter is not None
    assert isinstance(object_storage_adapter, IObjectStorageAdapter)
    assert isinstance(object_storage_adapter, ObjectStorageSecondaryAdapterFS)


def test_object_storage_service_configuration_nats_rpc_is_lazy():
    """Loading the "nats_rpc" adapter must construct the client without any
    network I/O -- ObjectStorageSecondaryAdapterNATSClient connects lazily on
    first use, so this must succeed with no live NATS server."""
    configuration = ObjectStorageServiceConfiguration(
        object_storage_adapter=ObjectStorageAdapterConfiguration(
            adapter="nats_rpc",
            config=ObjectStorageAdapterNATSConfiguration(
                nats_url="nats://127.0.0.1:4222",
                jwt_secret="test-shared-secret",
                service_identity="api",
            ),
        )
    )

    object_storage_adapter = configuration.object_storage_adapter.load()

    assert isinstance(object_storage_adapter, IObjectStorageAdapter)
    assert isinstance(object_storage_adapter, ObjectStorageSecondaryAdapterNATSClient)
