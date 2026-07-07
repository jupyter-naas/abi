from __future__ import annotations

import pytest

from naas_abi_core.services.source_control.adapters.secondary.InMemoryAdapter import (
    InMemoryAdapter,
)
from naas_abi_core.services.source_control.SourceControlPorts import (
    BranchNameConflictError,
    MergeBlockedError,
    PROPOSAL_MERGED,
    PROPOSAL_OPEN,
    ProposalNotFoundError,
    REVIEW_APPROVED,
    RepoNotFoundError,
)
from naas_abi_core.services.source_control.tests.source_control__secondary_adapter__generic_test import (
    GenericSourceControlSecondaryAdapterTest,
)


class TestInMemoryAdapter(GenericSourceControlSecondaryAdapterTest):
    @pytest.fixture
    def adapter_class(self):
        return InMemoryAdapter


def _repo(adapter: InMemoryAdapter) -> str:
    repo = adapter.ensure_repo(owner="alice", name="proj")
    return f"{repo.owner}/{repo.name}"


def test_ensure_user_is_idempotent() -> None:
    adapter = InMemoryAdapter()
    a = adapter.ensure_user(external_id="x", email="a@b.c", username="alice")
    b = adapter.ensure_user(external_id="x", email="a@b.c", username="alice")
    assert a == b


def test_ensure_repo_is_idempotent() -> None:
    adapter = InMemoryAdapter()
    first = adapter.ensure_repo(owner="alice", name="proj")
    second = adapter.ensure_repo(owner="alice", name="proj")
    assert first.id == second.id
    assert first.default_branch == "main"


def test_unknown_repo_raises() -> None:
    adapter = InMemoryAdapter()
    with pytest.raises(RepoNotFoundError):
        adapter.list_branches(repo_id="nope/nope")


def test_create_branch_and_conflict() -> None:
    adapter = InMemoryAdapter()
    repo_id = _repo(adapter)
    branch = adapter.create_branch(repo_id=repo_id, name="feature", from_ref="main")
    assert branch.name == "feature"
    assert {b.name for b in adapter.list_branches(repo_id=repo_id)} == {
        "main",
        "feature",
    }
    with pytest.raises(BranchNameConflictError):
        adapter.create_branch(repo_id=repo_id, name="feature", from_ref="main")


def test_proposal_lifecycle() -> None:
    adapter = InMemoryAdapter()
    repo_id = _repo(adapter)
    adapter.create_branch(repo_id=repo_id, name="feature", from_ref="main")

    proposal = adapter.create_proposal(
        repo_id=repo_id,
        title="Add feature",
        body="body",
        source_branch="feature",
        target_branch="main",
    )
    assert proposal.number == 1
    assert proposal.state == PROPOSAL_OPEN

    fetched = adapter.get_proposal(repo_id=repo_id, number=1)
    assert fetched.title == "Add feature"

    assert len(adapter.list_proposals(repo_id=repo_id)) == 1
    assert adapter.list_checks(repo_id=repo_id, number=1) == []

    with pytest.raises(ProposalNotFoundError):
        adapter.get_proposal(repo_id=repo_id, number=999)


def test_comments_round_trip() -> None:
    adapter = InMemoryAdapter()
    repo_id = _repo(adapter)
    adapter.create_proposal(
        repo_id=repo_id,
        title="t",
        body="b",
        source_branch="feature",
        target_branch="main",
    )
    adapter.add_comment(repo_id=repo_id, number=1, body="looks good")
    adapter.add_comment(
        repo_id=repo_id, number=1, body="nit", path="main.py", line=10
    )
    comments = adapter.list_comments(repo_id=repo_id, number=1)
    assert len(comments) == 2
    assert comments[1].path == "main.py"
    assert comments[1].line == 10


def test_merge_blocked_then_approved_then_merged() -> None:
    adapter = InMemoryAdapter()
    repo_id = _repo(adapter)
    adapter.set_branch_protection(
        repo_id=repo_id, branch="main", required_approvals=1, required_checks=[]
    )
    adapter.create_proposal(
        repo_id=repo_id,
        title="t",
        body="b",
        source_branch="feature",
        target_branch="main",
    )

    # No approvals yet -> blocked.
    with pytest.raises(MergeBlockedError):
        adapter.merge(repo_id=repo_id, number=1)

    review = adapter.submit_review(
        repo_id=repo_id, number=1, event="APPROVED", body="lgtm"
    )
    assert review.state == REVIEW_APPROVED
    assert adapter.get_proposal(repo_id=repo_id, number=1).approvals == 1

    result = adapter.merge(repo_id=repo_id, number=1)
    assert result.merged is True
    assert result.sha is not None
    assert adapter.get_proposal(repo_id=repo_id, number=1).state == PROPOSAL_MERGED


def test_list_reviews_returns_submitted_reviews() -> None:
    adapter = InMemoryAdapter()
    repo_id = _repo(adapter)
    adapter.create_proposal(
        repo_id=repo_id, title="t", body="b", source_branch="feature", target_branch="main"
    )
    assert adapter.list_reviews(repo_id=repo_id, number=1) == []
    adapter.submit_review(repo_id=repo_id, number=1, event="APPROVED", body="lgtm")
    reviews = adapter.list_reviews(repo_id=repo_id, number=1)
    assert len(reviews) == 1
    assert reviews[0].state == REVIEW_APPROVED
    assert reviews[0].body == "lgtm"


def test_list_proposal_commits_returns_list() -> None:
    adapter = InMemoryAdapter()
    repo_id = _repo(adapter)
    adapter.create_proposal(
        repo_id=repo_id, title="t", body="b", source_branch="feature", target_branch="main"
    )
    assert adapter.list_proposal_commits(repo_id=repo_id, number=1) == []
    with pytest.raises(ProposalNotFoundError):
        adapter.list_proposal_commits(repo_id=repo_id, number=999)


def test_merge_without_protection_succeeds() -> None:
    adapter = InMemoryAdapter()
    repo_id = _repo(adapter)
    adapter.create_proposal(
        repo_id=repo_id,
        title="t",
        body="b",
        source_branch="feature",
        target_branch="main",
    )
    result = adapter.merge(repo_id=repo_id, number=1)
    assert result.merged is True


def test_mint_git_token_returns_token() -> None:
    adapter = InMemoryAdapter()
    user_id = adapter.ensure_user(external_id="x", email="a@b.c", username="alice")
    token = adapter.mint_git_token(user_id=user_id)
    assert token.startswith("git-token-")
