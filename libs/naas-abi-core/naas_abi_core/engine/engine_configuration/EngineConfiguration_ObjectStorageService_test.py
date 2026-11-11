import pytest
from naas_abi_core.engine.engine_configuration.EngineConfiguration_ObjectStorageService import (
    ObjectStorageAdapterAzureBlobConfiguration,
    ObjectStorageAdapterConfiguration,
    ObjectStorageAdapterFSConfiguration,
    ObjectStorageAdapterNATSConfiguration,
    ObjectStorageServiceConfiguration,
)
from naas_abi_core.engine.nats_test_tokens import TEST_SERVICE_KEY
from naas_abi_core.services.object_storage.adapters.secondary.ObjectStorageSecondaryAdapterAzureBlob import (
    ObjectStorageSecondaryAdapterAzureBlob,
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
from pydantic import ValidationError


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
                service_key=TEST_SERVICE_KEY,
            ),
        )
    )

    object_storage_adapter = configuration.object_storage_adapter.load()

    assert isinstance(object_storage_adapter, IObjectStorageAdapter)
    assert isinstance(object_storage_adapter, ObjectStorageSecondaryAdapterNATSClient)


def test_object_storage_service_configuration_azure_blob_is_lazy():
    """Loading the "azure_blob" adapter builds its clients and credential
    without a request: Entra ID tokens are fetched on first use."""
    configuration = ObjectStorageServiceConfiguration(
        object_storage_adapter=ObjectStorageAdapterConfiguration(
            adapter="azure_blob",
            config=ObjectStorageAdapterAzureBlobConfiguration(
                account_url="https://abistore.blob.core.windows.net",
                container_name="abi",
                base_prefix="datastore",
                managed_identity_client_id="00000000-0000-0000-0000-000000000001",
            ),
        )
    )

    object_storage_adapter = configuration.object_storage_adapter.load()

    assert isinstance(object_storage_adapter, ObjectStorageSecondaryAdapterAzureBlob)
    assert (
        object_storage_adapter.container_client.url
        == "https://abistore.blob.core.windows.net/abi"
    )
    assert object_storage_adapter.base_prefix == "datastore"
    assert configuration.object_storage_adapter.local_storage() is None


def test_azure_blob_configuration_from_a_yaml_mapping():
    connection_string = "DefaultEndpointsProtocol=http;AccountName=a;AccountKey=secret"
    configuration = ObjectStorageAdapterConfiguration.model_validate(
        {
            "adapter": "azure_blob",
            "config": {"connection_string": connection_string, "container_name": "abi"},
        }
    )

    assert isinstance(configuration.config, ObjectStorageAdapterAzureBlobConfiguration)
    assert configuration.config.account_url is None
    assert "secret" not in repr(configuration.config)


@pytest.mark.parametrize(
    "config",
    [
        {"container_name": "abi"},
        {
            "container_name": "abi",
            "account_url": "https://abistore.blob.core.windows.net",
            "connection_string": "UseDevelopmentStorage=true",
        },
        {
            "container_name": "abi",
            "connection_string": "UseDevelopmentStorage=true",
            "managed_identity_client_id": "client-id",
        },
    ],
)
def test_azure_blob_configuration_needs_one_way_to_reach_the_account(config):
    with pytest.raises(ValidationError):
        ObjectStorageAdapterConfiguration.model_validate(
            {"adapter": "azure_blob", "config": config}
        )
