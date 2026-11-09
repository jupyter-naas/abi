"""The coding-environments routes, driven through the real router with a real IAM.

Roles are IAM's (``code_iam``: ``ws-1`` with an owner, an admin, a member and a
viewer, ``ws-2`` for the others); the kernel services are wired with the same
IAM, so a repository or an environment is reachable only once placed in the
workspace the caller holds a role in.
"""

from __future__ import annotations

from collections.abc import Iterator
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
from naas_abi.apps.nexus.apps.api.app.services.coding_environment.adapters.primary import (
    coding_environment__primary_adapter__guard as guard_api,
)
from naas_abi.apps.nexus.apps.api.app.services.coding_environment.testing import (
    AsUser,
    code_iam,
    kernel_services,
    place_repo,
    principal_of,
)
from naas_abi.apps.nexus.apps.api.app.services.iam.names import workspace_container
from naas_abi.apps.nexus.apps.api.app.services.iam.testing import NexusIam
from naas_abi_core.engine.call_context import as_service_account
from naas_abi_core.services.iam.IAMService import LEGACY_NEXUS_ISSUER
from naas_abi_core.services.iam.tests.iam_harness import IAMHarness, statement
from sqlalchemy import Delete

pytestmark = pytest.mark.usefixtures("engine_iam")

WS = "ws-1"
WS_CONTAINER = workspace_container("org-1", WS)
MONOREPO = "abi/monorepo"


class _FakeResult:
    def __init__(self, obj: object = None, rows: list | None = None) -> None:
        self._obj = obj
        self._rows = rows or []

    def scalar_one_or_none(self) -> object:
        return self._obj

    def all(self) -> list:
        return self._rows

    def scalars(self) -> SimpleNamespace:
        return SimpleNamespace(first=lambda: self._obj)


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
        if entity is CodingEnvironmentModel and len(descs) > 1:
            return _FakeResult(rows=[(e.id, e.repo_id) for e in self._envs])
        if entity is CodingEnvironmentModel:
            return _FakeResult()
        # Everything else is a WorkspaceModel lookup.
        return _FakeResult(obj=self._workspace)

    async def commit(self) -> None:
        return None

    async def rollback(self) -> None:
        return None


class Client:
    """A TestClient of the router; ``as_user`` picks who signs in."""

    def __init__(self, nexus: NexusIam) -> None:
        self.nexus = nexus
        self.iam = nexus.iam
        self.environments, self.source_control = kernel_services(nexus)
        place_repo(nexus, self.source_control, MONOREPO, WS)
        self._holder = {"user": "member"}
        app = FastAPI()
        app.include_router(ce_api.router, prefix="/coding-environments")
        app.add_middleware(AsUser, nexus=nexus, holder=self._holder)
        app.dependency_overrides[get_current_user_required] = lambda: User.model_construct(
            id=self._holder["user"],
            email=f"{self._holder['user']}@example.com",
            name=self._holder["user"].title(),
        )
        app.dependency_overrides[ce_api._get_coding_environment_service] = lambda: self.environments
        app.dependency_overrides[ce_api._get_source_control_service] = lambda: self.source_control
        app.dependency_overrides[guard_api.get_iam] = lambda: self.iam
        # One session shared across requests so the in-memory coding_environments
        # bindings written at provision time survive into the list request.
        session = _FakeSession(
            SimpleNamespace(id=WS, coding_default_repo_id=None, organization_id="org-1")
        )

        async def _fake_db():
            yield session

        app.dependency_overrides[get_db] = _fake_db
        self.http = TestClient(app)

    def as_user(self, user_id: str) -> Client:
        self._holder["user"] = user_id
        return self

    def get(self, path: str, **kwargs):
        return self.http.get(f"/coding-environments{path}", **kwargs)

    def post(self, path: str, **kwargs):
        return self.http.post(f"/coding-environments{path}", **kwargs)

    def put(self, path: str, **kwargs):
        return self.http.put(f"/coding-environments{path}", **kwargs)

    def delete(self, path: str, **kwargs):
        return self.http.delete(f"/coding-environments{path}", **kwargs)

    def collaborators(self, repo_id: str) -> dict:
        adapter = self.source_control.adapter
        return adapter._repos[repo_id].get("collaborators", {})  # type: ignore[attr-defined]

    def provision(self, name: str = "dev", *, workspace: str = WS, **extra) -> dict:
        resp = self.post(
            "",
            json={
                "workspace_id": workspace,
                "name": name,
                "template_id": "tmpl-default",
                **extra,
            },
        )
        assert resp.status_code == 200, resp.text
        return resp.json()


@pytest.fixture
def client() -> Iterator[Client]:
    with code_iam() as nexus:
        yield Client(nexus)


def _query(**extra: str) -> dict[str, str]:
    return {"workspace_id": WS, **extra}


# --- the routes, as a member of the workspace --------------------------------------


def test_templates(client: Client) -> None:
    resp = client.get("/templates", params=_query())
    assert resp.status_code == 200, resp.text
    assert any(t["id"] == "tmpl-default" for t in resp.json())


def test_provision_lifecycle_and_access(client: Client) -> None:
    env = client.provision()
    assert env["phase"] == "running"
    assert env["agent_ready"] is True
    env_id = env["id"]

    resp = client.post(f"/{env_id}/stop", params=_query())
    assert resp.json()["phase"] == "stopped"

    resp = client.post(f"/{env_id}/start", params=_query())
    assert resp.json()["phase"] == "running"

    resp = client.get(f"/{env_id}/access", params=_query())
    assert resp.status_code == 200
    assert "coder_session_token=" in resp.json()["url"]

    resp = client.delete(f"/{env_id}", params=_query())
    assert resp.status_code == 200

    resp = client.get(f"/{env_id}", params=_query())
    assert resp.status_code == 404


def test_list_environments(client: Client) -> None:
    # empty before anything is provisioned
    resp = client.get("", params=_query())
    assert resp.status_code == 200, resp.text
    assert resp.json() == []
    # provision two, then list returns both (scoped to the caller's identity)
    for name in ("alpha", "beta"):
        client.provision(name)
    resp = client.get("", params=_query())
    assert resp.status_code == 200, resp.text
    assert sorted(e["name"] for e in resp.json()) == ["alpha", "beta"]


def test_workspaces_scoped_to_repo(client: Client) -> None:
    # A second repo to host its own workspace.
    assert client.post("/repos", json={"workspace_id": WS, "name": "lib"}).status_code == 200
    # One workspace per repo.
    assert client.provision("mono-ws")["repo_id"] == MONOREPO
    assert client.provision("lib-ws", repo_id="abi/lib")["repo_id"] == "abi/lib"

    # Filtering by repo shows only that repo's workspace.
    mono_list = client.get("", params=_query(repo_id=MONOREPO)).json()
    assert [e["name"] for e in mono_list] == ["mono-ws"]
    lib_list = client.get("", params=_query(repo_id="abi/lib")).json()
    assert [e["name"] for e in lib_list] == ["lib-ws"]

    # No filter -> both (back-compat).
    both = client.get("", params=_query()).json()
    assert sorted(e["name"] for e in both) == ["lib-ws", "mono-ws"]


def test_provisioning_an_existing_name_adopts_the_callers_environment(client: Client) -> None:
    first = client.provision("dup")
    assert client.provision("dup")["id"] == first["id"]


def test_list_branches(client: Client) -> None:
    resp = client.get("/branches", params=_query())
    assert resp.status_code == 200, resp.text
    assert "main" in [b["name"] for b in resp.json()]


def test_branch_crud(client: Client) -> None:
    resp = client.post(
        "/branches", json={"workspace_id": WS, "name": "feature/x", "source_branch": "main"}
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["name"] == "feature/x"

    def names() -> list[str]:
        return [b["name"] for b in client.get("/branches", params=_query()).json()]

    assert "feature/x" in names()
    dup = client.post(
        "/branches", json={"workspace_id": WS, "name": "feature/x", "source_branch": "main"}
    )
    assert dup.status_code == 409
    # delete (name with a slash, url-encoded by the client)
    resp = client.delete("/branches", params=_query(name="feature/x"))
    assert resp.status_code == 200, resp.text
    assert "feature/x" not in names()


def test_get_logs(client: Client) -> None:
    env = client.provision("lg")
    resp = client.get(f"/{env['id']}/logs", params=_query())
    assert resp.status_code == 200, resp.text
    assert resp.json()["lines"]


def test_get_repo(client: Client) -> None:
    resp = client.get("/repo", params=_query())
    assert resp.status_code == 200, resp.text
    assert "/" in resp.json()["repo_id"]


def test_list_and_create_repos(client: Client) -> None:
    repos = client.get("/repos", params=_query()).json()
    # the configured default is surfaced first
    assert repos[0]["repo_id"] == MONOREPO
    resp = client.post("/repos", json={"workspace_id": WS, "name": "lib"})
    assert resp.status_code == 200, resp.text
    assert resp.json()["repo_id"] == "abi/lib"
    names = [r["repo_id"] for r in client.get("/repos", params=_query()).json()]
    assert "abi/lib" in names


def test_create_repo_is_empty_with_clone_url(client: Client) -> None:
    resp = client.post("/repos", json={"workspace_id": WS, "name": "fresh"})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["repo_id"] == "abi/fresh"
    assert body["clone_url"].endswith("/abi/fresh.git")
    # empty repo -> no branches yet (the push-setup signal for the UI)
    branches = client.get("/branches", params=_query(repo_id="abi/fresh")).json()
    assert branches == []


def test_the_agent_holds_a_key_of_the_user_bound_to_its_sidecar_never_a_session(
    engine_iam,
) -> None:
    import asyncio

    from naas_abi.apps.nexus.apps.api.app.services.auth import credentials

    base = "http://coder-ada-demo:8378"
    key = asyncio.run(ce_api._mint_agent_token("user-9", "ws-1", base, label="demo"))

    assert key.startswith("abi_pk_")
    found = asyncio.run(credentials.bearer_credential(key))
    assert found is not None
    assert (found.kind, found.user_id, found.resource) == ("coding", "user-9", base)


def test_generate_git_token(client: Client) -> None:
    resp = client.post("/git-token", json={"workspace_id": WS, "repo_id": MONOREPO})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["username"]
    assert body["token"]


def test_default_repo_get_set(client: Client) -> None:
    resp = client.get("/default-repo", params=_query())
    assert resp.status_code == 200, resp.text
    assert resp.json()["repo_id"] == MONOREPO
    # set a new default (team-shared, one of this workspace's repos), then read it back
    client.post("/repos", json={"workspace_id": WS, "name": "other"})
    client.as_user("admin")
    resp = client.put("/default-repo", json={"workspace_id": WS, "repo_id": "abi/other"})
    assert resp.status_code == 200, resp.text
    resp = client.get("/default-repo", params=_query())
    assert resp.json()["repo_id"] == "abi/other"


def test_repo_contents_and_file(client: Client) -> None:
    # the seeded monorepo was auto-initialised with a README
    entries = client.get("/repo-contents", params=_query()).json()
    assert any(e["name"] == "README.md" and e["type"] == "file" for e in entries)
    f = client.get("/repo-file", params=_query(path="README.md")).json()
    assert f["text"].startswith("# ")
    assert f["is_binary"] is False
    assert client.get("/repo-commits", params=_query()).status_code == 200


def test_repos_carry_metadata(client: Client) -> None:
    repos = client.get("/repos", params=_query()).json()
    mono = next(r for r in repos if r["repo_id"] == MONOREPO)
    assert "private" in mono and "empty" in mono and "clone_url" in mono


def test_branches_scoped_to_repo_id(client: Client) -> None:
    client.post("/repos", json={"workspace_id": WS, "name": "lib"})
    client.post(
        "/branches",
        json={"workspace_id": WS, "name": "feat", "source_branch": "main", "repo_id": "abi/lib"},
    )
    lib = [b["name"] for b in client.get("/branches", params=_query(repo_id="abi/lib")).json()]
    assert "feat" in lib
    # the default repo is unaffected
    default = [b["name"] for b in client.get("/branches", params=_query()).json()]
    assert "feat" not in default


def test_provision_creates_new_branch_from_source(client: Client) -> None:
    client.provision("feat", source_branch="main", branch="feature/login")
    # the new branch was created off main in the monorepo
    resp = client.get("/branches", params=_query())
    assert "feature/login" in [b["name"] for b in resp.json()]


def test_sandbox_runtime_is_a_write_of_the_workspaces_repository(client: Client) -> None:
    resp = client.post("/sandbox/runtime", params=_query(repo_id=MONOREPO))
    assert resp.status_code == 200, resp.text
    assert resp.json()["ensured"] is True


# --- write access only on a repository the caller may write ---------------


def _other_workspace_repo(client: Client, name: str = "theirs") -> str:
    """A repository placed in another workspace."""
    place_repo(client.nexus, client.source_control, f"abi/{name}", "ws-2")
    return f"abi/{name}"


@pytest.mark.parametrize("user", ["member", "both"])
def test_a_member_gets_no_write_access_to_another_workspaces_repository(
    client: Client, user: str
) -> None:
    """``both`` is a member of the other workspace too: the repository is still not
    this workspace's, whatever the user's roles reach."""
    client.as_user(user)
    theirs = _other_workspace_repo(client)
    resp = client.post("/git-token", json={"workspace_id": WS, "repo_id": theirs})
    assert resp.status_code == 404, resp.text
    resp = client.post(
        "",
        json={"workspace_id": WS, "name": "dev", "template_id": "tmpl-default", "repo_id": theirs},
    )
    assert resp.status_code == 404, resp.text
    resp = client.post("/sandbox/runtime", params=_query(repo_id=theirs))
    assert resp.status_code == 404, resp.text
    resp = client.post("/branches", json={"workspace_id": WS, "name": "x", "repo_id": theirs})
    assert resp.status_code == 404, resp.text
    resp = client.delete("/branches", params=_query(repo_id=theirs, name="main"))
    assert resp.status_code == 404, resp.text
    assert client.collaborators(theirs) == {}
    # Nor can it read it, or make it this workspace's default.
    for path in ("/repo-contents", "/branches", "/repo-commits"):
        assert client.get(path, params=_query(repo_id=theirs)).status_code == 404, path
    assert (
        client.get("/repo-file", params=_query(repo_id=theirs, path="README.md")).status_code == 404
    )
    client.as_user("admin")
    resp = client.put("/default-repo", json={"workspace_id": WS, "repo_id": theirs})
    assert resp.status_code == 404


def test_the_repository_list_shows_only_the_workspaces_own(client: Client) -> None:
    client.as_user("both")
    _other_workspace_repo(client)
    names = [r["repo_id"] for r in client.get("/repos", params=_query()).json()]
    assert names == [MONOREPO]


def test_a_member_cannot_take_another_workspaces_repository_name(client: Client) -> None:
    _other_workspace_repo(client)
    resp = client.post("/repos", json={"workspace_id": WS, "name": "theirs"})
    assert resp.status_code == 409, resp.text
    assert client.collaborators("abi/theirs") == {}


@pytest.mark.parametrize("name", ["secret", "SECRET", "sEcReT"])
def test_a_different_case_name_never_hands_over_another_workspaces_repository(
    client: Client, name: str
) -> None:
    """Regression (security review): the forge looks repositories up without
    case, so ``abi/secret`` is workspace B's ``abi/Secret``. A member of A asking
    to create it gets 409, no grant, and B's placement stays."""
    place_repo(client.nexus, client.source_control, "abi/Secret", "ws-2")
    resp = client.post("/repos", json={"workspace_id": WS, "name": name})
    assert resp.status_code == 409, resp.text
    assert client.collaborators("abi/Secret") == {}
    assert client.iam.resolve_placement("source_control", "abi%2Fsecret") == workspace_container(
        "org-1", "ws-2"
    )
    resp = client.post("/git-token", json={"workspace_id": WS, "repo_id": f"abi/{name}"})
    assert resp.status_code == 404, resp.text
    assert client.collaborators("abi/Secret") == {}


@pytest.mark.parametrize("name", ["legacy", "Legacy"])
def test_a_repository_that_predates_iam_is_never_claimed(client: Client, name: str) -> None:
    """Regression (security review): a repository with no placement is not
    free; asking to create it, in any case, places nothing and grants nothing."""
    with as_service_account("engine"):
        client.source_control.adapter.ensure_repo(owner="abi", name="legacy")  # type: ignore[attr-defined]
    resp = client.post("/repos", json={"workspace_id": WS, "name": name})
    assert resp.status_code == 409, resp.text
    assert client.collaborators("abi/legacy") == {}
    assert client.iam.placement_of("source_control", "abi%2Flegacy") is None


def test_a_viewer_gets_no_write_access(client: Client) -> None:
    client.as_user("viewer")
    resp = client.post("/git-token", json={"workspace_id": WS, "repo_id": MONOREPO})
    assert resp.status_code == 403, resp.text
    assert client.collaborators(MONOREPO) == {}
    # A viewer still reads the workspace's repositories.
    resp = client.get("/repo-contents", params=_query())
    assert resp.status_code == 200


def test_a_member_iam_denies_writing_gets_no_write_access(client: Client) -> None:
    h = IAMHarness(client.iam)
    record = h.admin("ensure_user", LEGACY_NEXUS_ISSUER, "member")
    h.grant(
        record.id,
        statement(
            "Deny",
            ["source_control:UpsertFile"],
            [f"{WS_CONTAINER}/source_control:repo/abi%2Fmonorepo"],
        ),
    )
    resp = client.post("/git-token", json={"workspace_id": WS, "repo_id": MONOREPO})
    assert resp.status_code == 403, resp.text
    assert client.collaborators(MONOREPO) == {}


def test_a_member_gets_write_access_to_a_repository_of_the_workspace(client: Client) -> None:
    resp = client.post("/repos", json={"workspace_id": WS, "name": "ours"})
    assert resp.status_code == 200, resp.text
    assert client.iam.resolve_placement("source_control", "abi%2Fours") == WS_CONTAINER
    resp = client.post("/git-token", json={"workspace_id": WS, "repo_id": "abi/ours"})
    assert resp.status_code == 200, resp.text
    assert client.collaborators("abi/ours") == {resp.json()["username"]: "write"}


# --- creating a repository: workspace roles, and a denial is not "name taken" ------


@pytest.mark.parametrize("user", ["owner", "admin", "member"])
def test_a_workspace_role_creates_a_repository_without_a_platform_grant(
    client: Client, user: str
) -> None:
    client.as_user(user)
    resp = client.post("/repos", json={"workspace_id": WS, "name": f"by-{user}"})
    assert resp.status_code == 200, resp.text
    assert client.iam.resolve_placement("source_control", f"abi%2Fby-{user}") == WS_CONTAINER


def test_a_refusal_of_iam_on_create_is_not_reported_as_a_taken_name(client: Client) -> None:
    h = IAMHarness(client.iam)
    record = h.admin("ensure_user", LEGACY_NEXUS_ISSUER, "member")
    h.grant(
        record.id,
        statement("Deny", ["source_control:EnsureRepo"], [f"{WS_CONTAINER}/source_control:repo/*"]),
    )
    resp = client.post("/repos", json={"workspace_id": WS, "name": "denied"})
    assert resp.status_code == 403, resp.text
    assert client.iam.placement_of("source_control", "abi%2Fdenied") is None


def test_a_viewer_cannot_create_a_repository(client: Client) -> None:
    client.as_user("viewer")
    resp = client.post("/repos", json={"workspace_id": WS, "name": "nope"})
    assert resp.status_code == 403, resp.text
    assert client.iam.placement_of("source_control", "abi%2Fnope") is None


# --- environments: personal to their owner and to their workspace ------------------


ENVIRONMENT_ROUTES = (
    ("GET", ""),
    ("POST", "/start"),
    ("POST", "/stop"),
    ("DELETE", ""),
    ("GET", "/logs"),
    ("GET", "/access"),
)


def _call_environment(client: Client, method: str, env_id: str, suffix: str, workspace: str):
    return client.http.request(
        method, f"/coding-environments/{env_id}{suffix}", params={"workspace_id": workspace}
    )


@pytest.mark.parametrize(("method", "suffix"), ENVIRONMENT_ROUTES)
def test_an_environment_is_found_only_by_its_owner(
    client: Client, method: str, suffix: str
) -> None:
    env_id = client.provision()["id"]
    for user in ("admin", "owner"):
        client.as_user(user)
        resp = _call_environment(client, method, env_id, suffix, WS)
        assert resp.status_code in (403, 404), (user, resp.status_code)
        assert resp.status_code != 200, user
    client.as_user("member")
    resp = _call_environment(client, method, env_id, suffix, WS)
    assert resp.status_code == 200, resp.text


def test_an_environment_is_placed_in_the_workspace_it_was_provisioned_for(client: Client) -> None:
    env_id = client.provision()["id"]
    owner = principal_of(client.nexus, "member")
    assert client.iam.resolve_placement("coding_environment", f"{owner}/{env_id}") == WS_CONTAINER


@pytest.mark.parametrize(("method", "suffix"), ENVIRONMENT_ROUTES)
def test_an_environment_is_not_reached_through_another_workspace(
    client: Client, method: str, suffix: str
) -> None:
    """``both`` holds a role in each workspace and owns the environment, which
    was provisioned for ``ws-2``: ``ws-1`` does not have it."""
    client.as_user("both")
    place_repo(client.nexus, client.source_control, "abi/second", "ws-2")
    env_id = client.provision("theirs", workspace="ws-2", repo_id="abi/second")["id"]
    assert _call_environment(client, method, env_id, suffix, WS).status_code == 404
    assert _call_environment(client, method, env_id, suffix, "ws-2").status_code == 200


def test_an_environment_of_nobody_in_the_workspace_is_not_found(client: Client) -> None:
    assert client.get("/no-such-environment", params=_query()).status_code == 404


# --- roles: viewers read, members write, admins set the default repository ---------

READS = (
    ("/templates", {}),
    ("/repos", {}),
    ("/repo-contents", {}),
    ("/repo-file", {"path": "README.md"}),
    ("/repo-commits", {}),
    ("/default-repo", {}),
    ("/branches", {}),
    ("/repo", {}),
    ("", {}),
)
WRITES = (
    ("POST", "/repos", {"json": {"workspace_id": WS, "name": "w"}}),
    ("POST", "/git-token", {"json": {"workspace_id": WS}}),
    ("POST", "/branches", {"json": {"workspace_id": WS, "name": "w"}}),
    ("DELETE", "/branches", {"params": _query(name="w")}),
    (
        "POST",
        "",
        {"json": {"workspace_id": WS, "name": "w", "template_id": "tmpl-default"}},
    ),
    ("POST", "/sandbox/runtime", {"params": _query(repo_id=MONOREPO)}),
    ("POST", "/e/start", {"params": _query()}),
    ("POST", "/e/stop", {"params": _query()}),
    ("DELETE", "/e", {"params": _query()}),
    ("GET", "/e/access", {"params": _query()}),
    ("PUT", "/default-repo", {"json": {"workspace_id": WS, "repo_id": MONOREPO}}),
)


@pytest.mark.parametrize(("path", "params"), READS)
def test_a_viewer_reads(client: Client, path: str, params: dict) -> None:
    client.as_user("viewer")
    resp = client.get(path, params=_query(**params))
    assert resp.status_code == 200, resp.text


@pytest.mark.parametrize(("method", "path", "kwargs"), WRITES)
def test_a_viewer_cannot_write(client: Client, method: str, path: str, kwargs: dict) -> None:
    client.as_user("viewer")
    resp = client.http.request(method, f"/coding-environments{path}", **kwargs)
    assert resp.status_code == 403, resp.text


@pytest.mark.parametrize(("method", "path", "kwargs"), WRITES)
def test_a_stranger_is_refused_everywhere(
    client: Client, method: str, path: str, kwargs: dict
) -> None:
    client.as_user("stranger")
    resp = client.http.request(method, f"/coding-environments{path}", **kwargs)
    assert resp.status_code == 403, resp.text
    assert "access to this workspace" in resp.json()["detail"]


@pytest.mark.parametrize(("path", "params"), READS)
def test_a_stranger_reads_nothing(client: Client, path: str, params: dict) -> None:
    client.as_user("stranger")
    resp = client.get(path, params=_query(**params))
    assert resp.status_code == 403, resp.text


def test_only_an_admin_sets_the_default_repository(client: Client) -> None:
    body = {"workspace_id": WS, "repo_id": MONOREPO}
    client.as_user("member")
    assert client.put("/default-repo", json=body).status_code == 403
    for user in ("admin", "owner"):
        client.as_user(user)
        assert client.put("/default-repo", json=body).status_code == 200, user


def test_the_section_is_refused_to_a_role_whose_feature_is_off() -> None:
    with code_iam(without_code=("member", "viewer")) as nexus:
        client = Client(nexus)
        for user in ("member", "viewer"):
            client.as_user(user)
            resp = client.get("/repos", params=_query())
            assert resp.status_code == 403, user
            assert "feature" in resp.json()["detail"]
            resp = client.post("/repos", json={"workspace_id": WS, "name": "off"})
            assert resp.status_code == 403, user
        client.as_user("admin")
        assert client.get("/repos", params=_query()).status_code == 200
