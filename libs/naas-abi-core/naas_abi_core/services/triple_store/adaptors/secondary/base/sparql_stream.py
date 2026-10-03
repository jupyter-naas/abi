"""Read a SPARQL 1.1 Protocol query response line by line.

Shared by the HTTP triple store adapters (Apache Jena TDB2, Oxigraph). They
ask for line-based formats (``ACCEPT``): tab-separated results for SELECT and
ASK, N-Triples for CONSTRUCT and DESCRIBE, so a result is parsed as it is read
and memory stays bounded by one batch. JSON results and Turtle are still read,
whole, for servers that cannot send those. See
docs/adr/20261003_nats-streamed-results.md.
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Iterator
from typing import Any, cast

from naas_abi_core.services.triple_store.TripleStorePorts import (
    Exceptions,
    QueryStream,
    Triple,
)
from rdflib import BNode, Graph, Literal, URIRef
from rdflib.plugins.parsers.ntriples import DummySink, W3CNTriplesParser
from rdflib.term import Node
from rdflib.util import from_n3

ACCEPT = (
    "text/tab-separated-values, application/n-triples;q=0.9, "
    "application/sparql-results+json;q=0.5, text/turtle;q=0.4"
)
BATCH_LINES = 1000
_BODY_EXCERPT = 500


class _Sink(DummySink):
    def __init__(self) -> None:
        super().__init__()
        self.triples: list[Triple] = []

    def triple(self, s: Node, p: Node, o: Node) -> None:
        self.triples.append((s, p, o))


def read_query_response(response: Any, *, operation: str, endpoint: str) -> QueryStream:
    """Read a streaming HTTP response (``headers``, ``iter_lines``, ``text``).

    A line the format cannot hold (a backend aborting mid-response appends its
    error text) raises ``Exceptions.RequestError`` from the iterator.
    """
    content_type = response.headers.get("Content-Type", "")

    def broken(line: str, cause: Exception | None = None) -> Exceptions.RequestError:
        return Exceptions.RequestError(
            operation=operation,
            message="The triple store aborted or corrupted the result stream",
            response_body=line[:_BODY_EXCERPT],
            endpoint=endpoint,
        )

    if "tab-separated-values" in content_type:
        lines = response.iter_lines(decode_unicode=True)
        header = _text(next(lines, ""))
        if header in ("true", "false"):  # Oxigraph: the bare boolean
            return QueryStream("ASK", ask_answer=header == "true")
        if header == "?_askResult":  # Jena
            return QueryStream("ASK", ask_answer=_text(next(lines, "")) == "true")
        variables = [name.removeprefix("?") for name in header.split("\t") if name]
        return QueryStream(
            "SELECT", vars=variables, rows=_tsv_rows(lines, variables, broken)
        )
    if "n-triples" in content_type:
        return QueryStream(
            "CONSTRUCT",
            triples=_n_triples(response.iter_lines(decode_unicode=True), broken),
        )
    if "sparql-results+json" in content_type:
        return _json_results(json.loads(response.text))
    if "turtle" in content_type:
        graph = Graph().parse(data=response.text, format="turtle")
        return QueryStream("CONSTRUCT", triples=iter(graph))
    raise ValueError(f"Unexpected content type: {content_type}")


def _text(line: str | bytes) -> str:
    return line.decode("utf-8") if isinstance(line, bytes) else line


def _tsv_rows(
    lines: Iterable[str | bytes], variables: list[str], broken: Any
) -> Iterator[dict[str, Node]]:
    for raw in lines:
        line = _text(raw)
        values = line.split("\t")
        if len(values) != len(variables):
            raise broken(line)
        try:
            yield {
                name: cast(Node, from_n3(value))
                for name, value in zip(variables, values)
                if value != ""
            }
        except Exception as exc:
            raise broken(line, exc) from exc


def _n_triples(lines: Iterable[str | bytes], broken: Any) -> Iterator[Triple]:
    bnodes: dict[str, BNode] = {}  # one blank node per label for the whole stream
    batch: list[str] = []
    for raw in lines:
        line = _text(raw)
        if line.strip() and not line.lstrip().startswith("#"):
            batch.append(line)
        if len(batch) >= BATCH_LINES:
            yield from _parse_n_triples(batch, bnodes, broken)
            batch = []
    if batch:
        yield from _parse_n_triples(batch, bnodes, broken)


def _parse_n_triples(
    lines: list[str], bnodes: dict[str, BNode], broken: Any
) -> list[Triple]:
    sink = _Sink()
    try:
        W3CNTriplesParser(sink=sink, bnode_context=bnodes).parsestring("\n".join(lines))
    except Exception as exc:
        raise broken(_first_bad_line(lines), exc) from exc
    return sink.triples


def _first_bad_line(lines: list[str]) -> str:
    for line in lines:
        try:
            W3CNTriplesParser(sink=_Sink(), bnode_context={}).parsestring(line)
        except Exception:  # noqa: BLE001
            return line
    return lines[0] if lines else ""


def _json_results(data: dict[str, Any]) -> QueryStream:
    if "boolean" in data:
        return QueryStream("ASK", ask_answer=bool(data["boolean"]))
    variables = list(data.get("head", {}).get("vars", []))
    bindings = data.get("results", {}).get("bindings", [])
    return QueryStream(
        "SELECT",
        vars=variables,
        rows=(
            {name: _json_term(value) for name, value in binding.items()}
            for binding in bindings
        ),
    )


def _json_term(value: dict[str, Any]) -> Node:
    if value.get("type") == "uri":
        return URIRef(value["value"])
    if value.get("type") == "bnode":
        return BNode(value["value"])
    if value.get("datatype"):
        return Literal(value["value"], datatype=URIRef(value["datatype"]))
    return Literal(value["value"], lang=value.get("xml:lang"))
