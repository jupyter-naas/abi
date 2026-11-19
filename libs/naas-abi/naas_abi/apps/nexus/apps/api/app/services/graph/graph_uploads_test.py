"""Graph uploads are parsed as data, off the event loop; caches stay per graph.

Uploads load no remote document (JSON-LD contexts are embedded or refused),
answer with fixed messages, are capped in size and parsed in a worker. A write
to one graph moves the cache keys of the scopes that read it, and no others,
and the cache directory is bounded.
"""

from __future__ import annotations

import asyncio
import json
import os
import threading
import time
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from fastapi import FastAPI
from naas_abi import ABIModule
from naas_abi.apps.nexus.apps.api.app.services.graph.testing import (
    acting_as_header,
    client,
    knowledge_team,
)
from naas_abi.apps.nexus.apps.api.app.services.workspaces.adapters.secondary import (
    resource_access_postgres as saved_policies,
)
from naas_abi.apps.nexus.graph_policy_config import WorkspaceGraphPolicyConfig
from naas_abi_core.engine.IEngine import IEngine
from naas_abi_core.services.triple_store.adaptors.secondary.TripleStoreService__SecondaryAdaptor__OxigraphEmbedded import (  # noqa: E501
    TripleStoreService__SecondaryAdaptor__OxigraphEmbedded as OxigraphEmbedded,
)
from naas_abi_core.services.triple_store.TripleStoreService import TripleStoreService
from naas_abi_core.utils import rdf_upload
from rdflib import Graph

_CONFIG = SimpleNamespace(
    configuration=SimpleNamespace(
        nexus_config=SimpleNamespace(ontology_base_uri="http://ontology.naas.ai/nexus/")
    )
)
with patch.object(ABIModule, "get_instance", return_value=_CONFIG):
    from naas_abi.apps.nexus.apps.api.app.services.graph import service as graph_service
    from naas_abi.apps.nexus.apps.api.app.services.graph.adapters.primary import (
        graph__primary_adapter__FastAPI as api,
    )
    from naas_abi.apps.nexus.apps.api.app.services.graph.service import GraphService

WS = "ws-1"
TURTLE = b"@prefix owl: <http://www.w3.org/2002/07/owl#> . <urn:a> a owl:NamedIndividual ."


class _Bus:
    def publish_many(self, *_args, **_kwargs) -> None:
        return None


class _Session:
    def __call__(self):
        return self

    async def __aenter__(self):
        return None

    async def __aexit__(self, *_args):
        return False


class _Listener:
    def __init__(self) -> None:
        self.hits: list[str] = []
        listener = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:  # noqa: N802
                listener.hits.append(self.path)
                body = json.dumps({"@context": {"name": "http://schema.org/name"}}).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/ld+json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *args: object) -> None:
                pass

        self._httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.port = self._httpd.server_address[1]
        threading.Thread(target=self._httpd.serve_forever, args=(0.05,), daemon=True).start()

    def close(self) -> None:
        self._httpd.shutdown()
        self._httpd.server_close()


@pytest.fixture
def listener() -> Iterator[_Listener]:
    srv = _Listener()
    yield srv
    srv.close()


@pytest.fixture
def stack(tmp_path, monkeypatch):
    with knowledge_team() as team:
        store = TripleStoreService(OxigraphEmbedded(str(tmp_path / "ox")))
        store.set_services(IEngine.Services(iam=team.iam, bus=_Bus()))

        async def saved(_db, workspace_id, _kind):
            return SimpleNamespace(data=WorkspaceGraphPolicyConfig().model_dump(), revision=1)

        monkeypatch.setattr(saved_policies, "load_resource_policy", saved)
        from naas_abi.apps.nexus.apps.api.app.core import database

        monkeypatch.setattr(database, "AsyncSessionLocal", _Session())
        app = FastAPI()
        app.include_router(api.router, prefix="/api/graph")
        app.dependency_overrides[api.get_graph_service] = lambda: GraphService(lambda: store)
        acting_as_header(app)
        yield app
        OxigraphEmbedded._stores.pop(str(tmp_path / "ox"), None)


async def _analyze(http, name: str, content: bytes):
    return await http.post(
        "/api/graph/analyze",
        data={"workspace_id": WS},
        files={"file": (name, content, "application/octet-stream")},
    )


def _jsonld(context: object) -> bytes:
    return json.dumps({"@context": context, "@id": "urn:a", "name": "x"}).encode()


@pytest.mark.asyncio
async def test_graph_uploads_keep_json_ld_to_embedded_contexts(stack, listener) -> None:
    contexts = [
        f"http://127.0.0.1:{listener.port}/ctx",
        f"http://127.0.0.1:{listener.port}/missing",
        "http://127.0.0.1:1/",
        "file:///etc/hostname",
        "file:///etc/definitely-not-here",
    ]
    async with client(stack, "viewer") as viewer:
        answers = [(await _analyze(viewer, "x.jsonld", _jsonld(c))) for c in contexts]
        embedded = await _analyze(viewer, "x.jsonld", _jsonld({"name": "http://schema.org/name"}))
    assert listener.hits == []
    assert {(a.status_code, a.json()["detail"]) for a in answers} == {
        (400, f"Failed to parse file: {rdf_upload.EMBEDDED_CONTEXTS_ONLY}")
    }
    assert embedded.status_code == 200, embedded.text
    assert embedded.json()["total_triples"] == 1


@pytest.mark.asyncio
async def test_graph_uploads_keep_error_messages_fixed(stack) -> None:
    async with client(stack, "viewer") as viewer:
        broken = await _analyze(viewer, "x.ttl", b"<urn:a> <urn:p> 'unterminated")
    assert broken.status_code == 400
    assert broken.json()["detail"] == f"Failed to parse file: {rdf_upload.NOT_PARSED}"


@pytest.mark.asyncio
async def test_graph_uploads_keep_the_event_loop_free(stack, monkeypatch) -> None:
    """A slow parse holds its own request only; another request is answered."""

    def slow_parse(content: bytes, fmt: str, *, timeout: float) -> Graph:
        time.sleep(1.5)
        return Graph()

    monkeypatch.setattr(rdf_upload, "parse_upload", slow_parse)
    async with client(stack, "viewer") as viewer, client(stack, "member") as member:
        upload = asyncio.create_task(_analyze(viewer, "x.ttl", TURTLE))
        await asyncio.sleep(0.2)
        started = time.monotonic()
        listing = await member.get("/api/graph/list", params={"workspace_id": WS})
        waited = time.monotonic() - started
        analysed = await upload
    assert listing.status_code == 200
    assert analysed.status_code == 200
    assert waited < 1.0


@pytest.mark.asyncio
async def test_graph_uploads_keep_to_the_size_cap(stack, monkeypatch) -> None:
    monkeypatch.setattr(api, "GRAPH_UPLOAD_MAX_BYTES", 64)
    async with client(stack, "member") as member:
        too_big = await _analyze(member, "x.ttl", TURTLE + b" " * 64)
        imported = await member.post(
            "/api/graph/import",
            data={"workspace_id": WS, "graph_uri": "urn:g"},
            files={"file": ("x.ttl", TURTLE + b" " * 64, "text/turtle")},
        )
    assert too_big.status_code == 413
    assert imported.status_code == 413


@pytest.mark.asyncio
async def test_graph_import_still_writes_named_individuals(stack) -> None:
    async with client(stack, "admin") as admin:
        created = await admin.post("/api/graph/create", json={"workspace_id": WS, "label": "A"})
        graph_uri = created.json()["uri"]
        imported = await admin.post(
            "/api/graph/import",
            data={"workspace_id": WS, "graph_uri": graph_uri},
            files={"file": ("x.ttl", TURTLE, "text/turtle")},
        )
    assert imported.status_code == 200, imported.text
    assert imported.json() == {"status": "imported", "count": 1}


def _scoped(namespace: str, *graphs: str) -> SimpleNamespace:
    return SimpleNamespace(
        cache_namespace=namespace, scope=SimpleNamespace(readable=frozenset(graphs))
    )


def test_graph_caches_keep_other_scopes_on_a_write() -> None:
    reader = _scoped("ws-1", "urn:g:one", "urn:g:shared")
    other = _scoped("ws-9", "urn:g:nine")
    sharer = _scoped("ws-2", "urn:g:shared")
    before = {
        name: graph_service._scope_cache_key(store, "graph_kpis")
        for name, store in (("reader", reader), ("other", other), ("sharer", sharer))
    }

    graph_service._invalidate_graph_cache("urn:g:nine")
    assert graph_service._scope_cache_key(reader, "graph_kpis") == before["reader"]
    assert graph_service._scope_cache_key(sharer, "graph_kpis") == before["sharer"]
    assert graph_service._scope_cache_key(other, "graph_kpis") != before["other"]

    graph_service._invalidate_graph_cache("urn:g:shared")
    assert graph_service._scope_cache_key(reader, "graph_kpis") != before["reader"]
    assert graph_service._scope_cache_key(sharer, "graph_kpis") != before["sharer"]


def test_graph_cache_directory_keeps_within_its_bounds(tmp_path) -> None:
    now = time.time()
    ages = {"ancient": 30 * 86400, "old": 400, "older": 500, "new": 100, "newest": 0}
    for name, age in ages.items():
        path = tmp_path / name
        path.write_text("{}")
        os.utime(path, (now - age, now - age))

    removed = graph_service._prune_cache_dir(
        str(tmp_path), max_entries=2, max_age=graph_service._CACHE_MAX_AGE, now=now
    )

    assert removed == 3
    assert sorted(p.name for p in tmp_path.iterdir()) == ["new", "newest"]
