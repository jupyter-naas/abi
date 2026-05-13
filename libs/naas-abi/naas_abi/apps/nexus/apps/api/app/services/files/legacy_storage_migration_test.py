from __future__ import annotations

from naas_abi.apps.nexus.apps.api.app.services.files.legacy_storage_migration import (
    LegacyStorageMigrator,
)
from naas_abi.apps.nexus.apps.api.app.services.files.service import FilesService
from naas_abi_core.services.object_storage.adapters.secondary.ObjectStorageSecondaryAdapterFS import (
    ObjectStorageSecondaryAdapterFS,
)
from naas_abi_core.services.object_storage.ObjectStorageService import ObjectStorageService


def _make_files_service(tmp_path) -> FilesService:
    adapter = ObjectStorageSecondaryAdapterFS(base_path=str(tmp_path))
    storage = ObjectStorageService(adapter=adapter)
    return FilesService(storage=storage)


def test_my_drive_legacy_files_are_moved_under_naas_abi(tmp_path) -> None:
    files_service = _make_files_service(tmp_path)
    files_service.create_file(
        path="my-drive/user-1/uploads/notes.md", content="hello", content_type="text/markdown"
    )

    LegacyStorageMigrator(files_service).ensure_my_drive_migrated("user-1")

    assert files_service.read_file(path="naas_abi/my-drive/user-1/uploads/notes.md").content == (
        "hello"
    )
    assert not files_service._file_exists("my-drive/user-1/uploads/notes.md")


def test_workspace_legacy_files_are_moved_under_naas_abi(tmp_path) -> None:
    files_service = _make_files_service(tmp_path)
    files_service.create_file(
        path="ws-1/docs/spec.md", content="spec", content_type="text/markdown"
    )

    LegacyStorageMigrator(files_service).ensure_workspace_drive_migrated("ws-1")

    assert (
        files_service.read_file(path="naas_abi/workspace-drive/ws-1/docs/spec.md").content
        == "spec"
    )
    assert not files_service._file_exists("ws-1/docs/spec.md")


def test_migration_is_idempotent(tmp_path) -> None:
    files_service = _make_files_service(tmp_path)
    files_service.create_file(
        path="my-drive/user-1/a.txt", content="a", content_type="text/plain"
    )
    migrator = LegacyStorageMigrator(files_service)
    migrator.ensure_my_drive_migrated("user-1")
    # Re-adding a legacy file after the marker is written must not trigger a second move
    files_service.create_file(
        path="my-drive/user-1/b.txt", content="b", content_type="text/plain"
    )
    migrator.ensure_my_drive_migrated("user-1")

    assert files_service._file_exists("my-drive/user-1/b.txt")
    assert not files_service._file_exists("naas_abi/my-drive/user-1/b.txt")


def test_migration_marker_is_written_when_no_legacy_data(tmp_path) -> None:
    files_service = _make_files_service(tmp_path)
    LegacyStorageMigrator(files_service).ensure_my_drive_migrated("user-1")
    assert files_service._file_exists("naas_abi/.migrated/my-drive/user-1")
