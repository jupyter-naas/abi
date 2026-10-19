"""
Authentication: Nexus has no login of its own (RFC §13).

People sign in at an identity provider (``/api/auth/oidc``, covered by
``app/services/oidc/oidc_sign_in_test.py``); the API reads the session cookie that
sign-in sets, a personal API key, or a session token the engine issued. Nothing
here makes a password, magic-link or one-time-code session.
Maps to: docs/TEST-PROTOCOL.md Section 2.
"""

import pytest

REMOVED_LOGIN_ROUTES = [
    ("POST", "/api/auth/login", {"email": "a@example.com", "password": "whatever"}),
    ("POST", "/api/auth/register", {"email": "a@example.com", "password": "whatever1", "name": "A"}),
    ("POST", "/api/auth/token", None),
    ("POST", "/api/auth/refresh", {"refresh_token": "x"}),
    ("POST", "/api/auth/magic-link/request", {"email": "a@example.com"}),
    ("POST", "/api/auth/magic-link/verify", {"token": "x"}),
    ("POST", "/api/auth/otp/verify", {"email": "a@example.com", "code": "123456"}),
    ("POST", "/api/auth/forgot-password", {"email": "a@example.com"}),
    ("POST", "/api/auth/reset-password", {"token": "x", "new_password": "whatever1"}),
    ("POST", "/api/auth/change-password", {"current_password": "x", "new_password": "whatever1"}),
    ("POST", "/api/auth/logout", None),
    ("GET", "/api/auth/config", None),
]


class TestNoBuiltInLogin:
    @pytest.mark.parametrize(("method", "path", "body"), REMOVED_LOGIN_ROUTES)
    async def test_the_login_routes_are_gone(self, client, test_user, method, path, body):
        response = await client.request(method, path, json=body)
        assert response.status_code in (404, 405), (path, response.status_code, response.text)
        # And they hand out no token, whoever asks.
        assert "access_token" not in response.text
        assert "refresh_token" not in response.text

    async def test_the_signed_in_users_own_routes_stay(self, client, test_user):
        for path in ("/api/auth/me", "/api/auth/oidc/providers"):
            response = await client.get(path, headers=test_user["headers"])
            assert response.status_code == 200, path


class TestProtectedEndpoints:
    """AUTH-03/04: Access control on protected endpoints."""

    async def test_no_token_returns_401(self, client):
        """AUTH-03: Accessing protected endpoint without token returns 401."""
        response = await client.get("/api/chat/conversations?workspace_id=ws-test")
        assert response.status_code == 401

    async def test_valid_token_returns_data(self, client, test_user, test_workspace):
        """AUTH-04: Accessing protected endpoint with a session of the engine works."""
        response = await client.get(
            f"/api/chat/conversations?workspace_id={test_workspace['id']}",
            headers=test_user["headers"],
        )
        assert response.status_code == 200

    async def test_invalid_token_returns_401(self, client):
        """Accessing protected endpoint with garbage token returns 401."""
        response = await client.get(
            "/api/chat/conversations?workspace_id=ws-test",
            headers={"Authorization": "Bearer garbage.token.here"},
        )
        assert response.status_code == 401

    async def test_a_revoked_session_returns_401(self, client, test_user, test_workspace):
        """The engine ends every token of a user at once (a suspension, a revocation)."""
        from naas_abi_core.engine.call_context import as_service_account

        from tests.conftest import CURRENT_IAM

        iam = CURRENT_IAM[0].iam
        path = f"/api/chat/conversations?workspace_id={test_workspace['id']}"
        assert (await client.get(path, headers=test_user["headers"])).status_code == 200
        record = iam.resolve_user(test_user["id"])
        with as_service_account("engine"):
            iam.suspend_principal(record.id)
        assert (await client.get(path, headers=test_user["headers"])).status_code == 401


class TestGetMe:
    """GET /api/auth/me tests."""

    async def test_get_me_authenticated(self, client, test_user):
        """Returns current user info when authenticated."""
        response = await client.get("/api/auth/me", headers=test_user["headers"])
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == test_user["id"]
        assert data["email"] == test_user["email"]

    async def test_get_me_unauthenticated(self, client):
        """Returns 401 when not authenticated."""
        response = await client.get("/api/auth/me")
        assert response.status_code == 401
