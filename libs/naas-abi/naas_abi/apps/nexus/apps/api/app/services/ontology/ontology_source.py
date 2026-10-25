"""Where an ontology's text comes from: a file of this engine, or a remote module.

An ontology is addressed by one string, its ``path``. For an in-engine module it
is a file on disk. For a remote module (``naas-abi-sdk``, over NATS) it is the id
``module/<module_id>/<path relative to ontologies/>``, the key the engine's
triple store gave the file when the module pushed it. The text of a remote file
lives only in the engine's schema graph, as base64 ``internal:content``; it is
never opened as a file, whatever the id looks like.
"""

from __future__ import annotations

import base64
import hashlib
import io
import threading
import time
from collections import OrderedDict
from collections.abc import Callable
from typing import Protocol

from naas_abi.apps.nexus.apps.api.app.services.ontology.ontology__schema import (
    OntologyPathNotFoundError,
)
from rdflib import Graph

REMOTE_PREFIX = "module/"
SCHEMA_GRAPH = "http://ontology.naas.ai/graph/schema"
_INTERNAL = "http://triple-store.internal#"
# Relative IRIs in a remote file resolve against this, as at load time.
_BASE = "http://ontology.naas.ai/"

DEFAULT_TTL_SECONDS = 30.0
DEFAULT_MAX_ENTRIES = 64


class _Queryable(Protocol):
    def query(self, query: str): ...


def is_remote_id(path: str) -> bool:
    """True for anything shaped like a remote id: it is never a disk path."""
    return path.startswith(REMOTE_PREFIX)


def parse_remote_id(path: str) -> tuple[str, str] | None:
    """``(module_id, relative path)`` of a well-formed remote id, else None.

    Rejects traversal (``..``, ``.``, empty segments), backslashes and control
    characters, so an id can neither name another store entry by accident nor be
    mistaken for a path outside ``ontologies/``.
    """
    if not is_remote_id(path):
        return None
    rest = path[len(REMOTE_PREFIX) :]
    if "\\" in rest or any(ord(char) < 32 or ord(char) == 127 for char in rest):
        return None
    parts = rest.split("/")
    if len(parts) < 2 or any(part in ("", ".", "..") for part in parts):
        return None
    return parts[0], "/".join(parts[1:])


def _literal(value: str) -> str:
    return (
        value.replace("\\", "\\\\")
        .replace('"', '\\"')
        .replace("\n", "\\n")
        .replace("\r", "\\r")
    )


def parse_remote_graph(path: str, text: str) -> Graph:
    return Graph().parse(io.StringIO(text), format="turtle", publicID=_BASE + path)


def content_version(text: str) -> tuple[int, int]:
    """A cheap change token for ``text``: (hash prefix, length)."""
    return int(hashlib.sha256(text.encode("utf-8")).hexdigest()[:15], 16), len(text)


class RemoteOntologyReader:
    """Reads remote ontologies from the engine's schema graph.

    The listing and each file's text are cached briefly and the cache is
    bounded, so a page that asks for the same ontology many times does not query
    the triple store each time, and a change a module pushes shows within
    ``ttl_seconds``.
    """

    def __init__(
        self,
        triple_store_getter: Callable[[], _Queryable],
        ttl_seconds: float = DEFAULT_TTL_SECONDS,
        max_entries: int = DEFAULT_MAX_ENTRIES,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._triple_store_getter = triple_store_getter
        self._ttl = ttl_seconds
        self._max_entries = max_entries
        self._clock = clock
        self._lock = threading.Lock()
        self._sources: tuple[float, list[str]] | None = None
        self._files: tuple[float, list[tuple[str, str]]] | None = None
        self._texts: OrderedDict[str, tuple[float, str]] = OrderedDict()

    def clear(self) -> None:
        with self._lock:
            self._sources = None
            self._files = None
            self._texts.clear()

    def sources(self) -> list[str]:
        """Well-formed remote ids in the schema graph, sorted."""
        now = self._clock()
        with self._lock:
            if self._sources and now - self._sources[0] < self._ttl:
                return list(self._sources[1])
        rows = self._triple_store_getter().query(
            f"""
            PREFIX internal: <{_INTERNAL}>
            SELECT DISTINCT ?filePath WHERE {{
                GRAPH <{SCHEMA_GRAPH}> {{
                    ?schema a internal:Schema ;
                        internal:filePath ?filePath .
                    FILTER(STRSTARTS(STR(?filePath), "{REMOTE_PREFIX}"))
                }}
            }}
            """
        )
        found = sorted(
            {str(row[0]) for row in rows if parse_remote_id(str(row[0])) is not None}
        )
        with self._lock:
            self._sources = (now, found)
        return list(found)

    def files(self) -> list[tuple[str, str]]:
        """``(remote id, Turtle text)`` of every well-formed remote ontology, sorted,
        from one query: a listing reads them all, and asking for each text would
        cost one query per file."""
        now = self._clock()
        with self._lock:
            if self._files and now - self._files[0] < self._ttl:
                return list(self._files[1])
        rows = self._triple_store_getter().query(
            f"""
            PREFIX internal: <{_INTERNAL}>
            SELECT ?filePath ?content WHERE {{
                GRAPH <{SCHEMA_GRAPH}> {{
                    ?schema a internal:Schema ;
                        internal:filePath ?filePath ;
                        internal:content ?content .
                    FILTER(STRSTARTS(STR(?filePath), "{REMOTE_PREFIX}"))
                }}
            }}
            """
        )
        found: dict[str, str] = {}
        for row in rows:
            path = str(row[0])
            if parse_remote_id(path) is None or path in found:
                continue
            found[path] = base64.b64decode(str(row[1])).decode("utf-8")
        listing = sorted(found.items())
        with self._lock:
            self._files = (now, listing)
        return list(listing)

    def read(self, path: str) -> str:
        """The Turtle text stored for remote id ``path``.

        Raises ``OntologyPathNotFoundError`` for a malformed id or one the schema
        graph does not hold. Never touches the filesystem.
        """
        if parse_remote_id(path) is None:
            raise OntologyPathNotFoundError(f"Ontology path not found: {path}")
        now = self._clock()
        with self._lock:
            cached = self._texts.get(path)
            if cached and now - cached[0] < self._ttl:
                self._texts.move_to_end(path)
                return cached[1]
        rows = self._triple_store_getter().query(
            f"""
            PREFIX internal: <{_INTERNAL}>
            SELECT ?content WHERE {{
                GRAPH <{SCHEMA_GRAPH}> {{
                    ?schema a internal:Schema ;
                        internal:filePath "{_literal(path)}" ;
                        internal:content ?content .
                }}
            }}
            """
        )
        encoded = next((str(row[0]) for row in rows), None)
        if encoded is None:
            raise OntologyPathNotFoundError(f"Ontology path not found: {path}")
        text = base64.b64decode(encoded).decode("utf-8")
        with self._lock:
            self._texts[path] = (now, text)
            self._texts.move_to_end(path)
            while len(self._texts) > self._max_entries:
                self._texts.popitem(last=False)
        return text


# The reader the module-level graph loaders use. OntologyService installs its
# own: there is one engine per process, and the loaders are plain functions.
_reader: RemoteOntologyReader | None = None


def install_reader(reader: RemoteOntologyReader | None) -> None:
    global _reader
    _reader = reader


def active_reader() -> RemoteOntologyReader:
    if _reader is None:
        raise OntologyPathNotFoundError("Remote ontologies are not available")
    return _reader


def load_remote_graph(path: str) -> Graph:
    """Graph of remote id ``path``, parsed from the schema graph's content."""
    return parse_remote_graph(path, active_reader().read(path))
