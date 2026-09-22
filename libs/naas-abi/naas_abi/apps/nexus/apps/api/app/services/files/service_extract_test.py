from __future__ import annotations

import io
import zipfile

import pytest
from naas_abi.apps.nexus.apps.api.app.services.files.files__schema import (
    InvalidArchiveError,
)
from naas_abi.apps.nexus.apps.api.app.services.files.service import FilesService
from naas_abi_core.services.object_storage.adapters.secondary.ObjectStorageSecondaryAdapterFS import (  # noqa: E501
    ObjectStorageSecondaryAdapterFS,
)
from naas_abi_core.services.object_storage.ObjectStorageService import ObjectStorageService


def _make_files_service(tmp_path) -> FilesService:
    adapter = ObjectStorageSecondaryAdapterFS(base_path=str(tmp_path))
    storage = ObjectStorageService(adapter=adapter)
    return FilesService(storage=storage)


def _zip_bytes(members: dict[str, bytes]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        for name, data in members.items():
            zf.writestr(name, data)
    return buf.getvalue()


def test_extract_zip_happy_path(tmp_path) -> None:
    files_service = _make_files_service(tmp_path)
    parent = "naas_abi/workspace-drive/ws-1"
    archive_path = f"{parent}/docs.zip"
    files_service.upload_file(
        filename="docs.zip",
        path=parent,
        content=_zip_bytes(
            {
                "readme.txt": b"hello",
                "nested/note.md": b"# note",
            }
        ),
        content_type="application/zip",
    )

    result = files_service.extract_archive(archive_path)

    assert result.type == "folder"
    assert result.path == f"{parent}/docs"
    assert result.name == "docs"
    assert files_service.read_file(f"{parent}/docs/readme.txt").content == "hello"
    assert files_service.read_file(f"{parent}/docs/nested/note.md").content == "# note"


def test_extract_rejects_path_traversal(tmp_path) -> None:
    files_service = _make_files_service(tmp_path)
    parent = "naas_abi/workspace-drive/ws-1"
    archive_path = f"{parent}/evil.zip"
    files_service.upload_file(
        filename="evil.zip",
        path=parent,
        content=_zip_bytes({"../escape.txt": b"nope"}),
        content_type="application/zip",
    )

    with pytest.raises(InvalidArchiveError, match="path traversal"):
        files_service.extract_archive(archive_path)

    # Destination folder must not be left behind after failure.
    names = {entry.name for entry in files_service.list_files(path=parent).files}
    assert "evil" not in names
    assert not files_service._file_exists(f"{parent}/escape.txt")


def test_extract_uses_collision_suffix(tmp_path) -> None:
    files_service = _make_files_service(tmp_path)
    parent = "naas_abi/workspace-drive/ws-1"
    files_service.create_folder(f"{parent}/bundle")
    files_service.upload_file(
        filename="bundle.zip",
        path=parent,
        content=_zip_bytes({"a.txt": b"one"}),
        content_type="application/zip",
    )

    result = files_service.extract_archive(f"{parent}/bundle.zip")

    assert result.path == f"{parent}/bundle-1"
    assert result.name == "bundle-1"
    assert files_service.read_file(f"{parent}/bundle-1/a.txt").content == "one"


def test_extract_invalid_archive(tmp_path) -> None:
    files_service = _make_files_service(tmp_path)
    parent = "naas_abi/workspace-drive/ws-1"
    files_service.upload_file(
        filename="broken.zip",
        path=parent,
        content=b"not-a-zip",
        content_type="application/zip",
    )

    with pytest.raises(InvalidArchiveError, match="Invalid or corrupted ZIP"):
        files_service.extract_archive(f"{parent}/broken.zip")

    names = {entry.name for entry in files_service.list_files(path=parent).files}
    assert "broken" not in names
