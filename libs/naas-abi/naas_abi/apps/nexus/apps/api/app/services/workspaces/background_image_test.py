from __future__ import annotations

import pytest
from naas_abi.apps.nexus.apps.api.app.services.files.drive_roots import workspace_drive_root
from naas_abi.apps.nexus.apps.api.app.services.files.service import FilesService
from naas_abi.apps.nexus.apps.api.app.services.workspaces.background_image import (
    BackgroundImageError,
    WorkspaceBackgroundImage,
    background_image_url,
    detect_image_extension,
    ensure_public_http_url,
)
from naas_abi_core.services.object_storage.adapters.secondary.ObjectStorageSecondaryAdapterFS import (  # noqa: E501
    ObjectStorageSecondaryAdapterFS,
)
from naas_abi_core.services.object_storage.ObjectStorageService import ObjectStorageService

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32
JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 32
WS = "ws-1"


def _files(tmp_path) -> FilesService:
    adapter = ObjectStorageSecondaryAdapterFS(base_path=str(tmp_path))
    return FilesService(storage=ObjectStorageService(adapter=adapter))


def _names(files: FilesService, folder: str) -> list[str]:
    return sorted(f.name for f in files.list_files(path=folder).files)


def _home(sub: str) -> str:
    return f"{workspace_drive_root(WS)}/.home/{sub}"


@pytest.mark.parametrize(
    ("content", "ext"),
    [
        (PNG, ".png"),
        (JPEG, ".jpg"),
        (b"GIF89a" + b"\x00" * 16, ".gif"),
        (b"RIFF\x00\x00\x00\x00WEBPVP8 " + b"\x00" * 16, ".webp"),
        (b"\x00\x00\x00\x1cftypavif" + b"\x00" * 16, ".avif"),
    ],
)
def test_detect_image_extension_reads_magic_bytes(content: bytes, ext: str) -> None:
    assert detect_image_extension(content) == ext


@pytest.mark.parametrize("content", [b"<svg xmlns='http://www.w3.org/2000/svg'/>", b"hello", b""])
def test_detect_image_extension_rejects_non_images(content: bytes) -> None:
    assert detect_image_extension(content) is None


def test_stage_writes_draft_under_home_tmp_and_replaces_previous_draft(tmp_path) -> None:
    files = _files(tmp_path)
    bg = WorkspaceBackgroundImage(files, WS)

    first = bg.stage(PNG)
    second = bg.stage(JPEG)

    assert first.endswith(".png") and second.endswith(".jpg")
    # One draft at a time: staging again clears the previous one.
    assert _names(files, _home("tmp")) == [second]
    assert bg.read_draft(second).content == JPEG


def test_stage_rejects_non_image_and_oversized_content(tmp_path) -> None:
    bg = WorkspaceBackgroundImage(_files(tmp_path), WS, max_bytes=64)

    with pytest.raises(BackgroundImageError, match="not a supported image"):
        bg.stage(b"<html></html>")
    with pytest.raises(BackgroundImageError, match="too large"):
        bg.stage(PNG + b"\x00" * 64)


def test_commit_moves_draft_clears_tmp_and_previous_images(tmp_path) -> None:
    files = _files(tmp_path)
    bg = WorkspaceBackgroundImage(files, WS)
    old = bg.commit(bg.stage(PNG))

    new = bg.commit(bg.stage(JPEG))

    assert _names(files, _home("background-img")) == [new]
    assert old != new
    assert _names(files, _home("tmp")) == []
    assert bg.read_current(new).content == JPEG


def test_current_name_is_the_committed_wallpaper(tmp_path) -> None:
    files = _files(tmp_path)
    bg = WorkspaceBackgroundImage(files, WS)
    assert bg.current_name() is None

    name = bg.commit(bg.stage(PNG))

    assert bg.current_name() == name


def test_commit_unknown_draft_fails(tmp_path) -> None:
    bg = WorkspaceBackgroundImage(_files(tmp_path), WS)

    with pytest.raises(BackgroundImageError, match="not found"):
        bg.commit("deadbeef.png")


@pytest.mark.parametrize("name", ["../secret.png", "a/b.png", ".hidden.png", "x.svg", ""])
def test_draft_and_current_names_are_validated(tmp_path, name: str) -> None:
    bg = WorkspaceBackgroundImage(_files(tmp_path), WS)

    with pytest.raises(BackgroundImageError):
        bg.read_draft(name)
    with pytest.raises(BackgroundImageError):
        bg.read_current(name)


def test_discard_clears_tmp(tmp_path) -> None:
    files = _files(tmp_path)
    bg = WorkspaceBackgroundImage(files, WS)
    bg.stage(PNG)

    bg.discard()

    assert _names(files, _home("tmp")) == []


def test_background_image_url_is_versioned_by_file_name() -> None:
    assert (
        background_image_url("ws-1", "abc.png") == "/api/workspaces/ws-1/background-image?v=abc.png"
    )


@pytest.mark.parametrize(
    "url",
    [
        "ftp://example.com/a.png",
        "file:///etc/passwd",
        "http://127.0.0.1/a.png",
        "http://localhost/a.png",
        "http://10.0.0.5/a.png",
        "http://169.254.169.254/latest/meta-data",
        "http://[::1]/a.png",
        "http://minio:9000/abi/a.png",
    ],
)
def test_ensure_public_http_url_blocks_non_public_targets(url: str) -> None:
    with pytest.raises(BackgroundImageError):
        ensure_public_http_url(url)


def test_ensure_public_http_url_accepts_public_address(monkeypatch) -> None:
    import socket

    monkeypatch.setattr(
        socket,
        "getaddrinfo",
        lambda *a, **k: [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443))],
    )

    ensure_public_http_url("https://example.com/a.png")


def test_background_image_url_carries_non_default_framing() -> None:
    assert (
        background_image_url("ws-1", "abc.png", x=25, y=62.5, zoom=1.75)
        == "/api/workspaces/ws-1/background-image?v=abc.png&x=25&y=62.5&z=1.75"
    )
