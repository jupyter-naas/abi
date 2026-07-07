from unittest.mock import MagicMock, Mock, patch

import rdflib
import pytest
import requests
from naas_abi_core.services.triple_store.adaptors.secondary.ApacheJenaTDB2 import (
    ApacheJenaTDB2,
)
from naas_abi_core.services.triple_store.TripleStorePorts import Exceptions
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

def _make_500_response(text: str = "Server error (mock)") -> Mock:
    resp = Mock(status_code=500)
    resp.text = text
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
    with pytest.raises(Exceptions.RequestError):
        adapter.insert(graph)

    assert adapter._session.post.call_count == 3  # 1 initial + 2 retries
    assert mock_sleep.call_count == 2


@patch("naas_abi_core.services.triple_store.adaptors.secondary.ApacheJenaTDB2.time.sleep")
def test_insert_does_not_retry_on_400(mock_sleep):
    adapter = _build_adapter()
    adapter.max_retries = 3

    bad_request = Mock(status_code=400)
    bad_request.text = "Malformed query (mock)"
    bad_request.raise_for_status.side_effect = requests.HTTPError(response=bad_request)
    adapter._session.post.return_value = bad_request

    graph = Graph()
    graph.add((URIRef("http://example.org/s"), RDF.type, URIRef("http://example.org/C")))

    with pytest.raises(Exceptions.RequestError):
        adapter.insert(graph)

    assert adapter._session.post.call_count == 1
    mock_sleep.assert_not_called()


# ---------------------------------------------------------------------------
# RequestError carries the server's diagnostics (status + body)
# ---------------------------------------------------------------------------

@patch("naas_abi_core.services.triple_store.adaptors.secondary.ApacheJenaTDB2.time.sleep")
def test_update_error_captures_status_and_body(mock_sleep):
    adapter = _build_adapter()
    adapter.max_retries = 0  # surface the failure on the first attempt

    body = "TDB2 transaction failed: java.io.IOException: No space left on device"
    adapter._session.post.return_value = _make_500_response(text=body)

    graph = Graph()
    graph.add((URIRef("http://example.org/s"), RDF.type, URIRef("http://example.org/C")))

    with pytest.raises(Exceptions.RequestError) as exc_info:
        adapter.insert(graph)

    err = exc_info.value
    assert err.operation == "update"
    assert err.status_code == 500
    assert err.endpoint == adapter.update_endpoint
    assert err.attempts == 1
    assert err.response_body == body
    # The human-readable summary used for the event message includes both the
    # status and the server's own words (the actual cause).
    detail = err.detail()
    assert "status=500" in detail
    assert "No space left on device" in detail


def test_update_error_body_is_truncated():
    adapter = _build_adapter()
    adapter.max_retries = 0

    huge = "x" * (adapter._MAX_ERROR_BODY + 500)
    adapter._session.post.return_value = _make_500_response(text=huge)

    graph = Graph()
    graph.add((URIRef("http://example.org/s"), RDF.type, URIRef("http://example.org/C")))

    with pytest.raises(Exceptions.RequestError) as exc_info:
        adapter.insert(graph)

    body = exc_info.value.response_body or ""
    assert len(body) <= adapter._MAX_ERROR_BODY + len("… [truncated]")
    assert body.endswith("… [truncated]")


def test_query_error_raises_request_error_with_query_operation():
    adapter = _build_adapter()
    adapter.max_retries = 0

    adapter._session.post.return_value = _make_500_response(text="boom")

    with pytest.raises(Exceptions.RequestError) as exc_info:
        adapter.query("SELECT ?s WHERE { ?s ?p ?o }")

    err = exc_info.value
    assert err.operation == "query"
    assert err.status_code == 500
    assert err.endpoint == adapter.query_endpoint


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

    with pytest.raises(Exceptions.RequestError, match="distributed write lock") as exc_info:
        adapter.insert(graph)

    assert exc_info.value.operation == "acquire_write_lock"
    assert mock_kv.set_if_not_exists.call_count == 3  # 1 + 2 retries
    assert mock_kv.delete_if_value_matches.call_count == 0


def test_distributed_lock_released_even_when_http_raises():
    """The distributed lock must be released even if the HTTP POST fails."""
    adapter, mock_kv = _build_adapter_with_kv()
    adapter.max_retries = 0  # No HTTP retries so the error surfaces immediately.

    err_response = Mock(status_code=500)
    err_response.text = "Server error (mock)"
    err_response.raise_for_status.side_effect = requests.HTTPError(response=err_response)
    adapter._session.post.return_value = err_response

    graph = Graph()
    graph.add((URIRef("http://example.org/s"), RDF.type, URIRef("http://example.org/C")))

    with pytest.raises(Exceptions.RequestError):
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


# ---------------------------------------------------------------------------
# Boot-time connectivity probe (_test_connection) resilience
#
# A restarting Fuseki can refuse connections or answer 500/503 for a few seconds
# while TDB2 attaches. Those blips must NOT crash the engine import; a *persistent*
# failure must surface the server's own body so the cause is diagnosable.
# ---------------------------------------------------------------------------

def _build_adapter_with_get(get_side_effect: list) -> ApacheJenaTDB2:
    """Build an adapter, driving the boot-time GET probe with ``get_side_effect``."""
    mock_session = MagicMock()
    mock_session.get.side_effect = get_side_effect
    mock_session.post.return_value = _ok_response()
    with patch(
        "naas_abi_core.services.triple_store.adaptors.secondary.ApacheJenaTDB2.requests.Session",
        return_value=mock_session,
    ):
        return ApacheJenaTDB2(jena_tdb2_url="http://localhost:3030/ds", timeout=30)


@patch("naas_abi_core.services.triple_store.adaptors.secondary.ApacheJenaTDB2.time.sleep")
def test_test_connection_retries_transient_500_then_succeeds(mock_sleep):
    # First probe 500s (Fuseki still attaching), second succeeds → construction
    # completes without raising.
    adapter = _build_adapter_with_get([_make_500_response(), _ok_response()])

    assert adapter._session.get.call_count == 2
    assert mock_sleep.call_count == 1


@patch("naas_abi_core.services.triple_store.adaptors.secondary.ApacheJenaTDB2.time.sleep")
def test_test_connection_retries_connection_error_then_succeeds(mock_sleep):
    # A refused connection while the server is coming up is transient, not fatal.
    adapter = _build_adapter_with_get(
        [requests.ConnectionError("connection refused"), _ok_response()]
    )

    assert adapter._session.get.call_count == 2
    assert mock_sleep.call_count == 1


@patch("naas_abi_core.services.triple_store.adaptors.secondary.ApacheJenaTDB2.time.sleep")
@patch.object(ApacheJenaTDB2, "_CONNECT_MAX_RETRIES", 2)
def test_test_connection_raises_request_error_after_retries_exhausted(mock_sleep):
    # A dataset that stays broken must surface a RequestError carrying the
    # server's body (the real cause), not a bare HTTPError.
    with pytest.raises(Exceptions.RequestError) as exc_info:
        _build_adapter_with_get(
            [_make_500_response(text="TDB2 recovery failed") for _ in range(3)]
        )

    err = exc_info.value
    assert err.operation == "connect"
    assert err.status_code == 500
    assert err.response_body == "TDB2 recovery failed"
    assert err.attempts == 3  # 1 initial + 2 retries
    assert mock_sleep.call_count == 2


@patch("naas_abi_core.services.triple_store.adaptors.secondary.ApacheJenaTDB2.time.sleep")
def test_test_connection_does_not_retry_non_retryable_status(mock_sleep):
    # A 401/404 is not transient — surface it immediately, no back-off.
    unauthorized = Mock(status_code=401)
    unauthorized.text = "Unauthorized"

    with pytest.raises(Exceptions.RequestError) as exc_info:
        _build_adapter_with_get([unauthorized])

    assert exc_info.value.operation == "connect"
    assert exc_info.value.status_code == 401
    assert exc_info.value.attempts == 1
    mock_sleep.assert_not_called()
