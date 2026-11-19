"""The File System drive, read off the engine's object storage configuration:
type, provider and location, never a credential; probed with one small read."""

from __future__ import annotations

import dataclasses
import uuid

import pytest
from naas_abi.apps.nexus.apps.api.app.services.drives.adapters.secondary.object_storage import (
    ObjectStorageDrive,
    describe_object_storage,
)
from naas_abi.apps.nexus.apps.api.app.services.drives.port import DriveLocation
from naas_abi_core.engine.engine_configuration.EngineConfiguration_ObjectStorageService import (
    ObjectStorageAdapterConfiguration,
)
from naas_abi_core.services.object_storage.ObjectStoragePort import Exceptions

# Generated per run: no credential-shaped literal in the repository (secret scanners
# flag those); the answers must carry none of them.
KEY_ID = f"canary-key-id-{uuid.uuid4().hex}"
SECRET = f"canary-secret-{uuid.uuid4().hex}"
TOKEN = f"canary-token-{uuid.uuid4().hex}"
NAAS_KEY = f"canary-naas-key-{uuid.uuid4().hex}"
NATS_KEY = f"canary-nats-key-{uuid.uuid4().hex}"
SECRETS = (KEY_ID, SECRET, TOKEN, NAAS_KEY, NATS_KEY)


def configuration(adapter: str, **config) -> ObjectStorageAdapterConfiguration:
    return ObjectStorageAdapterConfiguration(adapter=adapter, config=config)


def s3(**overrides) -> ObjectStorageAdapterConfiguration:
    config = {
        "bucket_name": "abi",
        "base_prefix": "abi/datastore",
        "access_key_id": KEY_ID,
        "secret_access_key": SECRET,
        "session_token": TOKEN,
        "endpoint_url": "http://minio:9000",
    }
    config.update(overrides)
    return configuration("s3", **config)


def no_secret_in(description) -> bool:
    text = repr(dataclasses.asdict(description))
    return not any(secret in text for secret in SECRETS)


def test_minio_is_the_file_system_an_s3_endpoint_names():
    description = describe_object_storage(s3())
    assert description.id == "file-system"
    assert description.name == "File System"
    assert description.type == "Object storage"
    assert description.provider == "MinIO (S3-compatible)"
    assert description.adapter == "s3"
    assert description.location == (
        DriveLocation("bucket", "abi"),
        DriveLocation("prefix", "abi/datastore"),
    )
    assert no_secret_in(description)


@pytest.mark.parametrize(
    "endpoint, provider",
    [
        (None, "Amazon S3"),
        ("https://s3.eu-west-3.amazonaws.com", "Amazon S3"),
        ("http://10.0.0.5:9000", "MinIO (S3-compatible)"),
        ("https://storage.example.com", "S3-compatible"),
    ],
)
def test_the_s3_endpoint_tells_the_provider(endpoint, provider):
    assert describe_object_storage(s3(endpoint_url=endpoint)).provider == provider


def test_an_empty_prefix_is_not_shown():
    assert describe_object_storage(s3(base_prefix="")).location == (DriveLocation("bucket", "abi"),)


def test_a_local_directory():
    description = describe_object_storage(configuration("fs", base_path="storage/datastore"))
    assert (description.type, description.provider, description.adapter) == (
        "Object storage",
        "Local file system",
        "fs",
    )
    assert description.location == (DriveLocation("path", "storage/datastore"),)


def test_cloudflare_r2_and_naas_keep_their_keys_to_themselves():
    r2 = describe_object_storage(
        configuration(
            "r2",
            account_id="acct",
            bucket_name="files",
            base_prefix="abi",
            access_key_id=KEY_ID,
            secret_access_key=SECRET,
        )
    )
    assert r2.provider == "Cloudflare R2 (S3-compatible)"
    assert r2.location == (DriveLocation("bucket", "files"), DriveLocation("prefix", "abi"))
    assert no_secret_in(r2)
    naas = describe_object_storage(
        configuration(
            "naas",
            naas_api_key=NAAS_KEY,
            workspace_id="ws",
            storage_name="store",
            base_prefix="",
        )
    )
    assert naas.provider == "Naas storage"
    assert naas.location == (DriveLocation("storage", "store"),)
    assert no_secret_in(naas)


def test_another_engines_storage_names_no_credential():
    description = describe_object_storage(
        configuration("nats_rpc", nats_url="nats://user:pass@nats:4222", service_key=NATS_KEY)
    )
    assert description.provider == "Another engine (over NATS)"
    assert description.location == ()
    assert no_secret_in(description)
    assert "pass" not in repr(description)


class Storage:
    def __init__(self, error: BaseException | None = None):
        self.error = error
        self.listed: list[str] = []

    def list_objects(self, prefix: str, queue=None) -> list[str]:
        self.listed.append(prefix)
        if self.error is not None:
            raise self.error
        return ["naas_abi/"]


def test_the_probe_lists_the_top_of_the_storage_once():
    storage = Storage()
    ObjectStorageDrive(s3(), lambda: storage).probe()
    assert storage.listed == [""]


def test_an_empty_storage_answers():
    """S3 says an empty prefix is not found: the storage answered all the same."""
    ObjectStorageDrive(s3(), lambda: Storage(Exceptions.ObjectNotFound("empty"))).probe()


def test_a_storage_that_fails_raises():
    with pytest.raises(ConnectionError):
        ObjectStorageDrive(s3(), lambda: Storage(ConnectionError("refused"))).probe()


def test_a_storage_the_engine_could_not_load_raises():
    def missing():
        raise RuntimeError("object storage is not configured")

    with pytest.raises(RuntimeError):
        ObjectStorageDrive(s3(), missing).probe()
