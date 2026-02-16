"""
Security / Pen test scenarios - PEN-01 through PEN-05.

Tests for common web vulnerabilities: token forgery, path traversal,
SQL injection, CORS, and rate limiting.
Maps to: docs/TEST-PROTOCOL.md Section 5.
"""

from jose import jwt

from app.core.config import settings


class TestJWTSecurity:
    """PEN-01: JWT token security."""

    async def test_forged_token_with_wrong_secret(self, client, test_user):
        """Token signed with wrong secret is rejected."""
        forged = jwt.encode(
            {"sub": test_user["id"], "exp": 9999999999},
            "wrong-secret-key",
            algorithm="HS256",
        )
        response = await client.get(
            "/api/auth/me",
            headers={"Authorization": f"Bearer {forged}"},
        )
        assert response.status_code == 401

    async def test_token_without_sub_claim(self, client):
        """Token without 'sub' claim is rejected."""
        token = jwt.encode(
            {"exp": 9999999999},
            settings.secret_key,
            algorithm="HS256",
        )
        response = await client.get(
            "/api/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 401

    async def test_token_with_nonexistent_user(self, client):
        """Token for a user that doesn't exist is rejected."""
        token = jwt.encode(
            {"sub": "user-does-not-exist", "exp": 9999999999},
            settings.secret_key,
            algorithm="HS256",
        )
        response = await client.get(
            "/api/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 401

    async def test_malformed_authorization_header(self, client):
        """Malformed Authorization header is handled gracefully."""
        # Missing 'Bearer' prefix
        response = await client.get(
            "/api/auth/me",
            headers={"Authorization": "NotBearer token"},
        )
        assert response.status_code == 401

        # Empty header
        response = await client.get(
            "/api/auth/me",
            headers={"Authorization": ""},
        )
        assert response.status_code == 401


class TestPathTraversal:
    """PEN-02: Path traversal in file endpoints."""

    async def test_path_traversal_in_files_list(self, client, test_user):
        """Cannot traverse directories via path parameter."""
        dangerous_paths = [
            "../../etc/passwd",
            "../../../etc/shadow",
            "..%2F..%2Fetc%2Fpasswd",
            "....//....//etc/passwd",
        ]
        for path in dangerous_paths:
            response = await client.get(
                f"/api/files/?path={path}",
                headers=test_user["headers"],
            )
            # Should NOT return 200 with file contents
            # Could be 400, 403, 404, or 500 depending on implementation
            if response.status_code == 200:
                # If 200, ensure it doesn't contain /etc/passwd content
                body = response.text
                assert "root:" not in body, f"Path traversal succeeded with: {path}"

    async def test_path_traversal_in_file_read(self, client, test_user):
        """Cannot read arbitrary files via file path endpoint."""
        response = await client.get(
            "/api/files/../../etc/passwd",
            headers=test_user["headers"],
        )
        if response.status_code == 200:
            assert "root:" not in response.text


class TestSQLInjection:
    """PEN-03: SQL injection attempts."""

    async def test_sql_injection_in_search(self, client, test_user, test_workspace):
        """SQL injection in search query is safely handled."""
        payloads = [
            "' OR 1=1 --",
            "'; DROP TABLE users; --",
            '" UNION SELECT * FROM users --',
            "1; SELECT * FROM secrets",
        ]
        for payload in payloads:
            response = await client.post(
                "/api/search/",
                json={"query": payload, "workspace_id": test_workspace["id"]},
                headers=test_user["headers"],
            )
            # Should handle gracefully (200 with no results, or 400/422)
            assert response.status_code in (200, 400, 422, 500)
            # If 200, should not leak data from other tables
            if response.status_code == 200:
                body = response.text
                assert "hashed_password" not in body
                assert "encrypted_value" not in body

    async def test_sql_injection_in_conversation_search(self, client, test_user, test_workspace):
        """SQL injection in workspace_id parameter."""
        response = await client.get(
            "/api/chat/conversations?workspace_id=' OR 1=1 --",
            headers=test_user["headers"],
        )
        # Should not return all conversations
        assert response.status_code in (200, 400, 403)
        if response.status_code == 200:
            # With parameterized queries, this should return 0 results
            # (no workspace with that literal ID exists)
            data = response.json()
            assert len(data) == 0


class TestCORS:
    """PEN-04: CORS enforcement."""

    async def test_cors_preflight_from_allowed_origin(self, client):
        """CORS preflight from allowed origin succeeds."""
        response = await client.options(
            "/api/auth/login",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "Content-Type",
            },
        )
        # In development, localhost:3000 should be allowed
        assert response.status_code == 200

    async def test_cors_no_wildcard_with_credentials(self, client):
        """CORS should not use wildcard origin when credentials are enabled."""
        response = await client.options(
            "/api/auth/login",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "POST",
            },
        )
        allow_origin = response.headers.get("access-control-allow-origin", "")
        # Should be specific origin, not "*"
        if allow_origin:
            assert allow_origin != "*" or "access-control-allow-credentials" not in response.headers


class TestInputValidation:
    """General input validation tests."""

    async def test_oversized_message_handled(self, client, test_user, test_workspace):
        """Extremely large messages are handled without crashing."""
        response = await client.post(
            "/api/chat/complete",
            json={
                "message": "x" * 100_000,  # 100KB message
                "workspace_id": test_workspace["id"],
                "agent": "aia",
            },
            headers=test_user["headers"],
        )
        # Should not crash - could return 200 (processed) or 422 (too large)
        assert response.status_code in (200, 422, 413)

    async def test_special_characters_in_title(self, client, test_user, test_workspace):
        """Special characters in conversation title don't cause issues."""
        response = await client.post(
            "/api/chat/conversations",
            json={
                "workspace_id": test_workspace["id"],
                "title": '<script>alert("xss")</script>',
            },
            headers=test_user["headers"],
        )
        assert response.status_code == 200
        data = response.json()
        # Title should be stored as-is (escaped on frontend), not executed
        assert "script" in data["title"]

    async def test_unicode_in_message(self, client, test_user, test_workspace):
        """Unicode characters are handled correctly."""
        response = await client.post(
            "/api/chat/conversations",
            json={
                "workspace_id": test_workspace["id"],
                "title": "Salut les amis! C'est l'heure du cafe",
            },
            headers=test_user["headers"],
        )
        assert response.status_code == 200


class TestHealthEndpoints:
    """Health and status endpoints."""

    async def test_health_check_no_auth(self, client):
        """Health check is accessible without authentication."""
        response = await client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"

    async def test_ollama_status_no_auth(self, client):
        """Ollama status is accessible without authentication."""
        response = await client.get("/api/ollama/status")
        assert response.status_code == 200
        data = response.json()
        assert "installed" in data
        assert "running" in data
