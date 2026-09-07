from __future__ import annotations

from naas_abi.apps.nexus.apps.api.app.services.files.service import FilesService
from naas_abi_core.services.object_storage.adapters.secondary.ObjectStorageSecondaryAdapterFS import (  # noqa: E501
    ObjectStorageSecondaryAdapterFS,
)
from naas_abi_core.services.object_storage.ObjectStorageService import ObjectStorageService


def _make_files_service(tmp_path) -> FilesService:
    adapter = ObjectStorageSecondaryAdapterFS(base_path=str(tmp_path))
    storage = ObjectStorageService(adapter=adapter)
    return FilesService(storage=storage)


def test_rename_workspace_drive_root_folder(tmp_path) -> None:
    files_service = _make_files_service(tmp_path)
    parent = "naas_abi/workspace-drive/ws-1"
    old_path = f"{parent}/operations"
    new_path = f"{parent}/ops-renamed"

    files_service.create_folder(old_path)
    files_service.create_file(
        path=f"{old_path}/notes.txt",
        content="hello",
        content_type="text/plain",
    )

    renamed = files_service.rename(old_path=old_path, new_path=new_path)

    assert renamed.type == "folder"
    assert renamed.path == new_path
    assert files_service._file_exists(f"{new_path}/notes.txt")
    assert not files_service._file_exists(f"{old_path}/notes.txt")
    names = {entry.name for entry in files_service.list_files(path=parent).files}
    assert "ops-renamed" in names


def test_rename_empty_workspace_drive_root_folder(tmp_path) -> None:
    files_service = _make_files_service(tmp_path)
    parent = "naas_abi/workspace-drive/ws-1"
    old_path = f"{parent}/s2_intelligence"
    new_path = f"{parent}/s2-intel"

    files_service.create_folder(parent)
    files_service.create_folder(old_path)
    renamed = files_service.rename(old_path=old_path, new_path=new_path)

    assert renamed.type == "folder"
    assert renamed.path == new_path
    assert files_service._is_directory(new_path)
    names = {entry.name for entry in files_service.list_files(path=parent).files}
    assert "s2-intel" in names
