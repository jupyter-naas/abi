"""chatgpt_analyze_pdf reads PDFs from public addresses only, and keeps no copy.

A listener on 127.0.0.1 stands for a service on the platform's own network and
serves a PDF. "public.example.com" resolves to a public address; its
connections are routed to the listener. The provider endpoint is a local
stand-in that echoes the text it is sent.
"""

from __future__ import annotations

import json
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
SECRET = "LISTENER-PDF-4417"


def _pdf_with_text(text: str) -> bytes:
    stream = f"BT /F1 12 Tf 20 100 Td ({text}) Tj ET".encode()
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        (
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 300 200] "
            b"/Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>"
        ),
        b"<< /Length "
        + str(len(stream)).encode()
        + b" >>\nstream\n"
        + stream
        + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for number, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{number} 0 obj\n".encode() + body + b"\nendobj\n"
    xref = len(out)
    out += f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode()
    for offset in offsets:
        out += f"{offset:010d} 00000 n \n".encode()
    out += (
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
        f"startxref\n{xref}\n%%EOF\n"
    ).encode()
    return bytes(out)


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
                body = _pdf_with_text(SECRET)
                self.send_response(200)
                self.send_header("Content-Type", "application/pdf")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def do_POST(self) -> None:
                payload = json.loads(
                    self.rfile.read(int(self.headers["Content-Length"]))
                )
                texts = [
                    part.get("text", "")
                    for message in payload.get("input", [])
                    if isinstance(message.get("content"), list)
                    for part in message["content"]
                ]
                answer = {
                    "output": [
                        {
                            "type": "message",
                            "content": [
                                {"type": "output_text", "text": " ".join(texts)}
                            ],
                        }
                    ]
                }
                body = json.dumps(answer).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
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
def analyze(
    monkeypatch: pytest.MonkeyPatch, tmp_path, listener: _Listener
) -> tuple[Any, list[tuple]]:
    """The tool as the agent builds it; object storage writes are recorded."""
    monkeypatch.chdir(tmp_path)
    import naas_abi_marketplace.ai.chatgpt as package
    from naas_abi_marketplace.ai.chatgpt.integrations.OpenAIResponsesIntegration import (
        OpenAIResponsesIntegrationConfiguration,
        as_tools,
    )

    stored: list[tuple] = []
    storage = SimpleNamespace(
        put_object=lambda *a, **k: stored.append(a),
        get_object=lambda *a, **k: b"",
    )
    module = SimpleNamespace(
        engine=SimpleNamespace(services=SimpleNamespace(object_storage=storage)),
        configuration=SimpleNamespace(datastore_path="chatgpt"),
    )
    monkeypatch.setattr(
        package.ABIModule, "get_instance", classmethod(lambda cls: module)
    )
    tools = as_tools(
        OpenAIResponsesIntegrationConfiguration(
            api_key="sk-test", base_url=f"http://{LOOPBACK}:{listener.port}/v1"
        )
    )
    tool = next(t for t in tools if t.name == "chatgpt_analyze_pdf")
    return tool, stored


def _invoke(tool: Any, url: str) -> str:
    try:
        return str(tool.invoke({"pdf_url": url}))
    except Exception as exc:  # noqa: BLE001 - a refusal may surface as an exception
        return f"refused: {exc}"


@pytest.mark.parametrize("host", ["127.0.0.1", "127.1", "localhost", "minio"])
def test_chatgpt_analyze_pdf_keeps_to_public_addresses(
    listener: _Listener, analyze: tuple[Any, list[tuple]], host: str
) -> None:
    tool, stored = analyze
    out = _invoke(tool, f"http://{host}:{listener.port}/report.pdf")
    assert SECRET not in out
    assert listener.hits == []
    assert stored == []


def test_chatgpt_analyze_pdf_keeps_redirects_to_public_addresses(
    listener: _Listener, analyze: tuple[Any, list[tuple]]
) -> None:
    tool, _ = analyze
    listener.redirect_to = f"http://{LOOPBACK}:{listener.port}/report.pdf"
    out = _invoke(tool, f"http://{PUBLIC_NAME}:{listener.port}/redirect")
    assert SECRET not in out
    assert listener.hits == ["/redirect"]


def test_chatgpt_analyze_pdf_keeps_no_copy_of_public_documents(
    listener: _Listener, analyze: tuple[Any, list[tuple]]
) -> None:
    tool, stored = analyze
    out = _invoke(tool, f"http://{PUBLIC_NAME}:{listener.port}/report.pdf")
    assert SECRET in out
    assert stored == []
