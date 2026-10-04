"""Restrict every Graph data query to the authorized SPARQL dataset."""

from __future__ import annotations

import re
from collections.abc import Iterator
from contextlib import contextmanager
from functools import lru_cache
from threading import Lock
from typing import Any, cast

from naas_abi.apps.nexus.apps.api.app.services.graph.access import GraphAccessScope
from naas_abi.apps.nexus.apps.api.app.services.graph.graph__schema import (
    GraphAccessError,
    GraphQuerySpecError,
)
from naas_abi.apps.nexus.apps.api.app.services.graph.query.sparql_safe import sparql_iri
from naas_abi_core.services.triple_store.TripleStorePorts import QueryStream
from pyparsing import ParseResults
from rdflib import Graph, URIRef
from rdflib.plugins.sparql.parser import parseQuery
from rdflib.plugins.sparql.parserutils import CompValue
from rdflib.query import Result

# Mask RDF terms and comments before locating the outer WHERE. Never interpret a
# keyword in a literal, IRI, comment or nested SELECT as query structure.
_TERMS = re.compile(
    r"""(?:\"\"\"(?:\\.|(?!\"\"\")[\s\S])*\"\"\"|"""
    r"'''(?:\\.|(?!''')[\s\S])*'''|"
    r""""(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*'|<[^<>"{}|^`\\\x00-\x20]*>|\#[^\r\n]*)"""
)
_VALUES_NAMED_GRAPH_PATTERN = re.compile(
    r"VALUES\s+\?(?:g|rg|tg|sg)\s*\{([^}]*)\}",
    re.IGNORECASE | re.DOTALL,
)
_IRI_IN_ANGLE = re.compile(r"<([^>]+)>")


def _graphs_from_values_clause(query: str) -> set[str] | None:
    """Union graph IRIs pinned by VALUES ?g / ?rg / ?tg / ?sg in the query."""
    matches = list(_VALUES_NAMED_GRAPH_PATTERN.finditer(query))
    if not matches:
        return None
    uris: set[str] = set()
    for match in matches:
        uris.update(m.group(1) for m in _IRI_IN_ANGLE.finditer(match.group(1)))
    return uris if uris else None


# RDFLib/pyparsing initializes parse-action arities lazily. Concurrent first
# parses can corrupt those wrappers and reject valid queries until restart.
# Serialize parsing only: cached shape checks and store execution stay parallel.
_PARSE_LOCK = Lock()


@lru_cache(maxsize=512)
def query_shape(query: str) -> tuple[str, int]:
    """Accept read queries without caller-selected datasets or federation."""
    try:
        with _PARSE_LOCK:
            parsed = parseQuery(query)
    except Exception as exc:
        raise GraphQuerySpecError("Invalid graph query") from exc

    def visit(value: Any) -> None:
        if isinstance(value, CompValue):
            if value.name in {"ServiceGraphPattern", "DatasetClause"}:
                raise GraphAccessError("Graph queries cannot override their workspace dataset")
            for child in value.values():
                visit(child)
        elif isinstance(value, (list, tuple, ParseResults)):
            for child in value:
                visit(child)

    visit(parsed)
    kind = parsed[1].name
    if kind not in {"SelectQuery", "AskQuery", "ConstructQuery"}:
        raise GraphQuerySpecError("Only SELECT, ASK and CONSTRUCT graph queries are supported")
    masked = _TERMS.sub(lambda m: " " * len(m.group()), query)
    depth = 0
    for token in re.finditer(r"\{|\}|(?<![\w?:$-])WHERE(?![\w:-])", masked, re.I):
        word = token.group().upper()
        if word == "WHERE" and depth == 0:
            return kind, token.start()
        depth += 1 if word == "{" else -1 if word == "}" else 0
    raise GraphQuerySpecError("Graph query requires an outer WHERE clause")


class WorkspaceGraphStore:
    """Data adapter; catalog metadata is deliberately unavailable through it.

    FROM NAMED fixes the dataset for explicit and variable GRAPH patterns,
    including nested queries. The default graph is the union of those same permitted graphs. This also scopes
    legacy schema enrichment; schema is readable only with an explicit grant.
    """

    def __init__(self, store: Any, scope: GraphAccessScope) -> None:
        self._store = store
        self.scope = scope
        # Never let an RDFLib adapter try to load an absent graph IRI over HTTP.
        self._graphs = scope.readable.intersection(str(g) for g in store.list_graphs())
        self.cache_namespace = "workspace-graphs-v1-" + scope.cache_key

    def query(self, query: str) -> Result | Graph:
        kind, scoped = self._scoped(query)
        if scoped is None:
            result = Result(kind)
            result.vars = []
            result.bindings = []
            result.askAnswer = False
            result.graph = Graph()
            return result
        return cast(Result | Graph, self._store.query(scoped))

    @contextmanager
    def query_stream(self, query: str) -> Iterator[QueryStream]:
        """``query``, read incrementally (TripleStoreService.query_stream)."""
        kind, scoped = self._scoped(query)
        if scoped is None:
            yield QueryStream(kind, ask_answer=False if kind == "ASK" else None)
            return
        with self._store.query_stream(scoped) as result:
            yield result

    @contextmanager
    def export(self, graph_name: URIRef) -> Iterator[Iterator[Any]]:
        """One readable named graph's triples, read lazily (TripleStoreService.export)."""
        self.scope.require(self.scope.workspace_id, [str(graph_name)])
        if str(graph_name) not in self._graphs:
            yield iter(())
            return
        with self._store.export(URIRef(graph_name)) as triples:
            yield triples

    def _scoped(self, query: str) -> tuple[str, str | None]:
        """The result type and ``query`` limited to the readable graphs, or
        ``None`` when no readable graph can match (an empty result)."""
        shape, offset = query_shape(query)
        kind = {
            "SelectQuery": "SELECT",
            "AskQuery": "ASK",
            "ConstructQuery": "CONSTRUCT",
        }[shape]
        if not self._graphs:
            return kind, None
        named = _graphs_from_values_clause(query)
        if named is not None:
            active = sorted(self._graphs.intersection(named))
            if not active:
                return "SELECT", None
        else:
            active = sorted(self._graphs)
        dataset = "\n".join(
            "FROM " + sparql_iri(g) + "\nFROM NAMED " + sparql_iri(g) for g in active
        )
        return kind, query[:offset] + dataset + "\n" + query[offset:]

    def list_graphs(self) -> list[URIRef]:
        return [URIRef(g) for g in sorted(self._graphs)]

    def insert(self, triples: Graph, graph_name: URIRef) -> Any:
        self.scope.require(self.scope.workspace_id, [str(graph_name)], write=True)
        return self._store.insert(triples, graph_name=graph_name)

    def remove(self, triples: Graph, graph_name: URIRef) -> Any:
        self.scope.require(self.scope.workspace_id, [str(graph_name)], write=True)
        return self._store.remove(triples, graph_name=graph_name)

    def clear_graph(self, graph_name: URIRef) -> Any:
        self.scope.require(self.scope.workspace_id, [str(graph_name)], write=True)
        return self._store.clear_graph(graph_name)

    def drop_graph(self, graph_name: URIRef) -> Any:
        self.scope.require(self.scope.workspace_id, [str(graph_name)], write=True)
        return self._store.drop_graph(graph_name)
