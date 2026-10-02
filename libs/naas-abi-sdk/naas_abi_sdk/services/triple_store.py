from __future__ import annotations

from naas_abi_proto.triple_store.v1 import triple_store_pb2 as pb

from naas_abi_sdk.services.errors import domain_error
from naas_abi_sdk.transport import RPCError


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
        return _graph((await self._call("get")).triples_nt)

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
