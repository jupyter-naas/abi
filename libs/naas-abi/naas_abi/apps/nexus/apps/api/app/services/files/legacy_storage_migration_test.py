from __future__ import annotations

import os

from naas_abi.apps.nexus.apps.api.app.services.files.legacy_storage_migration import (
    LegacyStorageMigrator,
)
from naas_abi.apps.nexus.apps.api.app.services.files.service import FilesService
from naas_abi_core.services.object_storage.adapters.secondary.ObjectStorageSecondaryAdapterFS import (
    ObjectStorageSecondaryAdapterFS,
)
from naas_abi_core.services.object_storage.ObjectStoragePort import Exceptions
from naas_abi_core.services.object_storage.ObjectStorageService import ObjectStorageService


class S3LikeAdapter(ObjectStorageSecondaryAdapterFS):
    """The FS adapter, but listing a file raises ObjectNotFound, as the S3 adapter does."""

    def list_objects(self, prefix, queue=None):
        if os.path.isfile(os.path.join(self.base_path, prefix)):
            raise Exceptions.ObjectNotFound(f"Prefix {prefix} not found")
        return super().list_objects(prefix, queue)


def _make_files_service(tmp_path, adapter_class=ObjectStorageSecondaryAdapterFS) -> FilesService:
    adapter = adapter_class(base_path=str(tmp_path))
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
    assert files_service._file_exists("naas_abi/.migrated/v2/my-drive/user-1")


def test_files_are_moved_when_listing_a_file_is_not_found(tmp_path) -> None:
    files_service = _make_files_service(tmp_path, S3LikeAdapter)
    files_service.create_file(
        path="ws-1/new-folder/report.pdf", content="pdf", content_type="application/pdf"
    )
    files_service.create_file(path="ws-1/top.md", content="top", content_type="text/markdown")

    LegacyStorageMigrator(files_service).ensure_workspace_drive_migrated("ws-1")

    root = "naas_abi/workspace-drive/ws-1"
    assert files_service.read_file(path=f"{root}/new-folder/report.pdf").content == "pdf"
    assert files_service.read_file(path=f"{root}/top.md").content == "top"
    assert not files_service._file_exists("ws-1/new-folder/report.pdf")
    assert not files_service._file_exists("ws-1/top.md")


def test_a_first_version_marker_does_not_stop_the_move(tmp_path) -> None:
    # The first version wrote its marker on S3 without moving anything.
    files_service = _make_files_service(tmp_path, S3LikeAdapter)
    files_service.create_file(
        path="naas_abi/.migrated/workspace-drive/ws-1", content="", content_type="text/plain"
    )
    files_service.create_file(path="ws-1/spec.md", content="spec", content_type="text/markdown")

    LegacyStorageMigrator(files_service).ensure_workspace_drive_migrated("ws-1")

    assert files_service.read_file(path="naas_abi/workspace-drive/ws-1/spec.md").content == "spec"
    assert files_service._file_exists("naas_abi/.migrated/v2/workspace-drive/ws-1")
