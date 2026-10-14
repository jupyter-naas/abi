from contextlib import contextmanager
from types import SimpleNamespace

from naas_abi_core.services.triple_store.TripleStorePorts import QueryStream
from rdflib import Literal, URIRef

from naas_abi.tools import platform_tools


class _Store:
    """Streams only: a materialized query fails the test."""

    def __init__(self, result):
        self.result = result

    def query(self, sparql):
        raise AssertionError("kg_sparql_query reads results as a stream")

    @contextmanager
    def query_stream(self, sparql):
        yield self.result


def _tool(monkeypatch, result):
    services = SimpleNamespace(triple_store=_Store(result))
    monkeypatch.setattr(platform_tools, "_services", lambda: services)
    (tool,) = [
        t
        for t in platform_tools.platform_service_tools()
        if t.name == "kg_sparql_query"
    ]
    return tool


def test_select_rows_are_capped_and_counted(monkeypatch):
    many = platform_tools.MAX_ROWS + 5
    rows = ({"s": URIRef(f"urn:s{n}")} for n in range(many))
    tool = _tool(monkeypatch, QueryStream("SELECT", vars=["s", "label"], rows=rows))

    result = tool.invoke({"query": "SELECT ?s ?label WHERE { ?s ?p ?o }"})

    assert result["total_rows"] == many and result["truncated"] is True
    assert len(result["rows"]) == platform_tools.MAX_ROWS
    assert result["rows"][0] == {"s": "urn:s0", "label": None}


def test_small_results_keep_the_plain_list(monkeypatch):
    rows = iter([{"s": URIRef("urn:a"), "label": Literal("A")}])
    tool = _tool(monkeypatch, QueryStream("SELECT", vars=["s", "label"], rows=rows))

    assert tool.invoke({"query": "SELECT * {}"}) == [{"s": "urn:a", "label": "A"}]


def test_ask_and_construct_answer(monkeypatch):
    assert _tool(monkeypatch, QueryStream("ASK", ask_answer=True)).invoke(
        {"query": "ASK {}"}
    ) == {"ask": True}
    triples = iter([(URIRef("urn:s"), URIRef("urn:p"), Literal("o"))])
    built = _tool(monkeypatch, QueryStream("CONSTRUCT", triples=triples))
    assert built.invoke({"query": "CONSTRUCT {}"}) == ['<urn:s> <urn:p> "o" .']
