"""The streaming defaults every ITripleStorePort inherits (docs/adr/20261003_nats-streamed-results.md)."""

import pytest
import rdflib
from naas_abi_core.services.triple_store.TripleStorePorts import (
    ITripleStorePort,
    QueryStream,
    graph_export_query,
)
from rdflib import Graph, Literal, URIRef

EX = rdflib.Namespace("http://example.org/")
PEOPLE = URIRef("http://example.org/graph/people")
PLACES = URIRef("http://example.org/graph/places")


class DatasetPort(ITripleStorePort):
    """Only the abstract methods, over an rdflib Dataset: no streaming of its own."""

    def __init__(self):
        self.ds = rdflib.Dataset(default_union=True)
        self.ds.graph(PEOPLE).add((EX.alice, EX.name, Literal("Alice", lang="en")))
        self.ds.graph(PEOPLE).add((EX.bob, EX.age, Literal(42)))
        self.ds.graph(PLACES).add((EX.paris, EX.name, Literal("Paris")))

    def insert(self, triples, graph_name):
        raise NotImplementedError

    def remove(self, triples, graph_name):
        raise NotImplementedError

    def get(self):
        result = Graph()
        for triple in self.ds.triples((None, None, None)):
            result.add(triple)
        return result

    def handle_view_event(self, view, event, triple):
        return None

    def query(self, query):
        return self.ds.query(query)

    def query_view(self, view, query):
        return self.query(query)

    def get_subject_graph(self, subject, graph_name):
        raise NotImplementedError

    def create_graph(self, graph_name):
        raise NotImplementedError

    def clear_graph(self, graph_name):
        raise NotImplementedError

    def drop_graph(self, graph_name):
        raise NotImplementedError

    def list_graphs(self):
        return [PEOPLE, PLACES]


def test_select_rows_stream_with_unbound_variables_left_out():
    port = DatasetPort()
    with port.query_stream(
        "SELECT ?s ?name WHERE { ?s ?p ?o OPTIONAL { ?s <http://example.org/name> ?name } }"
        " ORDER BY ?s"
    ) as result:
        assert (result.result_type, result.vars) == ("SELECT", ["s", "name"])
        rows = list(result.rows)
    assert rows == [
        {"s": EX.alice, "name": Literal("Alice", lang="en")},
        {"s": EX.bob},
        {"s": EX.paris, "name": Literal("Paris")},
    ]


def test_ask_and_construct_results_stream_too():
    port = DatasetPort()
    with port.query_stream("ASK { ?s ?p 42 }") as asked:
        assert (asked.result_type, asked.ask_answer) == ("ASK", True)
    with port.query_stream(
        "CONSTRUCT { ?s ?p ?o } WHERE { GRAPH <http://example.org/graph/places> { ?s ?p ?o } }"
    ) as built:
        assert built.result_type == "CONSTRUCT"
        assert list(built.triples) == [(EX.paris, EX.name, Literal("Paris"))]


@pytest.mark.parametrize(
    "result,expected",
    [
        (True, ("ASK", True, [])),
        (Graph().add((EX.a, EX.b, EX.c)), ("CONSTRUCT", None, [(EX.a, EX.b, EX.c)])),
    ],
    ids=["bare-bool", "bare-graph"],
)
def test_adapters_returning_bare_values_are_normalized(result, expected):
    # Some adapters hand back a bool for ASK or a Graph for CONSTRUCT.
    stream = QueryStream.from_result(result)
    assert (stream.result_type, stream.ask_answer, list(stream.triples)) == expected


def test_export_reads_one_named_graph_or_the_whole_store():
    port = DatasetPort()
    with port.export(PEOPLE) as triples:
        assert set(triples) == {
            (EX.alice, EX.name, Literal("Alice", lang="en")),
            (EX.bob, EX.age, Literal(42)),
        }
    with port.export() as everything:
        assert len(set(everything)) == 3


@pytest.mark.parametrize(
    "graph_name", ["http://x/a b", "http://x/>{", 'http://x/"', "relative"]
)
def test_export_refuses_a_graph_name_that_is_not_an_absolute_iri(graph_name):
    with pytest.raises(ValueError):
        graph_export_query(URIRef(graph_name))
