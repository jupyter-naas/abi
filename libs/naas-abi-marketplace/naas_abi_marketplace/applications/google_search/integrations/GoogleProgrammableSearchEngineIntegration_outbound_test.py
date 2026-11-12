"""googlesearch_extract_content_from_url reads public pages only, and keeps none.

A listener on 127.0.0.1 stands for a service on the platform's own network.
"public.example.com" resolves to a public address; its connections are routed
to the listener so a redirect from a public page can be followed.
"""

from __future__ import annotations

import socket
import threading
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from types import SimpleNamespace
from typing import Any

import httpcore
import pytest

LOOPBACK = "127.0.0.1"
PUBLIC = "93.184.216.34"
PUBLIC_NAME = "public.example.com"
SECRET = "listener-token-91c2"


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
                body = f"<html><body><p>token={SECRET}</p></body></html>".encode()
                self.send_response(200)
                self.send_header("Content-Type", "text/html")
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
    real_resolve = socket.getaddrinfo
    real_connect = httpcore.SyncBackend.connect_tcp

    def resolve(host, port, *args, **kwargs):  # type: ignore[no-untyped-def]
        if host == PUBLIC_NAME:
            return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (PUBLIC, port))]
        return real_resolve(host, port, *args, **kwargs)

    def connect(self, host, port, *args, **kwargs):  # type: ignore[no-untyped-def]
        return real_connect(
            self, LOOPBACK if host == PUBLIC else host, port, *args, **kwargs
        )

    monkeypatch.setattr(socket, "getaddrinfo", resolve)
    monkeypatch.setattr(httpcore.SyncBackend, "connect_tcp", connect)
    srv = _Listener()
    yield srv
    srv.close()


@pytest.fixture
def extract(monkeypatch: pytest.MonkeyPatch, tmp_path) -> tuple[Any, list[tuple]]:
    """The tool as the agents build it, with object storage recorded."""
    monkeypatch.chdir(tmp_path)
    import naas_abi_marketplace.applications.google_search as package
    from naas_abi_marketplace.applications.google_search.integrations.GoogleProgrammableSearchEngineIntegration import (
        GoogleProgrammableSearchEngineIntegrationConfiguration,
        as_tools,
    )

    stored: list[tuple] = []
    storage = SimpleNamespace(
        put_object=lambda *a, **k: stored.append(a),
        get_object=lambda *a, **k: b"",
    )
    module = SimpleNamespace(
        engine=SimpleNamespace(services=SimpleNamespace(object_storage=storage)),
        configuration=SimpleNamespace(datastore_path="google_search"),
    )
    monkeypatch.setattr(
        package.ABIModule, "get_instance", classmethod(lambda cls: module)
    )
    tools = as_tools(
        GoogleProgrammableSearchEngineIntegrationConfiguration(
            api_key="k", search_engine_id="cx"
        )
    )
    tool = next(t for t in tools if t.name == "googlesearch_extract_content_from_url")
    return tool, stored


def _invoke(tool: Any, url: str) -> str:
    try:
        return str(tool.invoke({"url": url}))
    except Exception as exc:  # noqa: BLE001 - a refusal may surface as an exception
        return f"refused: {exc}"


@pytest.mark.parametrize("host", ["127.0.0.1", "127.1", "localhost", "fuseki"])
def test_googlesearch_extract_content_keeps_to_public_addresses(
    listener: _Listener, extract: tuple[Any, list[tuple]], host: str
) -> None:
    tool, stored = extract
    out = _invoke(tool, f"http://{host}:{listener.port}/admin")
    assert SECRET not in out
    assert listener.hits == []
    assert stored == []


def test_googlesearch_extract_content_keeps_redirects_to_public_addresses(
    listener: _Listener, extract: tuple[Any, list[tuple]]
) -> None:
    tool, _ = extract
    listener.redirect_to = f"http://{LOOPBACK}:{listener.port}/admin"
    out = _invoke(tool, f"http://{PUBLIC_NAME}:{listener.port}/redirect")
    assert SECRET not in out
    assert listener.hits == ["/redirect"]


def test_googlesearch_extract_content_keeps_no_copy_of_public_pages(
    listener: _Listener, extract: tuple[Any, list[tuple]]
) -> None:
    tool, stored = extract
    out = _invoke(tool, f"http://{PUBLIC_NAME}:{listener.port}/page")
    assert SECRET in out
    assert stored == []
