import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from naas_abi.apps.nexus.apps.api.app.services.auth.adapters.primary.auth__primary_adapter__dependencies import (
    PlatformCaller,
    get_current_user,
    require_superadmin_or_api_key,
)
from naas_abi.apps.nexus.apps.api.app.services.auth.adapters.primary.auth__primary_adapter__schemas import (
    User,
)

KEY = "abi-key-for-tests"


def _user(*, superadmin):
    return User.model_construct(
        id="u1", email="u1@example.com", name="U1", is_superadmin=superadmin
    )


def _client(user):
    """An app whose only route needs the dependency; ``user`` is who the session resolves to."""
    app = FastAPI()

    @app.get("/who")
    async def who(caller: PlatformCaller = Depends(require_superadmin_or_api_key)):
        return {"via": caller.via, "user_id": caller.user_id}

    app.dependency_overrides[get_current_user] = lambda: user
    return TestClient(app)


@pytest.fixture(autouse=True)
def api_key(monkeypatch):
    monkeypatch.setenv("ABI_API_KEY", KEY)


def test_the_api_key_stands_for_the_operator_without_a_user():
    response = _client(None).get("/who", headers={"Authorization": f"Bearer {KEY}"})

    assert response.status_code == 200
    assert response.json() == {"via": "api_key", "user_id": ""}


def test_the_api_key_wins_over_a_session_that_is_not_a_super_admin():
    response = _client(_user(superadmin=False)).get(
        "/who", headers={"Authorization": f"Bearer {KEY}"}
    )

    assert response.json()["via"] == "api_key"


def test_a_super_admin_session_is_a_user_caller():
    response = _client(_user(superadmin=True)).get("/who")

    assert response.status_code == 200
    assert response.json() == {"via": "user", "user_id": "u1"}


def test_a_user_who_is_not_a_super_admin_gets_403():
    assert _client(_user(superadmin=False)).get("/who").status_code == 403


def test_no_credentials_get_401():
    response = _client(None).get("/who")

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


@pytest.mark.parametrize("token", ["wrong-key", KEY.upper(), KEY + " ", ""])
def test_another_token_is_not_the_api_key(token):
    response = _client(None).get("/who", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 401


def test_the_key_is_not_accepted_as_a_query_parameter_or_a_cookie():
    client = _client(None)

    assert client.get("/who", params={"token": KEY}).status_code == 401
    assert client.get("/who", cookies={"abi_app_html_token": KEY}).status_code == 401


def test_without_a_configured_key_nothing_is_accepted_as_one(monkeypatch):
    monkeypatch.delenv("ABI_API_KEY")

    assert _client(None).get("/who", headers={"Authorization": "Bearer "}).status_code == 401
    assert _client(None).get("/who", headers={"Authorization": f"Bearer {KEY}"}).status_code == 401
