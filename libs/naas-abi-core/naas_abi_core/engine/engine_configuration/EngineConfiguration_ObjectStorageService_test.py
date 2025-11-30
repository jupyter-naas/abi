from naas_abi_core.engine.engine_configuration.EngineConfiguration_ObjectStorageService import (
    ObjectStorageAdapterConfiguration,
    ObjectStorageAdapterFSConfiguration,
    ObjectStorageServiceConfiguration,
)
from naas_abi_core.services.object_storage.adapters.secondary.ObjectStorageSecondaryAdapterFS import (
    ObjectStorageSecondaryAdapterFS,
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
