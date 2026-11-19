"""Parse an uploaded RDF document in a separate process, with limits.

An upload is data: parsing it must not reach the network, open local files or
hold the caller's process. :func:`parse_upload` runs rdflib in a child Python
process that

- refuses JSON-LD documents that name a context or an import by URL (only
  embedded contexts are read), before rdflib sees them;
- cannot open network connections (an audit hook refuses them);
- is killed when it runs longer than ``timeout``;
- may use ``MAX_CHILD_MEMORY_BYTES`` of address space at most (where the
  platform supports the limit);
- hands back at most ``MAX_TRIPLES`` triples and ``MAX_OUTPUT_BYTES`` of
  N-Triples: what the parent buffers and parses again is bounded too.

At most ``MAX_CONCURRENT_PARSES`` children run at once; further calls wait,
within their own timeout, for a free slot.

The child hands the triples back as N-Triples, which the caller reads in
linear time. Run the call off the event loop (``asyncio.to_thread``).
"""

from __future__ import annotations

import json
import subprocess  # nosec B404 - runs this module with the current interpreter
import sys
import threading
import time
from typing import Any

from rdflib import Graph

FORMATS = frozenset({"turtle", "xml", "nt", "n3", "json-ld"})
DEFAULT_TIMEOUT_SECONDS = 60.0
MAX_CONCURRENT_PARSES = 4
MAX_CHILD_MEMORY_BYTES = 2 * 1024 * 1024 * 1024
_SLOTS = threading.BoundedSemaphore(MAX_CONCURRENT_PARSES)

_EXIT_REFUSED = 3
_EXIT_INVALID = 4

EMBEDDED_CONTEXTS_ONLY = "JSON-LD uploads may only use embedded contexts"
NOT_JSON_LD = "The file is not valid JSON-LD"
UNSUPPORTED_FORMAT = "This RDF format is not supported"
NOT_PARSED = "The file could not be parsed"
TOO_SLOW = "The file took too long to parse"
TOO_LARGE = "The file holds too many triples"
_REFUSALS = frozenset(
    {EMBEDDED_CONTEXTS_ONLY, NOT_JSON_LD, UNSUPPORTED_FORMAT, TOO_LARGE}
)

# What a child may hand back: the parent buffers and parses it again.
MAX_TRIPLES = 1_000_000
MAX_OUTPUT_BYTES = 256 * 1024 * 1024


_FORMATS_BY_EXTENSION = {
    ".ttl": "turtle",
    ".owl": "xml",
    ".rdf": "xml",
    ".xml": "xml",
    ".nt": "nt",
    ".n3": "n3",
    ".jsonld": "json-ld",
    ".json": "json-ld",
}


def format_for_filename(filename: str) -> str:
    """The rdflib format of an upload, from its file name; Turtle by default."""
    name = (filename or "").lower()
    for extension, fmt in _FORMATS_BY_EXTENSION.items():
        if name.endswith(extension):
            return fmt
    return "turtle"


class RdfUploadError(ValueError):
    """The upload was refused or could not be parsed; the message is fixed."""


def _string_reference(value: Any) -> bool:
    if isinstance(value, str):
        return True
    if isinstance(value, list):
        return any(isinstance(item, str) for item in value)
    return False


def refuse_remote_documents(document: Any) -> None:
    """Refuse a JSON-LD document that names a context or an import by URL."""
    stack = [document]
    while stack:
        node = stack.pop()
        if isinstance(node, dict):
            if "@import" in node:
                raise RdfUploadError(EMBEDDED_CONTEXTS_ONLY)
            if "@context" in node and _string_reference(node["@context"]):
                raise RdfUploadError(EMBEDDED_CONTEXTS_ONLY)
            stack.extend(node.values())
        elif isinstance(node, list):
            stack.extend(node)


def _parse_here(content: bytes, fmt: str) -> Graph:
    if fmt not in FORMATS:
        raise RdfUploadError(UNSUPPORTED_FORMAT)
    if fmt == "json-ld":
        try:
            document = json.loads(content)
        except (ValueError, UnicodeDecodeError) as exc:
            raise RdfUploadError(NOT_JSON_LD) from exc
        refuse_remote_documents(document)
    graph = Graph()
    graph.parse(data=content, format=fmt)
    return graph


def parse_upload(
    content: bytes,
    fmt: str,
    *,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
    max_triples: int = MAX_TRIPLES,
    max_output_bytes: int = MAX_OUTPUT_BYTES,
) -> Graph:
    """Parse ``content`` as ``fmt`` in a child process and return its graph.

    Raises :class:`RdfUploadError` when the format is unknown, the document
    is refused, it does not parse, parsing takes longer than ``timeout``, or
    the graph holds more than ``max_triples`` triples or ``max_output_bytes``
    of N-Triples (the child refuses before handing it back).
    """
    if fmt not in FORMATS:
        raise RdfUploadError(UNSUPPORTED_FORMAT)
    deadline = time.monotonic() + timeout
    if not _SLOTS.acquire(timeout=timeout):
        raise RdfUploadError(TOO_SLOW)
    try:
        done = subprocess.run(  # nosec B603 - fixed argv, no shell
            [
                sys.executable,
                "-m",
                __name__,
                fmt,
                str(max_triples),
                str(max_output_bytes),
            ],
            input=content,
            capture_output=True,
            timeout=max(0.0, deadline - time.monotonic()),
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise RdfUploadError(TOO_SLOW) from exc
    finally:
        _SLOTS.release()
    if done.returncode == _EXIT_REFUSED:
        lines = done.stderr.decode("utf-8", errors="replace").strip().splitlines()
        message = lines[-1] if lines else ""
        raise RdfUploadError(message if message in _REFUSALS else NOT_PARSED)
    if done.returncode != 0:
        raise RdfUploadError(NOT_PARSED)
    if len(done.stdout) > max_output_bytes:
        raise RdfUploadError(TOO_LARGE)
    graph = Graph()
    if done.stdout:
        graph.parse(data=done.stdout, format="nt")
    return graph


def _no_network(event: str, _args: tuple[Any, ...]) -> None:
    if event in {"socket.connect", "socket.getaddrinfo", "urllib.Request"}:
        raise PermissionError("an upload parser has no network")


def _limit_memory() -> None:
    try:
        import resource
    except ImportError:  # not on every platform
        return
    try:
        resource.setrlimit(
            resource.RLIMIT_AS, (MAX_CHILD_MEMORY_BYTES, MAX_CHILD_MEMORY_BYTES)
        )
    except (OSError, ValueError):
        pass


def _main(argv: list[str]) -> int:
    sys.addaudithook(_no_network)
    _limit_memory()
    fmt = argv[1] if len(argv) > 1 else ""
    max_triples = int(argv[2]) if len(argv) > 2 else MAX_TRIPLES
    max_output_bytes = int(argv[3]) if len(argv) > 3 else MAX_OUTPUT_BYTES
    content = sys.stdin.buffer.read()
    try:
        graph = _parse_here(content, fmt)
    except RdfUploadError as exc:
        sys.stderr.write(f"\n{exc}\n")
        return _EXIT_REFUSED
    except Exception:  # noqa: BLE001 - the parent reports a fixed message
        return _EXIT_INVALID
    if len(graph) > max_triples:
        sys.stderr.write(f"\n{TOO_LARGE}\n")
        return _EXIT_REFUSED
    output = graph.serialize(format="nt", encoding="utf-8")
    if len(output) > max_output_bytes:
        sys.stderr.write(f"\n{TOO_LARGE}\n")
        return _EXIT_REFUSED
    sys.stdout.buffer.write(output)
    return 0


if __name__ == "__main__":
    sys.exit(_main(sys.argv))
