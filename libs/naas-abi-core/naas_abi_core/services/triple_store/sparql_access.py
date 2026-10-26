"""What a SPARQL request reads and writes, for its authorization.

``read_shape`` reports a query's own dataset (``FROM``, ``FROM NAMED``), the
graphs it names in ``GRAPH <iri>``, and whether it calls ``SERVICE``; the
triple store then runs it over the graphs its caller may read.
``update_needs`` lists, for a SPARQL Update, the action each operation needs on
each graph:

==========================  =================================================
``INSERT DATA``             ``Insert``
``DELETE DATA``             ``Remove``
``DELETE/INSERT … WHERE``   ``Remove``/``Insert`` on the targets, ``Query`` on
                            what ``WHERE`` reads
``DELETE WHERE``            ``Remove`` and ``Query`` on its graphs
``LOAD``                    ``Insert``, and ``Query`` on every graph: the
                            source IRI may be one of the store's own graphs
``CLEAR`` / ``DROP``        ``ClearGraph`` / ``DropGraph``
``CREATE``                  ``CreateGraph``
``ADD``, ``COPY``, ``MOVE`` ``Query`` on the source, ``Insert`` on the target,
                            ``ClearGraph`` on the target for ``COPY`` and ``MOVE``
                            (they replace it), and ``DropGraph`` on the source
                            for ``MOVE``
==========================  =================================================

A ``DEFAULT``, ``NAMED`` or ``ALL`` target, or a graph variable, needs the action
on every graph (``EVERY_GRAPH``); the default graph is ``DEFAULT_GRAPH``.
Anything the parser cannot classify raises ``Exceptions.InvalidRequest`` (``INVALID_ARGUMENT``).
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import Any

from naas_abi_core.services.triple_store.TripleStorePorts import Exceptions
from rdflib import URIRef, Variable
from rdflib.plugins.sparql.algebra import translateQuery, translateUpdate
from rdflib.plugins.sparql.parser import parseQuery, parseUpdate
from rdflib.plugins.sparql.parserutils import CompValue

DEFAULT_GRAPH = "default"
EVERY_GRAPH = "*"
Target = URIRef | str  # an IRI, DEFAULT_GRAPH or EVERY_GRAPH


@dataclass(frozen=True)
class ReadShape:
    from_graphs: tuple[URIRef, ...] = ()
    from_named: tuple[URIRef, ...] = ()
    graphs: tuple[URIRef, ...] = ()  # GRAPH <iri>
    service: bool = False

    @property
    def has_dataset(self) -> bool:
        return bool(self.from_graphs or self.from_named)

    @property
    def named(self) -> tuple[URIRef, ...]:
        """Every graph the query names, once each, in order."""
        seen: list[URIRef] = []
        for graph in (*self.from_graphs, *self.from_named, *self.graphs):
            if graph not in seen:
                seen.append(graph)
        return tuple(seen)


@dataclass(frozen=True)
class Need:
    action: str
    graph: Target


@dataclass
class _Reads:
    graphs: list[URIRef] = field(default_factory=list)
    any_graph: bool = False  # GRAPH ?g
    default: bool = False  # patterns outside any GRAPH
    service: bool = False


@dataclass(frozen=True)
class Analysis:
    """A SPARQL request, parsed once: what a query reads, or what an update needs."""

    update: bool
    shape: ReadShape = field(default_factory=ReadShape)
    needs: tuple[Need, ...] = ()


# rdflib's SPARQL grammar is pyparsing, whose state is not thread-safe, and
# requests arrive on the NATS dispatcher's thread pool. The lock serializes
# this module's parses only: other rdflib SPARQL parsing in the process (an
# rdflib-backed adapter's own ``query``) does not take it.
_PARSE_LOCK = threading.Lock()


def analyze(request: str, *, union_default_graph: bool = False) -> Analysis:
    """Parse ``request`` once, as a query or else as an update.

    ``union_default_graph``: the store's default graph is the union of its
    named graphs, so an update reading the default graph reads every graph.
    Raises ``Exceptions.InvalidRequest`` for anything else.
    """
    with _PARSE_LOCK:
        try:
            query = translateQuery(parseQuery(request))
        except Exception:  # noqa: BLE001 - not a query: an update, or nothing
            query = None
        if query is None:
            try:
                operations = translateUpdate(parseUpdate(request)).algebra
            except Exception as exc:
                raise Exceptions.InvalidRequest(
                    "Unparsable SPARQL request: neither a query nor an update"
                ) from exc
    if query is not None:
        return Analysis(update=False, shape=_shape(query))
    needs: list[Need] = []
    for operation in operations:
        for need in _operation_needs(operation):
            if union_default_graph and need == Need("Query", DEFAULT_GRAPH):
                need = Need("Query", EVERY_GRAPH)
            if need not in needs:
                needs.append(need)
    return Analysis(update=True, needs=tuple(needs))


def read_shape(query: str) -> ReadShape:
    analysis = analyze(query)
    if analysis.update:
        raise Exceptions.InvalidRequest("A SPARQL update is not a query")
    return analysis.shape


def update_needs(update: str, *, union_default_graph: bool = False) -> list[Need]:
    analysis = analyze(update, union_default_graph=union_default_graph)
    if not analysis.update:
        raise Exceptions.InvalidRequest("A SPARQL query is not an update")
    return list(analysis.needs)


def _shape(parsed: Any) -> ReadShape:
    from_graphs: list[URIRef] = []
    from_named: list[URIRef] = []
    for clause in _field(parsed.algebra, "datasetClause") or ():
        if "default" in clause:
            from_graphs.append(URIRef(clause["default"]))
        if "named" in clause:
            from_named.append(URIRef(clause["named"]))
    reads = _reads(parsed.algebra)
    return ReadShape(
        tuple(from_graphs),
        tuple(from_named),
        tuple(reads.graphs),
        reads.service,
    )


def _operation_needs(operation: CompValue) -> list[Need]:
    name = operation.name
    if name == "InsertData":
        return _quad_needs("Insert", operation, DEFAULT_GRAPH)
    if name == "DeleteData":
        return _quad_needs("Remove", operation, DEFAULT_GRAPH)
    if name == "DeleteWhere":
        removes = _quad_needs("Remove", operation, DEFAULT_GRAPH)
        return removes + [Need("Query", need.graph) for need in removes]
    if name == "Modify":
        default: Target = (
            URIRef(operation["withClause"])
            if "withClause" in operation
            else DEFAULT_GRAPH
        )
        needs: list[Need] = []
        if "delete" in operation:
            needs += _quad_needs("Remove", operation["delete"], default)
        if "insert" in operation:
            needs += _quad_needs("Insert", operation["insert"], default)
        reads = _reads(_field(operation, "where"))
        if reads.service:
            # SERVICE leaves the dataset (USING included): every graph.
            needs.append(Need("Query", EVERY_GRAPH))
        using = _field(operation, "using") or []
        if using:
            for clause in using:
                graph = clause["default"] if "default" in clause else clause["named"]
                needs.append(Need("Query", URIRef(graph)))
        else:
            needs += [Need("Query", graph) for graph in reads.graphs]
            if reads.any_graph:
                needs.append(Need("Query", EVERY_GRAPH))
            if reads.default:
                needs.append(Need("Query", default))
        return needs
    if name == "Load":
        # The store dereferences the source itself, and it may be one of its
        # own graphs (or its SPARQL endpoint): as for SERVICE, every graph.
        return [
            Need("Insert", _target(_field(operation, "graphiri"))),
            Need("Query", EVERY_GRAPH),
        ]
    if name == "Clear":
        return [Need("ClearGraph", _target(_field(operation, "graphiri")))]
    if name == "Drop":
        return [Need("DropGraph", _target(_field(operation, "graphiri")))]
    if name == "Create":
        return [Need("CreateGraph", _target(_field(operation, "graphiri")))]
    if name in ("Add", "Copy", "Move"):
        source, target = (_target(g) for g in operation["graph"])
        needs = [Need("Query", source), Need("Insert", target)]
        if name in ("Copy", "Move"):
            needs.append(Need("ClearGraph", target))  # the target is replaced
        if name == "Move":
            needs.append(Need("DropGraph", source))
        return needs
    raise Exceptions.InvalidRequest(f"Unsupported SPARQL update operation {name}")


def _field(node: CompValue, name: str) -> Any:
    """A field, or None. ``CompValue.get`` answers the key itself when absent."""
    return node[name] if name in node else None  # noqa: SIM401


def _target(graph: Any) -> Target:
    if graph is None or graph == "DEFAULT":
        return DEFAULT_GRAPH
    if graph in ("NAMED", "ALL") or isinstance(graph, Variable):
        return EVERY_GRAPH
    return URIRef(graph)


def _quad_needs(action: str, clause: CompValue, default: Target) -> list[Need]:
    needs: list[Need] = []
    if _field(clause, "triples"):
        needs.append(Need(action, default))
    for graph in _field(clause, "quads") or {}:
        needs.append(Need(action, _target(graph)))
    return needs


def _reads(node: Any) -> _Reads:
    reads = _Reads()
    _walk(node, inside_graph=False, reads=reads)
    return reads


def _walk(node: Any, *, inside_graph: bool, reads: _Reads) -> None:
    if isinstance(node, CompValue):
        if node.name == "ServiceGraphPattern":
            reads.service = True
            return
        if node.name in ("Graph", "GraphGraphPattern"):  # algebra, or parsed EXISTS
            term = _field(node, "term")
            if isinstance(term, URIRef):
                if term not in reads.graphs:
                    reads.graphs.append(term)
            else:
                reads.any_graph = True
            for value in node.values():
                _walk(value, inside_graph=True, reads=reads)
            return
        if node.name in ("BGP", "TriplesBlock") and not inside_graph:
            if _field(node, "triples"):
                reads.default = True
        for value in node.values():
            _walk(value, inside_graph=inside_graph, reads=reads)
    elif isinstance(node, (list, tuple)):
        for value in node:
            _walk(value, inside_graph=inside_graph, reads=reads)
    elif isinstance(node, dict):
        for value in node.values():
            _walk(value, inside_graph=inside_graph, reads=reads)
