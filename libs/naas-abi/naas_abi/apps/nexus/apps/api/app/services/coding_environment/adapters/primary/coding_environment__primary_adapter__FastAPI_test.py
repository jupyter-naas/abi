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
from naas_abi_core.services.source_control.adapters.secondary.InMemoryAdapter import (
    InMemoryAdapter as SourceControlInMemoryAdapter,
)
from naas_abi_core.services.source_control.SourceControlService import (
    SourceControlService,
)


def _client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    """A TestClient with the router mounted against the in-memory fakes.

    Auth and workspace access are bypassed so the test needs no DB or live Coder.
    An in-memory source_control with the configured monorepo backs the
    auto-clone orchestration.
    """
    service = CodingEnvironmentService(InMemoryAdapter())
    source_control = SourceControlService(SourceControlInMemoryAdapter())
    owner, name = ce_api.settings.coding_repo_id.split("/", 1)
    source_control.ensure_repo(owner=owner, name=name)
    app = FastAPI()
    app.include_router(ce_api.router, prefix="/coding-environments")
    app.dependency_overrides[get_current_user_required] = lambda: User.model_construct(
        id="user-1", email="user@example.com", name="User One"
    )
    app.dependency_overrides[ce_api._get_coding_environment_service] = lambda: service
    app.dependency_overrides[ce_api._get_source_control_service] = lambda: source_control

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


def test_list_environments(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _client(monkeypatch)
    # empty before anything is provisioned
    resp = client.get("/coding-environments", params={"workspace_id": "org"})
    assert resp.status_code == 200, resp.text
    assert resp.json() == []
    # provision two, then list returns both (scoped to the caller's identity)
    for name in ("alpha", "beta"):
        assert (
            client.post(
                "/coding-environments",
                json={"workspace_id": "org", "name": name, "template_id": "tmpl-default"},
            ).status_code
            == 200
        )
    resp = client.get("/coding-environments", params={"workspace_id": "org"})
    assert resp.status_code == 200, resp.text
    assert sorted(e["name"] for e in resp.json()) == ["alpha", "beta"]


def test_duplicate_name_conflict(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _client(monkeypatch)
    body = {"workspace_id": "org", "name": "dup", "template_id": "tmpl-default"}
    assert client.post("/coding-environments", json=body).status_code == 200
    resp = client.post("/coding-environments", json=body)
    assert resp.status_code == 409


def test_list_branches(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _client(monkeypatch)
    resp = client.get("/coding-environments/branches", params={"workspace_id": "org"})
    assert resp.status_code == 200, resp.text
    assert "main" in [b["name"] for b in resp.json()]


def test_branch_crud(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _client(monkeypatch)
    # create
    resp = client.post(
        "/coding-environments/branches",
        json={"workspace_id": "org", "name": "feature/x", "source_branch": "main"},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["name"] == "feature/x"
    # appears in the list
    names = [
        b["name"]
        for b in client.get(
            "/coding-environments/branches", params={"workspace_id": "org"}
        ).json()
    ]
    assert "feature/x" in names
    # duplicate -> 409
    dup = client.post(
        "/coding-environments/branches",
        json={"workspace_id": "org", "name": "feature/x", "source_branch": "main"},
    )
    assert dup.status_code == 409
    # delete (name with a slash, url-encoded by the client)
    resp = client.delete(
        "/coding-environments/branches",
        params={"workspace_id": "org", "name": "feature/x"},
    )
    assert resp.status_code == 200, resp.text
    names = [
        b["name"]
        for b in client.get(
            "/coding-environments/branches", params={"workspace_id": "org"}
        ).json()
    ]
    assert "feature/x" not in names


def test_get_logs(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _client(monkeypatch)
    env = client.post(
        "/coding-environments",
        json={"workspace_id": "org", "name": "lg", "template_id": "tmpl-default"},
    ).json()
    resp = client.get(
        f"/coding-environments/{env['id']}/logs", params={"workspace_id": "org"}
    )
    assert resp.status_code == 200, resp.text
    assert isinstance(resp.json()["lines"], list)
    assert resp.json()["lines"]


def test_get_repo(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _client(monkeypatch)
    resp = client.get("/coding-environments/repo", params={"workspace_id": "org"})
    assert resp.status_code == 200, resp.text
    assert "/" in resp.json()["repo_id"]


def test_list_and_create_repos(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _client(monkeypatch)
    repos = client.get("/coding-environments/repos", params={"workspace_id": "org"}).json()
    assert any(r["repo_id"] == "abi/monorepo" for r in repos)
    # the configured default is surfaced first
    assert repos[0]["repo_id"] == "abi/monorepo"
    # create a new repo under the same owner
    resp = client.post(
        "/coding-environments/repos", json={"workspace_id": "org", "name": "lib"}
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["repo_id"] == "abi/lib"
    repos2 = [
        r["repo_id"]
        for r in client.get(
            "/coding-environments/repos", params={"workspace_id": "org"}
        ).json()
    ]
    assert "abi/lib" in repos2


def test_branches_scoped_to_repo_id(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _client(monkeypatch)
    client.post("/coding-environments/repos", json={"workspace_id": "org", "name": "lib"})
    client.post(
        "/coding-environments/branches",
        json={
            "workspace_id": "org",
            "name": "feat",
            "source_branch": "main",
            "repo_id": "abi/lib",
        },
    )
    lib = [
        b["name"]
        for b in client.get(
            "/coding-environments/branches",
            params={"workspace_id": "org", "repo_id": "abi/lib"},
        ).json()
    ]
    assert "feat" in lib
    # the default repo is unaffected
    default = [
        b["name"]
        for b in client.get(
            "/coding-environments/branches", params={"workspace_id": "org"}
        ).json()
    ]
    assert "feat" not in default


def test_provision_creates_new_branch_from_source(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _client(monkeypatch)
    resp = client.post(
        "/coding-environments",
        json={
            "workspace_id": "org",
            "name": "feat",
            "template_id": "tmpl-default",
            "source_branch": "main",
            "branch": "feature/login",
        },
    )
    assert resp.status_code == 200, resp.text
    # the new branch was created off main in the monorepo
    resp = client.get("/coding-environments/branches", params={"workspace_id": "org"})
    assert "feature/login" in [b["name"] for b in resp.json()]
