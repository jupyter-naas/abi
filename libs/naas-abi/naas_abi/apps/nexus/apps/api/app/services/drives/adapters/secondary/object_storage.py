"""The File System drive: the engine's object storage
(``services.object_storage.object_storage_adapter``).

Only what tells the drive apart is read off the configuration: the adapter, the
S3 endpoint's host (MinIO, Amazon S3 or another S3-compatible service), the
bucket, the prefix or the directory. Access keys, secrets, tokens, API keys and
URLs (which can hold a user and a password) never leave this adapter.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any
from urllib.parse import urlsplit

from naas_abi.apps.nexus.apps.api.app.services.drives.port import (
    DriveDescription,
    DriveLocation,
    DriveSource,
)
from naas_abi_core.services.object_storage.ObjectStoragePort import Exceptions

FILE_SYSTEM_ID = "file-system"
FILE_SYSTEM_NAME = "File System"
OBJECT_STORAGE = "Object storage"
MINIO_PORT = 9000

_PROVIDERS = {
    "fs": "Local file system",
    "r2": "Cloudflare R2 (S3-compatible)",
    "naas": "Naas storage",
    "nats_rpc": "Another engine (over NATS)",
    "custom": "Custom adapter",
}


def _setting(config: Any, name: str) -> str:
    value = config.get(name) if isinstance(config, dict) else getattr(config, name, None)
    return value.strip() if isinstance(value, str) else ""


def s3_provider(endpoint_url: str | None) -> str:
    """Amazon S3 without an endpoint or on ``amazonaws.com``; MinIO on a host named
    for it or on its port (9000); any other endpoint is S3-compatible."""
    if not endpoint_url:
        return "Amazon S3"
    try:
        parts = urlsplit(endpoint_url if "//" in endpoint_url else f"//{endpoint_url}")
        host, port = (parts.hostname or "").lower(), parts.port
    except ValueError:
        return "S3-compatible"
    if host == "amazonaws.com" or host.endswith(".amazonaws.com"):
        return "Amazon S3"
    if "minio" in host or port == MINIO_PORT:
        return "MinIO (S3-compatible)"
    return "S3-compatible"


def _location(*parts: tuple[str, str]) -> tuple[DriveLocation, ...]:
    return tuple(DriveLocation(label, value) for label, value in parts if value)


def describe_object_storage(configuration: Any) -> DriveDescription:
    """The File System as ``object_storage_adapter`` configures it, no credential in it."""
    adapter = str(getattr(configuration, "adapter", "") or "custom")
    config = getattr(configuration, "config", None)
    if adapter == "s3":
        provider = s3_provider(_setting(config, "endpoint_url") or None)
    else:
        provider = _PROVIDERS.get(adapter, adapter)
    if adapter in ("s3", "r2"):
        location = _location(
            ("bucket", _setting(config, "bucket_name")),
            ("prefix", _setting(config, "base_prefix").strip("/")),
        )
    elif adapter == "fs":
        location = _location(("path", _setting(config, "base_path")))
    elif adapter == "naas":
        location = _location(
            ("storage", _setting(config, "storage_name")),
            ("prefix", _setting(config, "base_prefix").strip("/")),
        )
    else:
        # Another engine's storage, or a custom adapter: nothing safe to show.
        location = ()
    return DriveDescription(
        id=FILE_SYSTEM_ID,
        name=FILE_SYSTEM_NAME,
        type=OBJECT_STORAGE,
        provider=provider,
        adapter=adapter,
        location=location,
    )


class ObjectStorageDrive(DriveSource):
    """``configuration``: the engine's ``object_storage_adapter``; ``storage``: its
    loaded adapter, resolved at each probe (raising when the engine has none)."""

    def __init__(self, configuration: Any, storage: Callable[[], Any]) -> None:
        self._configuration = configuration
        self._storage = storage

    def describe(self) -> DriveDescription:
        return describe_object_storage(self._configuration)

    def probe(self) -> None:
        """One listing of the storage's top level. The adapter is asked directly, not
        the kernel service: the question is whether the storage answers, not what the
        caller may list (the route already allowed the caller)."""
        try:
            self._storage().list_objects("")
        except Exceptions.ObjectNotFound:
            # An empty storage: S3 says the prefix is not found, which is an answer.
            return
