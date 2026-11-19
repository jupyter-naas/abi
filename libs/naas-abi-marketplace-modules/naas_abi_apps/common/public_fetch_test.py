"""fetch_public reaches public addresses only, on every hop.

A listener on 127.0.0.1 stands for a service on the module's own network.
"public.example.com" resolves to a public address; its connections are routed
to the listener so a redirect from a public page can be followed.
"""

from __future__ import annotations

import asyncio
import socket
import threading
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import httpcore
import pytest
from naas_abi_apps.common.public_fetch import (
    FetchRefused,
    check_url,
    fetch_public,
    is_public_address,
)

LOOPBACK = "127.0.0.1"
PUBLIC = "93.184.216.34"
PUBLIC_NAME = "public.example.com"
TOKEN = "listener-token-91c2"


class Listener:
    def __init__(self) -> None:
        self.hits: list[str] = []
        self.redirect_to = ""
        self.body = f"<html><body><p>token={TOKEN}</p></body></html>".encode()
        listener = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:
                listener.hits.append(self.path)
                if self.path.startswith("/redirect"):
                    self.send_response(302)
                    self.send_header("Location", listener.redirect_to)
                    self.end_headers()
                    return
                self.send_response(200)
                self.send_header("Content-Type", "text/html")
                self.send_header("Content-Length", str(len(listener.body)))
                self.end_headers()
                self.wfile.write(listener.body)

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
def listener(monkeypatch: pytest.MonkeyPatch) -> Iterator[Listener]:
    real_resolve = socket.getaddrinfo
    real_connect = httpcore.AnyIOBackend.connect_tcp

    def resolve(host, port, *args, **kwargs):  # type: ignore[no-untyped-def]
        if host == PUBLIC_NAME:
            return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (PUBLIC, port))]
        return real_resolve(host, port, *args, **kwargs)

    async def connect(self, host, port, *args, **kwargs):  # type: ignore[no-untyped-def]
        return await real_connect(
            self, LOOPBACK if host == PUBLIC else host, port, *args, **kwargs
        )

    monkeypatch.setattr(socket, "getaddrinfo", resolve)
    monkeypatch.setattr(httpcore.AnyIOBackend, "connect_tcp", connect)
    server = Listener()
    yield server
    server.close()


@pytest.mark.parametrize(
    "address",
    [
        "127.0.0.1",
        "10.0.0.1",
        "169.254.169.254",
        "100.64.0.1",
        "0.0.0.0",
        "224.0.0.1",
        "::1",
        "::ffff:127.0.0.1",
        "64:ff9b::a00:1",
        "fe80::1",
    ],
)
def test_addresses_off_the_public_internet_are_not_public(address: str) -> None:
    assert not is_public_address(address)


def test_a_public_address_is_public() -> None:
    assert is_public_address(PUBLIC)


@pytest.mark.parametrize(
    "url",
    [
        "file:///etc/passwd",
        "ftp://public.example.com/x",
        "http://localhost/x",
        "http://fuseki:3030/x",
        "http://metadata.google.internal/x",
        "http://[::1]/x",
        "http:///x",
    ],
)
def test_check_url_keeps_to_public_http_urls(url: str) -> None:
    with pytest.raises(FetchRefused):
        check_url(url)


@pytest.mark.parametrize("host", ["127.0.0.1", "127.1", "localhost", "fuseki"])
def test_fetch_public_keeps_to_public_addresses(listener: Listener, host: str) -> None:
    with pytest.raises(FetchRefused):
        asyncio.run(fetch_public(f"http://{host}:{listener.port}/admin"))
    assert listener.hits == []


def test_fetch_public_keeps_redirects_to_public_addresses(listener: Listener) -> None:
    listener.redirect_to = f"http://{LOOPBACK}:{listener.port}/admin"

    with pytest.raises(FetchRefused):
        asyncio.run(fetch_public(f"http://{PUBLIC_NAME}:{listener.port}/redirect"))
    assert listener.hits == ["/redirect"]


def test_fetch_public_keeps_names_that_resolve_privately_out(
    listener: Listener, monkeypatch: pytest.MonkeyPatch
) -> None:
    def resolve(host, port, *args, **kwargs):  # type: ignore[no-untyped-def]
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (LOOPBACK, port))]

    monkeypatch.setattr(socket, "getaddrinfo", resolve)

    with pytest.raises(FetchRefused):
        asyncio.run(fetch_public(f"http://inside.example.com:{listener.port}/admin"))
    assert listener.hits == []


def test_fetch_public_reads_public_pages_up_to_its_cap(listener: Listener) -> None:
    page = asyncio.run(fetch_public(f"http://{PUBLIC_NAME}:{listener.port}/page"))
    assert TOKEN in page.text and not page.truncated

    capped = asyncio.run(
        fetch_public(f"http://{PUBLIC_NAME}:{listener.port}/page", max_bytes=10)
    )
    assert capped.content == listener.body[:10] and capped.truncated
