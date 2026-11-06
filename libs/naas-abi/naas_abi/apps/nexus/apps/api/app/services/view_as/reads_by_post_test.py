"""The reads sent by POST, as a view treats them: each one is classified, the allowed ones
answer (held to the viewed workspace), the refused ones are refused "Read-only"."""

from __future__ import annotations

import json
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import patch

import httpx
import pytest
from fastapi import FastAPI, Request
from fastapi.routing import APIRoute
from naas_abi import ABIModule, NexusConfig
from naas_abi.apps.nexus.apps.api.app.services.view_as import confinement
from naas_abi.apps.nexus.apps.api.app.services.view_as.adapters.primary.view_as__primary_adapter__ASGI import (  # noqa: E501
    ViewGuardMiddleware,
)
from naas_abi.apps.nexus.apps.api.app.services.view_as.port import ViewRecord
from naas_abi.apps.nexus.apps.api.app.services.view_as.reads_by_post import (
    BODY,
    BY_ROUTE,
    QUERY,
    READS_BY_POST,
)

ALLOWED = {
    "/api/graph/explorer/catalog",
    "/api/graph/explorer/overview",
    "/api/graph/explorer/instances",
    "/api/graph/explorer/network",
    "/api/graph/discovery/relation-targets",
    "/api/graph/discovery/properties",
    "/api/graph/discovery/instances",
    "/api/graph/discovery/instance-detail",
    "/api/graph/discovery/relation-types",
    "/api/graph/discovery/relations",
    "/api/graph/discovery/triples-export",
    "/api/graph/network/node-properties",
    "/api/graph/network/node-instances",
    "/api/graph/query",
    "/api/graph/query/facets",
    "/api/view/filters/preview",
    "/api/datasets/{namespace}/query",
    "/api/search/private",
    "/api/iam/admin/simulate",
    "/api/apps/access-token",
    "/api/apps/remote-grant",
    "/api/app-projects/{slug}/preview-token",
    # Not on the list before this job, each with its reason:
    "/api/iam/admin/policies/validate",
    "/api/sheets/evaluate",
    "/api/search/topics/preview",
    "/api/maps/layouts/preview",
    "/api/maps/feeds/preview",
    "/api/agents/sync",
}
REFUSED = {
    "/api/v1/chat/completions",
    "/api/speech",
    "/api/speech/",
    "/api/transcribe",
    "/api/transcribe/",
    "/api/apps/sso-token",
    "/api/chat/conversations/{conversation_id}/export",
    "/api/graph/analyze",  # a multipart upload of the import flow
}


@pytest.fixture(scope="module")
def app() -> FastAPI:
    config = SimpleNamespace(configuration=SimpleNamespace(nexus_config=NexusConfig()))
    with patch.object(ABIModule, "get_instance", return_value=config):
        from naas_abi.apps.nexus.apps.api.app import main

        app = FastAPI()
        main._register_routes(app)
    return app


def test_every_entry_is_classified_with_its_reasons() -> None:
    assert len({e.key for e in READS_BY_POST}) == len(READS_BY_POST)  # no entry twice
    assert {e.path for e in READS_BY_POST if e.allowed} == ALLOWED
    assert {e.path for e in READS_BY_POST if not e.allowed} == REFUSED
    for entry in READS_BY_POST:
        assert entry.method == "POST"
        assert len(entry.reads) > 20 and len(entry.why_in_view) > 20, entry.path
        # Only an allowed read says where it names its workspace.
        if entry.allowed:
            assert entry.workspace in (BODY, QUERY, None), entry.path
        else:
            assert entry.workspace is None, entry.path


def test_the_list_names_routes_of_the_application(app) -> None:
    routes = {
        (method, route.path)
        for route in app.routes
        if isinstance(route, APIRoute)
        for method in route.methods
    }
    assert sorted(set(BY_ROUTE) - routes) == []


def _scope(app, path: str, method: str = "POST", query: bytes = b"") -> dict:
    return {
        "type": "http",
        "path": path,
        "method": method,
        "query_string": query,
        "app": app,
    }


def _judge(app, path, body=None, query=b""):
    return confinement.judge(
        _scope(app, path, query=query),
        person="Dave",
        workspace_id="alpha",
        workspace_name="Alpha",
        body=body,
    )


def _concrete(path: str) -> str:
    return (
        path.replace("{namespace}", "ns").replace("{slug}", "s").replace("{conversation_id}", "c")
    )


@pytest.mark.parametrize("entry", [e for e in READS_BY_POST if e.allowed], ids=lambda e: e.path)
def test_an_allowed_read_answers_when_it_names_the_viewed_workspace(app, entry) -> None:
    path = _concrete(entry.path)
    scope = _scope(app, path, query=b"workspace_id=alpha")
    assert confinement.needs_body(scope) is (entry.workspace == BODY)
    body = json.dumps({"workspace_id": "alpha"}).encode()
    assert _judge(app, path, body, b"workspace_id=alpha") is None
    if entry.workspace == BODY:
        other = json.dumps({"workspace_id": "bravo"}).encode()
        for bad in (other, b"{}", b"[]", b"nope", json.dumps({"workspace_id": ""}).encode()):
            refusal = _judge(app, path, bad)
            assert refusal is not None and refusal.detail.startswith("Outside this view"), (
                entry.path,
                bad,
            )
        assert _judge(app, path, None) is not None
    if entry.workspace == QUERY:
        assert _judge(app, path, None, b"workspace_id=bravo").detail.startswith("Outside")
        assert _judge(app, path, None, b"").detail.startswith("Outside")


@pytest.mark.parametrize("entry", [e for e in READS_BY_POST if not e.allowed], ids=lambda e: e.path)
def test_a_refused_read_is_read_only(app, entry) -> None:
    scope = _scope(app, _concrete(entry.path))
    assert confinement.needs_body(scope) is False
    refusal = _judge(app, _concrete(entry.path), b'{"workspace_id": "alpha"}')
    assert refusal is not None
    assert refusal.status == 403 and refusal.detail == "Read-only: you are viewing as Dave"


def test_only_post_is_a_read_sent_by_post(app) -> None:
    for method in ("PUT", "PATCH", "DELETE"):
        scope = _scope(app, "/api/graph/query", method=method)
        refusal = confinement.judge(
            scope,
            person="Dave",
            workspace_id="alpha",
            workspace_name="Alpha",
            body=b'{"workspace_id": "alpha"}',
        )
        assert refusal is not None and refusal.detail.startswith("Read-only"), method


# -- through the middleware: the body is read, judged and handed on whole -------------------


def _guarded_app(real_app: FastAPI) -> FastAPI:
    """A tiny app with a listed route and an unlisted one, behind the guard, as a view of
    Dave in Alpha (the identity middleware's job, done by a stub)."""
    tiny = FastAPI()
    echoed: list[bytes] = []

    @tiny.post("/api/graph/query")
    async def query(request: Request) -> dict:
        echoed.append(await request.body())
        return {"seen": json.loads(echoed[-1])}

    @tiny.post("/api/files/")
    async def write(request: Request) -> dict:
        return {"wrote": True}

    tiny.state.echoed = echoed
    view = ViewRecord(
        session_id="s",
        viewer_id="root",
        person_id="dave",
        person_principal_id="p-dave",
        person_name="Dave",
        workspace_id="alpha",
        workspace_name="Alpha",
        container="c",
        group_ids=(),
        groups_from=None,
        started_at=datetime(2026, 11, 6, 10),
        ends_at=datetime(2026, 11, 6, 10, 15),
    )
    tiny.add_middleware(ViewGuardMiddleware)

    class Stub:
        def __init__(self, app):
            self.app = app

        async def __call__(self, scope, receive, send):
            scope.setdefault("state", {})["nexus_view"] = view
            await self.app(scope, receive, send)

    tiny.add_middleware(Stub)
    return tiny


@pytest.mark.asyncio
async def test_the_guard_reads_the_body_judges_it_and_hands_it_on(app) -> None:
    tiny = _guarded_app(app)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=tiny), base_url="http://t"
    ) as client:
        ok = await client.post(
            "/api/graph/query", json={"workspace_id": "alpha", "spec": {"a": [1, 2]}}
        )
        assert ok.status_code == 200 and ok.json() == {
            "seen": {"workspace_id": "alpha", "spec": {"a": [1, 2]}}
        }
        other = await client.post("/api/graph/query", json={"workspace_id": "bravo"})
        assert other.status_code == 403
        assert other.json()["detail"] == "Outside this view: you are viewing as Dave in Alpha"
        write = await client.post("/api/files/", json={"workspace_id": "alpha"})
        assert write.status_code == 403
        assert write.json()["detail"] == "Read-only: you are viewing as Dave"
        huge = await client.post(
            "/api/graph/query",
            content=b'{"workspace_id": "alpha", "x": "' + b"a" * (9 * 1024 * 1024) + b'"}',
            headers={"content-type": "application/json"},
        )
        assert huge.status_code == 413
    assert len(tiny.state.echoed) == 1  # only the answered one reached the route
