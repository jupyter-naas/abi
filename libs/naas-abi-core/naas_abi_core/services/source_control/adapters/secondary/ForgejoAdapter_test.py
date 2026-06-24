from __future__ import annotations

from typing import Any

import pytest

from naas_abi_core.services.source_control.adapters.secondary.ForgejoAdapter import (
    ForgejoAdapter,
)
from naas_abi_core.services.source_control.SourceControlPorts import (
    AccessDeniedError,
    BranchNameConflictError,
    MergeBlockedError,
    MergeConflictError,
    PROPOSAL_OPEN,
    ProposalNotFoundError,
    REVIEW_APPROVED,
)
from naas_abi_core.services.source_control.tests.source_control__secondary_adapter__generic_test import (
    GenericSourceControlSecondaryAdapterTest,
)


class FakeResponse:
    def __init__(self, status_code: int = 200, payload: Any = None, text: str = ""):
        self.status_code = status_code
        self._payload = payload
        self.text = text
        self.content = b"{}" if payload is not None else b""

    def json(self) -> Any:
        return self._payload


class FakeSession:
    """Routes (method, url-substring) -> FakeResponse; records all calls."""

    def __init__(self, routes: list[tuple[str, str, FakeResponse]]):
        self.routes = list(routes)
        self.calls: list[dict] = []

    def request(self, method, url, headers=None, json=None, timeout=None):
        self.calls.append(
            {"method": method, "url": url, "headers": headers, "json": json}
        )
        for m, substring, response in self.routes:
            if m == method and substring in url:
                return response
        return FakeResponse(404, {"message": "not found"}, "not found")

    def find(self, method: str, substring: str) -> dict | None:
        for call in self.calls:
            if call["method"] == method and substring in call["url"]:
                return call
        return None


def _adapter(session: FakeSession) -> ForgejoAdapter:
    return ForgejoAdapter(
        base_url="https://forge.example.com",
        admin_token="admin-token",
        session=session,
    )


_PULL = {
    "id": 100,
    "number": 7,
    "title": "Add feature",
    "body": "body",
    "state": "open",
    "merged": False,
    "mergeable": True,
    "head": {"ref": "feature", "sha": "deadbeef"},
    "base": {"ref": "main"},
    "user": {"login": "alice"},
    "html_url": "https://forge.example.com/alice/proj/pulls/7",
}


class TestForgejoAdapter(GenericSourceControlSecondaryAdapterTest):
    @pytest.fixture
    def adapter_class(self):
        return ForgejoAdapter


def test_add_collaborator_puts_permission() -> None:
    session = FakeSession(
        [("PUT", "/repos/abi/monorepo/collaborators/alice", FakeResponse(204))]
    )
    _adapter(session).add_collaborator(repo_id="abi/monorepo", username="alice")
    call = session.find("PUT", "/collaborators/alice")
    assert call is not None
    assert call["json"] == {"permission": "write"}


def test_mint_git_token_resets_password_then_basic_auths() -> None:
    session = FakeSession(
        [
            ("PATCH", "/admin/users/alice", FakeResponse(200, {})),
            ("POST", "/users/alice/tokens", FakeResponse(201, {"sha1": "tok-xyz"})),
        ]
    )
    token = _adapter(session).mint_git_token(user_id="alice")
    assert token == "tok-xyz"
    # admin resets the password first, then the token is minted via BASIC auth
    assert session.find("PATCH", "/admin/users/alice") is not None
    mint = session.find("POST", "/users/alice/tokens")
    assert mint is not None
    assert mint["headers"]["Authorization"].startswith("Basic ")


def test_request_uses_token_auth_and_api_v1_base() -> None:
    session = FakeSession(
        [("GET", "/api/v1/repos/alice/proj", FakeResponse(200, {"id": 1, "name": "proj"}))]
    )
    adapter = _adapter(session)
    adapter.ensure_repo(owner="alice", name="proj")

    call = session.find("GET", "/repos/alice/proj")
    assert call is not None
    assert call["url"].startswith("https://forge.example.com/api/v1/")
    assert call["headers"]["Authorization"] == "token admin-token"


def test_ensure_user_creates_when_missing() -> None:
    session = FakeSession(
        [
            ("GET", "/users/alice", FakeResponse(404, {"message": "nf"}, "nf")),
            ("POST", "/admin/users", FakeResponse(201, {"id": 42})),
        ]
    )
    adapter = _adapter(session)

    user_id = adapter.ensure_user(
        external_id="ext", email="alice@example.com", username="alice"
    )
    assert user_id == "42"

    call = session.find("POST", "/admin/users")
    assert call is not None
    assert call["json"]["email"] == "alice@example.com"
    assert call["json"]["username"] == "alice"


def test_create_proposal_posts_head_and_base() -> None:
    session = FakeSession(
        [("POST", "/repos/alice/proj/pulls", FakeResponse(201, _PULL))]
    )
    adapter = _adapter(session)

    proposal = adapter.create_proposal(
        repo_id="alice/proj",
        title="Add feature",
        body="body",
        source_branch="feature",
        target_branch="main",
    )

    assert proposal.number == 7
    assert proposal.state == PROPOSAL_OPEN
    assert proposal.source_branch == "feature"
    assert proposal.target_branch == "main"
    assert proposal.author == "alice"

    call = session.find("POST", "/pulls")
    assert call is not None
    assert call["json"]["head"] == "feature"
    assert call["json"]["base"] == "main"
    assert call["json"]["title"] == "Add feature"


def test_submit_review_maps_event_and_state() -> None:
    session = FakeSession(
        [
            (
                "POST",
                "/repos/alice/proj/pulls/7/reviews",
                FakeResponse(200, {"id": 5, "state": "APPROVED", "user": {"login": "bob"}}),
            )
        ]
    )
    adapter = _adapter(session)

    review = adapter.submit_review(
        repo_id="alice/proj", number=7, event="approved", body="lgtm"
    )
    assert review.state == REVIEW_APPROVED
    assert review.author == "bob"

    call = session.find("POST", "/reviews")
    assert call is not None
    assert call["json"]["event"] == "APPROVED"
    assert call["json"]["body"] == "lgtm"


def test_merge_posts_method_and_returns_sha() -> None:
    session = FakeSession(
        [
            (
                "POST",
                "/repos/alice/proj/pulls/7/merge",
                FakeResponse(200, {"sha": "merged-sha", "message": "ok"}),
            )
        ]
    )
    adapter = _adapter(session)

    result = adapter.merge(repo_id="alice/proj", number=7, method="squash")
    assert result.merged is True
    assert result.sha == "merged-sha"

    call = session.find("POST", "/merge")
    assert call is not None
    assert call["json"]["Do"] == "squash"


def test_branch_name_conflict_maps_to_typed_error() -> None:
    session = FakeSession(
        [
            (
                "POST",
                "/repos/alice/proj/branches",
                FakeResponse(409, {"message": "exists"}, "exists"),
            )
        ]
    )
    adapter = _adapter(session)
    with pytest.raises(BranchNameConflictError):
        adapter.create_branch(repo_id="alice/proj", name="feature", from_ref="main")


def test_access_denied_maps_to_typed_error() -> None:
    session = FakeSession(
        [("GET", "/repos/alice/proj/branches", FakeResponse(403, {}, "forbidden"))]
    )
    adapter = _adapter(session)
    with pytest.raises(AccessDeniedError):
        adapter.list_branches(repo_id="alice/proj")


def test_proposal_not_found_maps_to_typed_error() -> None:
    session = FakeSession(
        [("GET", "/repos/alice/proj/pulls/7", FakeResponse(404, {}, "nf"))]
    )
    adapter = _adapter(session)
    with pytest.raises(ProposalNotFoundError):
        adapter.get_proposal(repo_id="alice/proj", number=7)


def test_merge_405_maps_to_merge_blocked() -> None:
    session = FakeSession(
        [("POST", "/repos/alice/proj/pulls/7/merge", FakeResponse(405, {}, "blocked"))]
    )
    adapter = _adapter(session)
    with pytest.raises(MergeBlockedError):
        adapter.merge(repo_id="alice/proj", number=7)


def test_merge_409_maps_to_merge_conflict() -> None:
    session = FakeSession(
        [("POST", "/repos/alice/proj/pulls/7/merge", FakeResponse(409, {}, "conflict"))]
    )
    adapter = _adapter(session)
    with pytest.raises(MergeConflictError):
        adapter.merge(repo_id="alice/proj", number=7)


def test_get_proposal_counts_approvals() -> None:
    session = FakeSession(
        [
            (
                "GET",
                "/repos/alice/proj/pulls/7/reviews",
                FakeResponse(
                    200,
                    [
                        {"state": "APPROVED"},
                        {"state": "COMMENT"},
                        {"state": "APPROVED", "dismissed": True},
                    ],
                ),
            ),
            ("GET", "/repos/alice/proj/pulls/7", FakeResponse(200, _PULL)),
        ]
    )
    adapter = _adapter(session)
    proposal = adapter.get_proposal(repo_id="alice/proj", number=7)
    assert proposal.approvals == 1
