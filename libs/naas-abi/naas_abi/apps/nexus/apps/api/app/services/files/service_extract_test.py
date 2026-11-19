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


PARENT = "naas_abi/workspace-drive/ws-1"


def _stored(files_service: FilesService, name: str, content: bytes) -> str:
    files_service.upload_file(
        filename=name, path=PARENT, content=content, content_type="application/octet-stream"
    )
    return f"{PARENT}/{name}"


def _tar_bytes(members: list[tuple[str, bytes | None, bytes]]) -> bytes:
    """(name, tar type or None for a regular file, data)."""
    import tarfile

    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tf:
        for name, kind, data in members:
            info = tarfile.TarInfo(name)
            if kind is not None:
                info.type = kind
            else:
                info.size = len(data)
            tf.addfile(info, io.BytesIO(data) if kind is None else None)
    return buf.getvalue()


def test_extract_keeps_every_member_counted(tmp_path) -> None:
    """Folders count against the member limit as files do."""
    from naas_abi.apps.nexus.apps.api.app.services.files.files__schema import (
        ExtractTooLargeError,
    )

    files_service = _make_files_service(tmp_path)
    files_service.max_extract_files = 20
    archive = _stored(
        files_service, "dirs.zip", _zip_bytes({f"d{i}/": b"" for i in range(21)})
    )
    with pytest.raises(ExtractTooLargeError, match="too many entries"):
        files_service.extract_archive(archive)
    assert not files_service._is_directory(f"{PARENT}/dirs")


def test_extract_keeps_special_members_out(tmp_path) -> None:
    import tarfile

    files_service = _make_files_service(tmp_path)
    for kind in (tarfile.FIFOTYPE, tarfile.CHRTYPE, tarfile.BLKTYPE):
        archive = _stored(
            files_service,
            "special.tar.gz",
            _tar_bytes([("ok.txt", None, b"fine"), ("pipe", kind, b"")]),
        )
        with pytest.raises(InvalidArchiveError, match="special member"):
            files_service.extract_archive(archive)
        assert not files_service._is_directory(f"{PARENT}/special")


def test_extract_keeps_tar_headers_read_one_at_a_time(tmp_path, monkeypatch) -> None:
    """The member table is never built whole before the count applies."""
    import tarfile

    from naas_abi.apps.nexus.apps.api.app.services.files.files__schema import (
        ExtractTooLargeError,
    )

    def no_whole_table(self):
        raise AssertionError("getmembers() reads the whole table first")

    monkeypatch.setattr(tarfile.TarFile, "getmembers", no_whole_table)
    files_service = _make_files_service(tmp_path)
    files_service.max_extract_files = 10
    archive = _stored(
        files_service, "many.tar.gz", _tar_bytes([(f"f{i}.txt", None, b"x") for i in range(50)])
    )
    with pytest.raises(ExtractTooLargeError, match="too many entries"):
        files_service.extract_archive(archive)


def test_extract_keeps_the_expansion_ratio(tmp_path) -> None:
    from naas_abi.apps.nexus.apps.api.app.services.files.files__schema import (
        ExtractTooLargeError,
    )

    files_service = _make_files_service(tmp_path)
    files_service.max_extract_ratio_floor = 1024 * 1024
    archive = _stored(files_service, "zeros.zip", _zip_bytes({"zeros.bin": b"\0" * (4 * 1024 * 1024)}))
    with pytest.raises(ExtractTooLargeError, match="uncompressed size"):
        files_service.extract_archive(archive)
    # Under the floor, a high ratio is fine.
    files_service.max_extract_ratio_floor = 16 * 1024 * 1024
    assert files_service.extract_archive(archive).type == "folder"


def test_extract_keeps_a_member_to_what_its_header_allows(tmp_path) -> None:
    """A member is counted as it is read, not only by what its header says."""
    from naas_abi.apps.nexus.apps.api.app.services.files.files__schema import (
        ExtractTooLargeError,
    )

    files_service = _make_files_service(tmp_path)
    files_service.max_extract_member_bytes = 1024
    content = bytearray(_zip_bytes({"big.txt": b"a" * 4096}))
    # Rewrite the declared sizes (local header and central directory) to 10 bytes.
    import struct

    local = content.find(b"PK\x03\x04")
    struct.pack_into("<I", content, local + 22, 10)
    central = content.find(b"PK\x01\x02")
    struct.pack_into("<I", content, central + 24, 10)
    archive = _stored(files_service, "lying.zip", bytes(content))
    with pytest.raises((ExtractTooLargeError, InvalidArchiveError)):
        files_service.extract_archive(archive)
    assert not files_service._file_exists(f"{PARENT}/lying/big.txt")


def test_extract_keeps_storage_errors_apart_from_archive_errors(tmp_path, monkeypatch) -> None:
    """A storage failure while writing is not a bad archive: it surfaces as
    itself (a server error), and what was written is removed."""
    files_service = _make_files_service(tmp_path)
    archive = _stored(files_service, "ok.zip", _zip_bytes({"a.txt": b"a", "b.txt": b"b"}))
    real_write = files_service._write_bytes

    def failing_write(path: str, content: bytes) -> None:
        if path.endswith("b.txt"):
            raise RuntimeError("storage is down")
        real_write(path, content)

    monkeypatch.setattr(files_service, "_write_bytes", failing_write)
    with pytest.raises(RuntimeError, match="storage is down"):
        files_service.extract_archive(archive)
    assert not files_service._file_exists(f"{PARENT}/ok/a.txt")
