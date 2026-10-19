from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient
from naas_abi.apps.nexus.apps.api.app.services.identity_events import middleware as mw
from naas_abi.apps.nexus.apps.api.app.services.identity_events.middleware import (
    RequestIdentityMiddleware,
    workspace_id_from_request,
)
from naas_abi_core.engine.call_context import ANONYMOUS, current_call_context
from naas_abi_core.services.event.context import (
    event_actor_user_id,
    event_actor_workspace_id,
    event_triggered_via,
)


def _app() -> FastAPI:
    app = FastAPI()
    app.add_middleware(RequestIdentityMiddleware)

    def seen() -> dict:
        context = current_call_context()
        return {
            "user": event_actor_user_id.get(),
            "workspace": event_actor_workspace_id.get(),
            "via": event_triggered_via.get(),
            "principal": context.principal.id,
            "on_behalf_of": context.on_behalf_of.id if context.on_behalf_of else None,
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
        mw,
        "_decode_token",
        lambda token: {"sub": "usr-1", "aud": "abi:session"} if token == "good" else None,
    )
    client = TestClient(_app())

    body = client.get(
        "/api/workspaces/ws-1/members", headers={"Authorization": "Bearer good"}
    ).json()

    # Nexus calls as ``api`` on behalf of the signed-in user.
    assert body == {
        "user": "usr-1",
        "workspace": "ws-1",
        "via": "api",
        "principal": "api",
        "on_behalf_of": "usr-1",
    }
    assert event_actor_user_id.get() is None
    assert event_actor_workspace_id.get() is None
    assert current_call_context() == ANONYMOUS


def test_sync_endpoints_see_it_too_and_query_workspace_works(monkeypatch) -> None:
    monkeypatch.setattr(mw, "_decode_token", lambda token: {"sub": "usr-1", "aud": "abi:session"})
    client = TestClient(_app())

    body = client.get("/api/files?workspace_id=ws-9", headers={"Authorization": "Bearer t"}).json()

    assert body["user"] == "usr-1" and body["workspace"] == "ws-9"
    assert (body["principal"], body["on_behalf_of"]) == ("api", "usr-1")


def test_anonymous_requests_have_no_actor(monkeypatch) -> None:
    monkeypatch.setattr(mw, "_decode_token", lambda token: None)
    client = TestClient(_app())

    assert client.get("/api/files", headers={"Authorization": "Bearer bad"}).json()["user"] is None
    # No verified user: anonymous, never Nexus's own trusted ``api``.
    assert client.get("/api/files").json() == {
        "user": None,
        "workspace": None,
        "via": "api",
        "principal": "anonymous",
        "on_behalf_of": None,
    }


def _seen_with(monkeypatch, payload, revoked=False):
    monkeypatch.setattr(mw, "_decode_token", lambda token: payload)

    async def is_revoked(jti):
        if isinstance(revoked, Exception):
            raise revoked
        return revoked

    monkeypatch.setattr(mw, "_is_revoked", is_revoked)
    client = TestClient(_app())
    return client.get("/api/files", headers={"Authorization": "Bearer t"}).json()


def test_a_session_token_names_its_user(monkeypatch) -> None:
    body = _seen_with(monkeypatch, {"sub": "usr-1", "jti": "j1", "aud": "abi:session"})
    assert (body["principal"], body["on_behalf_of"], body["user"]) == (
        "api",
        "usr-1",
        "usr-1",
    )


def test_a_scoped_link_token_names_no_user(monkeypatch) -> None:
    body = _seen_with(
        monkeypatch, {"sub": "usr-1", "jti": "j1", "aud": "abi:session", "scope": "app-html"}
    )
    assert (body["principal"], body["on_behalf_of"], body["user"]) == (
        "anonymous",
        None,
        None,
    )


def test_a_revoked_token_names_no_user(monkeypatch) -> None:
    body = _seen_with(
        monkeypatch, {"sub": "usr-1", "jti": "j1", "aud": "abi:session"}, revoked=True
    )
    assert (body["principal"], body["on_behalf_of"]) == ("anonymous", None)


def test_a_failed_revocation_check_names_no_user(monkeypatch) -> None:
    body = _seen_with(
        monkeypatch,
        {"sub": "usr-1", "jti": "j1", "aud": "abi:session"},
        revoked=RuntimeError("db down"),
    )
    assert (body["principal"], body["on_behalf_of"]) == ("anonymous", None)


def test_workspace_id_extraction() -> None:
    assert workspace_id_from_request("/api/workspaces/ws-1", b"") == "ws-1"
    assert workspace_id_from_request("/api/workspaces/ws-1/members/usr-2", b"") == "ws-1"
    assert workspace_id_from_request("/api/chat", b"workspace_id=ws-2&x=1") == "ws-2"
    assert workspace_id_from_request("/api/workspaces", b"") is None
    assert workspace_id_from_request("/api/workspaces/", b"") is None
