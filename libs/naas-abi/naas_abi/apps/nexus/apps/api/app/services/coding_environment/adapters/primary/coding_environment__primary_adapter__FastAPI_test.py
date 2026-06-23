from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from naas_abi.apps.nexus.apps.api.app.api.endpoints.auth import (
    User,
    get_current_user_required,
)
from naas_abi.apps.nexus.apps.api.app.services.coding_environment.adapters.primary import (
    coding_environment__primary_adapter__FastAPI as ce_api,
)
from naas_abi_core.services.coding_environment.adapters.secondary.InMemoryAdapter import (
    InMemoryAdapter,
)
from naas_abi_core.services.coding_environment.CodingEnvironmentService import (
    CodingEnvironmentService,
)


def _client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    """A TestClient with the router mounted against the in-memory fake.

    Auth and workspace access are bypassed so the test needs no DB or live Coder.
    """
    service = CodingEnvironmentService(InMemoryAdapter())
    app = FastAPI()
    app.include_router(ce_api.router, prefix="/coding-environments")
    app.dependency_overrides[get_current_user_required] = lambda: User.model_construct(
        id="user-1", email="user@example.com", name="User One"
    )
    app.dependency_overrides[ce_api._get_coding_environment_service] = lambda: service

    async def _allow(user_id: str, workspace_id: str) -> str:
        return "owner"

    monkeypatch.setattr(ce_api, "require_workspace_access", _allow)
    return TestClient(app)


def test_templates(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _client(monkeypatch)
    resp = client.get("/coding-environments/templates", params={"workspace_id": "org"})
    assert resp.status_code == 200, resp.text
    assert any(t["id"] == "tmpl-default" for t in resp.json())


def test_provision_lifecycle_and_access(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _client(monkeypatch)
    resp = client.post(
        "/coding-environments",
        json={"workspace_id": "org", "name": "dev", "template_id": "tmpl-default"},
    )
    assert resp.status_code == 200, resp.text
    env = resp.json()
    assert env["phase"] == "running"
    assert env["agent_ready"] is True
    env_id = env["id"]

    resp = client.post(f"/coding-environments/{env_id}/stop", params={"workspace_id": "org"})
    assert resp.json()["phase"] == "stopped"

    resp = client.post(f"/coding-environments/{env_id}/start", params={"workspace_id": "org"})
    assert resp.json()["phase"] == "running"

    resp = client.get(f"/coding-environments/{env_id}/access", params={"workspace_id": "org"})
    assert resp.status_code == 200
    assert "coder_session_token=" in resp.json()["url"]

    resp = client.delete(f"/coding-environments/{env_id}", params={"workspace_id": "org"})
    assert resp.status_code == 200

    resp = client.get(f"/coding-environments/{env_id}", params={"workspace_id": "org"})
    assert resp.status_code == 404


def test_duplicate_name_conflict(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _client(monkeypatch)
    body = {"workspace_id": "org", "name": "dup", "template_id": "tmpl-default"}
    assert client.post("/coding-environments", json=body).status_code == 200
    resp = client.post("/coding-environments", json=body)
    assert resp.status_code == 409
