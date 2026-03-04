"""
Authentication tests - AUTH-01 through AUTH-07.

Tests login, registration, token validation, and session management.
Maps to: docs/TEST-PROTOCOL.md Section 2.
"""

from tests.conftest import TEST_PASSWORD


class TestLogin:
    """AUTH-01/02: Login with valid and invalid credentials."""

    async def test_login_valid_credentials(self, client, test_user):
        """AUTH-01: Login with correct email/password returns token."""
        response = await client.post(
            "/api/auth/login",
            json={"email": test_user["email"], "password": TEST_PASSWORD},
        )
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["user"]["id"] == test_user["id"]
        assert data["user"]["email"] == test_user["email"]
        assert data["token_type"] == "bearer"

    async def test_login_invalid_password(self, client, test_user):
        """AUTH-02: Login with wrong password returns 401."""
        response = await client.post(
            "/api/auth/login",
            json={"email": test_user["email"], "password": "wrongpassword"},
        )
        assert response.status_code == 401
        assert "Invalid" in response.json()["detail"]

    async def test_login_nonexistent_user(self, client):
        """Login with non-existent email returns 401."""
        response = await client.post(
            "/api/auth/login",
            json={"email": "nobody@example.com", "password": "whatever"},
        )
        assert response.status_code == 401

    async def test_login_missing_fields(self, client):
        """Login with missing fields returns 422."""
        response = await client.post("/api/auth/login", json={"email": "a@b.com"})
        assert response.status_code == 422


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

        token = create_access_token(
            data={"sub": "user-test"}, expires_delta=timedelta(seconds=-1)
        )
        response = await client.get(
            "/api/chat/conversations?workspace_id=ws-test",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 401


class TestRegistration:
    """User registration tests."""

    async def test_register_new_user(self, client):
        """Register creates a new user and returns token."""
        response = await client.post(
            "/api/auth/register",
            json={
                "email": "new@example.com",
                "password": "securepass123",
                "name": "New User",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["user"]["email"] == "new@example.com"
        assert data["user"]["name"] == "New User"

    async def test_register_duplicate_email(self, client, test_user):
        """Registering with an existing email returns 400."""
        response = await client.post(
            "/api/auth/register",
            json={
                "email": test_user["email"],
                "password": "securepass123",
                "name": "Duplicate",
            },
        )
        assert response.status_code == 400

    async def test_register_short_password(self, client):
        """Password below minimum length returns 422."""
        response = await client.post(
            "/api/auth/register",
            json={
                "email": "short@example.com",
                "password": "abc",
                "name": "Short Pass",
            },
        )
        assert response.status_code == 422


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
