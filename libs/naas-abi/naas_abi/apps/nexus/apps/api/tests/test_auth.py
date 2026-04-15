"""
Authentication tests for magic-link login and token validation.
Maps to: docs/TEST-PROTOCOL.md Section 2.
"""


class TestMagicLink:
    async def test_request_magic_link(self, client, test_user):
        response = await client.post(
            "/api/auth/magic-link/request",
            json={"email": test_user["email"]},
        )
        assert response.status_code == 200
        assert response.json()["status"] == "success"

    async def test_request_magic_link_unknown_user_does_not_create_token(self, client):
        from sqlalchemy import text

        import app.core.database as db_module

        email = "not-registered@example.com"
        response = await client.post(
            "/api/auth/magic-link/request",
            json={"email": email},
        )
        assert response.status_code == 200
        assert response.json()["status"] == "success"

        with db_module.engine.connect() as conn:
            user_row = conn.execute(
                text("SELECT id FROM users WHERE email = :email"),
                {"email": email},
            ).fetchone()
            assert user_row is None

    async def test_verify_magic_link(self, client, test_user):
        from sqlalchemy import text

        import app.core.database as db_module

        await client.post("/api/auth/magic-link/request", json={"email": test_user["email"]})

        with db_module.engine.connect() as conn:
            row = conn.execute(
                text(
                    "SELECT token FROM magic_link_tokens WHERE user_id = :user_id ORDER BY created_at DESC LIMIT 1"
                ),
                {"user_id": test_user["id"]},
            ).fetchone()
            assert row is not None
            hashed_token = row[0]

        # Adapter accepts both hashed and plain token for backward compatibility.
        response = await client.post(
            "/api/auth/magic-link/verify",
            json={"token": hashed_token},
        )
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["user"]["id"] == test_user["id"]

    async def test_password_login_is_disabled(self, client, test_user):
        response = await client.post(
            "/api/auth/login",
            json={"email": test_user["email"], "password": "whatever"},
        )
        assert response.status_code == 410


class TestProtectedEndpoints:
    """AUTH-03/04: Access control on protected endpoints."""

    async def test_no_token_returns_401(self, client):
        """AUTH-03: Accessing protected endpoint without token returns 401."""
        response = await client.get("/api/chat/conversations?workspace_id=ws-test")
        assert response.status_code == 401

    async def test_valid_token_returns_data(self, client, test_user, test_workspace):
        """AUTH-04: Accessing protected endpoint with valid token works."""
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

    async def test_expired_token_returns_401(self, client):
        """Expired token returns 401."""
        from datetime import timedelta

        from app.api.endpoints.auth import create_access_token

        token, _ = create_access_token(
            data={"sub": "user-test"}, expires_delta=timedelta(seconds=-1)
        )
        response = await client.get(
            "/api/chat/conversations?workspace_id=ws-test",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 401


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
