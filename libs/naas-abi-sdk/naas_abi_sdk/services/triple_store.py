from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import Any, cast

from naas_abi_proto.triple_store.v1 import triple_store_pb2 as pb

from naas_abi_sdk.services._streams import open_stream
from naas_abi_sdk.services.errors import domain_error
from naas_abi_sdk.transport import RPCError

TRANSFER_PREFIX = "abi.svc.triple_store.v1.transfer"


async def _nothing() -> AsyncIterator[Any]:
    return
    yield


@dataclass
class QueryStream:
    """A SPARQL result read as it arrives (docs/adr/20261003_nats-streamed-results.md).

    ``rows`` (SELECT: variable name -> rdflib term, unbound variables absent) and
    ``triples`` (CONSTRUCT/DESCRIBE) are single-use async iterators, valid inside
    the ``query_stream`` block only.
    """

    result_type: str
    vars: list[str] = field(default_factory=list)
    ask_answer: bool | None = None
    rows: AsyncIterator[dict] = field(default_factory=_nothing)
    triples: AsyncIterator[tuple] = field(default_factory=_nothing)


class _Sink:
    def __init__(self) -> None:
        self.triples: list[tuple] = []

    def triple(self, s, p, o) -> None:
        self.triples.append((s, p, o))


def _decode_triples(frame: bytes, bnodes: dict) -> list[tuple]:
    _rdf()
    from rdflib.plugins.parsers.ntriples import W3CNTriplesParser

    sink = _Sink()
    W3CNTriplesParser(sink=cast(Any, sink), bnode_context=bnodes).parsestring(
        frame.decode()
    )
    return sink.triples


def _rdf():
    try:
        import rdflib
    except ImportError as exc:
        raise ImportError("Install naas-abi-sdk[rdf] for RDF service values") from exc
    return rdflib


def _graph(data):
    graph = _rdf().Graph()
    if data:
        graph.parse(data=data, format="nt")
    return graph


class TripleStoreService:
    def __init__(self, client):
        self._client = client

    async def _call(self, operation, **values):
        cls = getattr(pb, "".join(p.title() for p in operation.split("_")) + "Request")
        try:
            return await getattr(self._client, operation)(cls(**values))
        except RPCError as exc:
            raise domain_error(exc) from exc

    async def insert(self, triples, graph_name) -> None:
        await self._call(
            "insert",
            triples_nt=triples.serialize(format="nt", encoding="utf-8"),
            graph_name=str(graph_name),
        )

    async def remove(self, triples, graph_name) -> None:
        await self._call(
            "remove",
            triples_nt=triples.serialize(format="nt", encoding="utf-8"),
            graph_name=str(graph_name),
        )

    async def get(self):
        """The whole store, read over the export stream: no RPC size cap."""
        graph = _rdf().Graph()
        async with self.export() as triples:
            async for triple in triples:
                graph.add(triple)
        return graph

    async def get_subject_graph(self, subject: str, graph_name: str = "*"):
        return _graph(
            (
                await self._call(
                    "get_subject_graph", subject=subject, graph_name=graph_name
                )
            ).triples_nt
        )

    def _result(self, value):
        rdf = _rdf()
        from rdflib.query import Result
        from rdflib.util import from_n3

        result = Result(value.result_type)
        if value.result_type == "ASK":
            result.askAnswer = value.ask_answer
        elif value.result_type in ("CONSTRUCT", "DESCRIBE"):
            result.graph = _graph(value.construct_triples_nt)
        else:
            result.vars = [rdf.Variable(v) for v in value.select.vars]
            result.bindings = [
                {rdf.Variable(k): from_n3(v) for k, v in row.bindings.items()}
                for row in value.select.rows
            ]
        return result

    async def query(self, query: str):
        return self._result((await self._call("query", query=query)).success)

    async def query_view(self, view: str, query: str):
        return self._result(
            (await self._call("query_view", view=view, query=query)).success
        )

    # Streamed reads over transfer frames (docs/adr/20261003_nats-streamed-results.md).

    @asynccontextmanager
    async def query_stream(self, query: str) -> AsyncIterator[QueryStream]:
        metadata = pb.QueryRequest(query=query).SerializeToString()
        async with self._frames("query", metadata) as frames:
            header = pb.QueryResult.FromString(await anext(frames))
            result = QueryStream(header.result_type)
            if header.result_type == "ASK":
                result.ask_answer = header.ask_answer
            elif header.result_type == "SELECT":
                result.vars = list(header.select.vars)
                result.rows = self._rows(frames)
            elif header.result_type in ("CONSTRUCT", "DESCRIBE"):
                result.triples = self._triples(frames)
            yield result

    @asynccontextmanager
    async def export(self, graph_name=None) -> AsyncIterator[AsyncIterator[tuple]]:
        metadata = str(graph_name).encode() if graph_name is not None else b""
        async with self._frames("export", metadata) as frames:
            yield self._triples(frames)

    @asynccontextmanager
    async def _frames(
        self, operation: str, metadata: bytes
    ) -> AsyncIterator[AsyncIterator[bytes]]:
        async with open_stream(
            self._client, TRANSFER_PREFIX, operation, metadata
        ) as frames:
            if frames is None:
                raise RPCError("UNAVAILABLE", "No triple store engine hosts streams")
            yield frames

    @staticmethod
    async def _rows(frames: AsyncIterator[bytes]) -> AsyncIterator[dict]:
        _rdf()
        from rdflib.util import from_n3

        async for frame in frames:
            for row in pb.SelectResult.FromString(frame).rows:
                yield {name: from_n3(value) for name, value in row.bindings.items()}

    @staticmethod
    async def _triples(frames: AsyncIterator[bytes]) -> AsyncIterator[tuple]:
        bnodes: dict = {}  # one blank node per label for the whole stream
        async for frame in frames:
            for triple in _decode_triples(frame, bnodes):
                yield triple

    async def create_graph(self, graph_name) -> None:
        await self._call("create_graph", graph_name=str(graph_name))

    async def clear_graph(self, graph_name) -> None:
        await self._call("clear_graph", graph_name=str(graph_name))

    async def drop_graph(self, graph_name) -> None:
        await self._call("drop_graph", graph_name=str(graph_name))

    async def list_graphs(self) -> list:
        return [
            _rdf().URIRef(name)
            for name in (await self._call("list_graphs")).graph_names.graph_names
        ]

    def subscribe(self, *args, **kwargs):
        raise NotImplementedError(
            "RDF callback subscriptions are not exposed by the remote service facade"
        )
