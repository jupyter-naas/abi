"""Publish and read personnel cockpit datasets from ObjectStorage."""

from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path
from typing import Any

from naas_abi_core.services.object_storage.ObjectStorageFactory import (
    ObjectStorageFactory,
)
from naas_abi_core.services.object_storage.ObjectStorageService import (
    ObjectStorageService,
)
from naas_abi_core.utils.Storage import find_storage_folder
from naas_abi_core.utils.StorageUtils import StorageUtils
from naas_abi_marketplace.domains.personnel.paths import (
    PERSONNEL_ROOT,
    cockpit_storage_prefix,
    module_datastore_path,
)

DEMO_DATA_COMMAND = (
    "cd libs/naas-abi-marketplace/naas_abi_marketplace/domains/personnel "
    "&& make app-personnel-cockpit-demo"
)


def _datastore_root() -> str:
    storage_root = find_storage_folder(str(PERSONNEL_ROOT))
    return os.path.join(storage_root, "datastore")


@lru_cache(maxsize=1)
def get_object_storage() -> ObjectStorageService:
    """Filesystem-backed ObjectStorage rooted at ``.abi/storage/datastore``."""
    return ObjectStorageFactory.ObjectStorageServiceFS(_datastore_root())


@lru_cache(maxsize=1)
def get_storage_utils() -> StorageUtils:
    return StorageUtils(get_object_storage())


def storage_key(relative_path: str) -> str:
    return relative_path.lstrip("/").replace("\\", "/")


def _storage_location(
    relative_path: str, *, datastore_path: str | None = None
) -> tuple[str, str]:
    """Split a cockpit-relative path into ObjectStorage ``prefix`` and ``key``."""
    parts = storage_key(relative_path).split("/")
    if not parts or not parts[-1]:
        raise ValueError(f"Invalid cockpit dataset path: {relative_path!r}")
    prefix_root = cockpit_storage_prefix(datastore_path)
    if len(parts) == 1:
        return prefix_root, parts[0]
    return f"{prefix_root}/{'/'.join(parts[:-1])}", parts[-1]


def publish_json(
    relative_path: str,
    payload: dict[str, Any] | list[Any],
    *,
    datastore_path: str | None = None,
) -> None:
    dir_path, file_name = _storage_location(
        relative_path, datastore_path=datastore_path
    )
    get_storage_utils().save_json(payload, dir_path, file_name, copy=False)


def publish_bytes(
    relative_path: str,
    content: bytes,
    *,
    datastore_path: str | None = None,
) -> None:
    dir_path, file_name = _storage_location(
        relative_path, datastore_path=datastore_path
    )
    get_object_storage().put_object(dir_path, file_name, content)


def publish_data_tree(
    local_data_root: Path, *, datastore_path: str | None = None
) -> list[str]:
    """Mirror ``apps/cockpit/data/`` into ObjectStorage under the module prefix."""
    written: list[str] = []
    for path in sorted(local_data_root.rglob("*.json")):
        relative = path.relative_to(local_data_root).as_posix()
        publish_bytes(relative, path.read_bytes(), datastore_path=datastore_path)
        written.append(relative)
    return written


class MissingDatasetError(FileNotFoundError):
    """A cockpit dataset is not published in ObjectStorage yet.

    Carries where the file was expected and how to produce it, so the API and
    the UI can say that instead of a bare 404.
    """

    def __init__(
        self,
        relative_path: str,
        *,
        storage_key: str,
        local_path: str,
        command: str = DEMO_DATA_COMMAND,
    ) -> None:
        self.relative_path = relative_path
        self.storage_key = storage_key
        self.local_path = local_path
        self.command = command
        super().__init__(
            f"Dataset not published: {relative_path}\n"
            f"Expected in storage: {storage_key}\n"
            f"Local file: {local_path}\n"
            f"Run: {command}"
        )

    def as_detail(self) -> dict[str, str]:
        """Payload shape the cockpit API returns as the 404 ``detail``."""
        return {
            "error": "missing_dataset",
            "dataset": self.relative_path,
            "expected_storage_key": self.storage_key,
            "expected_local_path": self.local_path,
            "command": self.command,
            "message": str(self),
        }


def read_json(
    relative_path: str, *, datastore_path: str | None = None
) -> dict[str, Any]:
    dir_path, file_name = _storage_location(
        relative_path, datastore_path=datastore_path
    )
    text = get_storage_utils().get_text(dir_path, file_name)
    if text is None:
        raise MissingDatasetError(
            relative_path,
            storage_key=f"{dir_path}/{file_name}",
            local_path=os.path.join(_datastore_root(), dir_path, file_name),
        )
    return json.loads(text)


def storage_has_datasets(*, datastore_path: str | None = None) -> bool:
    dir_path, file_name = _storage_location(
        "globals/entities.json", datastore_path=datastore_path
    )
    manifest = os.path.join(_datastore_root(), dir_path, file_name)
    return os.path.isfile(manifest)


def runtime_storage_prefix(*, datastore_path: str | None = None) -> str:
    return cockpit_storage_prefix(datastore_path or module_datastore_path())
