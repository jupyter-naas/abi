from __future__ import annotations

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
from naas_abi_core.services.source_control.adapters.secondary.InMemoryAdapter import (
    InMemoryAdapter,
)
from naas_abi_core.services.source_control.SourceControlService import (
    SourceControlService,
)

REPO = "org/monorepo"


def _client(monkeypatch: pytest.MonkeyPatch) -> tuple[TestClient, SourceControlService]:
    service = SourceControlService(InMemoryAdapter())
    service.ensure_repo(owner="org", name="monorepo")
    app = FastAPI()
    app.include_router(cr.router, prefix="/code-review")
    app.dependency_overrides[get_current_user_required] = lambda: User.model_construct(
        id="u1", email="u@example.com", name="U One"
    )
    app.dependency_overrides[cr._get_source_control_service] = lambda: service

    async def _allow(user_id: str, workspace_id: str) -> str:
        return "owner"

    monkeypatch.setattr(cr, "require_workspace_access", _allow)
    return TestClient(app), service


def test_branch_proposal_review_merge(monkeypatch: pytest.MonkeyPatch) -> None:
    client, _ = _client(monkeypatch)
    resp = client.post(
        "/code-review/branches",
        json={"workspace_id": "ws", "repo_id": REPO, "name": "feat", "from_ref": "main"},
    )
    assert resp.status_code == 200, resp.text

    resp = client.post(
        "/code-review/proposals",
        json={
            "workspace_id": "ws",
            "repo_id": REPO,
            "title": "Add feature",
            "source_branch": "feat",
            "target_branch": "main",
        },
    )
    assert resp.status_code == 200, resp.text
    number = resp.json()["number"]

    resp = client.get("/code-review/proposals", params={"workspace_id": "ws", "repo_id": REPO})
    assert any(p["number"] == number for p in resp.json())

    resp = client.post(
        "/code-review/proposal/review",
        json={"workspace_id": "ws", "repo_id": REPO, "number": number, "event": "approved"},
    )
    assert resp.json()["state"] == "approved"

    resp = client.post(
        "/code-review/proposal/merge",
        json={"workspace_id": "ws", "repo_id": REPO, "number": number},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["merged"] is True

    resp = client.get(
        "/code-review/proposal",
        params={"workspace_id": "ws", "repo_id": REPO, "number": number},
    )
    assert resp.json()["state"] == "merged"


def test_proposal_reviews_and_commits_endpoints(monkeypatch: pytest.MonkeyPatch) -> None:
    client, _ = _client(monkeypatch)
    client.post(
        "/code-review/branches",
        json={"workspace_id": "ws", "repo_id": REPO, "name": "feat3", "from_ref": "main"},
    )
    number = client.post(
        "/code-review/proposals",
        json={
            "workspace_id": "ws",
            "repo_id": REPO,
            "title": "Third",
            "source_branch": "feat3",
            "target_branch": "main",
        },
    ).json()["number"]

    # reviews: empty, then reflects a submitted review
    assert (
        client.get(
            "/code-review/proposal/reviews",
            params={"workspace_id": "ws", "repo_id": REPO, "number": number},
        ).json()
        == []
    )
    client.post(
        "/code-review/proposal/review",
        json={"workspace_id": "ws", "repo_id": REPO, "number": number, "event": "approved", "body": "lgtm"},
    )
    reviews = client.get(
        "/code-review/proposal/reviews",
        params={"workspace_id": "ws", "repo_id": REPO, "number": number},
    ).json()
    assert len(reviews) == 1
    assert reviews[0]["state"] == "approved"
    assert reviews[0]["body"] == "lgtm"

    # commits endpoint responds with a list
    commits = client.get(
        "/code-review/proposal/commits",
        params={"workspace_id": "ws", "repo_id": REPO, "number": number},
    )
    assert commits.status_code == 200, commits.text
    assert isinstance(commits.json(), list)


def test_actions_runs_endpoint(monkeypatch: pytest.MonkeyPatch) -> None:
    client, _ = _client(monkeypatch)
    resp = client.get(
        "/code-review/actions/runs", params={"workspace_id": "ws", "repo_id": REPO}
    )
    assert resp.status_code == 200, resp.text
    assert isinstance(resp.json(), list)


def test_merge_blocked_until_approved(monkeypatch: pytest.MonkeyPatch) -> None:
    client, service = _client(monkeypatch)
    service.set_branch_protection(
        repo_id=REPO, branch="main", required_approvals=1, required_checks=[]
    )
    client.post(
        "/code-review/branches",
        json={"workspace_id": "ws", "repo_id": REPO, "name": "feat2", "from_ref": "main"},
    )
    resp = client.post(
        "/code-review/proposals",
        json={
            "workspace_id": "ws",
            "repo_id": REPO,
            "title": "Second",
            "source_branch": "feat2",
            "target_branch": "main",
        },
    )
    number = resp.json()["number"]

    blocked = client.post(
        "/code-review/proposal/merge",
        json={"workspace_id": "ws", "repo_id": REPO, "number": number},
    )
    assert blocked.status_code == 422, blocked.text

    client.post(
        "/code-review/proposal/review",
        json={"workspace_id": "ws", "repo_id": REPO, "number": number, "event": "approved"},
    )
    merged = client.post(
        "/code-review/proposal/merge",
        json={"workspace_id": "ws", "repo_id": REPO, "number": number},
    )
    assert merged.status_code == 200, merged.text
    assert merged.json()["merged"] is True


def test_repo_not_found(monkeypatch: pytest.MonkeyPatch) -> None:
    client, _ = _client(monkeypatch)
    resp = client.get(
        "/code-review/branches", params={"workspace_id": "ws", "repo_id": "org/missing"}
    )
    assert resp.status_code == 404
