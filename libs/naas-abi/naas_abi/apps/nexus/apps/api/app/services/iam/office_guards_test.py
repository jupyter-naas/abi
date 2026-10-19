"""Slides, documents and sheets decide through IAM: viewers read, members write.

The three routers share one resource type, ``project/<kind>/<slug>``, and one
feature per kind. These tests drive the real routers (fake source control and
database) with the ``team`` fixture's real IAM.
"""

from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from naas_abi.apps.nexus.apps.api.app.api.endpoints.auth import (
    User,
    get_current_user_required,
)
from naas_abi.apps.nexus.apps.api.app.core.config import FeatureFlagsConfig
from naas_abi.apps.nexus.apps.api.app.core.database import get_db
from naas_abi.apps.nexus.apps.api.app.services.documents.adapters.primary import (
    documents__primary_adapter__FastAPI as documents_api,
)
from naas_abi.apps.nexus.apps.api.app.services.iam.authz import AuthzDenied
from naas_abi.apps.nexus.apps.api.app.services.iam.catalog import LEVEL_OF
from naas_abi.apps.nexus.apps.api.app.services.iam.guards import Declared
from naas_abi.apps.nexus.apps.api.app.services.iam.names import workspace_scope
from naas_abi.apps.nexus.apps.api.app.services.iam.office_guards import ProjectGuard
from naas_abi.apps.nexus.apps.api.app.services.iam.testing import NexusIam
from naas_abi.apps.nexus.apps.api.app.services.sheets.adapters.primary import (
    sheets__primary_adapter__FastAPI as sheets_api,
)
from naas_abi.apps.nexus.apps.api.app.services.slides.adapters.primary import (
    slides__primary_adapter__FastAPI as slides_api,
)
from naas_abi_core.engine.call_context import as_service_account
from naas_abi_core.services.iam.IAMService import LEGACY_NEXUS_ISSUER
from naas_abi_core.services.iam.policy import PolicyDocument, Statement
from naas_abi_core.services.source_control.adapters.secondary.InMemoryAdapter import (
    InMemoryAdapter,
)
from naas_abi_core.services.source_control.SourceControlPorts import Diff, DiffFile
from naas_abi_core.services.source_control.SourceControlService import (
    SourceControlService,
)

WORKSPACE = "ws-1"
SLUG = "roles"
HTML = "<main>draft</main>"
WORKBOOK = (
    '<script type="application/vnd.nexus.sheet+json">'
    '{"title": "T", "sheets": [{"name": "A", "rows": [[1]]}]}</script>'
)
EVERY_FEATURE = ("slides", "documents", "sheets")


@dataclass(frozen=True)
class Kind:
    name: str
    module: Any
    # Routes that only read: (path under the kind's prefix, query).
    reads: tuple[tuple[str, dict[str, str]], ...]
    # Routes that change something: (method, path, body). Their workspace is in the body.
    writes: tuple[tuple[str, str, dict[str, Any]], ...]
    # Routes that change something with the workspace in the query: (method, path).
    queried_writes: tuple[tuple[str, str], ...]
    content: str
    html: str


PROJECT = f"/projects/{SLUG}"


def _kind(
    name: str,
    module: Any,
    *,
    content: str,
    html: str,
    parts: str,
    read_parts: tuple[str, ...],
    extra_writes: tuple[tuple[str, str, dict[str, Any]], ...] = (),
) -> Kind:
    reads = [
        ("/projects", {}),
        (PROJECT, {}),
        ("/templates", {}),
        (f"{PROJECT}/history", {}),
        (f"{PROJECT}/history/diff", {"base": "0" * 40}),
        (f"{PROJECT}/version", {}),
        (f"{PROJECT}/tree", {}),
        (f"{PROJECT}/assets/missing.png", {}),
        *[(f"{PROJECT}/{part}", {}) for part in read_parts],
    ]
    writes = [
        ("POST", "/projects", {"title": "Blocked", "slug": "blocked"}),
        ("PATCH", PROJECT, {"title": "Renamed"}),
        ("PUT", f"{PROJECT}/{content}", {"html": html}),
        ("POST", f"{PROJECT}/apply-template", {"template_id": module._discover_seed_ids()[0]}),
        ("POST", f"{PROJECT}/{parts}/insert", {"after_index": -1}),
        ("POST", f"{PROJECT}/{parts}/delete", {"index": 0}),
        ("POST", f"{PROJECT}/{parts}/duplicate", {"index": 0}),
        ("POST", f"{PROJECT}/{parts}/reorder", {"from_index": 0, "to_index": 0}),
        *extra_writes,
    ]
    return Kind(
        name=name,
        module=module,
        reads=tuple(reads),
        writes=tuple(writes),
        queried_writes=(("POST", f"{PROJECT}/runtime"),),
        content=content,
        html=html,
    )


KINDS = (
    _kind(
        "slides",
        slides_api,
        content="deck",
        html=HTML,
        parts="slides",
        read_parts=("deck", "slides"),
    ),
    _kind(
        "documents",
        documents_api,
        content="document",
        html=HTML,
        parts="sections",
        read_parts=("document", "sections", "outline"),
        extra_writes=(
            ("POST", f"{PROJECT}/commands", {"requests": [{"type": "insert_page_break"}]}),
        ),
    ),
    _kind(
        "sheets",
        sheets_api,
        content="workbook",
        html=WORKBOOK,
        parts="sheets",
        read_parts=("workbook", "export/xlsx", "slides"),
        extra_writes=(("POST", "/evaluate", {"html": WORKBOOK}),),
    ),
)
BY_NAME = {kind.name: kind for kind in KINDS}


class Client:
    """The three routers on one app, called as one user or another."""

    def __init__(self, monkeypatch: pytest.MonkeyPatch) -> None:
        self.user = "member"
        app = FastAPI()
        app.state.source_control = SourceControlService(InMemoryAdapter())
        for kind in KINDS:
            app.include_router(kind.module.router, prefix=f"/{kind.name}")
            monkeypatch.setattr(kind.module, "_get_coding_environment", lambda _r: None)
        app.dependency_overrides[get_current_user_required] = lambda: User.model_construct(
            id=self.user, email=f"{self.user}@example.com", name=self.user
        )

        async def no_db():
            yield None

        app.dependency_overrides[get_db] = no_db
        self.http = TestClient(app, raise_server_exceptions=False)

    def call(
        self,
        user: str,
        kind: Kind,
        method: str,
        path: str,
        body: dict[str, Any] | None = None,
        **query,
    ):
        self.user = user
        query = {"workspace_id": WORKSPACE, **query}
        url = f"/{kind.name}{path}"
        if body is None:
            return self.http.request(method, url, params=query)
        payload = {"workspace_id": WORKSPACE, **body}
        return self.http.request(method, url, json=payload)

    def create(self, kind: Kind, user: str = "member") -> None:
        response = self.call(user, kind, "POST", "/projects", {"title": "Roles", "slug": SLUG})
        assert response.status_code == 200, response.text


def _attach_deny(team: NexusIam, user: str, resource: str) -> None:
    """A custom policy denying ``user`` reading ``resource``, attached in the workspace."""
    deny = PolicyDocument(statements=(Statement("Deny", ("nexus:GetProject",), (resource,)),))
    with as_service_account("engine"):
        policy = team.iam.create_policy(f"deny-{user}", deny)
        principal = team.iam.ensure_user(LEGACY_NEXUS_ISSUER, user, provider="nexus")
        team.iam.attach_policy(policy.id, principal.id, workspace_scope("org-1", WORKSPACE))


@pytest.fixture
def client(team, monkeypatch) -> Client:
    return Client(monkeypatch)


@pytest.fixture(params=KINDS, ids=lambda kind: kind.name)
def kind(request) -> Kind:
    return request.param


def test_a_viewer_reads_exactly_what_a_member_reads(client: Client, kind: Kind) -> None:
    client.create(kind)
    for path, query in kind.reads:
        member = client.call("member", kind, "GET", path, **query)
        viewer = client.call("viewer", kind, "GET", path, **query)
        assert viewer.status_code == member.status_code != 403, (path, viewer.text)
    listed = client.call("viewer", kind, "GET", "/projects").json()
    assert [project["slug"] for project in listed] == [SLUG]


def test_a_viewer_changes_nothing(client: Client, kind: Kind) -> None:
    client.create(kind)
    before = client.call("member", kind, "GET", f"{PROJECT}/{kind.content}").json()
    for method, path, body in kind.writes:
        response = client.call("viewer", kind, method, path, body)
        assert response.status_code == 403, (method, path, response.text)
    for method, path in kind.queried_writes:
        response = client.call("viewer", kind, method, path)
        assert response.status_code == 403, (method, path, response.text)
    project = client.call("member", kind, "GET", PROJECT).json()
    assert project["title"] == "Roles"
    after = client.call("member", kind, "GET", f"{PROJECT}/{kind.content}").json()
    assert after == before
    slugs = [p["slug"] for p in client.call("member", kind, "GET", "/projects").json()]
    assert slugs == [SLUG]


def test_a_member_and_an_admin_write(client: Client, kind: Kind) -> None:
    client.create(kind)
    for user in ("member", "admin", "owner"):
        for method, path, body in kind.writes:
            response = client.call(user, kind, method, path, body)
            assert response.status_code != 403, (user, method, path, response.text)
        for method, path in kind.queried_writes:
            response = client.call(user, kind, method, path)
            assert response.status_code != 403, (user, method, path, response.text)
    renamed = client.call("member", kind, "PATCH", PROJECT, {"title": "Mine"})
    assert renamed.status_code == 200, renamed.text
    saved = client.call("admin", kind, "PUT", f"{PROJECT}/{kind.content}", {"html": kind.html})
    assert saved.status_code == 200, saved.text


def test_a_stranger_reaches_nothing(client: Client, kind: Kind) -> None:
    client.create(kind)
    for path, query in kind.reads:
        response = client.call("stranger", kind, "GET", path, **query)
        assert response.status_code == 403, (path, response.text)
        assert "access to this workspace" in response.json()["detail"]
    for method, path, body in kind.writes:
        response = client.call("stranger", kind, method, path, body)
        assert response.status_code == 403, (method, path, response.text)
    for method, path in kind.queried_writes:
        assert client.call("stranger", kind, method, path).status_code == 403


def test_a_member_of_another_workspace_is_a_stranger_here(
    client: Client, team: NexusIam, kind: Kind
) -> None:
    client.create(kind)
    other = team.workspace("org-1", "ws-2")
    team.grant("outsider", "owner", other)
    response = client.call("outsider", kind, "GET", PROJECT)
    assert response.status_code == 403
    # Even a project of their own workspace is not reached through ours.
    response = client.call("outsider", kind, "GET", PROJECT, workspace_id="ws-2")
    assert response.status_code == 404


def test_the_diff_reports_only_the_projects_own_files(
    client: Client, kind: Kind, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``base`` and ``head`` come from the client, who may name any commit of the
    shared repository: the files of other decks are not listed."""
    client.create(kind)
    own = f"{kind.name}/{WORKSPACE}/{SLUG}/{kind.content}.html"
    elsewhere = f"{kind.name}/ws-2/other/{kind.content}.html"

    def file(path: str, old_path: str | None = None) -> DiffFile:
        return DiffFile(path=path, status="modified", additions=1, deletions=0, old_path=old_path)

    diff = Diff(files=(file(own), file(elsewhere), file(f"{kind.name}/{WORKSPACE}/{SLUG}-2/x")))
    diff = Diff(files=(*diff.files, file(f"{own}.moved", old_path=elsewhere)))
    source_control = client.http.app.state.source_control
    monkeypatch.setattr(source_control, "get_diff", lambda **_: diff)
    response = client.call(
        "member", kind, "GET", f"{PROJECT}/history/diff", base="a" * 40, head="b" * 40
    )
    assert response.status_code == 200, response.text
    assert [f["path"] for f in response.json()["files"]] == [own, f"{own}.moved"]


@pytest.mark.parametrize("disabled", EVERY_FEATURE)
def test_a_kind_whose_feature_is_off_is_refused_for_the_role(monkeypatch, disabled: str) -> None:
    everything = ["maps", "chat", "files", *EVERY_FEATURE]
    left = [feature for feature in everything if feature != disabled]
    flags = FeatureFlagsConfig(
        enabled_features=everything,
        role_baseline={
            "owner": everything,
            "admin": everything,
            "member": left,
            "viewer": left,
        },
    )
    nexus = NexusIam(flags)
    scope = nexus.workspace("org-1", WORKSPACE)
    for user in ("owner", "member", "viewer"):
        nexus.grant(user, user, scope)
    with nexus.installed():
        http = Client(monkeypatch)
        for other in KINDS:
            for user in ("member", "viewer"):
                response = http.call(user, other, "GET", "/projects")
                if other.name == disabled:
                    assert response.status_code == 403, (user, other.name)
                    assert "feature is not available" in response.json()["detail"]
                else:
                    assert response.status_code == 200, (user, other.name, response.text)
        # The role that keeps the feature is not affected.
        assert http.call("owner", BY_NAME[disabled], "GET", "/projects").status_code == 200
        write = http.call("member", BY_NAME[disabled], "POST", "/projects", {"title": "T"})
        assert write.status_code == 403


def test_a_policy_can_deny_one_project_and_the_list_leaves_it_out(
    client: Client, team: NexusIam
) -> None:
    kind = BY_NAME["slides"]
    for slug in ("open", "secret"):
        created = client.call("member", kind, "POST", "/projects", {"title": slug, "slug": slug})
        assert created.status_code == 200, created.text
    _attach_deny(
        team, "viewer", f"{workspace_scope('org-1', WORKSPACE)}:nexus:project/slides/secret"
    )
    listed = client.call("viewer", kind, "GET", "/projects").json()
    assert [p["slug"] for p in listed] == ["open"]
    assert client.call("viewer", kind, "GET", "/projects/secret").status_code == 403
    assert client.call("member", kind, "GET", "/projects/secret").status_code == 200


def test_a_policy_names_a_kind_of_project_by_its_first_id_part(
    client: Client, team: NexusIam
) -> None:
    for kind in KINDS:
        client.create(kind)
    resource = f"{workspace_scope('org-1', WORKSPACE)}:nexus:project/documents/*"
    _attach_deny(team, "viewer", resource)
    assert client.call("viewer", BY_NAME["slides"], "GET", PROJECT).status_code == 200
    assert client.call("viewer", BY_NAME["sheets"], "GET", PROJECT).status_code == 200
    assert client.call("viewer", BY_NAME["documents"], "GET", PROJECT).status_code == 403


def test_every_route_of_the_three_routers_declares_its_action() -> None:
    """Each route has a project guard or an inline declaration, and a write
    method never declares only a read."""
    for kind in KINDS:
        for route in kind.module.router.routes:
            declared = [
                dependency.call
                for dependency in route.dependant.dependencies
                if isinstance(dependency.call, ProjectGuard | Declared)
            ]
            assert declared, (kind.name, route.path)
            levels = {LEVEL_OF[call.action] for call in declared}
            if route.methods & {"POST", "PUT", "PATCH", "DELETE"}:
                assert levels == {"write"}, (kind.name, route.path)
            else:
                assert levels <= {"list", "read"}, (kind.name, route.path)


@pytest.mark.asyncio
async def test_every_project_guard_decides_by_the_level_of_its_action(team: NexusIam) -> None:
    """Viewers hold ``list`` and ``read``, members and up ``write``; a stranger nothing."""
    wrong = []
    checked = 0
    for kind in KINDS:
        for route in kind.module.router.routes:
            for dependency in route.dependant.dependencies:
                guard = dependency.call
                if not isinstance(guard, ProjectGuard):
                    continue
                checked += 1
                request = SimpleNamespace(
                    path_params={"workspace_id": WORKSPACE, "slug": SLUG}, query_params={}
                )
                reads = LEVEL_OF[guard.action] in ("list", "read")
                for user, expected in (
                    ("viewer", reads),
                    ("member", True),
                    ("admin", True),
                    ("owner", True),
                    ("stranger", False),
                ):
                    try:
                        await guard(request, SimpleNamespace(id=user))
                        allowed = True
                    except AuthzDenied:
                        allowed = False
                    if allowed != expected:
                        wrong.append((kind.name, route.path, guard.action, user))
    assert wrong == []
    assert checked >= 30  # the guarded routes: every one with its workspace in the query
