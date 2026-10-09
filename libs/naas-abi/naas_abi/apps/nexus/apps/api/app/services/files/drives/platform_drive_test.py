"""The platform drive receives the nine staff folders once, without touching existing files."""

from __future__ import annotations

import pytest
from naas_abi.apps.nexus.apps.api.app.services.files.drives.platform_drive import (
    PLATFORM_STAFF_MARKER,
    PLATFORM_STAFF_MARKER_ROOT,
    backfill_platform_drive,
    ensure_platform_staff_folders,
)
from naas_abi.apps.nexus.apps.api.app.services.files.drives.utils.staff_folders import (
    README_NAME,
    STAFF_FOLDERS,
    staff_folder_readme,
)
from naas_abi_core.services.object_storage.adapters.secondary.ObjectStorageSecondaryAdapterFS import (  # noqa: E501
    ObjectStorageSecondaryAdapterFS,
)
from naas_abi_core.services.object_storage.ObjectStoragePort import Exceptions
from naas_abi_core.services.object_storage.ObjectStorageService import ObjectStorageService


def _storage(tmp_path) -> ObjectStorageService:
    return ObjectStorageService(
        adapter=ObjectStorageSecondaryAdapterFS(base_path=str(tmp_path / "datastore"))
    )


def _has(storage: ObjectStorageService, prefix: str, key: str) -> bool:
    try:
        storage.get_object(prefix, key)
        return True
    except Exceptions.ObjectNotFound:
        return False


def _readme(storage: ObjectStorageService, folder: str) -> bytes:
    return storage.get_object(f"naas_abi/platform-drive/{folder}", README_NAME)


@pytest.mark.asyncio
async def test_backfill_creates_platform_staff_folders_once_and_keeps_files(tmp_path) -> None:
    storage = _storage(tmp_path)
    storage.put_object("naas_abi/platform-drive/bob", "keep.txt", b"legacy")
    storage.put_object("naas_abi/platform-drive/intelligence", README_NAME, b"# Ours")

    first = await backfill_platform_drive(storage)

    assert first == {"staff_folders": 1}
    assert storage.get_object("naas_abi/platform-drive/bob", "keep.txt") == b"legacy"
    assert _readme(storage, "intelligence") == b"# Ours"
    for folder in STAFF_FOLDERS:
        prefix = f"naas_abi/platform-drive/{folder}"
        assert _has(storage, prefix, ".nexus_folder")
        if folder != "intelligence":
            assert _readme(storage, folder).decode("utf-8") == staff_folder_readme(folder)
    assert _has(storage, PLATFORM_STAFF_MARKER_ROOT, PLATFORM_STAFF_MARKER)

    second = await backfill_platform_drive(storage)

    assert second == {"staff_folders": 0}
    assert _readme(storage, "intelligence") == b"# Ours"
    assert ensure_platform_staff_folders(storage) is False


@pytest.mark.asyncio
async def test_a_deleted_platform_staff_folder_stays_deleted(tmp_path) -> None:
    storage = _storage(tmp_path)
    await backfill_platform_drive(storage)
    storage.delete_object("naas_abi/platform-drive/logistics", README_NAME)
    storage.delete_object("naas_abi/platform-drive/logistics", ".nexus_folder")

    written = await backfill_platform_drive(storage)

    assert written == {"staff_folders": 0}
    assert not _has(storage, "naas_abi/platform-drive/logistics", README_NAME)
    assert not _has(storage, "naas_abi/platform-drive/logistics", ".nexus_folder")
    assert _has(storage, "naas_abi/platform-drive/personnel", README_NAME)
