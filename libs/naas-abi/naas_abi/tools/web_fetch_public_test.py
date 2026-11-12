"""web_fetch and the Slides fetchers reach public addresses only.

A listener on 127.0.0.1 stands for a service on the platform's own network.
"public.example.com" resolves to a public address; its connections are routed
to the listener so a redirect from a public page can be followed.
"""

from __future__ import annotations

import socket
import struct
import threading
import zlib
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import httpcore
import pytest

from naas_abi.tools import slides_tools, web_tools

LOOPBACK = "127.0.0.1"
PUBLIC = "93.184.216.34"
PUBLIC_NAME = "public.example.com"
BODY = "listener body 7d1f"


def _png(width: int = 800, height: int = 600) -> bytes:
    def chunk(kind: bytes, data: bytes) -> bytes:
        crc = zlib.crc32(kind + data) & 0xFFFFFFFF
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", crc)

    raw = b"".join(b"\x00" + b"\x00" * width for _ in range(height))
    header = struct.pack(">IIBBBBB", width, height, 8, 0, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", header)
        + chunk(b"IDAT", zlib.compress(raw))
        + chunk(b"IEND", b"")
    )


class _Listener:
    def __init__(self) -> None:
        self.hits: list[str] = []
        self.redirect_to = ""
        listener = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:
                listener.hits.append(self.path)
                if self.path.startswith("/redirect"):
                    self.send_response(302)
                    self.send_header("Location", listener.redirect_to)
                    self.end_headers()
                    return
                if self.path.startswith("/img"):
                    body, kind = _png(), "image/png"
                else:
                    body, kind = f"<p>{BODY}</p>".encode(), "text/html"
                self.send_response(200)
                self.send_header("Content-Type", kind)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *args: object) -> None:
                pass

        self._httpd = ThreadingHTTPServer((LOOPBACK, 0), Handler)
        self.port = self._httpd.server_address[1]
        threading.Thread(
            target=self._httpd.serve_forever, args=(0.05,), daemon=True
        ).start()

    def close(self) -> None:
        self._httpd.shutdown()
        self._httpd.server_close()


@pytest.fixture
def listener(monkeypatch: pytest.MonkeyPatch) -> Iterator[_Listener]:
    """The listener, plus a resolver that knows the service and public names."""
    real_resolve = socket.getaddrinfo
    real_connect = httpcore.SyncBackend.connect_tcp

    def resolve(host, port, *args, **kwargs):  # type: ignore[no-untyped-def]
        if host == PUBLIC_NAME:
            return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (PUBLIC, port))]
        if host in ("fuseki", "fuseki.example.com"):
            host = LOOPBACK
        return real_resolve(host, port, *args, **kwargs)

    def connect(self, host, port, *args, **kwargs):  # type: ignore[no-untyped-def]
        return real_connect(
            self, LOOPBACK if host == PUBLIC else host, port, *args, **kwargs
        )

    monkeypatch.setattr(socket, "getaddrinfo", resolve)
    monkeypatch.setattr(httpcore.SyncBackend, "connect_tcp", connect)
    web_tools.reset_web_tool_turn()
    srv = _Listener()
    yield srv
    srv.close()


_INTERNAL_HOSTS = [
    "127.0.0.1",
    "127.1",
    "2130706433",
    "0x7f000001",
    "localhost.",
    "[::ffff:127.0.0.1]",
    "fuseki",
    "fuseki.example.com",
]


@pytest.mark.parametrize("host", _INTERNAL_HOSTS)
def test_web_fetch_keeps_to_public_addresses(listener: _Listener, host: str) -> None:
    result = web_tools.make_web_fetch_tool().invoke(
        {"url": f"http://{host}:{listener.port}/secret"}
    )
    assert BODY not in result
    assert result.startswith("Error")
    assert listener.hits == []


def test_web_fetch_keeps_redirects_to_public_addresses(listener: _Listener) -> None:
    listener.redirect_to = f"http://{LOOPBACK}:{listener.port}/secret"
    result = web_tools.make_web_fetch_tool().invoke(
        {"url": f"http://{PUBLIC_NAME}:{listener.port}/redirect"}
    )
    assert BODY not in result
    assert listener.hits == ["/redirect"]


def test_web_fetch_still_reads_public_pages(listener: _Listener) -> None:
    result = web_tools.make_web_fetch_tool().invoke(
        {"url": f"http://{PUBLIC_NAME}:{listener.port}/page"}
    )
    assert BODY in result


@pytest.mark.parametrize("host", _INTERNAL_HOSTS)
def test_slides_image_fetch_keeps_to_public_addresses(
    listener: _Listener, host: str
) -> None:
    result = slides_tools._download_remote_image(
        f"http://{host}:{listener.port}/img.png"
    )
    assert "bytes" not in result
    assert "error" in result
    assert listener.hits == []


def test_slides_image_fetch_keeps_redirects_to_public_addresses(
    listener: _Listener,
) -> None:
    listener.redirect_to = f"http://{LOOPBACK}:{listener.port}/img.png"
    result = slides_tools._download_remote_image(
        f"http://{PUBLIC_NAME}:{listener.port}/redirect"
    )
    assert "bytes" not in result
    assert listener.hits == ["/redirect"]


def test_slides_image_fetch_keeps_redirects_on_http(listener: _Listener) -> None:
    ftp = socket.socket()
    ftp.bind((LOOPBACK, 0))
    ftp.listen(1)
    ftp.settimeout(0.5)
    listener.redirect_to = f"ftp://{LOOPBACK}:{ftp.getsockname()[1]}/x.png"
    try:
        result = slides_tools._download_remote_image(
            f"http://{PUBLIC_NAME}:{listener.port}/redirect"
        )
        assert "error" in result
        with pytest.raises(OSError):
            ftp.accept()
    finally:
        ftp.close()


def test_slides_image_fetch_still_reads_public_images(listener: _Listener) -> None:
    result = slides_tools._download_remote_image(
        f"http://{PUBLIC_NAME}:{listener.port}/img.png"
    )
    assert result.get("media_type") == "image/png", result
    assert result["bytes"].startswith(b"\x89PNG")


@pytest.mark.parametrize("host", _INTERNAL_HOSTS)
def test_slides_profile_fetch_keeps_to_public_addresses(
    listener: _Listener, host: str
) -> None:
    result = slides_tools._fetch_public_profile_page(
        f"http://{host}:{listener.port}/profile"
    )
    assert "html" not in result
    assert listener.hits == []


def test_slides_profile_fetch_keeps_redirects_to_public_addresses(
    listener: _Listener,
) -> None:
    listener.redirect_to = f"http://localhost:{listener.port}/profile"
    result = slides_tools._fetch_public_profile_page(
        f"http://{PUBLIC_NAME}:{listener.port}/redirect"
    )
    assert "html" not in result
    assert listener.hits == ["/redirect"]
