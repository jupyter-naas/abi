from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient
from naas_abi.apps.nexus.apps.api.app.services.identity_events import middleware as mw
from naas_abi.apps.nexus.apps.api.app.services.identity_events.middleware import (
    RequestIdentityMiddleware,
    workspace_id_from_request,
)
from naas_abi_core.services.event.context import (
    event_actor_user_id,
    event_actor_workspace_id,
    event_triggered_via,
)


def _app() -> FastAPI:
    app = FastAPI()
    app.add_middleware(RequestIdentityMiddleware)

    def seen() -> dict:
        return {
            "user": event_actor_user_id.get(),
            "workspace": event_actor_workspace_id.get(),
            "via": event_triggered_via.get(),
        }

    @app.get("/api/workspaces/{workspace_id}/members")
    async def members(workspace_id: str) -> dict:
        return seen()

    @app.get("/api/files")
    def files() -> dict:  # sync endpoint: runs in the threadpool
        return seen()

    return app


def test_identity_is_set_for_the_request_and_cleared_after(monkeypatch) -> None:
    monkeypatch.setattr(
        mw, "_decode_token", lambda token: {"sub": "usr-1"} if token == "good" else None
    )
    client = TestClient(_app())

    body = client.get(
        "/api/workspaces/ws-1/members", headers={"Authorization": "Bearer good"}
    ).json()

    assert body == {"user": "usr-1", "workspace": "ws-1", "via": "api"}
    assert event_actor_user_id.get() is None
    assert event_actor_workspace_id.get() is None


def test_sync_endpoints_see_it_too_and_query_workspace_works(monkeypatch) -> None:
    monkeypatch.setattr(mw, "_decode_token", lambda token: {"sub": "usr-1"})
    client = TestClient(_app())

    body = client.get("/api/files?workspace_id=ws-9", headers={"Authorization": "Bearer t"}).json()

    assert body == {"user": "usr-1", "workspace": "ws-9", "via": "api"}


def test_anonymous_requests_have_no_actor(monkeypatch) -> None:
    monkeypatch.setattr(mw, "_decode_token", lambda token: None)
    client = TestClient(_app())

    assert client.get("/api/files", headers={"Authorization": "Bearer bad"}).json()["user"] is None
    assert client.get("/api/files").json() == {"user": None, "workspace": None, "via": "api"}


def test_workspace_id_extraction() -> None:
    assert workspace_id_from_request("/api/workspaces/ws-1", b"") == "ws-1"
    assert workspace_id_from_request("/api/workspaces/ws-1/members/usr-2", b"") == "ws-1"
    assert workspace_id_from_request("/api/chat", b"workspace_id=ws-2&x=1") == "ws-2"
    assert workspace_id_from_request("/api/workspaces", b"") is None
    assert workspace_id_from_request("/api/workspaces/", b"") is None
