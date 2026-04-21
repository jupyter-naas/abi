from unittest.mock import MagicMock, Mock, patch

import rdflib
import pytest
import requests
from naas_abi_core.services.triple_store.adaptors.secondary.ApacheJenaTDB2 import (
    ApacheJenaTDB2,
)
from rdflib import RDF, Graph, Literal, URIRef
from rdflib.term import Variable


def _ok_response() -> Mock:
    resp = Mock(status_code=200)
    resp.raise_for_status = Mock()
    return resp


def _build_adapter() -> ApacheJenaTDB2:
    """Build an adapter with a mocked session so no real HTTP is made."""
    mock_session = MagicMock()
    mock_session.get.return_value = _ok_response()
    mock_session.post.return_value = _ok_response()
    with patch(
        "naas_abi_core.services.triple_store.adaptors.secondary.ApacheJenaTDB2.requests.Session",
        return_value=mock_session,
    ):
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

    adapter._session.post.return_value = _ok_response()
    adapter.insert(graph, graph_name)

    assert adapter._session.post.call_args.args[0] == adapter.update_endpoint
    call_kwargs = adapter._session.post.call_args.kwargs
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

    adapter._session.post.return_value = _ok_response()
    adapter.remove(graph, graph_name)

    assert adapter._session.post.call_args.args[0] == adapter.update_endpoint
    call_kwargs = adapter._session.post.call_args.kwargs
    assert call_kwargs["headers"]["Content-Type"] == "application/sparql-update"
    assert expected_fragment in call_kwargs["data"]


def test_query_update_routes_to_update_endpoint():
    adapter = _build_adapter()
    adapter._session.post.return_value = _ok_response()

    adapter.query('INSERT DATA { <http://example.org/s> <http://example.org/p> "o" . }')

    assert adapter._session.post.call_args.args[0] == adapter.update_endpoint


def test_query_select_returns_rows():
    adapter = _build_adapter()

    response = _ok_response()
    response.headers = {"Content-Type": "application/sparql-results+json"}
    response.text = '{"head":{"vars":["s"]},"results":{"bindings":[{"s":{"type":"uri","value":"http://example.org/alice"}}]}}'
    adapter._session.post.return_value = response

    result = list(adapter.query("SELECT ?s WHERE { ?s ?p ?o }"))

    assert len(result) == 1
    assert str(result[0].s) == "http://example.org/alice"


def test_query_construct_returns_graph():
    adapter = _build_adapter()

    response = _ok_response()
    response.headers = {"Content-Type": "application/n-triples"}
    response.text = '<http://example.org/alice> <http://example.org/name> "Alice" .\n'
    adapter._session.post.return_value = response

    result = adapter.query("CONSTRUCT { ?s ?p ?o } WHERE { ?s ?p ?o }")

    assert isinstance(result, Graph)
    assert len(result) == 1


def test_query_ask_returns_rdflib_ask_result():
    adapter = _build_adapter()

    response = _ok_response()
    response.headers = {"Content-Type": "application/sparql-results+json"}
    response.text = '{"head":{},"boolean":true}'
    adapter._session.post.return_value = response

    result = adapter.query("ASK WHERE { ?s ?p ?o }")

    assert isinstance(result, rdflib.query.Result)
    assert result.askAnswer is True


def test_graph_management_queries_delegate_to_query():
    adapter = _build_adapter()
    graph_name = URIRef("http://example.org/graphs/g1")

    with patch.object(
        adapter, "query", return_value=rdflib.query.Result("SELECT")
    ) as mock_query:
        adapter.create_graph(graph_name)
        adapter.clear_graph(graph_name)
        adapter.clear_graph()
        adapter.drop_graph(graph_name)

    assert mock_query.call_args_list[0].args[0] == f"CREATE GRAPH <{str(graph_name)}>"
    assert mock_query.call_args_list[1].args[0] == f"CLEAR GRAPH <{str(graph_name)}>"
    assert mock_query.call_args_list[2].args[0] == "CLEAR DEFAULT"
    assert mock_query.call_args_list[3].args[0] == f"DROP GRAPH <{str(graph_name)}>"


def test_list_graphs_returns_graph_uris_from_query_rows():
    adapter = _build_adapter()
    graph_name = URIRef("http://example.org/graphs/g1")

    query_result = rdflib.query.Result("SELECT")
    query_result.vars = [Variable("g")]
    query_result.bindings = [{Variable("g"): graph_name}]

    with patch.object(adapter, "query", return_value=query_result):
        graphs = adapter.list_graphs()

    assert graphs == [graph_name]


# ---------------------------------------------------------------------------
# Retry behaviour
# ---------------------------------------------------------------------------

def _make_500_response() -> Mock:
    resp = Mock(status_code=500)
    resp.raise_for_status.side_effect = requests.HTTPError(response=resp)
    return resp


@patch("naas_abi_core.services.triple_store.adaptors.secondary.ApacheJenaTDB2.time.sleep")
def test_insert_retries_on_500_and_succeeds(mock_sleep):
    adapter = _build_adapter()
    adapter.max_retries = 2
    adapter.retry_delay = 0.1

    graph = Graph()
    graph.add((URIRef("http://example.org/s"), RDF.type, URIRef("http://example.org/C")))

    adapter._session.post.side_effect = [_make_500_response(), _ok_response()]
    adapter.insert(graph)

    assert adapter._session.post.call_count == 2
    assert mock_sleep.call_count == 1


@patch("naas_abi_core.services.triple_store.adaptors.secondary.ApacheJenaTDB2.time.sleep")
def test_insert_raises_after_all_retries_exhausted(mock_sleep):
    adapter = _build_adapter()
    adapter.max_retries = 2
    adapter.retry_delay = 0.1

    graph = Graph()
    graph.add((URIRef("http://example.org/s"), RDF.type, URIRef("http://example.org/C")))

    adapter._session.post.side_effect = [
        _make_500_response(),
        _make_500_response(),
        _make_500_response(),
    ]
    with pytest.raises(requests.HTTPError):
        adapter.insert(graph)

    assert adapter._session.post.call_count == 3  # 1 initial + 2 retries
    assert mock_sleep.call_count == 2


@patch("naas_abi_core.services.triple_store.adaptors.secondary.ApacheJenaTDB2.time.sleep")
def test_insert_does_not_retry_on_400(mock_sleep):
    adapter = _build_adapter()
    adapter.max_retries = 3

    bad_request = Mock(status_code=400)
    bad_request.raise_for_status.side_effect = requests.HTTPError(response=bad_request)
    adapter._session.post.return_value = bad_request

    graph = Graph()
    graph.add((URIRef("http://example.org/s"), RDF.type, URIRef("http://example.org/C")))

    with pytest.raises(requests.HTTPError):
        adapter.insert(graph)

    assert adapter._session.post.call_count == 1
    mock_sleep.assert_not_called()


def test_write_lock_is_present():
    """The adapter must expose a threading.Lock for write serialisation."""
    import threading

    adapter = _build_adapter()
    assert isinstance(adapter._write_lock, type(threading.Lock()))


# ---------------------------------------------------------------------------
# Distributed lock via KeyValueService
# ---------------------------------------------------------------------------

def _build_adapter_with_kv() -> tuple:
    """Return (adapter, mock_kv_service) with a mocked KeyValueService injected."""
    mock_kv = MagicMock()
    # Default: lock always acquired on first attempt.
    mock_kv.set_if_not_exists.return_value = True
    mock_kv.delete_if_value_matches.return_value = True

    mock_session = MagicMock()
    mock_session.get.return_value = _ok_response()
    mock_session.post.return_value = _ok_response()
    with patch(
        "naas_abi_core.services.triple_store.adaptors.secondary.ApacheJenaTDB2.requests.Session",
        return_value=mock_session,
    ):
        adapter = ApacheJenaTDB2(
            jena_tdb2_url="http://localhost:3030/ds",
            timeout=30,
            key_value_service=mock_kv,
        )
    return adapter, mock_kv


def test_distributed_lock_acquired_and_released_on_insert():
    adapter, mock_kv = _build_adapter_with_kv()

    graph = Graph()
    graph.add((URIRef("http://example.org/s"), RDF.type, URIRef("http://example.org/C")))
    adapter.insert(graph)

    assert mock_kv.set_if_not_exists.call_count == 1
    call_kwargs = mock_kv.set_if_not_exists.call_args
    assert call_kwargs.args[0] == adapter._dataset_lock_key
    assert call_kwargs.kwargs["ttl"] == adapter.timeout + 10

    assert mock_kv.delete_if_value_matches.call_count == 1
    # The token passed to release must match the one used to acquire.
    acquire_token = mock_kv.set_if_not_exists.call_args.args[1]
    release_token = mock_kv.delete_if_value_matches.call_args.args[1]
    assert acquire_token == release_token


@patch("naas_abi_core.services.triple_store.adaptors.secondary.ApacheJenaTDB2.time.sleep")
def test_distributed_lock_retries_when_busy_then_succeeds(mock_sleep):
    adapter, mock_kv = _build_adapter_with_kv()
    adapter.max_retries = 2

    # Lock busy on first attempt, free on second.
    mock_kv.set_if_not_exists.side_effect = [False, True]

    graph = Graph()
    graph.add((URIRef("http://example.org/s"), RDF.type, URIRef("http://example.org/C")))
    adapter.insert(graph)

    assert mock_kv.set_if_not_exists.call_count == 2
    assert mock_sleep.call_count == 1
    assert mock_kv.delete_if_value_matches.call_count == 1


@patch("naas_abi_core.services.triple_store.adaptors.secondary.ApacheJenaTDB2.time.sleep")
def test_distributed_lock_raises_after_all_attempts_exhausted(mock_sleep):
    adapter, mock_kv = _build_adapter_with_kv()
    adapter.max_retries = 2

    mock_kv.set_if_not_exists.return_value = False  # Lock never released.

    graph = Graph()
    graph.add((URIRef("http://example.org/s"), RDF.type, URIRef("http://example.org/C")))

    with pytest.raises(RuntimeError, match="distributed write lock"):
        adapter.insert(graph)

    assert mock_kv.set_if_not_exists.call_count == 3  # 1 + 2 retries
    assert mock_kv.delete_if_value_matches.call_count == 0


def test_distributed_lock_released_even_when_http_raises():
    """The distributed lock must be released even if the HTTP POST fails."""
    adapter, mock_kv = _build_adapter_with_kv()
    adapter.max_retries = 0  # No HTTP retries so the error surfaces immediately.

    err_response = Mock(status_code=500)
    err_response.raise_for_status.side_effect = requests.HTTPError(response=err_response)
    adapter._session.post.return_value = err_response

    graph = Graph()
    graph.add((URIRef("http://example.org/s"), RDF.type, URIRef("http://example.org/C")))

    with pytest.raises(requests.HTTPError):
        adapter.insert(graph)

    # Lock must still be released in the finally block.
    assert mock_kv.delete_if_value_matches.call_count == 1


def test_dataset_lock_key_is_stable_and_url_scoped():
    """Two adapters for different URLs must get different lock keys."""
    adapter_a, _ = _build_adapter_with_kv()

    mock_kv = MagicMock()
    mock_kv.set_if_not_exists.return_value = True
    mock_session = MagicMock()
    mock_session.get.return_value = _ok_response()
    mock_session.post.return_value = _ok_response()
    with patch(
        "naas_abi_core.services.triple_store.adaptors.secondary.ApacheJenaTDB2.requests.Session",
        return_value=mock_session,
    ):
        adapter_b = ApacheJenaTDB2(
            jena_tdb2_url="http://other-host:3030/ds2",
            key_value_service=mock_kv,
        )

    assert adapter_a._dataset_lock_key != adapter_b._dataset_lock_key


# ---------------------------------------------------------------------------
# clear_graph default graph
# ---------------------------------------------------------------------------

def test_clear_graph_with_name_emits_clear_graph():
    adapter = _build_adapter()
    graph_name = URIRef("http://example.org/graphs/g1")

    with patch.object(adapter, "query", return_value=rdflib.query.Result("SELECT")) as mock_query:
        adapter.clear_graph(graph_name)

    mock_query.assert_called_once_with(f"CLEAR GRAPH <{str(graph_name)}>")


def test_clear_graph_without_name_emits_clear_default():
    adapter = _build_adapter()

    with patch.object(adapter, "query", return_value=rdflib.query.Result("SELECT")) as mock_query:
        adapter.clear_graph()

    mock_query.assert_called_once_with("CLEAR DEFAULT")
