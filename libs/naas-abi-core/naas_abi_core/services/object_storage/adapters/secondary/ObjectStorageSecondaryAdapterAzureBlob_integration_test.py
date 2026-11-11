import io
import time
import uuid

import pytest
from azure.core.exceptions import ResourceNotFoundError
from azure.storage.blob import ContainerClient
from naas_abi_core.services.object_storage.adapters.secondary.ObjectStorageSecondaryAdapterAzureBlob import (
    ObjectStorageSecondaryAdapterAzureBlob,
)
from naas_abi_core.services.object_storage.ObjectStoragePort import Exceptions
from naas_abi_core.services.object_storage.tests.object_storage__secondary_adapter__generic_test import (
    ObjectStorageSecondaryAdapterContract,
)
from testcontainers.azurite import AzuriteContainer

# Azurite answers with the account key of its emulator account, so these tests
# go through `connection_string`; Entra ID needs a real tenant.
AZURITE_IMAGE = "mcr.microsoft.com/azure-storage/azurite:latest"


@pytest.fixture(scope="session")
def azurite_connection_string():
    try:
        with AzuriteContainer(AZURITE_IMAGE).with_command(
            # The SDK may speak a newer service version than the emulator knows.
            "azurite-blob --blobHost 0.0.0.0 --skipApiVersionCheck"
        ) as container:
            connection_string = container.get_connection_string()

            deadline = time.time() + 45
            while time.time() < deadline:
                try:
                    probe = ContainerClient.from_connection_string(
                        connection_string, "readiness"
                    )
                    probe.create_container()
                    probe.delete_container()
                    break
                except Exception:  # noqa: BLE001
                    time.sleep(0.5)
            else:
                pytest.fail("Azurite container did not become ready in time")

            yield connection_string
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"Docker/Testcontainers unavailable: {exc}")


@pytest.fixture
def container_name(azurite_connection_string):
    name = f"abi-{uuid.uuid4().hex[:12]}"
    container = ContainerClient.from_connection_string(azurite_connection_string, name)
    container.create_container()
    yield name
    container.delete_container()


@pytest.mark.integration
class TestObjectStorageSecondaryAdapterAzureBlobIntegration(
    ObjectStorageSecondaryAdapterContract
):
    @pytest.fixture
    def adapter(self, azurite_connection_string, container_name):
        return ObjectStorageSecondaryAdapterAzureBlob(
            container_name=container_name,
            connection_string=azurite_connection_string,
            base_prefix="datastore",
        )

    def test_round_trip_and_metadata(self, adapter):
        adapter.put_object("papers", "2024/report.pdf", b"12345")
        adapter.put_object("papers", "2024/report.pdf", b"123456")

        assert adapter.get_object("papers", "2024/report.pdf") == b"123456"
        metadata = adapter.get_object_metadata("papers", "2024/report.pdf")
        assert metadata.file_name == "report.pdf"
        assert metadata.file_size_bytes == 6
        assert metadata.modified_time is not None
        assert metadata.file_path.endswith(
            f"/{adapter.container_name}/datastore/papers/2024/report.pdf"
        )

    def test_streams_a_payload_larger_than_a_block(self, adapter):
        payload = bytes(range(256)) * (5 * 4096)  # 5 MiB, more than one 4 MiB block

        class _Unsized(io.RawIOBase):
            """No length and no seek: the SDK has to upload it in blocks."""

            def __init__(self, data: bytes):
                self._data = io.BytesIO(data)

            def readable(self) -> bool:
                return True

            def readinto(self, buffer) -> int:
                chunk = self._data.read(len(buffer))
                buffer[: len(chunk)] = chunk
                return len(chunk)

        adapter.put_object_stream("bulk", "big.bin", _Unsized(payload))

        with adapter.get_object_stream("bulk", "big.bin") as stream:
            head = stream.read(10)
            rest = stream.read()
        assert head + rest == payload

    def test_missing_objects_and_prefixes_are_object_not_found(self, adapter):
        for call in (
            lambda: adapter.get_object("papers", "missing.pdf"),
            lambda: adapter.delete_object("papers", "missing.pdf"),
            lambda: adapter.get_object_metadata("papers", "missing.pdf"),
            lambda: adapter.list_objects("missing"),
            lambda: adapter.list_objects_recursive("missing"),
        ):
            with pytest.raises(Exceptions.ObjectNotFound):
                call()

    def test_a_missing_container_is_not_object_not_found(
        self, azurite_connection_string
    ):
        adapter = ObjectStorageSecondaryAdapterAzureBlob(
            container_name="no-such-container",
            connection_string=azurite_connection_string,
        )

        for call in (
            lambda: adapter.get_object("papers", "missing.pdf"),
            lambda: adapter.get_object_metadata("papers", "missing.pdf"),
        ):
            with pytest.raises(ResourceNotFoundError) as raised:
                call()
            assert not isinstance(raised.value, Exceptions.ObjectNotFound)

    def test_list_objects_names_folders_with_a_trailing_slash(self, adapter):
        adapter.put_object("papers", "root.pdf", b"r")
        adapter.put_object("papers", "2024/spring.pdf", b"s")

        listed = adapter.list_objects("papers")

        assert sorted(listed) == ["papers/2024/", "papers/root.pdf"]
        assert adapter.folders(listed) == {"papers/2024/"}
