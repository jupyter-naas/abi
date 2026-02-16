"""
Chat API tests - CHAT-01 through CHAT-05.

Tests conversation CRUD, streaming, and message handling.
Note: Ollama-dependent tests are skipped if Ollama is not running.
Maps to: docs/TEST-PROTOCOL.md Section 4.
"""

from unittest.mock import AsyncMock, patch


class TestConversationCRUD:
    """Conversation create, read, delete."""

    async def test_create_conversation(self, client, test_user, test_workspace):
        """Create a new conversation in a workspace."""
        response = await client.post(
            "/api/chat/conversations",
            json={
                "workspace_id": test_workspace["id"],
                "title": "Test Conversation",
                "agent": "aia",
            },
            headers=test_user["headers"],
        )
        assert response.status_code == 200
        data = response.json()
        assert data["workspace_id"] == test_workspace["id"]
        assert data["title"] == "Test Conversation"
        assert data["agent"] == "aia"
        assert "id" in data

    async def test_list_conversations(self, client, test_user, test_workspace):
        """List conversations returns workspace-scoped results."""
        # Create two conversations
        for title in ["Conv A", "Conv B"]:
            await client.post(
                "/api/chat/conversations",
                json={"workspace_id": test_workspace["id"], "title": title},
                headers=test_user["headers"],
            )

        response = await client.get(
            f"/api/chat/conversations?workspace_id={test_workspace['id']}",
            headers=test_user["headers"],
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2

    async def test_get_conversation_with_messages(self, client, test_user, test_workspace):
        """Get a conversation by ID includes messages."""
        # Create conversation
        conv_response = await client.post(
            "/api/chat/conversations",
            json={"workspace_id": test_workspace["id"], "title": "With Messages"},
            headers=test_user["headers"],
        )
        conv = conv_response.json()

        response = await client.get(
            f"/api/chat/conversations/{conv['id']}",
            headers=test_user["headers"],
        )
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == conv["id"]
        assert "messages" in data

    async def test_delete_conversation(self, client, test_user, test_workspace):
        """Delete a conversation."""
        conv_response = await client.post(
            "/api/chat/conversations",
            json={"workspace_id": test_workspace["id"], "title": "To Delete"},
            headers=test_user["headers"],
        )
        conv = conv_response.json()

        response = await client.delete(
            f"/api/chat/conversations/{conv['id']}",
            headers=test_user["headers"],
        )
        assert response.status_code == 200

        # Verify it's gone
        response = await client.get(
            f"/api/chat/conversations/{conv['id']}",
            headers=test_user["headers"],
        )
        assert response.status_code == 404


class TestChatComplete:
    """POST /api/chat/complete tests (non-streaming)."""

    async def test_complete_creates_conversation_if_missing(
        self, client, test_user, test_workspace
    ):
        """Chat complete auto-creates a conversation when none exists."""
        # Mock the provider to avoid needing Ollama
        with patch(
            "app.api.endpoints.chat.check_ollama_status",
            new_callable=AsyncMock,
            return_value={"status": "offline", "models": [], "multimodal_models": []},
        ):
            response = await client.post(
                "/api/chat/complete",
                json={
                    "message": "Hello test",
                    "workspace_id": test_workspace["id"],
                    "agent": "aia",
                },
                headers=test_user["headers"],
            )
            assert response.status_code == 200
            data = response.json()
            assert "conversation_id" in data
            assert "message" in data

    async def test_complete_with_existing_conversation(
        self, client, test_user, test_workspace
    ):
        """Chat complete can append to an existing conversation."""
        conv_response = await client.post(
            "/api/chat/conversations",
            json={"workspace_id": test_workspace["id"], "title": "Existing"},
            headers=test_user["headers"],
        )
        conv = conv_response.json()

        with patch(
            "app.api.endpoints.chat.check_ollama_status",
            new_callable=AsyncMock,
            return_value={"status": "offline", "models": [], "multimodal_models": []},
        ):
            response = await client.post(
                "/api/chat/complete",
                json={
                    "conversation_id": conv["id"],
                    "workspace_id": test_workspace["id"],
                    "message": "Follow up",
                    "agent": "aia",
                },
                headers=test_user["headers"],
            )
            assert response.status_code == 200
            assert response.json()["conversation_id"] == conv["id"]


class TestChatStream:
    """POST /api/chat/stream tests (SSE)."""

    async def test_stream_returns_sse_format(self, client, test_user, test_workspace):
        """Chat stream returns Server-Sent Events format."""
        with patch(
            "app.api.endpoints.chat.check_ollama_status",
            new_callable=AsyncMock,
            return_value={"status": "offline", "models": [], "multimodal_models": []},
        ):
            response = await client.post(
                "/api/chat/stream",
                json={
                    "message": "Hello",
                    "workspace_id": test_workspace["id"],
                    "agent": "aia",
                },
                headers=test_user["headers"],
            )
            # Should return SSE even for error case (no provider)
            assert response.status_code == 200
            assert "text/event-stream" in response.headers.get("content-type", "")

    async def test_stream_requires_auth(self, client, test_workspace):
        """Chat stream requires authentication."""
        response = await client.post(
            "/api/chat/stream",
            json={
                "message": "Hello",
                "workspace_id": test_workspace["id"],
                "agent": "aia",
            },
        )
        assert response.status_code == 401


class TestOllamaStatus:
    """Ollama status endpoint tests."""

    async def test_ollama_status_endpoint(self, client):
        """GET /api/ollama/status returns status object."""
        response = await client.get("/api/ollama/status")
        assert response.status_code == 200
        data = response.json()
        assert "installed" in data
        assert "running" in data
        assert "models" in data
        assert "default_model" in data
