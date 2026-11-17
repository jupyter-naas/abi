from __future__ import annotations

import pytest
from naas_abi.apps.nexus.apps.api.app.services.files.drives.utils.drive_roots import (
    workspace_drive_root,
)
from naas_abi.apps.nexus.apps.api.app.services.files.service import FilesService
from naas_abi.apps.nexus.apps.api.app.services.workspaces.background_image import (
    BackgroundImageError,
    WorkspaceBackgroundImage,
    background_image_url,
    detect_image_extension,
    ensure_public_http_url,
    fetch_image_url,
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
    ("url", "message"),
    [
        ("ftp://example.com/a.png", "Only http"),
        ("file:///etc/passwd", "Only http"),
        ("http://[::1/a.png", "Only http"),
        ("http://127.0.0.1/a.png", "private or local"),
        ("http://localhost/a.png", "private or local"),
        ("http://10.0.0.5/a.png", "private or local"),
        ("http://169.254.169.254/latest/meta-data", "private or local"),
        ("http://[::1]/a.png", "private or local"),
        ("http://minio:9000/abi/a.png", "private or local"),
    ],
)
def test_wallpaper_fetch_keeps_non_public_targets_out(url: str, message: str) -> None:
    import asyncio

    with pytest.raises(BackgroundImageError, match=message):
        asyncio.run(fetch_image_url(url))


def test_background_image_url_carries_non_default_framing() -> None:
    assert (
        background_image_url("ws-1", "abc.png", x=25, y=62.5, zoom=1.75)
        == "/api/workspaces/ws-1/background-image?v=abc.png&x=25&y=62.5&z=1.75"
    )


def test_remove_archives_the_wallpaper_and_clears_drafts(tmp_path) -> None:
    from datetime import datetime

    files = _files(tmp_path)
    bg = WorkspaceBackgroundImage(files, WS)
    name = bg.commit(bg.stage(PNG))
    bg.stage(JPEG)  # a draft in progress

    archived = bg.remove(now=datetime(2026, 10, 14, 10, 0, 5))

    assert archived == f"20261014T100005Z_{name}"
    assert bg.current_name() is None
    assert _names(files, _home("tmp")) == []
    assert _names(files, _home("archives")) == [archived]
    assert bg.remove(now=datetime(2026, 10, 14, 11, 0, 0)) is None


class _ImageListener:
    """An image server on 127.0.0.1, standing for a service on the platform's network."""

    def __init__(self) -> None:
        import threading
        from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

        self.hits: list[str] = []
        self.redirect_to = ""
        listener = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:  # noqa: N802
                listener.hits.append(self.path)
                if self.path.startswith("/redirect"):
                    self.send_response(302)
                    self.send_header("Location", listener.redirect_to)
                    self.end_headers()
                    return
                self.send_response(200)
                self.send_header("Content-Type", "image/png")
                self.send_header("Content-Length", str(len(PNG)))
                self.end_headers()
                self.wfile.write(PNG)

            def log_message(self, *args: object) -> None:
                pass

        self._httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.port = self._httpd.server_address[1]
        threading.Thread(target=self._httpd.serve_forever, args=(0.05,), daemon=True).start()

    def close(self) -> None:
        self._httpd.shutdown()
        self._httpd.server_close()


@pytest.fixture
def image_listener():
    listener = _ImageListener()
    yield listener
    listener.close()


def _public_then_loopback(monkeypatch, name: str) -> tuple[list[str], list[str]]:
    """Answer ``name`` with a public address once, then loopback; record connects.

    Connections to the public address are recorded and refused, so the test
    never leaves the machine.
    """
    import socket

    import httpcore

    real = socket.getaddrinfo
    lookups: list[str] = []
    connected: list[str] = []

    def resolve(host, port, *args, **kwargs):
        if host == name:
            lookups.append(host)
            ip = "93.184.216.34" if len(lookups) == 1 else "127.0.0.1"
            return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (ip, port))]
        return real(host, port, *args, **kwargs)

    real_connect = httpcore.AnyIOBackend.connect_tcp

    async def connect(self, host, port, *args, **kwargs):
        connected.append(host)
        if host == "93.184.216.34":
            raise httpcore.ConnectError("unreachable in tests")
        return await real_connect(self, host, port, *args, **kwargs)

    monkeypatch.setattr(socket, "getaddrinfo", resolve)
    monkeypatch.setattr(httpcore.AnyIOBackend, "connect_tcp", connect)
    return lookups, connected


def test_wallpaper_fetch_keeps_the_checked_address(monkeypatch, image_listener) -> None:
    """The name is looked up once and the connection goes to that address."""
    import asyncio

    lookups, connected = _public_then_loopback(monkeypatch, "wallpapers.example.com")

    with pytest.raises(BackgroundImageError):
        asyncio.run(fetch_image_url(f"http://wallpapers.example.com:{image_listener.port}/a.png"))

    assert lookups == ["wallpapers.example.com"]
    assert connected == ["93.184.216.34"]
    assert image_listener.hits == []


@pytest.mark.parametrize("host", ["127.0.0.1", "127.1", "localhost", "[::ffff:127.0.0.1]", "minio"])
def test_wallpaper_fetch_keeps_to_public_addresses(image_listener, host: str) -> None:
    import asyncio

    with pytest.raises(BackgroundImageError):
        asyncio.run(fetch_image_url(f"http://{host}:{image_listener.port}/a.png"))
    assert image_listener.hits == []


def test_wallpaper_fetch_keeps_redirects_to_public_addresses(monkeypatch, image_listener) -> None:
    import asyncio
    import socket

    import httpcore

    real = socket.getaddrinfo
    real_connect = httpcore.AnyIOBackend.connect_tcp

    def resolve(host, port, *args, **kwargs):
        if host == "wallpapers.example.com":
            return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", port))]
        return real(host, port, *args, **kwargs)

    async def connect(self, host, port, *args, **kwargs):
        target = "127.0.0.1" if host == "93.184.216.34" else host
        return await real_connect(self, target, port, *args, **kwargs)

    monkeypatch.setattr(socket, "getaddrinfo", resolve)
    monkeypatch.setattr(httpcore.AnyIOBackend, "connect_tcp", connect)
    image_listener.redirect_to = f"http://127.0.0.1:{image_listener.port}/internal.png"

    with pytest.raises(BackgroundImageError):
        asyncio.run(
            fetch_image_url(f"http://wallpapers.example.com:{image_listener.port}/redirect")
        )
    assert image_listener.hits == ["/redirect"]

    # The same public host serving the image directly is still fetched.
    assert (
        asyncio.run(fetch_image_url(f"http://wallpapers.example.com:{image_listener.port}/a.png"))
        == PNG
    )


@pytest.mark.parametrize(
    ("url", "message"),
    [
        ("ftp://example.com/a.png", "Only http"),
        ("http://[::1/a.png", "Only http"),
        ("http://127.0.0.1/a.png", "private or local"),
        ("http://minio:9000/abi/a.png", "private or local"),
    ],
)
def test_wallpaper_url_check_keeps_non_public_targets_out(url: str, message: str) -> None:
    with pytest.raises(BackgroundImageError, match=message):
        ensure_public_http_url(url)


def test_wallpaper_url_check_keeps_public_addresses_in(monkeypatch) -> None:
    import socket

    monkeypatch.setattr(
        socket,
        "getaddrinfo",
        lambda *a, **k: [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443))],
    )
    ensure_public_http_url("https://example.com/a.png")
