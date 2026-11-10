from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient
from naas_abi.apps.nexus.apps.api.app.services.auth.credentials import Credential
from naas_abi.apps.nexus.apps.api.app.services.identity_events import middleware as mw
from naas_abi.apps.nexus.apps.api.app.services.identity_events.middleware import (
    RequestIdentityMiddleware,
)
from naas_abi_core.engine.call_context import current_call_context
from naas_abi_core.services.event.context import (
    event_actor_container,
    event_actor_user_id,
    event_triggered_via,
)
from naas_abi_core.services.iam.names import UNRESOLVED


def _app() -> FastAPI:
    app = FastAPI()
    app.add_middleware(RequestIdentityMiddleware)

    def seen() -> dict:
        context = current_call_context()
        return {
            "user": event_actor_user_id.get(),
            "workspace": event_actor_container.get(),
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

    @app.get("/api/auth/me")
    async def me() -> dict:
        return seen()

    return app


def _credentials(monkeypatch, by_token: dict[str, Credential]) -> None:
    """What the engine's IAM would say of each bearer token (``bearer_credential``)."""

    async def known(token: str) -> Credential | None:
        return by_token.get(token)

    monkeypatch.setattr(mw, "bearer_credential", known)


def _session(user: str = "usr-1", **fields) -> Credential:
    return Credential(kind="session", user_id=user, **fields)


WS1 = "abi:nexus:organization/org-1/nexus:workspace/ws-1"


def test_identity_is_set_for_the_request_and_cleared_after(monkeypatch, nexus_iam) -> None:
    nexus_iam.workspace("org-1", "ws-1")
    outside = current_call_context()
    _credentials(monkeypatch, {"good": _session()})
    client = TestClient(_app())

    body = client.get(
        "/api/workspaces/ws-1/members", headers={"Authorization": "Bearer good"}
    ).json()

    # Nexus calls as ``api`` on behalf of the signed-in user.
    assert body == {
        "user": "usr-1",
        "workspace": WS1,
        "via": "api",
        "principal": "api",
        "on_behalf_of": "usr-1",
    }
    assert event_actor_user_id.get() is None
    assert current_call_context() == outside


def test_sync_endpoints_see_it_too_and_query_workspace_works(monkeypatch, nexus_iam) -> None:
    nexus_iam.workspace(None, "ws-9")
    _credentials(monkeypatch, {"t": _session()})
    client = TestClient(_app())

    body = client.get("/api/files?workspace_id=ws-9", headers={"Authorization": "Bearer t"}).json()

    assert body["user"] == "usr-1" and body["workspace"] == "abi:nexus:workspace/ws-9"
    assert (body["principal"], body["on_behalf_of"]) == ("api", "usr-1")


def test_anonymous_requests_have_no_actor(monkeypatch) -> None:
    _credentials(monkeypatch, {})
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


def _seen_with(monkeypatch, credential: Credential | None, path: str = "/api/files"):
    _credentials(monkeypatch, {"t": credential} if credential else {})
    client = TestClient(_app())
    return client.get(path, headers={"Authorization": "Bearer t"}).json()


def test_a_session_names_its_user(monkeypatch) -> None:
    body = _seen_with(monkeypatch, _session())
    assert (body["principal"], body["on_behalf_of"], body["user"]) == ("api", "usr-1", "usr-1")


def test_a_token_the_engine_does_not_vouch_for_names_no_user(monkeypatch) -> None:
    # Revoked, expired, suspended, forged, signed with Nexus's old secret: none
    # is a credential (``bearer_credential`` says None).
    body = _seen_with(monkeypatch, None)
    assert (body["principal"], body["on_behalf_of"], body["user"]) == ("anonymous", None, None)


def test_a_credential_of_a_kind_the_route_does_not_take_names_no_user(monkeypatch) -> None:
    coding = Credential(kind="coding", user_id="usr-1")
    body = _seen_with(monkeypatch, coding)
    assert (body["principal"], body["on_behalf_of"]) == ("anonymous", None)
    # An API key on the account's own routes is refused the same way.
    key = Credential(kind="api-key", user_id="usr-1")
    assert _seen_with(monkeypatch, key, "/api/auth/me")["on_behalf_of"] is None
    assert _seen_with(monkeypatch, key)["on_behalf_of"] == "usr-1"


def test_a_scope_narrows_the_context(monkeypatch) -> None:
    from naas_abi_core.engine.call_context import current_call_context as ctx

    scope = ({"effect": "Allow", "actions": ["triple_store:Query"], "resources": ["*"]},)
    _credentials(monkeypatch, {"k": Credential(kind="api-key", user_id="usr-1", scope=scope)})
    app = _app()
    seen: dict = {}

    @app.get("/api/narrowed")
    async def narrowed() -> dict:
        seen["scope"] = ctx().scope
        return {}

    TestClient(app).get("/api/narrowed", headers={"Authorization": "Bearer k"})
    assert seen["scope"] == scope


def test_a_workspace_iam_does_not_know_is_a_container_nobody_registered(
    monkeypatch, nexus_iam
) -> None:
    """A deleted (or unknown) workspace: the call is made in ``UNRESOLVED``, so
    what it creates is not found, never placed on the platform. No workspace in
    the path: no container."""
    _credentials(monkeypatch, {"good": _session()})
    client = TestClient(_app())
    headers = {"Authorization": "Bearer good"}

    gone = client.get("/api/workspaces/ws-gone/members", headers=headers).json()
    assert gone["workspace"] == UNRESOLVED
    assert client.get("/api/files", headers=headers).json()["workspace"] is None
