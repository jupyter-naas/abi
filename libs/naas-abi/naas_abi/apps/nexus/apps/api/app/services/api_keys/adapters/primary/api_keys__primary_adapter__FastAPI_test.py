"""The API keys routes, over a real IAM: make, list, use, revoke."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from naas_abi.apps.nexus.apps.api.app.services.api_keys.adapters.primary import router
from naas_abi.apps.nexus.apps.api.app.services.auth import credentials
from naas_abi.apps.nexus.apps.api.app.services.auth.adapters.primary.auth__primary_adapter__dependencies import (
    get_auth_service,
    get_current_user_required,
)
from naas_abi.apps.nexus.apps.api.app.services.auth.port import AuthUserRecord
from naas_abi.apps.nexus.apps.api.app.services.auth.service import AuthService
from naas_abi.apps.nexus.apps.api.app.services.auth.testing import session_token
from naas_abi.apps.nexus.apps.api.app.services.identity_events.middleware import (
    RequestIdentityMiddleware,
)
from naas_abi_core.engine.call_context import as_service_account, current_call_context
from naas_abi_core.services.iam.adapters.secondary.IAMStoreMemory import IAMStoreMemory
from naas_abi_core.services.iam.IAMService import IAMService


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
def attempts(monkeypatch):
    """The rate limit's database, in memory: failed exchanges per caller."""
    from naas_abi.apps.nexus.apps.api.app.services.api_keys.adapters.primary import (
        api_keys__primary_adapter__FastAPI as adapter,
    )

    seen: list[tuple[str, str]] = []

    async def ensure(identifier: str, endpoint: str, limit: int) -> None:
        from fastapi import HTTPException

        if sum(1 for entry in seen if entry == (identifier, endpoint)) >= limit:
            raise HTTPException(status_code=429, detail="Too many attempts.")

    async def record(identifier: str, endpoint: str) -> None:
        seen.append((identifier, endpoint))

    monkeypatch.setattr(adapter, "ensure_under_limit", ensure)
    monkeypatch.setattr(adapter, "record_attempt", record)
    return seen


@pytest.fixture
def client(iam, ada, attempts):
    app = FastAPI()
    app.add_middleware(RequestIdentityMiddleware)
    app.include_router(router, prefix="/api/iam")
    adapter = AsyncMock()
    adapter.get_user_by_id.side_effect = lambda user_id: AuthUserRecord(
        id=user_id,
        email=f"{user_id}@example.com",
        name="Ada",
        created_at=datetime.utcnow(),
    )
    app.dependency_overrides[get_auth_service] = lambda: AuthService(adapter=adapter)

    @app.get("/api/whoami")
    async def whoami(user=Depends(get_current_user_required)) -> dict:
        context = current_call_context()
        return {
            "id": user.id,
            "scope": list(context.scope) if context.scope is not None else None,
        }

    return TestClient(app)


def session_headers(user_id: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {session_token(credentials.IAM(), user_id)}"}


def create(client, ada, **body):
    return client.post(
        "/api/iam/api-keys",
        json={"name": "ci", **body},
        headers=session_headers(ada.id),
    )


def test_a_key_is_made_once_listed_without_its_secret_and_used(client, ada):
    created = create(client, ada)
    assert created.status_code == 201, created.text
    secret = created.json()["secret"]
    key = created.json()["key"]
    assert secret.startswith(f"abi_pk_{key['id']}_")
    assert (key["name"], key["status"], key["access"]) == ("ci", "active", "full")
    assert key["prefix"] == f"abi_pk_{key['id']}"
    assert key["scope"] is None

    listed = client.get("/api/iam/api-keys", headers=session_headers(ada.id))
    assert listed.status_code == 200
    assert [k["id"] for k in listed.json()] == [key["id"]]
    assert secret not in listed.text and "secret" not in listed.json()[0]

    used = client.get("/api/whoami", headers={"Authorization": f"Bearer {secret}"})
    assert used.status_code == 200 and used.json() == {"id": ada.id, "scope": None}
    assert (
        client.get("/api/iam/api-keys", headers=session_headers(ada.id)).json()[0]["last_used_at"]
        is not None
    )


def test_a_key_lasts_a_year_by_default_and_at_most_a_year(client, ada):
    key = create(client, ada).json()["key"]
    expires = datetime.fromisoformat(key["expires_at"])
    assert timedelta(days=364) < expires - datetime.now(UTC) <= timedelta(days=366)
    short = create(client, ada, expires_in_days=30).json()["key"]
    assert (
        timedelta(days=29)
        < datetime.fromisoformat(short["expires_at"]) - datetime.now(UTC)
        <= timedelta(days=31)
    )
    assert create(client, ada, expires_in_days=400).status_code == 422
    assert create(client, ada, expires_in_days=0).status_code == 422


def test_a_read_only_key_reads_and_is_narrowed_to_what_reads(client, ada):
    created = create(client, ada, access="read").json()
    assert created["key"]["access"] == "read"
    scope = created["key"]["scope"]
    assert scope and all(s["effect"] == "Allow" for s in scope)
    names = {a for s in scope for a in s["actions"]}
    assert "iam:ListKeys" in names and "iam:GetPrincipal" in names
    assert "iam:CreateKey" not in names and "iam:RevokeKey" not in names
    used = client.get(
        "/api/whoami", headers={"Authorization": f"Bearer {created['secret']}"}
    ).json()
    assert used["scope"] == scope
    listed = client.get("/api/iam/api-keys", headers=session_headers(ada.id)).json()
    assert listed[0]["access"] == "read"


def test_a_custom_key_names_its_statements(client, ada):
    scope = [{"effect": "Allow", "actions": ["triple_store:Query"], "resources": ["*"]}]
    created = create(client, ada, access="custom", scope=scope).json()
    assert created["key"]["access"] == "custom" and created["key"]["scope"] == scope
    used = client.get(
        "/api/whoami", headers={"Authorization": f"Bearer {created['secret']}"}
    ).json()
    assert used["scope"] == scope


@pytest.mark.parametrize(
    "body",
    [
        {"access": "custom"},  # no statements
        {"access": "custom", "scope": []},
        {"access": "custom", "scope": [{"effect": "Deny", "actions": ["*"], "resources": ["*"]}]},
        {"access": "custom", "scope": [{"effect": "Allow", "actions": ["x:Y"]}]},
        {"access": "full", "scope": [{"effect": "Allow", "actions": ["*"], "resources": ["*"]}]},
        {"access": "read", "scope": [{"effect": "Allow", "actions": ["*"], "resources": ["*"]}]},
        {"access": "anything"},
        {"name": ""},
        {"name": "   "},
    ],
)
def test_an_invalid_key_is_refused_with_a_reason(client, ada, body):
    response = client.post(
        "/api/iam/api-keys",
        json={"name": "ci", **body},
        headers=session_headers(ada.id),
    )
    assert response.status_code == 422, response.text


def test_five_active_keys_at_most(client, ada):
    for index in range(5):
        assert create(client, ada, name=f"k{index}").status_code == 201
    sixth = create(client, ada, name="k5")
    assert sixth.status_code == 409
    first = client.get("/api/iam/api-keys", headers=session_headers(ada.id)).json()[0]
    assert (
        client.delete(
            f"/api/iam/api-keys/{first['id']}", headers=session_headers(ada.id)
        ).status_code
        == 200
    )
    assert create(client, ada, name="k5").status_code == 201


def test_a_revoked_key_stops_at_once_and_says_so(client, ada):
    created = create(client, ada).json()
    bearer = {"Authorization": f"Bearer {created['secret']}"}
    assert client.get("/api/whoami", headers=bearer).status_code == 200
    revoked = client.delete(
        f"/api/iam/api-keys/{created['key']['id']}", headers=session_headers(ada.id)
    )
    assert revoked.status_code == 200 and revoked.json()["status"] == "revoked"
    assert client.get("/api/whoami", headers=bearer).status_code == 401
    listed = client.get("/api/iam/api-keys", headers=session_headers(ada.id)).json()
    assert listed[0]["status"] == "revoked"
    # Revoking again is the same answer: it is revoked.
    again = client.delete(
        f"/api/iam/api-keys/{created['key']['id']}", headers=session_headers(ada.id)
    )
    assert again.status_code == 200


def test_a_key_is_the_owners_alone(client, ada, iam):
    with as_service_account("engine"):
        eve = iam.ensure_user("https://idp.example", "eve")
    created = create(client, ada).json()
    assert client.get("/api/iam/api-keys", headers=session_headers(eve.id)).json() == []
    stolen = client.delete(
        f"/api/iam/api-keys/{created['key']['id']}", headers=session_headers(eve.id)
    )
    assert stolen.status_code == 404
    bearer = {"Authorization": f"Bearer {created['secret']}"}
    assert client.get("/api/whoami", headers=bearer).status_code == 200


def test_a_key_cannot_manage_keys(client, ada):
    secret = create(client, ada).json()["secret"]
    bearer = {"Authorization": f"Bearer {secret}"}
    # The keys' own management is session-only: a key cannot make another key,
    # list them, or widen itself.
    for response in (
        client.get("/api/iam/api-keys", headers=bearer),
        client.post("/api/iam/api-keys", json={"name": "x"}, headers=bearer),
        client.delete("/api/iam/api-keys/whatever", headers=bearer),
    ):
        assert response.status_code == 403, response.text
    assert len(client.get("/api/iam/api-keys", headers=session_headers(ada.id)).json()) == 1


def test_no_session_no_keys(client):
    assert client.get("/api/iam/api-keys").status_code == 401
    assert client.post("/api/iam/api-keys", json={"name": "x"}).status_code == 401
    assert client.delete("/api/iam/api-keys/x").status_code == 401


def test_other_kinds_of_keys_are_not_listed(client, ada, iam):
    from naas_abi_core.engine.call_context import (
        CallContext,
        service_account,
        use_call_context,
        user,
    )
    from naas_abi_core.engine.nats_auth import APP_AUDIENCE, CODING_AUDIENCE

    with use_call_context(CallContext(principal=service_account("api"), on_behalf_of=user(ada.id))):
        iam.create_key(
            ada.id,
            audience=CODING_AUDIENCE,
            resource="http://coder:8378",
            expires_at=datetime.now(UTC) + timedelta(days=1),
        )
        iam.create_key(
            ada.id,
            kind="grant",
            audience=APP_AUDIENCE,
            expires_at=datetime.now(UTC) + timedelta(hours=1),
        )
    assert client.get("/api/iam/api-keys", headers=session_headers(ada.id)).json() == []


# -- the token endpoint of scripts -----------------------------------------------------------------


def test_a_script_exchanges_its_key_for_a_short_token(client, ada):
    secret = create(client, ada).json()["secret"]
    for send in (
        lambda: client.post(
            "/api/iam/token",
            data={"grant_type": "client_credentials", "client_secret": secret},
        ),
        lambda: client.post(
            "/api/iam/token",
            json={"grant_type": "client_credentials", "client_secret": secret},
        ),
    ):
        response = send()
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["token_type"] == "Bearer" and 0 < body["expires_in"] <= 600
        used = client.get(
            "/api/whoami", headers={"Authorization": f"Bearer {body['access_token']}"}
        )
        assert used.status_code == 200 and used.json()["id"] == ada.id


def test_the_token_endpoint_refuses_every_bad_request_alike(client, ada, iam):
    secret = create(client, ada).json()["secret"]
    unknown = client.post(
        "/api/iam/token",
        data={"grant_type": "client_credentials", "client_secret": "abi_pk_aaaaaaaaaaaaaaaa_x"},
    )
    assert unknown.status_code == 401 and unknown.json()["detail"] == "invalid_client"
    garbage = client.post(
        "/api/iam/token", data={"grant_type": "client_credentials", "client_secret": "nope"}
    )
    assert garbage.status_code == 401 and garbage.json() == unknown.json()
    wrong_grant = client.post(
        "/api/iam/token", data={"grant_type": "password", "client_secret": secret}
    )
    assert wrong_grant.status_code == 400
    assert wrong_grant.json()["detail"] == "unsupported_grant_type"
    missing = client.post("/api/iam/token", data={"grant_type": "client_credentials"})
    assert missing.status_code == 400 and missing.json()["detail"] == "invalid_request"
    # A key of another purpose is no API key.
    from naas_abi_core.engine.call_context import (
        CallContext,
        service_account,
        use_call_context,
        user,
    )
    from naas_abi_core.engine.nats_auth import CODING_AUDIENCE

    with use_call_context(CallContext(principal=service_account("api"), on_behalf_of=user(ada.id))):
        coding = iam.create_key(
            ada.id,
            audience=CODING_AUDIENCE,
            resource="http://coder:8378",
            expires_at=datetime.now(UTC) + timedelta(days=1),
        ).value
    other = client.post(
        "/api/iam/token",
        data={"grant_type": "client_credentials", "client_secret": coding},
    )
    assert other.status_code == 401 and other.json() == unknown.json()


def test_a_revoked_key_buys_no_token(client, ada):
    created = create(client, ada).json()
    client.delete(f"/api/iam/api-keys/{created['key']['id']}", headers=session_headers(ada.id))
    response = client.post(
        "/api/iam/token",
        data={"grant_type": "client_credentials", "client_secret": created["secret"]},
    )
    assert response.status_code == 401


def test_without_the_engine_nobody_is_signed_in_and_the_token_route_says_so(client, ada):
    headers = session_headers(ada.id)  # made while there still is an engine
    previous = credentials.configure_iam(lambda: None)
    try:
        # No engine, no one to vouch for a session: nobody is signed in...
        response = client.get("/api/iam/api-keys", headers=headers)
        assert response.status_code == 401
        # ...and the public token endpoint says why it cannot answer.
        token = client.post(
            "/api/iam/token",
            data={"grant_type": "client_credentials", "client_secret": "abi_pk_x_y"},
        )
        assert token.status_code == 503
    finally:
        credentials.configure_iam(previous)


def test_failed_exchanges_are_rate_limited_and_good_ones_are_not_counted(client, ada, attempts):
    from naas_abi.apps.nexus.apps.api.app.core.config import settings

    secret = create(client, ada).json()["secret"]
    good = {"grant_type": "client_credentials", "client_secret": secret}
    bad = {"grant_type": "client_credentials", "client_secret": "abi_pk_aaaaaaaaaaaaaaaa_x"}
    for _ in range(3):
        assert client.post("/api/iam/token", data=good).status_code == 200
    assert attempts == []
    for _ in range(settings.rate_limit_ip_attempts):
        assert client.post("/api/iam/token", data=bad).status_code == 401
    # Over the limit, even the right key waits.
    assert client.post("/api/iam/token", data=good).status_code == 429
