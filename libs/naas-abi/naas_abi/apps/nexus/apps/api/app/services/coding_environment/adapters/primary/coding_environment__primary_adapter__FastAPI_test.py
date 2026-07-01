from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from naas_abi.apps.nexus.apps.api.app.api.endpoints.auth import (
    User,
    get_current_user_required,
)
from naas_abi.apps.nexus.apps.api.app.core.database import get_db
from naas_abi.apps.nexus.apps.api.app.models import CodingEnvironmentModel
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
from sqlalchemy import Delete


class _FakeResult:
    def __init__(self, obj: object = None, rows: list | None = None) -> None:
        self._obj = obj
        self._rows = rows or []

    def scalar_one_or_none(self) -> object:
        return self._obj

    def all(self) -> list:
        return self._rows


class _FakeSession:
    """Minimal AsyncSession stand-in: one in-memory workspace row plus an
    in-memory ``coding_environments`` table (the per-repo workspace bindings)."""

    def __init__(self, workspace: object) -> None:
        self._workspace = workspace
        self._envs: list[CodingEnvironmentModel] = []

    def add(self, obj: object) -> None:
        if isinstance(obj, CodingEnvironmentModel):
            self._envs.append(obj)

    async def execute(self, statement: object, *args: object, **kwargs: object) -> _FakeResult:
        # Cleanup on workspace deletion.
        if isinstance(statement, Delete):
            try:
                target = statement.whereclause.right.value  # type: ignore[union-attr]
                self._envs = [e for e in self._envs if e.id != target]
            except Exception:
                pass
            return _FakeResult()
        # The (env id -> repo) lookup selects CodingEnvironmentModel columns.
        descs = getattr(statement, "column_descriptions", []) or []
        entity = descs[0].get("entity") if descs else None
        if entity is CodingEnvironmentModel:
            return _FakeResult(rows=[(e.id, e.repo_id) for e in self._envs])
        # Everything else is a WorkspaceModel lookup.
        return _FakeResult(obj=self._workspace)

    async def commit(self) -> None:
        return None

    async def rollback(self) -> None:
        return None


def _client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    """A TestClient with the router mounted against the in-memory fakes.

    Auth, workspace access and the DB are bypassed so the test needs no real DB
    or live Coder. An in-memory source_control with the configured monorepo
    backs the auto-clone orchestration.
    """
    service = CodingEnvironmentService(InMemoryAdapter())
    source_control = SourceControlService(SourceControlInMemoryAdapter())
    owner, name = ce_api.settings.coding_repo_id.split("/", 1)
    source_control.ensure_repo(owner=owner, name=name)
    workspace_row = SimpleNamespace(id="org", coding_default_repo_id=None)
    app = FastAPI()
    app.include_router(ce_api.router, prefix="/coding-environments")
    app.dependency_overrides[get_current_user_required] = lambda: User.model_construct(
        id="user-1", email="user@example.com", name="User One"
    )
    app.dependency_overrides[ce_api._get_coding_environment_service] = lambda: service
    app.dependency_overrides[ce_api._get_source_control_service] = lambda: source_control

    # One session shared across requests so the in-memory coding_environments
    # bindings written at provision time survive into the list request.
    session = _FakeSession(workspace_row)

    async def _fake_db():
        yield session

    app.dependency_overrides[get_db] = _fake_db

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


def test_workspaces_scoped_to_repo(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _client(monkeypatch)
    # A second repo to host its own workspace.
    assert (
        client.post(
            "/coding-environments/repos", json={"workspace_id": "org", "name": "lib"}
        ).status_code
        == 200
    )
    # One workspace per repo.
    mono = client.post(
        "/coding-environments",
        json={"workspace_id": "org", "name": "mono-ws", "template_id": "tmpl-default"},
    ).json()
    assert mono["repo_id"] == "abi/monorepo"
    lib = client.post(
        "/coding-environments",
        json={
            "workspace_id": "org",
            "name": "lib-ws",
            "template_id": "tmpl-default",
            "repo_id": "abi/lib",
        },
    ).json()
    assert lib["repo_id"] == "abi/lib"

    # Filtering by repo shows only that repo's workspace.
    mono_list = client.get(
        "/coding-environments", params={"workspace_id": "org", "repo_id": "abi/monorepo"}
    ).json()
    assert [e["name"] for e in mono_list] == ["mono-ws"]
    lib_list = client.get(
        "/coding-environments", params={"workspace_id": "org", "repo_id": "abi/lib"}
    ).json()
    assert [e["name"] for e in lib_list] == ["lib-ws"]

    # No filter -> both (back-compat).
    both = client.get("/coding-environments", params={"workspace_id": "org"}).json()
    assert sorted(e["name"] for e in both) == ["lib-ws", "mono-ws"]


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


def test_create_repo_is_empty_with_clone_url(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _client(monkeypatch)
    resp = client.post(
        "/coding-environments/repos", json={"workspace_id": "org", "name": "fresh"}
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["repo_id"] == "abi/fresh"
    assert body["clone_url"].endswith("/abi/fresh.git")
    # empty repo -> no branches yet (the push-setup signal for the UI)
    branches = client.get(
        "/coding-environments/branches",
        params={"workspace_id": "org", "repo_id": "abi/fresh"},
    ).json()
    assert branches == []


def test_mint_agent_token_round_trips() -> None:
    from naas_abi.apps.nexus.apps.api.app.services.auth.service import decode_token

    tok = ce_api._mint_agent_token("user-9")
    payload = decode_token(tok)
    assert payload is not None
    assert payload["sub"] == "user-9"


def test_generate_git_token(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _client(monkeypatch)
    resp = client.post(
        "/coding-environments/git-token",
        json={"workspace_id": "org", "repo_id": "abi/monorepo"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["username"]
    assert body["token"]


def test_default_repo_get_set(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _client(monkeypatch)
    # defaults to the configured repo
    resp = client.get("/coding-environments/default-repo", params={"workspace_id": "org"})
    assert resp.status_code == 200, resp.text
    assert resp.json()["repo_id"] == "abi/monorepo"
    # set a new default (team-shared), then read it back
    resp = client.put(
        "/coding-environments/default-repo",
        json={"workspace_id": "org", "repo_id": "abi/other"},
    )
    assert resp.status_code == 200, resp.text
    resp = client.get("/coding-environments/default-repo", params={"workspace_id": "org"})
    assert resp.json()["repo_id"] == "abi/other"


def test_repo_contents_and_file(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _client(monkeypatch)
    # the seeded monorepo was auto-initialised with a README
    entries = client.get(
        "/coding-environments/repo-contents", params={"workspace_id": "org"}
    ).json()
    assert any(e["name"] == "README.md" and e["type"] == "file" for e in entries)
    f = client.get(
        "/coding-environments/repo-file",
        params={"workspace_id": "org", "path": "README.md"},
    ).json()
    assert f["text"].startswith("# ")
    assert f["is_binary"] is False


def test_repos_carry_metadata(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _client(monkeypatch)
    repos = client.get("/coding-environments/repos", params={"workspace_id": "org"}).json()
    mono = next(r for r in repos if r["repo_id"] == "abi/monorepo")
    assert "private" in mono and "empty" in mono and "clone_url" in mono


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
