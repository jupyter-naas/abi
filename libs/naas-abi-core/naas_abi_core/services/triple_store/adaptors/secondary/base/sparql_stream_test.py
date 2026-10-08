import pytest
from naas_abi_core.services.triple_store.adaptors.secondary.base.sparql_stream import (
    read_query_response,
)
from naas_abi_core.services.triple_store.TripleStorePorts import Exceptions
from rdflib import BNode, Literal, URIRef
from rdflib.namespace import XSD


class Response:
    """A streaming HTTP response: lines are produced only as they are read."""

    def __init__(self, content_type, lines, text=""):
        self.headers = {"Content-Type": content_type}
        self._lines = lines
        self.text = text
        self.read = 0

    def iter_lines(self, decode_unicode=False):
        for line in self._lines:
            self.read += 1
            yield line


def read(response):
    return read_query_response(
        response, operation="query", endpoint="http://store/query"
    )


def test_tsv_rows_are_parsed_lazily_with_typed_terms():
    response = Response(
        "text/tab-separated-values; charset=utf-8",
        [
            "?s\t?label\t?n",
            '<http://ex/a>\t"Alice"@en\t1',
            '_:b0\t"a\\tb\\nc"\t1.5',
            '<http://ex/c>\t\t"2"^^<http://www.w3.org/2001/XMLSchema#long>',
        ],
    )

    result = read(response)
    assert (result.result_type, result.vars) == ("SELECT", ["s", "label", "n"])
    assert response.read == 1  # only the header so far
    rows = iter(result.rows)
    assert next(rows) == {
        "s": URIRef("http://ex/a"),
        "label": Literal("Alice", lang="en"),
        "n": Literal("1", datatype=XSD.integer),
    }
    assert response.read == 2
    second, third = list(rows)
    assert second["label"] == Literal("a\tb\nc") and second["s"] == BNode("b0")
    assert second["n"] == Literal("1.5", datatype=XSD.decimal)
    assert third == {
        "s": URIRef("http://ex/c"),
        "n": Literal("2", datatype=XSD.long),
    }  # the empty column is unbound


@pytest.mark.parametrize(
    "lines,answer",
    [(["true"], True), (["false"], False), (["?_askResult", "true"], True)],
    ids=["oxigraph", "oxigraph-false", "jena"],
)
def test_tsv_ask_answers(lines, answer):
    result = read(Response("text/tab-separated-values", lines))
    assert (result.result_type, result.ask_answer) == ("ASK", answer)


def test_n_triples_stream_in_batches_and_keep_blank_nodes_across_them(monkeypatch):
    from naas_abi_core.services.triple_store.adaptors.secondary.base import (
        sparql_stream,
    )

    monkeypatch.setattr(sparql_stream, "BATCH_LINES", 2)
    response = Response(
        "application/n-triples",
        [
            "_:x <http://ex/p> <http://ex/a> .",
            "# a comment",
            '<http://ex/b> <http://ex/p> "v" .',
            "",
            '_:x <http://ex/q> "w"@fr .',
        ],
    )

    triples = list(read(response).triples)

    subjects = {s for s, _, _ in triples}
    assert len(triples) == 3 and len(subjects) == 2  # the same _:x in both batches


def test_a_backend_aborting_mid_stream_raises_its_text_as_a_request_error():
    # Fuseki can answer 200, write rows, then append a Java exception.
    response = Response(
        "text/tab-separated-values",
        ["?s", "<http://ex/a>", "java.lang.NullPointerException: Node.hashCode()\t"],
    )
    rows = read(response).rows

    assert next(rows) == {"s": URIRef("http://ex/a")}
    with pytest.raises(Exceptions.RequestError) as raised:
        next(rows)
    assert raised.value.operation == "query"
    assert "NullPointerException" in raised.value.response_body


def test_json_results_are_still_read_when_the_server_cannot_send_tsv():
    response = Response(
        "application/sparql-results+json",
        [],
        text='{"head": {"vars": ["s", "n"]}, "results": {"bindings": ['
        '{"s": {"type": "uri", "value": "http://ex/a"},'
        ' "n": {"type": "literal", "value": "3",'
        ' "datatype": "http://www.w3.org/2001/XMLSchema#integer"}}]}}',
    )
    result = read(response)
    assert list(result.rows) == [
        {"s": URIRef("http://ex/a"), "n": Literal("3", datatype=XSD.integer)}
    ]


def test_an_unexpected_content_type_is_refused():
    with pytest.raises(ValueError, match="content type"):
        read(Response("text/html", []))


def test_a_broken_n_triples_line_is_the_one_reported():
    response = Response(
        "application/n-triples",
        ["<http://ex/a> <http://ex/p> <http://ex/b> .", "org.apache.jena.Oops: boom"],
    )
    with pytest.raises(Exceptions.RequestError) as raised:
        list(read(response).triples)
    assert raised.value.response_body == "org.apache.jena.Oops: boom"
