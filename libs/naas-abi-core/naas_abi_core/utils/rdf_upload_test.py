"""Uploaded RDF is parsed as data: no remote documents, no network, a time limit."""

from __future__ import annotations

import json
import socket
import subprocess
import sys
import threading
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from naas_abi_core.utils import rdf_upload
from naas_abi_core.utils.rdf_upload import RdfUploadError, parse_upload


class _Listener:
    def __init__(self) -> None:
        self.hits: list[str] = []
        listener = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:
                listener.hits.append(self.path)
                body = json.dumps(
                    {"@context": {"name": "http://schema.org/name"}}
                ).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/ld+json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *args: object) -> None:
                pass

        self._httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.port = self._httpd.server_address[1]
        threading.Thread(
            target=self._httpd.serve_forever, args=(0.05,), daemon=True
        ).start()

    def close(self) -> None:
        self._httpd.shutdown()
        self._httpd.server_close()


@pytest.fixture
def listener() -> Iterator[_Listener]:
    srv = _Listener()
    yield srv
    srv.close()


def _jsonld(context: object, **extra: object) -> bytes:
    return json.dumps(
        {"@context": context, "@id": "urn:a", "name": "x", **extra}
    ).encode()


def test_rdf_upload_keeps_json_ld_to_embedded_contexts(listener: _Listener) -> None:
    url = f"http://127.0.0.1:{listener.port}/ctx"
    refused = [
        _jsonld(url),
        _jsonld([url, {"name": "http://schema.org/name"}]),
        _jsonld("file:///etc/hostname"),
        _jsonld({"@import": url, "name": "http://schema.org/name"}),
        _jsonld(
            {"name": {"@id": "http://schema.org/name", "@context": url}},
        ),
        json.dumps(
            [
                {
                    "@context": {},
                    "@id": "urn:a",
                    "urn:p": {"@context": url, "@id": "urn:b"},
                }
            ]
        ).encode(),
    ]
    for document in refused:
        with pytest.raises(RdfUploadError) as info:
            parse_upload(document, "json-ld", timeout=30)
        assert str(info.value) == rdf_upload.EMBEDDED_CONTEXTS_ONLY
    assert listener.hits == []


def test_rdf_upload_still_reads_embedded_json_ld() -> None:
    graph = parse_upload(
        _jsonld({"name": "http://schema.org/name"}), "json-ld", timeout=30
    )
    assert len(graph) == 1


@pytest.mark.parametrize(
    ("content", "fmt"),
    [
        (b"<urn:a> <urn:p> <urn:b> .\n", "nt"),
        (b"@prefix ex: <urn:ex:> . ex:a ex:p ex:b , ex:c .", "turtle"),
        (
            (
                b'<?xml version="1.0"?><rdf:RDF'
                b' xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"'
                b' xmlns:ex="urn:ex:"><rdf:Description rdf:about="urn:ex:a"><ex:p>v</ex:p>'
                b"</rdf:Description></rdf:RDF>"
            ),
            "xml",
        ),
    ],
)
def test_rdf_upload_still_reads_rdf_formats(content: bytes, fmt: str) -> None:
    assert len(parse_upload(content, fmt, timeout=30)) >= 1


def test_rdf_upload_keeps_messages_fixed() -> None:
    with pytest.raises(RdfUploadError) as info:
        parse_upload(b"<not turtle", "turtle", timeout=30)
    assert str(info.value) == rdf_upload.NOT_PARSED
    with pytest.raises(RdfUploadError) as info:
        parse_upload(b"{", "json-ld", timeout=30)
    assert str(info.value) == rdf_upload.NOT_JSON_LD
    with pytest.raises(RdfUploadError):
        parse_upload(b"", "trig", timeout=30)


def test_rdf_upload_keeps_to_its_time_limit() -> None:
    with pytest.raises(RdfUploadError) as info:
        parse_upload(b"<urn:a> <urn:p> <urn:b> .\n", "nt", timeout=0.001)
    assert str(info.value) == rdf_upload.TOO_SLOW


def test_rdf_upload_parser_keeps_off_the_network(listener: _Listener) -> None:
    """The child that parses an upload refuses every connection it would open."""
    code = (
        "import socket, sys\n"
        "from naas_abi_core.utils import rdf_upload\n"
        "sys.addaudithook(rdf_upload._no_network)\n"
        "try:\n"
        f"    socket.create_connection(('127.0.0.1', {listener.port}), timeout=2)\n"
        "except PermissionError:\n"
        "    sys.exit(7)\n"
        "sys.exit(0)\n"
    )
    done = subprocess.run(  # nosec B603 - fixed argv
        [sys.executable, "-c", code], capture_output=True, timeout=60, check=False
    )
    assert done.returncode == 7, done.stderr
    assert listener.hits == []
    # The listener itself is reachable from here: the hook is what refused it.
    with socket.create_connection(("127.0.0.1", listener.port), timeout=2):
        pass


@pytest.mark.parametrize(
    ("name", "fmt"),
    [
        ("a.ttl", "turtle"),
        ("A.OWL", "xml"),
        ("a.rdf", "xml"),
        ("a.nt", "nt"),
        ("a.n3", "n3"),
        ("a.jsonld", "json-ld"),
        ("a.json", "json-ld"),
        ("a", "turtle"),
    ],
)
def test_rdf_upload_keeps_the_format_of_the_file_name(name: str, fmt: str) -> None:
    assert rdf_upload.format_for_filename(name) == fmt


def test_rdf_upload_keeps_concurrent_parses_bounded(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """With every slot taken, a parse waits within its timeout, then gives up."""
    monkeypatch.setattr(rdf_upload, "_SLOTS", threading.BoundedSemaphore(1))
    assert rdf_upload._SLOTS.acquire(blocking=False)
    try:
        with pytest.raises(RdfUploadError) as info:
            parse_upload(b"<urn:a> <urn:p> <urn:b> .\n", "nt", timeout=0.3)
        assert str(info.value) == rdf_upload.TOO_SLOW
    finally:
        rdf_upload._SLOTS.release()


@pytest.mark.skipif(sys.platform != "linux", reason="RLIMIT_AS is enforced on Linux")
def test_rdf_upload_parser_keeps_within_its_memory_limit() -> None:
    code = (
        "import sys\n"
        "from naas_abi_core.utils import rdf_upload\n"
        "rdf_upload._limit_memory()\n"
        "try:\n"
        "    block = bytearray(rdf_upload.MAX_CHILD_MEMORY_BYTES + 1)\n"
        "except MemoryError:\n"
        "    sys.exit(7)\n"
        "sys.exit(0)\n"
    )
    done = subprocess.run(  # nosec B603 - fixed argv
        [sys.executable, "-c", code], capture_output=True, timeout=60, check=False
    )
    assert done.returncode == 7, done.stderr


def test_rdf_upload_keeps_what_the_parent_reads_bounded() -> None:
    three = b"<urn:a> <urn:p> <urn:b> .\n<urn:a> <urn:p> <urn:c> .\n<urn:a> <urn:p> <urn:d> .\n"
    with pytest.raises(RdfUploadError) as info:
        parse_upload(three, "nt", timeout=30, max_triples=2)
    assert str(info.value) == rdf_upload.TOO_LARGE
    with pytest.raises(RdfUploadError) as info:
        parse_upload(three, "nt", timeout=30, max_output_bytes=40)
    assert str(info.value) == rdf_upload.TOO_LARGE
    assert len(parse_upload(three, "nt", timeout=30, max_triples=3)) == 3
