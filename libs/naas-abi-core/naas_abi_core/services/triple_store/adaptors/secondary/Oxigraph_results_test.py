"""Oxigraph.query must return what the triple store port declares (and NATS can send)."""

from unittest.mock import Mock, patch

import rdflib
from naas_abi_core.services.triple_store.adaptors.secondary.Oxigraph import Oxigraph
from rdflib import Graph, Literal, URIRef, Variable


def _adapter() -> Oxigraph:
    with patch.object(Oxigraph, "_test_connection"):
        return Oxigraph("http://oxigraph.test:7878")


def _response(content_type: str, text: str) -> Mock:
    response = Mock()
    response.headers = {"Content-Type": content_type}
    response.text = text
    response.raise_for_status = Mock()
    return response


def test_select_returns_an_rdflib_select_result():
    adapter = _adapter()
    body = (
        '{"head":{"vars":["s","name"]},"results":{"bindings":['
        '{"s":{"type":"uri","value":"http://example.org/alice"},'
        '"name":{"type":"literal","value":"Alice","xml:lang":"en"}},'
        '{"s":{"type":"uri","value":"http://example.org/bob"}}'
        "]}}"
    )
    with patch("requests.post", return_value=_response("application/sparql-results+json", body)):
        result = adapter.query("SELECT ?s ?name WHERE { ?s ?p ?name }")

    assert isinstance(result, rdflib.query.Result) and result.type == "SELECT"
    assert result.vars == [Variable("s"), Variable("name")]
    rows = list(result)
    assert rows[0].name == Literal("Alice", lang="en")
    assert rows[1].s == URIRef("http://example.org/bob")
    assert rows[1].name is None
    assert len(list(result)) == 2  # re-iterable, unlike the iterator it replaces


def test_select_without_rows_keeps_its_vars():
    adapter = _adapter()
    body = '{"head":{"vars":["g"]},"results":{"bindings":[]}}'
    with patch("requests.post", return_value=_response("application/sparql-results+json", body)):
        result = adapter.query("SELECT ?g WHERE { GRAPH ?g { ?s ?p ?o } }")

    assert result.vars == [Variable("g")] and list(result) == []


def test_ask_returns_its_answer():
    adapter = _adapter()
    with patch(
        "requests.post",
        return_value=_response("application/sparql-results+json", '{"head":{},"boolean":true}'),
    ):
        result = adapter.query("ASK { ?s ?p ?o }")

    assert isinstance(result, rdflib.query.Result) and result.type == "ASK"
    assert result.askAnswer is True


def test_select_results_cross_nats():
    """The NATS primary adapter serializes it (it rejected the old iterator)."""
    from naas_abi_core.services.triple_store.adapters.primary.triple_store__primary_adapter__NATS import (
        _query_result_to_pb,
    )

    adapter = _adapter()
    body = '{"head":{"vars":["s"]},"results":{"bindings":[{"s":{"type":"uri","value":"http://x/a"}}]}}'
    with patch("requests.post", return_value=_response("application/sparql-results+json", body)):
        result = adapter.query("SELECT ?s WHERE { ?s ?p ?o }")

    message = _query_result_to_pb(result)
    assert message.result_type == "SELECT"
    assert message.select.rows[0].bindings["s"] == "<http://x/a>"


def test_construct_returns_a_graph():
    adapter = _adapter()
    with patch(
        "requests.post",
        return_value=_response("application/n-triples", "<http://x/a> <http://x/p> <http://x/b> .\n"),
    ):
        result = adapter.query("CONSTRUCT { ?s ?p ?o } WHERE { ?s ?p ?o }")

    assert isinstance(result, Graph) and len(result) == 1
