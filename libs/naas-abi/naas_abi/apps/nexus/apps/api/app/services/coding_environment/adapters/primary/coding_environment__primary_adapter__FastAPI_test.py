from __future__ import annotations

from types import SimpleNamespace
from urllib.parse import parse_qs

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
from naas_abi_core.engine.call_context import (
    CallContext,
    as_service_account,
    service_account,
    use_call_context,
    user,
)
from naas_abi_core.services.coding_environment.adapters.secondary.InMemoryAdapter import (
    InMemoryAdapter,
)
from naas_abi_core.services.coding_environment.CodingEnvironmentService import (
    CodingEnvironmentService,
)
from naas_abi_core.services.iam.IAMService import LEGACY_NEXUS_ISSUER
from naas_abi_core.services.iam.tests.authorization_contract import (
    contract_iam,
    wire,
)
from naas_abi_core.services.iam.tests.iam_harness import IAMHarness, statement
from naas_abi_core.services.source_control.adapters.secondary.InMemoryAdapter import (
    InMemoryAdapter as SourceControlInMemoryAdapter,
)
from naas_abi_core.services.source_control.SourceControlService import (
    SourceControlService,
)
from sqlalchemy import Delete

pytestmark = pytest.mark.usefixtures("engine_iam")


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

    async def get(self, model: object, key: object) -> object:
        if model is CodingEnvironmentModel:
            return next((e for e in self._envs if e.id == key), None)
        return None

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


class _AsUser:
    """Each request runs as ``api`` on behalf of the signed-in user, in its
    workspace, as Nexus's identity middleware sets it."""

    def __init__(self, app, user_id: str = "user-1") -> None:
        self.app, self.user_id = app, user_id

    async def __call__(self, scope, receive, send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        query = parse_qs(scope.get("query_string", b"").decode())
        context = CallContext(
            principal=service_account("api"),
            on_behalf_of=user(self.user_id),
            workspace_id=(query.get("workspace_id") or [None])[0],
        )
        with use_call_context(context):
            await self.app(scope, receive, send)


def _client(monkeypatch: pytest.MonkeyPatch, role: str = "owner") -> TestClient:
    """A TestClient with the router mounted against the in-memory fakes.

    Auth, workspace access and the DB are bypassed so the test needs no real DB
    or live Coder. An in-memory source_control with the configured monorepo
    backs the auto-clone orchestration. The kernel services are wired with an
    IAM; the caller is ``api`` acting for ``user-1``, a Nexus user, whose
    workspace role is ``role``.
    """
    iam = contract_iam()
    service = wire(CodingEnvironmentService(InMemoryAdapter()), iam)
    source_control = wire(SourceControlService(SourceControlInMemoryAdapter()), iam)
    owner, name = ce_api.settings.coding_repo_id.split("/", 1)
    with as_service_account("engine"):
        source_control.ensure_repo(owner=owner, name=name)
    workspace_row = SimpleNamespace(id="org", coding_default_repo_id=None, organization_id=None)
    app = FastAPI()
    app.include_router(ce_api.router, prefix="/coding-environments")
    app.add_middleware(_AsUser)
    app.dependency_overrides[get_current_user_required] = lambda: User.model_construct(
        id="user-1", email="user@example.com", name="User One"
    )
    app.dependency_overrides[ce_api._get_coding_environment_service] = lambda: service
    app.dependency_overrides[ce_api._get_source_control_service] = lambda: source_control
    app.dependency_overrides[ce_api._get_iam] = lambda: iam

    # One session shared across requests so the in-memory coding_environments
    # bindings written at provision time survive into the list request.
    session = _FakeSession(workspace_row)

    async def _fake_db():
        yield session

    app.dependency_overrides[get_db] = _fake_db

    async def _allow(user_id: str, workspace_id: str) -> str:
        return role

    monkeypatch.setattr(ce_api, "require_workspace_access", _allow)
    client = TestClient(app)
    client.iam = iam  # type: ignore[attr-defined]
    client.source_control = source_control  # type: ignore[attr-defined]
    return client


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
        for b in client.get("/coding-environments/branches", params={"workspace_id": "org"}).json()
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
        for b in client.get("/coding-environments/branches", params={"workspace_id": "org"}).json()
    ]
    assert "feature/x" not in names


def test_get_logs(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _client(monkeypatch)
    env = client.post(
        "/coding-environments",
        json={"workspace_id": "org", "name": "lg", "template_id": "tmpl-default"},
    ).json()
    resp = client.get(f"/coding-environments/{env['id']}/logs", params={"workspace_id": "org"})
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
    resp = client.post("/coding-environments/repos", json={"workspace_id": "org", "name": "lib"})
    assert resp.status_code == 200, resp.text
    assert resp.json()["repo_id"] == "abi/lib"
    repos2 = [
        r["repo_id"]
        for r in client.get("/coding-environments/repos", params={"workspace_id": "org"}).json()
    ]
    assert "abi/lib" in repos2


def test_create_repo_is_empty_with_clone_url(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _client(monkeypatch)
    resp = client.post("/coding-environments/repos", json={"workspace_id": "org", "name": "fresh"})
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


def test_the_agent_holds_a_key_of_the_user_bound_to_its_sidecar_never_a_session(
    engine_iam,
) -> None:
    import asyncio

    from naas_abi.apps.nexus.apps.api.app.services.auth import credentials
    from naas_abi.apps.nexus.apps.api.app.services.auth.service import decode_token

    base = "http://coder-ada-demo:8378"
    key = asyncio.run(ce_api._mint_agent_token("user-9", "ws-1", base, label="demo"))

    assert key.startswith("abi_pk_")
    assert decode_token(key) is None  # no session, whatever it is presented to
    found = asyncio.run(credentials.bearer_credential(key))
    assert found is not None
    assert (found.kind, found.user_id, found.resource) == ("coding", "user-9", base)


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
    # set a new default (team-shared, one of this workspace's repos), then read it back
    client.post("/coding-environments/repos", json={"workspace_id": "org", "name": "other"})
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
        for b in client.get("/coding-environments/branches", params={"workspace_id": "org"}).json()
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


# --- bug (b): write access only on a repository the caller may write ---------------


def _collaborators(client: TestClient, repo_id: str) -> dict:
    adapter = client.source_control.adapter  # type: ignore[attr-defined]
    return adapter._repos[repo_id].get("collaborators", {})


def _other_workspace_repo(client: TestClient) -> str:
    """A repository placed in another workspace."""
    iam = client.iam  # type: ignore[attr-defined]
    with as_service_account("engine"):
        client.source_control.ensure_repo(owner="abi", name="theirs")  # type: ignore[attr-defined]
        iam.put_placement("source_control", "abi%2Ftheirs", "-", "other-ws")
        iam.put_placement("source_control", "abi%2Ftheirs/*", "-", "other-ws")
    return "abi/theirs"


def test_a_member_gets_no_write_access_to_another_workspaces_repository(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = _client(monkeypatch, role="member")
    theirs = _other_workspace_repo(client)
    resp = client.post(
        "/coding-environments/git-token",
        json={"workspace_id": "org", "repo_id": theirs},
    )
    assert resp.status_code == 404, resp.text
    resp = client.post(
        "/coding-environments",
        json={
            "workspace_id": "org",
            "name": "dev",
            "template_id": "tmpl-default",
            "repo_id": theirs,
        },
    )
    assert resp.status_code == 404, resp.text
    resp = client.post(
        "/coding-environments/sandbox/runtime",
        params={"workspace_id": "org", "repo_id": theirs},
    )
    assert resp.status_code == 404, resp.text
    resp = client.post(
        "/coding-environments/branches",
        json={"workspace_id": "org", "name": "x", "repo_id": theirs},
    )
    assert resp.status_code == 404, resp.text
    assert _collaborators(client, theirs) == {}
    # Nor can it read it, or make it this workspace's default.
    resp = client.get(
        "/coding-environments/repo-contents",
        params={"workspace_id": "org", "repo_id": theirs},
    )
    assert resp.status_code == 404
    resp = client.put(
        "/coding-environments/default-repo",
        json={"workspace_id": "org", "repo_id": theirs},
    )
    assert resp.status_code in (403, 404)


def test_a_member_cannot_take_another_workspaces_repository_name(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = _client(monkeypatch, role="member")
    _other_workspace_repo(client)
    resp = client.post("/coding-environments/repos", json={"workspace_id": "org", "name": "theirs"})
    assert resp.status_code == 409, resp.text
    assert _collaborators(client, "abi/theirs") == {}


@pytest.mark.parametrize("name", ["secret", "SECRET", "sEcReT"])
def test_a_different_case_name_never_hands_over_another_workspaces_repository(
    monkeypatch: pytest.MonkeyPatch, name: str
) -> None:
    """Regression (security review): the forge looks repositories up without
    case, so ``abi/secret`` is workspace A's ``abi/Secret``. A member of B
    asking to create it gets 409, no grant, and A's placement stays."""
    client = _client(monkeypatch, role="member")
    iam = client.iam  # type: ignore[attr-defined]
    with as_service_account("engine"):
        client.source_control.ensure_repo(owner="abi", name="Secret")  # type: ignore[attr-defined]
        iam.put_placement("source_control", "abi%2Fsecret", "-", "other-ws")
        iam.put_placement("source_control", "abi%2Fsecret/*", "-", "other-ws")
    resp = client.post("/coding-environments/repos", json={"workspace_id": "org", "name": name})
    assert resp.status_code == 409, resp.text
    assert _collaborators(client, "abi/Secret") == {}
    assert iam.resolve_placement("source_control", "abi%2Fsecret") == ("-", "other-ws")
    resp = client.post(
        "/coding-environments/git-token",
        json={"workspace_id": "org", "repo_id": f"abi/{name}"},
    )
    assert resp.status_code == 404, resp.text
    assert _collaborators(client, "abi/Secret") == {}


@pytest.mark.parametrize("name", ["legacy", "Legacy"])
def test_a_repository_that_predates_iam_is_never_claimed(
    monkeypatch: pytest.MonkeyPatch, name: str
) -> None:
    """Regression (security review): a repository with no placement is not
    free; asking to create it, in any case, places nothing and grants nothing."""
    client = _client(monkeypatch, role="member")
    with as_service_account("engine"):
        client.source_control.adapter.ensure_repo(owner="abi", name="legacy")  # type: ignore[attr-defined]
    resp = client.post("/coding-environments/repos", json={"workspace_id": "org", "name": name})
    assert resp.status_code == 409, resp.text
    assert _collaborators(client, "abi/legacy") == {}
    assert client.iam.placement_of("source_control", "abi%2Flegacy") is None  # type: ignore[attr-defined]


def test_a_viewer_gets_no_write_access(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _client(monkeypatch, role="viewer")
    resp = client.post(
        "/coding-environments/git-token",
        json={"workspace_id": "org", "repo_id": "abi/monorepo"},
    )
    assert resp.status_code == 403, resp.text
    assert _collaborators(client, "abi/monorepo") == {}
    # A viewer still reads the workspace's repositories.
    resp = client.get("/coding-environments/repo-contents", params={"workspace_id": "org"})
    assert resp.status_code == 200


def test_a_member_iam_denies_writing_gets_no_write_access(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = _client(monkeypatch, role="member")
    h = IAMHarness(client.iam)  # type: ignore[attr-defined]
    record = h.admin("ensure_user", LEGACY_NEXUS_ISSUER, "user-1")
    h.grant(
        record.id,
        statement(
            "Deny",
            ["source_control:UpsertFile"],
            ["abi:-:-:source_control:repo/abi%2Fmonorepo"],
        ),
    )
    resp = client.post(
        "/coding-environments/git-token",
        json={"workspace_id": "org", "repo_id": "abi/monorepo"},
    )
    assert resp.status_code == 403, resp.text
    assert _collaborators(client, "abi/monorepo") == {}


def test_a_member_gets_write_access_to_a_repository_of_the_workspace(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = _client(monkeypatch, role="member")
    resp = client.post("/coding-environments/repos", json={"workspace_id": "org", "name": "ours"})
    assert resp.status_code == 200, resp.text
    assert client.iam.resolve_placement("source_control", "abi%2Fours") == (  # type: ignore[attr-defined]
        "-",
        "org",
    )
    resp = client.post(
        "/coding-environments/git-token",
        json={"workspace_id": "org", "repo_id": "abi/ours"},
    )
    assert resp.status_code == 200, resp.text
    assert _collaborators(client, "abi/ours") == {resp.json()["username"]: "write"}
