"""The triple store's named graphs as items: id = the graph IRI.

Wraps the engine's ``TripleStoreService`` (sync, so calls run in a worker
thread) through its public API only: ``list_graphs``, SPARQL ``SELECT`` (the
result form every adapter and the NATS contract carry), ``create_graph``,
``clear_graph``, ``drop_graph`` and ``insert``. A read shows the triple count
and the first triples as Turtle; a download exports the whole graph as Turtle.
Writing Turtle replaces the graph's content (clear, then insert: not atomic) or
creates the graph. The service's own schema graph is read-only: ``load_schema``
and ``remove_schema`` keep its bookkeeping. Stores without named graphs (the
filesystem adapter) list nothing and refuse writes.

Listing filters graph IRIs on the server (``query``) and counts the triples of
the listed page in one grouped SPARQL query (``VALUES`` over the page's graphs).
A read returns a ``triples`` view: the first triples as N-Triples terms, sorted,
with prefixes (well-known ones plus readable names for the preview's frequent
namespaces), the total, and the top predicates and classes from one aggregate
query. Stores that cannot aggregate still list and preview, without counts.
"""

from __future__ import annotations

import asyncio
import re
from collections import Counter
from collections.abc import Iterable
from dataclasses import replace
from typing import Any

from naas_abi.apps.nexus.apps.api.app.services.sysadmin.resources import (
    Action,
    InvalidResource,
    ResourceCapabilities,
    ResourceDetail,
    ResourceEntry,
    ResourceNotFound,
    ResourcePage,
    ResourceTooLarge,
    UnsupportedOperation,
    paginate,
    text_preview,
)
from naas_abi_core import logger
from naas_abi_core.services.triple_store.TripleStorePorts import Exceptions
from rdflib import BNode, Graph, Literal, URIRef

SERVICE = "triple_store"
SCHEMA_GRAPH = URIRef("http://ontology.naas.ai/graph/schema")
GRAPH_ACTIONS: tuple[Action, ...] = ("read", "download", "write", "delete")
SCHEMA_ACTIONS: tuple[Action, ...] = ("read", "download")
PREVIEW_TRIPLES = 200
SUMMARY_TOP = 8
GENERATED_PREFIXES = 6
XSD_STRING = "http://www.w3.org/2001/XMLSchema#string"
# Mirrors the web's compactIri: always offered when the preview uses them.
WELL_KNOWN = {
    "rdf": "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
    "rdfs": "http://www.w3.org/2000/01/rdf-schema#",
    "owl": "http://www.w3.org/2002/07/owl#",
    "xsd": "http://www.w3.org/2001/XMLSchema#",
    "skos": "http://www.w3.org/2004/02/skos/core#",
    "dcterms": "http://purl.org/dc/terms/",
    "foaf": "http://xmlns.com/foaf/0.1/",
    "bfo": "http://purl.obolibrary.org/obo/BFO_",
    "cco": "https://www.commoncoreontologies.org/",
    "abi": "http://ontology.naas.ai/abi/",
}
# An absolute IRI that is safe inside SPARQL's <...> (RFC 3987 excluded characters).
IRI = re.compile(r"[A-Za-z][A-Za-z0-9+.\-]*:[^\s<>\"{}|\\^`]+")


def _iri(resource_id: str) -> URIRef | None:
    return URIRef(resource_id) if IRI.fullmatch(resource_id) else None


def _escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n").replace("\r", "\\r")


def ntriples_term(term: Any) -> str:
    """A term in strict N-Triples syntax (rdflib's ``n3`` uses Turtle's long strings)."""
    if isinstance(term, URIRef):
        return f"<{term}>"
    if isinstance(term, BNode):
        return f"_:{term}"
    if isinstance(term, Literal):
        text = f'"{_escape(str(term))}"'
        if term.language:
            return f"{text}@{term.language}"
        if term.datatype is not None and str(term.datatype) != XSD_STRING:
            return f"{text}^^<{term.datatype}>"
        return text
    return str(term)


def _namespace(iri: str) -> str | None:
    cut = max(iri.rfind("#"), iri.rfind("/"))
    return iri[: cut + 1] if 0 < cut < len(iri) - 1 else None


def _prefix_name(namespace: str) -> str:
    """A readable prefix: the namespace's last path segment that starts with a letter."""
    body = namespace.split("://", 1)[-1].strip("/#")
    for segment in reversed(body.split("/")[1:] or body.split("/")):
        cleaned = re.sub(r"[^a-z0-9]", "", segment.lower())
        if cleaned and cleaned[0].isalpha():
            return cleaned[:12]
    host = re.sub(r"[^a-z0-9]", "", body.split("/")[0].split(".")[0].lower())
    return host[:12] if host and host[0].isalpha() else "ns"


def prefixes_for(iris: Iterable[str], limit: int = GENERATED_PREFIXES) -> dict[str, str]:
    """Well-known prefixes the IRIs use, plus names for their most frequent other namespaces."""
    iris = list(iris)
    used = {p: ns for p, ns in WELL_KNOWN.items() if any(i.startswith(ns) for i in iris)}
    counts = Counter(
        ns
        for iri in iris
        if (ns := _namespace(iri)) and not any(iri.startswith(k) for k in WELL_KNOWN.values())
    )
    taken = set(WELL_KNOWN)
    for namespace, uses in counts.most_common(limit):
        if uses < 2:
            break
        name = base = _prefix_name(namespace)
        suffix = 2
        while name in taken:
            name, suffix = f"{base}{suffix}", suffix + 1
        taken.add(name)
        used[name] = namespace
    return used


def _name(iri: str) -> str:
    trimmed = iri.rstrip("/#")
    for separator in ("#", "/"):
        if separator in trimmed:
            tail = trimmed.rsplit(separator, 1)[1]
            if tail:
                return tail
    return iri


class TripleStoreResources:
    service = SERVICE
    capabilities = ResourceCapabilities(
        browse=True, create=True, write_format="Turtle", search=True
    )

    def __init__(self, store: Any, *, preview_triples: int = PREVIEW_TRIPLES) -> None:
        self._store = store
        self._preview_triples = preview_triples

    # --- sync helpers, run in a worker thread ---------------------------------------

    def _graphs(self) -> list[str]:
        return sorted(str(g) for g in self._store.list_graphs())

    def _entry(self, iri: str, attributes: dict[str, str] | None = None) -> ResourceEntry:
        schema = iri == str(SCHEMA_GRAPH)
        attributes = {**({"role": "schema"} if schema else {}), **(attributes or {})}
        actions = SCHEMA_ACTIONS if schema else GRAPH_ACTIONS
        return ResourceEntry(iri, _name(iri), "item", actions, attributes=attributes)

    def _counts(self, graphs: list[str]) -> dict[str, int] | None:
        """Triples per graph in one query, or None when the store cannot aggregate."""
        valid = [g for g in graphs if _iri(g) is not None]
        if not valid:
            return {}
        values = " ".join(f"<{g}>" for g in valid)
        sparql = (
            f"SELECT ?g (COUNT(*) AS ?n) WHERE {{ VALUES ?g {{ {values} }} "
            "GRAPH ?g { ?s ?p ?o } } GROUP BY ?g"
        )
        try:
            rows = list(self._store.query(sparql))
        except Exception as exc:  # noqa: BLE001 - counts are a nicety; the list still works
            logger.debug(f"sysadmin triple_store: no counts ({type(exc).__name__})")
            return None
        counts = dict.fromkeys(valid, 0)
        for graph, n in rows:
            counts[str(graph)] = int(n)
        return counts

    def _summary(self, graph: URIRef) -> dict[str, Any] | None:
        """Top predicates and classes of ``graph`` from one aggregate query."""
        sparql = (
            "SELECT ?kind ?x (COUNT(*) AS ?n) WHERE { "
            f"GRAPH <{graph}> {{ "
            '{ ?s ?x ?o . BIND("p" AS ?kind) } UNION { ?s a ?x . BIND("c" AS ?kind) } '
            "} } GROUP BY ?kind ?x"
        )
        try:
            rows = [(str(k), str(x), int(n)) for k, x, n in self._store.query(sparql)]
        except Exception as exc:  # noqa: BLE001 - the preview works without it
            logger.debug(f"sysadmin triple_store: no summary ({type(exc).__name__})")
            return None

        def top(kind: str) -> list[list[Any]]:
            ranked = sorted((r for r in rows if r[0] == kind), key=lambda r: (-r[2], r[1]))
            return [[x, n] for _, x, n in ranked[:SUMMARY_TOP]]

        return {
            "predicates": top("p"),
            "classes": top("c"),
            "predicate_count": sum(1 for r in rows if r[0] == "p"),
            "class_count": sum(1 for r in rows if r[0] == "c"),
        }

    def _existing(self, resource_id: str) -> URIRef:
        graph = _iri(resource_id)
        if graph is None or resource_id not in self._graphs():
            raise ResourceNotFound(SERVICE, resource_id)
        return graph

    def _count(self, graph: URIRef) -> int:
        rows = list(
            self._store.query(f"SELECT (COUNT(*) AS ?n) WHERE {{ GRAPH <{graph}> {{ ?s ?p ?o }} }}")
        )
        return int(rows[0][0]) if rows and rows[0][0] is not None else 0

    def _triples(self, graph: URIRef, limit: int | None) -> Graph:
        sparql = f"SELECT ?s ?p ?o WHERE {{ GRAPH <{graph}> {{ ?s ?p ?o }} }}"
        if limit is not None:
            sparql += f" LIMIT {int(limit)}"
        triples = Graph()
        for s, p, o in self._store.query(sparql):
            triples.add((s, p, o))
        return triples

    def _stat(self, resource_id: str) -> ResourceEntry:
        graph = self._existing(resource_id)
        return self._entry(
            resource_id,
            {"triples": str(self._count(graph)), "media_type": "text/turtle"},
        )

    def _list(self, parent: str, cursor: str | None, limit: int, query: str | None) -> ResourcePage:
        graphs = self._graphs()
        if parent:
            if parent in graphs:
                raise InvalidResource(SERVICE, f"{parent!r} is a graph, not a folder")
            raise ResourceNotFound(SERVICE, parent)
        if query:
            needle = query.lower()
            graphs = [g for g in graphs if needle in g.lower()]
        page = paginate("", [self._entry(g) for g in graphs], cursor, limit)
        counts = self._counts([e.id for e in page.entries])
        if counts is None:
            return page
        entries = tuple(
            replace(e, attributes={**e.attributes, "triples": str(counts.get(e.id, 0))})
            for e in page.entries
        )
        return replace(page, entries=entries)

    def _read(self, resource_id: str) -> ResourceDetail:
        entry = self._stat(resource_id)
        graph = URIRef(resource_id)
        total = int(entry.attributes["triples"])
        shown = self._triples(graph, self._preview_triples)
        triples = sorted(
            [ntriples_term(s), ntriples_term(p), ntriples_term(o)] for s, p, o in shown
        )
        iris = [str(term) for triple in shown for term in triple if isinstance(term, URIRef)]
        iris += [
            str(o.datatype)
            for _, _, o in shown
            if isinstance(o, Literal) and o.datatype is not None
        ]
        prefixes = prefixes_for(iris)
        for prefix, namespace in prefixes.items():
            shown.bind(prefix, namespace, override=True)
        content = text_preview(shown.serialize(format="turtle").encode())
        if total > len(shown):
            content = replace(content, truncated=True)
        view: dict[str, Any] = {
            "type": "triples",
            "triples": triples,
            "prefixes": prefixes,
            "total": total,
        }
        summary = self._summary(graph) if total else None
        if summary:
            view.update(summary)
        return ResourceDetail(entry, content, view)

    def _download(self, resource_id: str, max_bytes: int) -> bytes:
        """The graph as N-Triples (valid Turtle), read from the store's export
        and refused as soon as it passes ``max_bytes``."""
        graph = self._existing(resource_id)
        data = bytearray()
        with self._store.export(graph) as triples:
            for s, p, o in triples:
                data += f"{ntriples_term(s)} {ntriples_term(p)} {ntriples_term(o)} .\n".encode()
                if len(data) > max_bytes:
                    raise ResourceTooLarge(SERVICE, resource_id, len(data), max_bytes)
        return bytes(data)

    def _write(self, resource_id: str, content: bytes) -> ResourceEntry:
        graph = _iri(resource_id)
        if graph is None:
            raise InvalidResource(SERVICE, f"a graph name must be an absolute IRI: {resource_id!r}")
        if graph == SCHEMA_GRAPH:
            raise UnsupportedOperation(SERVICE, "write the schema graph")
        try:
            triples = Graph().parse(data=content.decode("utf-8"), format="turtle")
        except Exception as exc:  # noqa: BLE001 - any parse failure is the caller's input
            raise InvalidResource(SERVICE, f"invalid Turtle: {exc}") from exc
        try:
            if resource_id in self._graphs():
                self._store.clear_graph(graph)
            else:
                try:
                    self._store.create_graph(graph)
                except Exceptions.GraphAlreadyExistsError:
                    self._store.clear_graph(graph)
            if len(triples):
                self._store.insert(triples, graph)
        except NotImplementedError as exc:
            raise UnsupportedOperation(SERVICE, "named graphs on this store") from exc
        return self._stat(resource_id)

    def _delete(self, resource_id: str) -> None:
        graph = self._existing(resource_id)
        if graph == SCHEMA_GRAPH:
            raise UnsupportedOperation(SERVICE, "drop the schema graph")
        try:
            self._store.drop_graph(graph)
        except Exceptions.GraphNotFoundError as exc:
            raise ResourceNotFound(SERVICE, resource_id) from exc
        except NotImplementedError as exc:
            raise UnsupportedOperation(SERVICE, "named graphs on this store") from exc

    # --- ServiceResources --------------------------------------------------------------

    async def list(
        self, parent: str = "", *, cursor: str | None = None, limit: int = 100, **options: Any
    ) -> ResourcePage:
        return await asyncio.to_thread(self._list, parent, cursor, limit, options.get("query"))

    async def stat(self, resource_id: str) -> ResourceEntry:
        return await asyncio.to_thread(self._stat, resource_id)

    async def read(self, resource_id: str, *, reveal: bool = False) -> ResourceDetail:
        return await asyncio.to_thread(self._read, resource_id)

    async def download(self, resource_id: str, *, max_bytes: int) -> bytes:
        return await asyncio.to_thread(self._download, resource_id, max_bytes)

    async def write(self, resource_id: str, content: bytes) -> ResourceEntry:
        return await asyncio.to_thread(self._write, resource_id, content)

    async def delete(self, resource_id: str) -> None:
        await asyncio.to_thread(self._delete, resource_id)
