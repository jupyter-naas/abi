"""Who the `abi dev` SPARQL server answers: its own host, its token, SPARQL media types."""

from __future__ import annotations

from urllib.parse import urlencode

import pytest

pytest.importorskip("pyoxigraph")

from naas_abi_core.services.triple_store.oxigraph_server import (
    _host_name,
    create_app,
)
from starlette.testclient import TestClient

TOKEN = "per-run-token"
AUTH = {"Authorization": f"Bearer {TOKEN}"}
HOST = {"Host": "127.0.0.1:7878"}
UPDATE = "INSERT DATA { <http://example.org/s> <http://example.org/p> \"o\" }"
ASK = "ASK { <http://example.org/s> ?p ?o }"


@pytest.fixture
def client(tmp_path):
    return TestClient(create_app(str(tmp_path / "store"), token=TOKEN))


def _stored(client: TestClient) -> bool:
    response = client.get(
        "/query",
        params={"query": ASK},
        headers={**HOST, **AUTH, "Accept": "application/sparql-results+json"},
    )
    assert response.status_code == 200
    return response.json()["boolean"] is True


@pytest.mark.parametrize(
    ("content_type", "body"),
    [
        ("application/x-www-form-urlencoded", urlencode({"update": UPDATE})),
        ("text/plain", UPDATE),
        ("multipart/form-data; boundary=x", UPDATE),
        ("", UPDATE),
    ],
)
def test_dev_sparql_server_keeps_updates_to_the_sparql_media_type(
    client, content_type, body
):
    refused = client.post(
        "/update",
        content=body,
        headers={**HOST, **AUTH, "Content-Type": content_type},
    )

    assert refused.status_code == 415
    assert not _stored(client)
    applied = client.post(
        "/update",
        content=UPDATE,
        headers={**HOST, **AUTH, "Content-Type": "application/sparql-update"},
    )
    assert applied.status_code == 204
    assert _stored(client)


def test_dev_sparql_server_keeps_queries_and_bulk_writes_to_their_media_types(client):
    form = client.post(
        "/query",
        content=urlencode({"query": ASK}),
        headers={**HOST, **AUTH, "Content-Type": "application/x-www-form-urlencoded"},
    )
    text = client.post(
        "/store?default",
        content='<http://example.org/s> <http://example.org/p> "o" .',
        headers={**HOST, **AUTH, "Content-Type": "text/plain"},
    )

    assert (form.status_code, text.status_code) == (415, 415)
    assert not _stored(client)


@pytest.mark.parametrize("host", ["elsewhere.example", "elsewhere.example:7878", ""])
def test_dev_sparql_server_keeps_to_its_own_host(client, host):
    response = client.get(
        "/query",
        params={"query": ASK},
        headers={"Host": host, **AUTH, "Accept": "application/sparql-results+json"},
    )

    assert response.status_code == 421


@pytest.mark.parametrize("host", ["127.0.0.1:7878", "localhost:7878", "[::1]:7878"])
def test_dev_sparql_server_serves_loopback_names(client, host):
    response = client.get(
        "/query",
        params={"query": ASK},
        headers={"Host": host, **AUTH, "Accept": "application/sparql-results+json"},
    )

    assert response.status_code == 200


@pytest.mark.parametrize("credential", [None, "Bearer wrong", f"Basic {TOKEN}", TOKEN])
def test_dev_sparql_server_keeps_to_its_token(client, credential):
    headers = {**HOST, "Content-Type": "application/sparql-update"}
    if credential is not None:
        headers["Authorization"] = credential

    response = client.post("/update", content=UPDATE, headers=headers)

    assert response.status_code == 401
    assert not _stored(client)
    assert client.get("/health", headers=HOST).status_code == 200


def test_host_names_drop_their_port():
    assert _host_name("127.0.0.1:7878") == "127.0.0.1"
    assert _host_name("[::1]:7878") == "::1"
    assert _host_name("LOCALHOST") == "localhost"
    assert _host_name("::1") == "::1"
