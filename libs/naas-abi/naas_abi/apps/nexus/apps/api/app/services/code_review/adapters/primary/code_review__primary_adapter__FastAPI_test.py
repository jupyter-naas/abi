"""The code-review routes, driven through the real router with a real IAM.

Every route names a workspace and a repository, and the repository must belong
to that workspace: a member of one workspace never acts on another's.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from naas_abi.apps.nexus.apps.api.app.api.endpoints.auth import (
    User,
    get_current_user_required,
)
from naas_abi.apps.nexus.apps.api.app.services.code_review.adapters.primary import (
    code_review__primary_adapter__FastAPI as cr,
)
from naas_abi.apps.nexus.apps.api.app.services.coding_environment.adapters.primary import (
    coding_environment__primary_adapter__guard as guard_api,
)
from naas_abi.apps.nexus.apps.api.app.services.coding_environment.testing import (
    AsUser,
    code_iam,
    kernel_services,
    place_repo,
)
from naas_abi.apps.nexus.apps.api.app.services.iam.testing import NexusIam
from naas_abi_core.engine.call_context import as_service_account
from naas_abi_core.services.iam.IAMService import LEGACY_NEXUS_ISSUER
from naas_abi_core.services.iam.tests.iam_harness import IAMHarness, statement

REPO = "org/monorepo"
WS = "ws-1"
THEIRS = "org/theirs"


class Client:
    """A TestClient of the router; ``as_user`` picks who signs in."""

    def __init__(self, nexus: NexusIam) -> None:
        self.iam = nexus.iam
        _, self.service = kernel_services(nexus)
        place_repo(nexus, self.service, REPO, WS)
        place_repo(nexus, self.service, THEIRS, "ws-2")
        self._holder = {"user": "member"}
        app = FastAPI()
        app.include_router(cr.router, prefix="/code-review")
        app.add_middleware(AsUser, nexus=nexus, holder=self._holder)
        app.dependency_overrides[get_current_user_required] = lambda: User.model_construct(
            id=self._holder["user"],
            email=f"{self._holder['user']}@example.com",
            name=self._holder["user"].title(),
        )
        app.dependency_overrides[cr._get_source_control_service] = lambda: self.service
        app.dependency_overrides[guard_api.get_iam] = lambda: self.iam
        self.http = TestClient(app)

    def as_user(self, user_id: str) -> Client:
        self._holder["user"] = user_id
        return self

    def request(self, method: str, path: str, **kwargs):
        return self.http.request(method, f"/code-review{path}", **kwargs)

    def get(self, path: str, **kwargs):
        return self.request("GET", path, **kwargs)

    def post(self, path: str, **kwargs):
        return self.request("POST", path, **kwargs)


@pytest.fixture
def client() -> Iterator[Client]:
    with code_iam() as nexus:
        yield Client(nexus)


def _params(repo: str = REPO, workspace: str = WS, **extra) -> dict:
    return {"workspace_id": workspace, "repo_id": repo, **extra}


def _body(repo: str = REPO, workspace: str = WS, **extra) -> dict:
    return {"workspace_id": workspace, "repo_id": repo, **extra}


def _open_proposal(client: Client, branch: str = "feat", repo: str = REPO) -> int:
    resp = client.post("/branches", json=_body(repo, name=branch, from_ref="main"))
    assert resp.status_code == 200, resp.text
    resp = client.post(
        "/proposals",
        json=_body(
            repo,
            title="Add feature",
            source_branch=branch,
            target_branch="main",
        ),
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["number"]


# --- the review flow, as a member ---------------------------------------------------


def test_branch_proposal_review_merge(client: Client) -> None:
    number = _open_proposal(client)
    resp = client.get("/proposals", params=_params())
    assert any(p["number"] == number for p in resp.json())

    resp = client.post("/proposal/review", json=_body(number=number, event="approved"))
    assert resp.json()["state"] == "approved"

    resp = client.post("/proposal/merge", json=_body(number=number))
    assert resp.status_code == 200, resp.text
    assert resp.json()["merged"] is True

    resp = client.get("/proposal", params=_params(number=number))
    assert resp.json()["state"] == "merged"


def test_proposal_reviews_and_commits_endpoints(client: Client) -> None:
    number = _open_proposal(client, "feat3")
    assert client.get("/proposal/reviews", params=_params(number=number)).json() == []
    client.post("/proposal/review", json=_body(number=number, event="approved", body="lgtm"))
    reviews = client.get("/proposal/reviews", params=_params(number=number)).json()
    assert len(reviews) == 1
    assert reviews[0]["state"] == "approved"
    assert reviews[0]["body"] == "lgtm"

    commits = client.get("/proposal/commits", params=_params(number=number))
    assert commits.status_code == 200, commits.text
    assert isinstance(commits.json(), list)


def test_comments_diff_and_checks(client: Client) -> None:
    number = _open_proposal(client, "feat4")
    resp = client.post("/proposal/comments", json=_body(number=number, body="looks good"))
    assert resp.status_code == 200, resp.text
    comments = client.get("/proposal/comments", params=_params(number=number)).json()
    assert [c["body"] for c in comments] == ["looks good"]
    assert client.get("/proposal/diff", params=_params(number=number)).status_code == 200
    assert client.get("/proposal/checks", params=_params(number=number)).status_code == 200


def test_actions_runs_endpoint(client: Client) -> None:
    resp = client.get("/actions/runs", params=_params())
    assert resp.status_code == 200, resp.text
    assert isinstance(resp.json(), list)


def test_merge_blocked_until_approved(client: Client) -> None:
    client.service.set_branch_protection(
        repo_id=REPO, branch="main", required_approvals=1, required_checks=[]
    )
    number = _open_proposal(client, "feat2")
    blocked = client.post("/proposal/merge", json=_body(number=number))
    assert blocked.status_code == 422, blocked.text

    client.post("/proposal/review", json=_body(number=number, event="approved"))
    merged = client.post("/proposal/merge", json=_body(number=number))
    assert merged.status_code == 200, merged.text
    assert merged.json()["merged"] is True


def test_repo_not_found(client: Client) -> None:
    resp = client.get("/branches", params=_params("org/missing"))
    assert resp.status_code == 404


# --- a workspace never acts on another workspace's repository -----------------------


def _routes(repo: str, workspace: str, number: int = 1):
    """Every route of the router, aimed at ``repo`` through ``workspace``."""
    query = _params(repo, workspace)
    on_proposal = _params(repo, workspace, number=number)
    body = _body(repo, workspace)
    return [
        ("GET", "/branches", {"params": query}),
        ("POST", "/branches", {"json": {**body, "name": "x", "from_ref": "main"}}),
        ("GET", "/proposals", {"params": query}),
        (
            "POST",
            "/proposals",
            {
                "json": {
                    **body,
                    "title": "t",
                    "source_branch": "x",
                    "target_branch": "main",
                }
            },
        ),
        ("GET", "/proposal", {"params": on_proposal}),
        ("GET", "/proposal/diff", {"params": on_proposal}),
        ("GET", "/proposal/commits", {"params": on_proposal}),
        ("GET", "/proposal/comments", {"params": on_proposal}),
        ("POST", "/proposal/comments", {"json": {**body, "number": number, "body": "c"}}),
        ("GET", "/proposal/reviews", {"params": on_proposal}),
        (
            "POST",
            "/proposal/review",
            {"json": {**body, "number": number, "event": "approved"}},
        ),
        ("GET", "/proposal/checks", {"params": on_proposal}),
        ("POST", "/proposal/merge", {"json": {**body, "number": number}}),
        ("GET", "/actions/runs", {"params": query}),
    ]


def test_every_route_of_the_router_is_covered_by_the_table(client: Client) -> None:
    from fastapi.routing import APIRoute

    declared = {
        (method, f"{route.path}")
        for route in cr.router.routes
        if isinstance(route, APIRoute)
        for method in route.methods
    }
    covered = {(method, path) for method, path, _ in _routes(REPO, WS)}
    assert declared == covered


@pytest.mark.parametrize("user", ["member", "both", "other"])
def test_no_route_reaches_a_repository_of_another_workspace(client: Client, user: str) -> None:
    """``both`` is a member of each workspace, ``other`` of ``ws-2`` only: asking
    ``ws-2`` for ``ws-1``'s repository, or ``ws-1`` for ``ws-2``'s, finds nothing,
    whatever the roles of the user reach."""
    client.as_user(user)
    workspace = "ws-2" if user == "other" else WS
    foreign = REPO if user == "other" else THEIRS
    for method, path, kwargs in _routes(foreign, workspace):
        resp = client.request(method, path, **kwargs)
        assert resp.status_code == 404, (method, path, resp.status_code, resp.text)


def test_a_member_of_both_workspaces_may_use_each_repository_through_its_own(
    client: Client,
) -> None:
    client.as_user("both")
    assert client.get("/branches", params=_params(REPO, "ws-1")).status_code == 200
    assert client.get("/branches", params=_params(THEIRS, "ws-2")).status_code == 200


def test_nothing_was_written_to_the_other_workspaces_repository(client: Client) -> None:
    client.as_user("both")
    for method, path, kwargs in _routes(THEIRS, WS):
        if method == "POST":
            client.request(method, path, **kwargs)
    with as_service_account("engine"):
        branches = [b.name for b in client.service.list_branches(repo_id=THEIRS)]
        proposals = client.service.list_proposals(repo_id=THEIRS, state="all")
    assert branches == ["main"]
    assert proposals == []


# --- roles --------------------------------------------------------------------------


def _reads() -> list[tuple[str, str, dict]]:
    return [r for r in _routes(REPO, WS) if r[0] == "GET"]


def _writes() -> list[tuple[str, str, dict]]:
    return [r for r in _routes(REPO, WS) if r[0] != "GET"]


@pytest.mark.parametrize(("method", "path", "kwargs"), _reads())
def test_a_viewer_reads(client: Client, method: str, path: str, kwargs: dict) -> None:
    number = _open_proposal(client)
    client.as_user("viewer")
    kwargs = {**kwargs, "params": {**kwargs["params"], "number": number}}
    resp = client.request(method, path, **kwargs)
    assert resp.status_code == 200, resp.text


@pytest.mark.parametrize(("method", "path", "kwargs"), _writes())
def test_a_viewer_cannot_write(client: Client, method: str, path: str, kwargs: dict) -> None:
    client.as_user("viewer")
    resp = client.request(method, path, **kwargs)
    assert resp.status_code == 403, resp.text


@pytest.mark.parametrize(("method", "path", "kwargs"), [*_reads(), *_writes()])
def test_a_stranger_is_refused_everywhere(
    client: Client, method: str, path: str, kwargs: dict
) -> None:
    client.as_user("stranger")
    resp = client.request(method, path, **kwargs)
    assert resp.status_code == 403, resp.text
    assert "access to this workspace" in resp.json()["detail"]


@pytest.mark.parametrize("user", ["owner", "admin", "member"])
def test_members_and_up_write(client: Client, user: str) -> None:
    client.as_user(user)
    number = _open_proposal(client, f"by-{user}")
    resp = client.post("/proposal/comments", json=_body(number=number, body="c"))
    assert resp.status_code == 200, resp.text


def test_the_section_is_refused_to_a_role_whose_feature_is_off() -> None:
    with code_iam(without_code=("member", "viewer")) as nexus:
        client = Client(nexus)
        for user in ("member", "viewer"):
            client.as_user(user)
            resp = client.get("/branches", params=_params())
            assert resp.status_code == 403, user
            assert "feature" in resp.json()["detail"]
            resp = client.post("/branches", json=_body(name="off", from_ref="main"))
            assert resp.status_code == 403, user
        client.as_user("admin")
        assert client.get("/branches", params=_params()).status_code == 200


def test_a_user_iam_denies_the_action_is_refused_whatever_the_route_says(
    client: Client,
) -> None:
    """The kernel decides on the repository too: an explicit deny of ``Merge`` is
    a 403, not a 500, even though the workspace and role allow the route."""
    number = _open_proposal(client)
    client.post("/proposal/review", json=_body(number=number, event="approved"))
    h = IAMHarness(client.iam)
    record = h.admin("ensure_user", LEGACY_NEXUS_ISSUER, "member")
    h.grant(
        record.id,
        statement("Deny", ["source_control:Merge"], ["abi:org-1:ws-1:source_control:*"]),
    )
    resp = client.post("/proposal/merge", json=_body(number=number))
    assert resp.status_code == 403, resp.text
