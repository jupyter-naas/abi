import asyncio
import io
from contextlib import contextmanager
from datetime import UTC, datetime

import pytest
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.adapters.secondary.object_storage_resources import (
    ObjectStorageResources,
)
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.contracts import (
    ServiceResourcesContract,
)
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.resources import (
    PREVIEW_BYTES,
    InvalidResource,
)
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.tests import fixtures
from naas_abi_core.services.object_storage.adapters.secondary.ObjectStorageSecondaryAdapterFS import (
    ObjectStorageSecondaryAdapterFS,
)
from naas_abi_core.services.object_storage.ObjectStoragePort import (
    Exceptions,
    IObjectStorageAdapter,
    ObjectMetaData,
)
from naas_abi_core.services.object_storage.ObjectStorageService import ObjectStorageService


def _seed(storage):
    for name, value in fixtures.SEED_ITEMS.items():
        storage.put_object("", name, value)
    for name, value in fixtures.SEED_NESTED.items():
        storage.put_object(fixtures.SEED_CONTAINER, name, value)
    return storage


class S3StyleAdapter(IObjectStorageAdapter):
    """Lists like S3 with a delimiter: direct keys plus ``folder/`` common prefixes;
    a folder has no metadata and a missing prefix is ObjectNotFound."""

    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}
        self.metadata_calls = 0

    @staticmethod
    def _key(prefix: str, key: str) -> str:
        return f"{prefix.strip('/')}/{key}" if prefix.strip("/") else key

    def get_object(self, prefix, key):
        try:
            return self.objects[self._key(prefix, key)]
        except KeyError:
            raise Exceptions.ObjectNotFound(key) from None

    @contextmanager
    def get_object_stream(self, prefix, key):
        yield io.BytesIO(self.get_object(prefix, key))

    def put_object(self, prefix, key, content):
        self.objects[self._key(prefix, key)] = content

    def put_object_stream(self, prefix, key, stream):
        self.put_object(prefix, key, stream.read())

    def delete_object(self, prefix, key):
        self.get_object(prefix, key)
        del self.objects[self._key(prefix, key)]

    def list_objects(self, prefix, queue=None):
        under = [k for k in self.objects if k.startswith(prefix)]
        if prefix and not under:
            raise Exceptions.ObjectNotFound(prefix)
        listed = set()
        for key in under:
            rest = key[len(prefix) :]
            listed.add(prefix + rest.split("/", 1)[0] + ("/" if "/" in rest else ""))
        return sorted(listed)

    def list_objects_recursive(self, prefix, queue=None):
        return sorted(k for k in self.objects if k.startswith(prefix))

    def get_object_metadata(self, prefix, key):
        self.metadata_calls += 1
        data = self.get_object(prefix, key)
        return ObjectMetaData(
            file_path=self._key(prefix, key),
            file_name=key,
            file_size_bytes=len(data),
            created_time=None,
            modified_time=datetime(2026, 10, 2, tzinfo=UTC),
            accessed_time=None,
            permissions=None,
            mime_type="text/plain",
            encoding=None,
        )


class TestObjectStorageResourcesOnFilesystem(ServiceResourcesContract):
    containers = True

    @pytest.fixture
    def resources(self, tmp_path):
        storage = ObjectStorageService(ObjectStorageSecondaryAdapterFS(str(tmp_path)))
        return ObjectStorageResources(_seed(storage))


class TestObjectStorageResourcesOnS3StyleListing(ServiceResourcesContract):
    containers = True

    @pytest.fixture
    def resources(self):
        return ObjectStorageResources(_seed(ObjectStorageService(S3StyleAdapter())))


def test_only_the_listed_page_pays_for_metadata():
    adapter = S3StyleAdapter()
    for i in range(20):
        adapter.put_object("", f"file-{i:02}", b"x")
    resources = ObjectStorageResources(ObjectStorageService(adapter))

    page = asyncio.run(resources.list("", limit=3))

    assert [e.name for e in page.entries] == ["file-00", "file-01", "file-02"]
    assert adapter.metadata_calls == 3


@pytest.mark.parametrize("bad", ["../escape", "a/../../b", "/abs", "a//b", "a\\b", "x/"])
def test_paths_cannot_escape_or_be_malformed(tmp_path, bad):
    storage = ObjectStorageService(ObjectStorageSecondaryAdapterFS(str(tmp_path / "root")))
    resources = ObjectStorageResources(storage)

    with pytest.raises(InvalidResource):
        asyncio.run(resources.write(bad, b"x"))
    assert not (tmp_path / "escape").exists()


def test_previews_are_bounded_and_report_the_full_size(tmp_path):
    storage = ObjectStorageService(ObjectStorageSecondaryAdapterFS(str(tmp_path)))
    storage.put_object("logs", "big.txt", b"y" * (3 * PREVIEW_BYTES))
    storage.put_object("img", "logo.png", b"\x89PNG\r\n\x1a\n\x00")
    resources = ObjectStorageResources(storage)

    big = asyncio.run(resources.read("logs/big.txt"))
    png = asyncio.run(resources.read("img/logo.png"))

    assert big.content.truncated is True
    assert big.content.size == 3 * PREVIEW_BYTES
    assert len(big.content.text) == PREVIEW_BYTES
    assert (png.content.encoding, png.content.text) == ("binary", None)
    assert big.entry.attributes == {"media_type": "text/plain"}


def test_writing_creates_intermediate_folders(tmp_path):
    storage = ObjectStorageService(ObjectStorageSecondaryAdapterFS(str(tmp_path)))
    resources = ObjectStorageResources(storage)

    asyncio.run(resources.write("reports/2026/q3.csv", b"a,b\n"))

    (reports,) = asyncio.run(resources.list("")).entries
    assert (reports.id, reports.kind) == ("reports", "container")
    (year,) = asyncio.run(resources.list("reports")).entries
    assert (year.id, year.kind) == ("reports/2026", "container")
