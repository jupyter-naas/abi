"""Where each kind of credential is refused (task #62's regression tests).

A coding agent's key, an app-html link, a preview link and a remote app grant
each open their own route and nothing else: every one is refused on ``/api/*``
and on the WebSocket, and none acts as a session. A personal API key works
where an API key belongs and nowhere else.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from jose import jwt as jose_jwt
from naas_abi.apps.nexus.apps.api.app.services.apps import links
from naas_abi.apps.nexus.apps.api.app.services.apps.app_html_access import (
    mint_app_html_access_token,
)
from naas_abi.apps.nexus.apps.api.app.services.apps.projects.preview_token import (
    mint_preview_token,
)
from naas_abi.apps.nexus.apps.api.app.services.apps.remote.grant import (
    mint_remote_app_grant,
)
from naas_abi.apps.nexus.apps.api.app.services.auth import credentials
from naas_abi.apps.nexus.apps.api.app.services.auth.adapters.primary.auth__primary_adapter__dependencies import (
    get_auth_service,
    get_current_user_required,
)
from naas_abi.apps.nexus.apps.api.app.services.auth.port import AuthUserRecord
from naas_abi.apps.nexus.apps.api.app.services.auth.service import AuthService
from naas_abi.apps.nexus.apps.api.app.services.identity_events.middleware import (
    RequestIdentityMiddleware,
)
from naas_abi.apps.nexus.apps.api.app.services.websocket import runtime as websocket
from naas_abi_core.engine.call_context import (
    CallContext,
    as_service_account,
    current_call_context,
    service_account,
    use_call_context,
    user,
)
from naas_abi_core.engine.nats_auth import (
    AGENT_AUDIENCE,
    API_KEY_AUDIENCE,
    APP_AUDIENCE,
    CODING_AUDIENCE,
    PREVIEW_AUDIENCE,
    SESSION_AUDIENCE,
)
from naas_abi_core.services.iam.adapters.secondary.IAMStoreMemory import IAMStoreMemory
from naas_abi_core.services.iam.IAMPorts import (
    TOKEN_TYPE_JWT,
    TOKEN_TYPE_SESSION,
    TokenExchange,
)
from naas_abi_core.services.iam.IAMService import IAMService

ROUTES = {
    "api": "/api/workspaces/ws-1/members",
    "account": "/api/auth/me",
    "keys": "/api/iam/api-keys",
    "gateway": "/api/v1/models",
}
SIDECAR = "http://coder-ada-x:8378"


@pytest.fixture
def iam():
    service = IAMService(IAMStoreMemory())
    service.bootstrap()
    previous = credentials.configure_iam(lambda: service)
    yield service
    credentials.configure_iam(previous)


@pytest.fixture
def ada(iam):
    with as_service_account("engine"):
        return iam.ensure_user("https://idp.example", "ada")


@pytest.fixture
def client(iam, ada):
    app = FastAPI()
    app.add_middleware(RequestIdentityMiddleware)
    adapter = AsyncMock()
    adapter.get_user_by_id.side_effect = lambda user_id: AuthUserRecord(
        id=user_id,
        email="ada@example.com",
        name="Ada",
        created_at=datetime.utcnow(),
    )
    app.dependency_overrides[get_auth_service] = lambda: AuthService(adapter=adapter)
    seen: dict[str, CallContext] = {}

    def route(path: str) -> None:
        async def handler(user=Depends(get_current_user_required)) -> dict:
            seen[path] = current_call_context()
            return {"id": user.id}

        app.add_api_route(path, handler, methods=["GET"])

    for path in ROUTES.values():
        route(path)
    test_client = TestClient(app)
    test_client.seen = seen  # type: ignore[attr-defined]
    return test_client


def _acting_for(record):
    return use_call_context(
        CallContext(principal=service_account("api"), on_behalf_of=user(record.id))
    )


def _engine_token(iam, record, audience, **fields) -> str:
    with as_service_account("api"):
        session = iam.exchange_token(
            TokenExchange(record.id, TOKEN_TYPE_SESSION, SESSION_AUDIENCE)
        ).token
        if audience == SESSION_AUDIENCE:
            return session
        return iam.exchange_token(TokenExchange(session, TOKEN_TYPE_JWT, audience, **fields)).token


# What an older Nexus signed with its ``secret_key``: sessions, links, coding agents.
# Nexus signs nothing now (RFC §13), and none of it is read.
OLD_SECRET = "the-key-nexus-used-to-sign-with"


def _legacy_jwt(**claims) -> str:
    return jose_jwt.encode(
        {"jti": "j", "exp": datetime.now(UTC) + timedelta(days=30), **claims},
        OLD_SECRET,
        algorithm="HS256",
    )


def credentials_of(iam, record) -> dict[str, str]:
    """One of each kind of credential this API must tell apart."""
    with _acting_for(record):
        personal = iam.create_key(record.id, description="script").value
        coding = iam.create_key(
            record.id,
            audience=CODING_AUDIENCE,
            resource=SIDECAR,
            expires_at=datetime.now(UTC) + timedelta(days=30),
        ).value
    with _acting_for(record):
        app_link, _ = mint_app_html_access_token(user_id=record.id)
        preview = mint_preview_token(user_id=record.id, workspace_id="ws-1", slug="demo")
        remote = mint_remote_app_grant(user_id=record.id, module_id="acme.research", app="console")
    return {
        "legacy_session_jwt": _legacy_jwt(sub=record.id, aud=SESSION_AUDIENCE),
        "engine_session": _engine_token(iam, record, SESSION_AUDIENCE),
        "api_key": personal,
        "api_key_token": _engine_token(iam, record, API_KEY_AUDIENCE),
        "coding_key": coding,
        "coding_token": _engine_token(iam, record, CODING_AUDIENCE),
        "legacy_coding_jwt": _legacy_jwt(sub=record.id, ws_base=SIDECAR, ws_secret="secret"),
        "app_html_link": app_link,
        "legacy_app_html_jwt": _legacy_jwt(
            sub=record.id, scope="app-html", path_prefix="/app-html/x/"
        ),
        "preview_link": preview,
        "legacy_preview_jwt": _legacy_jwt(scope="app-preview", uid=record.id),
        "remote_app_grant": remote,
        "app_token": _engine_token(iam, record, APP_AUDIENCE),
        "preview_token": _engine_token(iam, record, PREVIEW_AUDIENCE),
        "agent_delegation": _agent_delegation(iam, record),
        "service_token": iam.issue_service_token("api").token,
    }


def _agent_delegation(iam, record) -> str:
    with as_service_account("api"):
        return iam.exchange_token(
            TokenExchange(record.id, TOKEN_TYPE_SESSION, AGENT_AUDIENCE)
        ).token


def _get(client, route, token):
    return client.get(ROUTES[route], headers={"Authorization": f"Bearer {token}"})


def _authenticated(response) -> bool:
    return response.status_code == 200


# -- the credentials that are no session -------------------------------------------------------

NO_SESSION = [
    "legacy_session_jwt",
    "coding_key",
    "coding_token",
    "legacy_coding_jwt",
    "app_html_link",
    "legacy_app_html_jwt",
    "preview_link",
    "legacy_preview_jwt",
    "remote_app_grant",
    "app_token",
    "preview_token",
    "agent_delegation",
    "service_token",
]


@pytest.mark.parametrize("kind", NO_SESSION)
@pytest.mark.parametrize("route", ["api", "account", "keys"])
def test_no_link_agent_key_or_delegation_is_a_session_on_the_api(client, iam, ada, kind, route):
    response = _get(client, route, credentials_of(iam, ada)[kind])
    assert response.status_code in (401, 403), (kind, route, response.text)
    assert route not in client.seen or client.seen.get(ROUTES[route]) is None


@pytest.mark.parametrize("kind", NO_SESSION)
def test_none_of_them_names_a_user_to_the_kernel_either(client, iam, ada, kind):
    token = credentials_of(iam, ada)[kind]
    # A coding agent's own route (the gateway) takes it: that is its purpose.
    routes = {
        name: path
        for name, path in ROUTES.items()
        if not (name == "gateway" and kind.startswith("coding"))
    }
    for path in routes.values():
        client.get(path, headers={"Authorization": f"Bearer {token}"})
    # No handler ran, so none ran as ``api`` for the user.
    assert client.seen == {}


def test_the_session_is_accepted_everywhere(client, iam, ada):
    token = credentials_of(iam, ada)["engine_session"]
    for route in ROUTES:
        response = _get(client, route, token)
        assert _authenticated(response), (route, response.text)
    context = client.seen[ROUTES["api"]]
    assert context.principal.id == "api"
    assert context.on_behalf_of is not None and context.on_behalf_of.id == ada.id


# -- the coding agent's key reaches the gateway and nothing else ------------------------------------


@pytest.mark.parametrize("kind", ["coding_key", "coding_token"])
def test_a_coding_agent_credential_reaches_the_gateway_only(client, iam, ada, kind):
    token = credentials_of(iam, ada)[kind]
    assert _authenticated(_get(client, "gateway", token))
    for route in ("api", "account", "keys"):
        assert _get(client, route, token).status_code == 403, route
    context = client.seen[ROUTES["gateway"]]
    assert context.on_behalf_of is not None and context.on_behalf_of.id == ada.id


def test_a_coding_agent_is_refused_with_a_reason_not_a_blank_401(client, iam, ada):
    response = _get(client, "api", credentials_of(iam, ada)["coding_key"])
    assert response.status_code == 403
    assert "coding" in response.json()["detail"]


# -- API keys -------------------------------------------------------------------------------------


@pytest.mark.parametrize("kind", ["api_key", "api_key_token"])
def test_an_api_key_works_where_a_key_belongs_and_not_on_the_account(client, iam, ada, kind):
    token = credentials_of(iam, ada)[kind]
    assert _authenticated(_get(client, "api", token))
    assert _authenticated(_get(client, "gateway", token))
    # The account and the keys' own management take a session only.
    assert _get(client, "account", token).status_code == 403
    assert _get(client, "keys", token).status_code == 403


def test_an_api_key_stops_when_it_is_revoked(client, iam, ada):
    with _acting_for(ada):
        created = iam.create_key(ada.id, description="ci")
    assert _authenticated(_get(client, "api", created.value))
    with _acting_for(ada):
        iam.revoke_key(ada.id, created.record.key_id)
    assert _get(client, "api", created.value).status_code == 401


def test_an_api_key_stops_when_it_expires(client, iam, ada):
    import time

    with _acting_for(ada):
        created = iam.create_key(ada.id, expires_at=datetime.now(UTC) + timedelta(seconds=1))
    assert _authenticated(_get(client, "api", created.value))
    time.sleep(1.2)
    assert _get(client, "api", created.value).status_code == 401


def test_an_api_keys_scope_narrows_the_kernel_calls_of_the_request(client, iam, ada):
    scope = ({"effect": "Allow", "actions": ["triple_store:Query"], "resources": ["*"]},)
    with _acting_for(ada):
        created = iam.create_key(ada.id, scope=scope)
    assert _authenticated(_get(client, "api", created.value))
    context = client.seen[ROUTES["api"]]
    assert context.scope == scope
    assert context.on_behalf_of is not None and context.on_behalf_of.id == ada.id


def test_a_suspended_user_s_keys_and_tokens_all_stop(client, iam, ada):
    made = credentials_of(iam, ada)
    with as_service_account("engine"):
        iam.suspend_principal(ada.id)
    for kind in ("engine_session", "api_key", "api_key_token", "coding_key"):
        assert _get(client, "gateway", made[kind]).status_code in (401, 403), kind


def test_revoking_all_of_a_users_tokens_stops_their_sessions_and_agents(client, iam, ada):
    made = credentials_of(iam, ada)
    assert _authenticated(_get(client, "api", made["engine_session"]))
    assert _authenticated(_get(client, "gateway", made["coding_key"]))
    assert asyncio.run(credentials.revoke_user_credentials(ada.id)) is True
    for kind in ("engine_session", "api_key_token", "coding_key", "coding_token"):
        assert _get(client, "gateway", made[kind]).status_code in (401, 403), kind
    # A personal API key is the user's to keep.
    assert _authenticated(_get(client, "api", made["api_key"]))


# -- the WebSocket ---------------------------------------------------------------------------------


@pytest.fixture
def socket(monkeypatch):
    accepted: list[str] = []

    async def accept(sid, user_id):
        accepted.append(user_id)
        return True

    monkeypatch.setattr(websocket, "_accept", accept)
    return accepted


def connect(token: str) -> bool:
    return asyncio.run(websocket.connect("sid-1", {}, {"token": token}))


@pytest.mark.parametrize("kind", NO_SESSION + ["api_key", "api_key_token"])
def test_the_websocket_takes_nothing_but_a_session(iam, ada, socket, kind):
    assert connect(credentials_of(iam, ada)[kind]) is False
    assert socket == []


def test_the_websocket_takes_a_session(iam, ada, socket):
    made = credentials_of(iam, ada)
    assert connect(made["engine_session"]) is True
    assert socket == [ada.id]


def test_the_websocket_refuses_a_session_revoked_since(iam, ada, socket):
    made = credentials_of(iam, ada)
    asyncio.run(credentials.revoke_user_credentials(ada.id))
    assert connect(made["engine_session"]) is False
    assert socket == []


# -- the app routes open their own links only -------------------------------------------------------


def test_a_link_opens_its_own_route_and_no_other(iam, ada):
    """An app-html link is no preview link, no remote app grant and no session;
    each is read only for the audience it was made for."""
    made = credentials_of(iam, ada)
    assert links.open_link(made["app_html_link"], APP_AUDIENCE) is not None
    assert links.open_link(made["app_html_link"], PREVIEW_AUDIENCE) is None
    assert links.open_link(made["preview_link"], PREVIEW_AUDIENCE) is not None
    assert links.open_link(made["preview_link"], APP_AUDIENCE) is None
    assert links.open_link(made["remote_app_grant"], APP_AUDIENCE) is not None
    assert links.open_link(made["api_key"], APP_AUDIENCE) is None  # a key is no link
    assert links.open_link(made["coding_key"], APP_AUDIENCE) is None
