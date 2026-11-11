import importlib
import io
import sys
from datetime import UTC, datetime

import pytest
from azure.core.exceptions import ResourceExistsError, ResourceNotFoundError
from azure.storage.blob import BlobPrefix, BlobProperties, ContentSettings
from naas_abi_core.services.object_storage.adapters.secondary import (
    ObjectStorageSecondaryAdapterAzureBlob as module,
)
from naas_abi_core.services.object_storage.adapters.secondary.ObjectStorageSecondaryAdapterAzureBlob import (
    ObjectStorageSecondaryAdapterAzureBlob,
)
from naas_abi_core.services.object_storage.ObjectStoragePort import Exceptions
from naas_abi_core.services.object_storage.tests.object_storage__secondary_adapter__generic_test import (
    ObjectStorageSecondaryAdapterContract,
)

ACCOUNT_URL = "https://abistore.privatelink.blob.core.windows.net"
MODIFIED = datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC)
CREATED = datetime(2026, 1, 1, tzinfo=UTC)


def _not_found(code: str) -> ResourceNotFoundError:
    error = ResourceNotFoundError(message=f"{code}")
    error.error_code = code  # type: ignore[attr-defined]
    return error


class _FakeDownloader:
    """``StorageStreamDownloader``: the body, read in parts."""

    def __init__(self, content: bytes):
        self._stream = io.BytesIO(content)
        self.reads: list[int] = []

    def read(self, size: int = -1) -> bytes:
        self.reads.append(size)
        return self._stream.read(size)

    def readall(self) -> bytes:
        return self._stream.read()


class _FakeBlobClient:
    def __init__(self, container: "_FakeContainerClient", name: str):
        self._container = container
        self.blob_name = name
        self.url = f"{container.url}/{name}"

    def get_blob_properties(self) -> BlobProperties:
        self._container.check_container()
        if self.blob_name not in self._container.blobs:
            raise _not_found("BlobNotFound")
        properties = BlobProperties(
            name=self.blob_name, metadata=self._container.metadata.get(self.blob_name)
        )
        properties.size = len(self._container.blobs[self.blob_name])
        properties.creation_time = CREATED
        properties.last_modified = MODIFIED
        properties.content_settings = ContentSettings(
            content_type="application/pdf", content_encoding="gzip"
        )
        return properties


class _FakeContainerClient:
    """An in-memory blob container, with the surface of ``ContainerClient``
    the adapter uses and the service's listing semantics."""

    def __init__(self, account_url: str, container_name: str, credential=None):
        self.account_url = account_url
        self.container_name = container_name
        self.credential = credential
        self.url = f"{account_url.rstrip('/')}/{container_name}"
        self.blobs: dict[str, bytes] = {}
        self.metadata: dict[str, dict[str, str]] = {}
        self.exists = True
        self.uploads: list[tuple[str, object, bool]] = []
        self.downloads: list[_FakeDownloader] = []

    @classmethod
    def from_connection_string(cls, conn_str: str, container_name: str):
        client = cls("http://127.0.0.1:10000/devstoreaccount1", container_name)
        client.connection_string = conn_str  # type: ignore[attr-defined]
        return client

    def check_container(self) -> None:
        if not self.exists:
            raise _not_found("ContainerNotFound")

    def upload_blob(self, name, data, overwrite=False):
        self.check_container()
        self.uploads.append((name, data, overwrite))
        if name in self.blobs and not overwrite:
            raise ResourceExistsError(message="BlobAlreadyExists")
        if isinstance(data, bytes):
            self.blobs[name] = data
            return
        chunks = []
        while chunk := data.read(4):
            chunks.append(chunk)
        self.blobs[name] = b"".join(chunks)

    def download_blob(self, blob):
        self.check_container()
        if blob not in self.blobs:
            raise _not_found("BlobNotFound")
        downloader = _FakeDownloader(self.blobs[blob])
        self.downloads.append(downloader)
        return downloader

    def delete_blob(self, blob):
        self.check_container()
        if blob not in self.blobs:
            raise _not_found("BlobNotFound")
        del self.blobs[blob]

    def get_blob_client(self, blob):
        return _FakeBlobClient(self, blob)

    def _properties(self, name: str) -> BlobProperties:
        return BlobProperties(name=name, metadata=self.metadata.get(name, {}))

    def list_blobs(self, name_starts_with=None, include=None):
        self.check_container()
        assert include == ["metadata"]
        prefix = name_starts_with or ""
        return [
            self._properties(name)
            for name in sorted(self.blobs)
            if name.startswith(prefix)
        ]

    def walk_blobs(self, name_starts_with=None, include=None, delimiter="/"):
        self.check_container()
        assert include == ["metadata"]
        prefix = name_starts_with or ""
        items: list[BlobProperties | BlobPrefix] = []
        seen: set[str] = set()
        for name in sorted(self.blobs):
            if not name.startswith(prefix):
                continue
            rest = name[len(prefix) :]
            if delimiter in rest:
                folder = prefix + rest[: rest.index(delimiter) + 1]
                if folder not in seen:
                    seen.add(folder)
                    items.append(BlobPrefix(prefix=folder))
            else:
                items.append(self._properties(name))
        return items


class _FakeCredential:
    def __init__(self, **kwargs):
        self.kwargs = kwargs


@pytest.fixture
def fakes(monkeypatch):
    credentials: list[_FakeCredential] = []

    def credential(**kwargs):
        made = _FakeCredential(**kwargs)
        credentials.append(made)
        return made

    monkeypatch.setattr(module, "ContainerClient", _FakeContainerClient)
    monkeypatch.setattr(module, "DefaultAzureCredential", credential)
    return credentials


def _adapter(**kwargs) -> ObjectStorageSecondaryAdapterAzureBlob:
    return ObjectStorageSecondaryAdapterAzureBlob(
        **{"container_name": "abi", "account_url": ACCOUNT_URL, **kwargs}
    )


def _container(adapter: ObjectStorageSecondaryAdapterAzureBlob) -> _FakeContainerClient:
    assert isinstance(adapter.container_client, _FakeContainerClient)
    return adapter.container_client


# -- credentials -------------------------------------------------------------


def test_account_url_authenticates_with_default_azure_credential(fakes):
    adapter = _adapter()

    container = _container(adapter)
    assert container.account_url == ACCOUNT_URL
    assert container.container_name == "abi"
    assert len(fakes) == 1
    assert container.credential is fakes[0]
    # No client id passed: DefaultAzureCredential keeps reading AZURE_CLIENT_ID,
    # where an explicit None would force the system-assigned identity.
    assert fakes[0].kwargs == {}


def test_managed_identity_client_id_selects_a_user_assigned_identity(fakes):
    _adapter(managed_identity_client_id="00000000-0000-0000-0000-000000000001")

    assert fakes[0].kwargs == {
        "managed_identity_client_id": "00000000-0000-0000-0000-000000000001"
    }


def test_connection_string_is_used_in_place_of_entra_id(fakes):
    adapter = ObjectStorageSecondaryAdapterAzureBlob(
        container_name="abi", connection_string="UseDevelopmentStorage=true"
    )

    container = _container(adapter)
    assert container.connection_string == "UseDevelopmentStorage=true"  # type: ignore[attr-defined]
    assert container.credential is None
    assert fakes == []


@pytest.mark.parametrize(
    "kwargs",
    [
        {},
        {"account_url": ACCOUNT_URL, "connection_string": "x"},
        {"connection_string": "x", "managed_identity_client_id": "id"},
    ],
)
def test_needs_exactly_one_way_to_reach_the_account(fakes, kwargs):
    with pytest.raises(ValueError):
        ObjectStorageSecondaryAdapterAzureBlob(container_name="abi", **kwargs)


def test_construction_makes_no_request():
    # The real SDK clients: building them must not reach the network.
    adapter = _adapter(managed_identity_client_id="client-id")

    assert adapter.container_client.url == f"{ACCOUNT_URL}/abi"


def test_missing_azure_extra_reads_as_an_install_hint(monkeypatch):
    monkeypatch.delitem(sys.modules, module.__name__)
    monkeypatch.setitem(sys.modules, "azure.identity", None)

    with pytest.raises(ModuleNotFoundError, match=r"naas-abi-core\[azure\]"):
        importlib.import_module(module.__name__)


# -- blob names --------------------------------------------------------------


def test_blob_names_join_the_normalized_base_prefix_prefix_and_key(fakes):
    adapter = _adapter(base_prefix="/datastore/")

    adapter.put_object("/workspaces//ws1/", "/inputs/workbook.xlsx", b"x")

    assert list(_container(adapter).blobs) == [
        "datastore/workspaces/ws1/inputs/workbook.xlsx"
    ]


def test_put_object_overwrites(fakes):
    adapter = _adapter()

    adapter.put_object("p", "k", b"one")
    adapter.put_object("p", "k", b"two")

    assert adapter.get_object("p", "k") == b"two"
    assert all(overwrite for _, _, overwrite in _container(adapter).uploads)


def test_put_object_stream_hands_the_stream_to_the_sdk(fakes):
    adapter = _adapter()
    stream = io.BytesIO(b"x" * 10)

    adapter.put_object_stream("p", "big.bin", stream)

    # The SDK uploads it in blocks; the adapter never reads it whole.
    assert _container(adapter).uploads == [("p/big.bin", stream, True)]
    assert adapter.get_object("p", "big.bin") == b"x" * 10


# -- reads and not-found -----------------------------------------------------


def test_get_object_stream_reads_in_parts(fakes):
    adapter = _adapter()
    adapter.put_object("p", "k", b"abcdefghij")

    with adapter.get_object_stream("p", "k") as stream:
        assert stream.read(3) == b"abc"
        assert stream.read() == b"defghij"

    assert stream.closed
    assert all(size > 0 for size in _container(adapter).downloads[0].reads)


@pytest.mark.parametrize(
    "call",
    [
        lambda a: a.get_object("p", "missing"),
        lambda a: a.get_object_stream("p", "missing").__enter__(),
        lambda a: a.delete_object("p", "missing"),
        lambda a: a.get_object_metadata("p", "missing"),
        lambda a: a.list_objects("missing"),
        lambda a: a.list_objects_recursive("missing"),
    ],
)
def test_a_missing_blob_or_prefix_is_object_not_found(fakes, call):
    with pytest.raises(Exceptions.ObjectNotFound):
        call(_adapter())


def test_a_missing_container_is_raised_as_is(fakes):
    adapter = _adapter()
    _container(adapter).exists = False

    with pytest.raises(ResourceNotFoundError) as raised:
        adapter.get_object("p", "k")

    assert not isinstance(raised.value, Exceptions.ObjectNotFound)


def test_get_object_metadata_maps_blob_properties(fakes):
    adapter = _adapter(base_prefix="datastore")
    adapter.put_object("papers/2024", "q1/report.pdf", b"12345")

    metadata = adapter.get_object_metadata("papers/2024", "q1/report.pdf")

    assert (
        metadata.file_path == f"{ACCOUNT_URL}/abi/datastore/papers/2024/q1/report.pdf"
    )
    assert metadata.file_name == "report.pdf"
    assert metadata.file_size_bytes == 5
    assert metadata.created_time == CREATED
    assert metadata.modified_time == MODIFIED
    assert metadata.mime_type == "application/pdf"
    assert metadata.encoding == "gzip"


# -- listings ----------------------------------------------------------------


def test_list_objects_names_folders_with_a_trailing_slash(fakes):
    adapter = _adapter(base_prefix="datastore")
    adapter.put_object("papers", "root.pdf", b"r")
    adapter.put_object("papers", "2024/spring.pdf", b"s")

    listed = adapter.list_objects("papers")

    assert listed == ["papers/2024/", "papers/root.pdf"]
    assert adapter.folders(listed) == {"papers/2024/"}


def test_list_objects_of_the_root(fakes):
    adapter = _adapter()
    adapter.put_object("", "top.txt", b"t")
    adapter.put_object("papers", "a.pdf", b"a")

    assert adapter.list_objects("") == ["papers/", "top.txt"]


def test_hierarchical_namespace_directories_are_not_objects(fakes):
    # On a Data Lake Storage Gen2 account the Blob API lists each directory as
    # a zero-byte blob marked hdi_isfolder, next to its contents.
    adapter = _adapter(base_prefix="datastore")
    adapter.put_object("papers", "2024/spring.pdf", b"s")
    container = _container(adapter)
    container.blobs["datastore/papers/2024"] = b""
    container.metadata["datastore/papers/2024"] = {"hdi_isfolder": "true"}
    container.blobs["datastore/papers/marker/"] = b""

    assert adapter.list_objects("papers") == ["papers/2024/", "papers/marker/"]
    assert adapter.list_objects_recursive("papers") == ["papers/2024/spring.pdf"]


class TestObjectStorageSecondaryAdapterAzureBlob(ObjectStorageSecondaryAdapterContract):
    @pytest.fixture
    def adapter(self, fakes):
        return _adapter(base_prefix="datastore")
