"""Tests for OpenAI-compatible API endpoints."""

import json
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from naas_abi_core.apps.api.openai_api import (
    OpenAIChatCompletionRequest,
    OpenAIMessage,
    create_openai_router,
)


@pytest.fixture
def mock_engine():
    """Create a mock engine with test agents."""
    engine = MagicMock()

    # Create a mock agent
    mock_agent = MagicMock()
    mock_agent.name = "test-agent"
    mock_agent.description = "Test agent for unit tests"

    # Create mock New method
    mock_agent_instance = MagicMock()
    mock_agent_instance.name = "test-agent"
    mock_agent_instance.description = "Test agent for unit tests"
    mock_agent_instance.invoke = MagicMock(return_value="Test response")
    mock_agent_instance.stream = MagicMock(return_value=[])
    mock_agent_instance.duplicate = MagicMock(return_value=mock_agent_instance)
    mock_agent_instance.state = MagicMock()
    mock_agent_instance.state.set_thread_id = MagicMock()

    mock_agent.New = MagicMock(return_value=mock_agent_instance)

    # Create mock module with agents
    mock_module = MagicMock()
    mock_module.agents = [mock_agent]

    engine.modules = {"test_module": mock_module}

    return engine


@pytest.fixture
def mock_auth():
    """Create a mock authentication dependency."""

    def auth_dependency():
        return True

    return auth_dependency


@pytest.fixture
def client(mock_engine, mock_auth):
    """Create a test client with the OpenAI router."""
    from fastapi import FastAPI

    app = FastAPI()
    router = create_openai_router(mock_engine, mock_auth)
    app.include_router(router)

    return TestClient(app)


def test_list_models(client):
    """Test listing available models."""
    response = client.get("/v1/models")
    assert response.status_code == 200

    data = response.json()
    assert data["object"] == "list"
    assert len(data["data"]) > 0
    assert data["data"][0]["id"] == "test-agent"
    assert data["data"][0]["object"] == "model"
    assert data["data"][0]["owned_by"] == "abi"


def test_retrieve_model(client):
    """Test retrieving a specific model."""
    response = client.get("/v1/models/test-agent")
    assert response.status_code == 200

    data = response.json()
    assert data["id"] == "test-agent"
    assert data["object"] == "model"
    assert data["owned_by"] == "abi"


def test_retrieve_nonexistent_model(client):
    """Test retrieving a model that doesn't exist."""
    response = client.get("/v1/models/nonexistent-agent")
    assert response.status_code == 404


def test_chat_completion_non_streaming(client):
    """Test non-streaming chat completion."""
    request_data = {
        "model": "test-agent",
        "messages": [
            {"role": "system", "content": "You are a helpful assistant"},
            {"role": "user", "content": "Hello!"},
        ],
        "stream": False,
    }

    response = client.post("/v1/chat/completions", json=request_data)
    assert response.status_code == 200

    data = response.json()
    assert data["object"] == "chat.completion"
    assert data["model"] == "test-agent"
    assert len(data["choices"]) == 1
    assert data["choices"][0]["message"]["role"] == "assistant"
    assert data["choices"][0]["message"]["content"] == "Test response"
    assert data["choices"][0]["finish_reason"] == "stop"
    assert "usage" in data


def test_chat_completion_invalid_model(client):
    """Test chat completion with invalid model."""
    request_data = {
        "model": "nonexistent-agent",
        "messages": [{"role": "user", "content": "Hello!"}],
        "stream": False,
    }

    response = client.post("/v1/chat/completions", json=request_data)
    assert response.status_code == 404


def test_openai_request_validation():
    """Test OpenAI request model validation."""
    # Valid request
    request = OpenAIChatCompletionRequest(
        model="test-agent",
        messages=[OpenAIMessage(role="user", content="Hello")],
    )
    assert request.model == "test-agent"
    assert len(request.messages) == 1
    assert request.stream is False
    assert request.temperature == 1.0

    # Request with parameters
    request = OpenAIChatCompletionRequest(
        model="test-agent",
        messages=[OpenAIMessage(role="user", content="Hello")],
        temperature=0.7,
        stream=True,
        max_tokens=100,
    )
    assert request.temperature == 0.7
    assert request.stream is True
    assert request.max_tokens == 100
