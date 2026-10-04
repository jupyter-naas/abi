"""Frames of a streamed triple store read (docs/adr/20261003_nats-streamed-results.md).

Shared by the NATS primary and client; no new protobuf messages. A ``query``
stream starts with a header (``QueryResult`` without rows or triples), then
carries batches: ``SelectResult`` with rows only (SELECT), or N-Triples lines
(CONSTRUCT/DESCRIBE and every ``export`` frame). Row values use rdflib's N3
term syntax, as the unary ``query`` reply does.
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator
from typing import cast

from naas_abi_core.proto.triple_store.v1 import triple_store_pb2
from naas_abi_core.services.triple_store.TripleStorePorts import QueryStream, Triple
from rdflib import BNode
from rdflib.plugins.parsers.ntriples import DummySink, W3CNTriplesParser
from rdflib.plugins.serializers.nt import _nt_row
from rdflib.term import Node
from rdflib.util import from_n3

FRAME_BYTES = 256 * 1024


def encode_header(result: QueryStream) -> bytes:
    header = triple_store_pb2.QueryResult(result_type=result.result_type)
    if result.result_type == "ASK":
        header.ask_answer = bool(result.ask_answer)
    elif result.result_type == "SELECT":
        header.select.vars.extend(result.vars)
    return header.SerializeToString()


def decode_header(frame: bytes) -> QueryStream:
    header = triple_store_pb2.QueryResult.FromString(frame)
    if header.result_type == "ASK":
        return QueryStream("ASK", ask_answer=header.ask_answer)
    return QueryStream(header.result_type, vars=list(header.select.vars))


def row_frames(
    rows: Iterable[dict[str, Node]], frame_bytes: int = FRAME_BYTES
) -> Iterator[bytes]:
    batch, size = triple_store_pb2.SelectResult(), 0
    for row in rows:
        bindings = {name: term.n3() for name, term in row.items()}
        batch.rows.append(triple_store_pb2.Row(bindings=bindings))
        size += sum(len(name) + len(value) + 8 for name, value in bindings.items())
        if size >= frame_bytes:
            yield batch.SerializeToString()
            batch, size = triple_store_pb2.SelectResult(), 0
    if batch.rows:
        yield batch.SerializeToString()


def decode_rows(frame: bytes) -> list[dict[str, Node]]:
    batch = triple_store_pb2.SelectResult.FromString(frame)
    return [
        {name: cast(Node, from_n3(value)) for name, value in row.bindings.items()}
        for row in batch.rows
    ]


def nt_line(triple: Triple) -> str:
    """One triple as an N-Triples line, newline included (also valid Turtle)."""
    return _nt_row(triple)


def triple_frames(
    triples: Iterable[Triple], frame_bytes: int = FRAME_BYTES
) -> Iterator[bytes]:
    lines: list[str] = []
    size = 0
    for triple in triples:
        line = nt_line(triple)
        lines.append(line)
        size += len(line)
        if size >= frame_bytes:
            yield "".join(lines).encode("utf-8")
            lines, size = [], 0
    if lines:
        yield "".join(lines).encode("utf-8")


class _Sink(DummySink):
    def __init__(self) -> None:
        super().__init__()
        self.triples: list[Triple] = []

    def triple(self, s: Node, p: Node, o: Node) -> None:
        self.triples.append((s, p, o))


def decode_triples(frame: bytes, bnodes: dict[str, BNode]) -> list[Triple]:
    """``bnodes`` is shared by every frame of one stream (one node per label)."""
    sink = _Sink()
    W3CNTriplesParser(sink=sink, bnode_context=bnodes).parsestring(
        frame.decode("utf-8")
    )
    return sink.triples
