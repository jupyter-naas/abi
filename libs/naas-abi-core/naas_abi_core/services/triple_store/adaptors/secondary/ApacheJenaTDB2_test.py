from unittest.mock import Mock, patch

import rdflib
import pytest
from naas_abi_core.services.triple_store.adaptors.secondary.ApacheJenaTDB2 import (
    ApacheJenaTDB2,
)
from rdflib import RDF, Graph, Literal, URIRef


def _build_adapter() -> ApacheJenaTDB2:
    with patch(
        "naas_abi_core.services.triple_store.adaptors.secondary.ApacheJenaTDB2.requests.get"
    ) as mock_get:
        mock_get.return_value = Mock(status_code=200)
        mock_get.return_value.raise_for_status = Mock()
        return ApacheJenaTDB2(jena_tdb2_url="http://localhost:3030/ds", timeout=30)


def test_init_endpoints():
    adapter = _build_adapter()

    assert adapter.jena_tdb2_url == "http://localhost:3030/ds"
    assert adapter.query_endpoint == "http://localhost:3030/ds/query"
    assert adapter.update_endpoint == "http://localhost:3030/ds/update"
    assert adapter.data_endpoint == "http://localhost:3030/ds/data"


@pytest.mark.parametrize(
    "graph_name, expected_fragment",
    [
        (None, b"INSERT DATA"),
        (
            URIRef("http://example.org/graphs/people"),
            b"GRAPH <http://example.org/graphs/people>",
        ),
    ],
)
def test_insert_posts_expected_sparql_update(graph_name, expected_fragment):
    adapter = _build_adapter()
    graph = Graph()
    graph.add(
        (
            URIRef("http://example.org/alice"),
            RDF.type,
            URIRef("http://example.org/Person"),
        )
    )

    with patch(
        "naas_abi_core.services.triple_store.adaptors.secondary.ApacheJenaTDB2.requests.post"
    ) as mock_post:
        mock_post.return_value = Mock(status_code=200)
        mock_post.return_value.raise_for_status = Mock()

        adapter.insert(graph, graph_name=graph_name)

        assert mock_post.call_args.args[0] == adapter.update_endpoint
        call_kwargs = mock_post.call_args.kwargs
        assert call_kwargs["headers"]["Content-Type"] == "application/sparql-update"
        assert expected_fragment in call_kwargs["data"]


@pytest.mark.parametrize(
    "graph_name, expected_fragment",
    [
        (None, b"DELETE DATA"),
        (
            URIRef("http://example.org/graphs/people"),
            b"GRAPH <http://example.org/graphs/people>",
        ),
    ],
)
def test_remove_posts_expected_sparql_update(graph_name, expected_fragment):
    adapter = _build_adapter()
    graph = Graph()
    graph.add(
        (
            URIRef("http://example.org/alice"),
            URIRef("http://example.org/name"),
            Literal("Alice"),
        )
    )

    with patch(
        "naas_abi_core.services.triple_store.adaptors.secondary.ApacheJenaTDB2.requests.post"
    ) as mock_post:
        mock_post.return_value = Mock(status_code=200)
        mock_post.return_value.raise_for_status = Mock()

        adapter.remove(graph, graph_name=graph_name)

        assert mock_post.call_args.args[0] == adapter.update_endpoint
        call_kwargs = mock_post.call_args.kwargs
        assert call_kwargs["headers"]["Content-Type"] == "application/sparql-update"
        assert expected_fragment in call_kwargs["data"]


def test_query_update_routes_to_update_endpoint():
    adapter = _build_adapter()

    response = Mock(status_code=200)
    response.raise_for_status = Mock()

    with patch(
        "naas_abi_core.services.triple_store.adaptors.secondary.ApacheJenaTDB2.requests.post",
        return_value=response,
    ) as mock_post:
        adapter.query(
            'INSERT DATA { <http://example.org/s> <http://example.org/p> "o" . }'
        )

    assert mock_post.call_args.args[0] == adapter.update_endpoint


def test_query_select_returns_rows():
    adapter = _build_adapter()

    response = Mock(status_code=200)
    response.raise_for_status = Mock()
    response.headers = {"Content-Type": "application/sparql-results+json"}
    response.text = '{"head":{"vars":["s"]},"results":{"bindings":[{"s":{"type":"uri","value":"http://example.org/alice"}}]}}'

    with patch(
        "naas_abi_core.services.triple_store.adaptors.secondary.ApacheJenaTDB2.requests.post",
        return_value=response,
    ):
        result = list(adapter.query("SELECT ?s WHERE { ?s ?p ?o }"))

    assert len(result) == 1
    assert str(result[0].s) == "http://example.org/alice"


def test_query_construct_returns_graph():
    adapter = _build_adapter()

    response = Mock(status_code=200)
    response.raise_for_status = Mock()
    response.headers = {"Content-Type": "application/n-triples"}
    response.text = '<http://example.org/alice> <http://example.org/name> "Alice" .\n'

    with patch(
        "naas_abi_core.services.triple_store.adaptors.secondary.ApacheJenaTDB2.requests.post",
        return_value=response,
    ):
        result = adapter.query("CONSTRUCT { ?s ?p ?o } WHERE { ?s ?p ?o }")

    assert isinstance(result, Graph)
    assert len(result) == 1


def test_query_ask_returns_rdflib_ask_result():
    adapter = _build_adapter()

    response = Mock(status_code=200)
    response.raise_for_status = Mock()
    response.headers = {"Content-Type": "application/sparql-results+json"}
    response.text = '{"head":{},"boolean":true}'

    with patch(
        "naas_abi_core.services.triple_store.adaptors.secondary.ApacheJenaTDB2.requests.post",
        return_value=response,
    ):
        result = adapter.query("ASK WHERE { ?s ?p ?o }")

    assert isinstance(result, rdflib.query.Result)
    assert result.askAnswer is True
