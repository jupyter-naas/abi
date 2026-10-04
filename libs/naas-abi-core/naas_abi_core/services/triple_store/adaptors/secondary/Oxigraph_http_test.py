"""The Oxigraph HTTP adapter against a real SPARQL endpoint: ``oxigraph_server``,
the store ``abi dev`` runs, served in-process (no Docker)."""

import socket
import threading
import time

import pytest
from naas_abi_core.services.triple_store.adaptors.secondary.Oxigraph import Oxigraph
from naas_abi_core.services.triple_store.tests.triple_store__secondary_adapter__generic_test import (
    GenericTripleStoreSecondaryAdapterTest,
)

uvicorn = pytest.importorskip("uvicorn")
pytest.importorskip("pyoxigraph")


@pytest.fixture(scope="module")
def endpoint(tmp_path_factory):
    from naas_abi_core.services.triple_store.oxigraph_server import create_app

    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    server = uvicorn.Server(
        uvicorn.Config(
            create_app(str(tmp_path_factory.mktemp("oxigraph"))),
            host="127.0.0.1",
            port=port,
            log_level="warning",
        )
    )
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    deadline = time.monotonic() + 10
    while not server.started:
        if time.monotonic() > deadline:
            pytest.fail("oxigraph_server did not start")
        time.sleep(0.05)
    yield f"http://127.0.0.1:{port}"
    server.should_exit = True
    thread.join(timeout=5)


class TestOxigraphHTTP(GenericTripleStoreSecondaryAdapterTest):
    @pytest.fixture
    def adapter(self, endpoint):
        return Oxigraph(endpoint)

    @pytest.fixture
    def supports_named_graphs(self) -> bool:
        return True

    def test_creating_an_existing_graph_raises_the_ports_error(self, adapter):
        # Oxigraph refuses CREATE GRAPH on an existing (even empty) graph;
        # callers must get the port's typed error, not an HTTP 500.
        from naas_abi_core.services.triple_store.TripleStorePorts import Exceptions
        from rdflib import URIRef

        graph = URIRef("http://test.example.org/graph/created-twice")
        adapter.create_graph(graph)

        with pytest.raises(Exceptions.GraphAlreadyExistsError):
            adapter.create_graph(graph)


def test_streams_are_read_from_the_http_response_not_from_query(endpoint, monkeypatch):
    from rdflib import Graph, Literal, URIRef

    adapter = Oxigraph(endpoint)
    graph_name = URIRef("http://test.example.org/stream/http")
    g = Graph()
    for n in range(2500):  # more than one N-Triples batch
        g.add(
            (
                URIRef(f"http://test.example.org/s{n}"),
                URIRef("http://test.example.org/n"),
                Literal(n),
            )
        )
    adapter.insert(g, graph_name)

    def materialized(*args, **kwargs):
        raise AssertionError("streams must not read the whole result")

    monkeypatch.setattr(adapter, "query", materialized)
    monkeypatch.setattr(adapter, "get", materialized)
    try:
        with adapter.query_stream(
            f"SELECT ?n WHERE {{ GRAPH <{graph_name}> {{ ?s ?p ?n }} }}"
        ) as result:
            assert sorted(int(row["n"]) for row in result.rows) == list(range(2500))
        with adapter.export(graph_name) as triples:
            assert set(triples) == set(g)
        with adapter.export() as default_graph:
            assert list(default_graph) == []  # the data is in a named graph
    finally:
        monkeypatch.undo()
        adapter.remove(g, graph_name)


def test_the_dev_server_streams_results_instead_of_buffering_them(endpoint):
    import requests

    with requests.post(
        f"{endpoint}/query",
        headers={
            "Content-Type": "application/sparql-query",
            "Accept": "text/tab-separated-values",
        },
        data=b"SELECT ?n WHERE { VALUES ?n { 1 2 3 } }",
        stream=True,
    ) as response:
        assert response.headers.get("transfer-encoding") == "chunked"
        assert "content-length" not in response.headers
        assert response.text.splitlines() == ["?n", "1", "2", "3"]

    bad = requests.post(
        f"{endpoint}/query",
        headers={"Content-Type": "application/sparql-query"},
        data=b"SELECT WHERE {",
    )
    assert bad.status_code == 400  # still a status, not a broken stream
