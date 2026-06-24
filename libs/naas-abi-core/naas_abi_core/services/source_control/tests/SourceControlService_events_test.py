# mypy: disable-error-code="arg-type,misc"
from __future__ import annotations

import pytest

from naas_abi_core.services.source_control.adapters.secondary.InMemoryAdapter import (
    InMemoryAdapter,
)
from naas_abi_core.services.source_control.ontologies.modules.SourceControlEventOntology import (
    ProposalMergeBlocked,
    ProposalMerged,
    ProposalOpened,
    ReviewSubmitted,
)
from naas_abi_core.services.source_control.SourceControlPorts import (
    Branch,
    Check,
    Comment,
    Diff,
    ISourceControlAdapter,
    MergeBlockedError,
    MergeResult,
    PROPOSAL_OPEN,
    Proposal,
    Repo,
    REVIEW_APPROVED,
    Review,
)
from naas_abi_core.services.source_control.SourceControlService import (
    SourceControlService,
)


class _FakeEventService:
    def __init__(self) -> None:
        self.published: list = []

    def publish(self, event) -> None:
        self.published.append(event)


class _ExplodingEventService:
    def publish(self, event) -> None:
        raise RuntimeError("event bus down")


class _FakeServices:
    def __init__(self, events=None) -> None:
        self._events = events

    def events_available(self) -> bool:
        return self._events is not None

    @property
    def events(self):
        assert self._events is not None
        return self._events


class _BlockedMergeAdapter(ISourceControlAdapter):
    """Adapter whose merge always raises MergeBlockedError."""

    def ensure_user(self, **kwargs) -> str:
        return "user-x"

    def ensure_repo(self, **kwargs) -> Repo:
        return Repo(
            id="repo-1",
            name="proj",
            owner="alice",
            default_branch="main",
            clone_url="",
            html_url="",
        )

    def add_collaborator(self, **kwargs) -> None:
        return None

    def list_branches(self, **kwargs) -> list[Branch]:
        return []

    def create_branch(self, **kwargs) -> Branch:
        return Branch(name="feature", commit_sha="sha")

    def delete_branch(self, **kwargs) -> None:
        return None

    def get_diff(self, **kwargs) -> Diff:
        return Diff()

    def create_proposal(self, **kwargs) -> Proposal:
        return Proposal(
            id="pr-1",
            number=1,
            title="t",
            body="b",
            state=PROPOSAL_OPEN,
            source_branch="feature",
            target_branch="main",
            author="alice",
            mergeable=True,
            approvals=0,
            html_url="",
        )

    def list_proposals(self, **kwargs) -> list[Proposal]:
        return []

    def get_proposal(self, **kwargs) -> Proposal:
        return self.create_proposal()

    def get_proposal_diff(self, **kwargs) -> Diff:
        return Diff()

    def list_comments(self, **kwargs) -> list[Comment]:
        return []

    def add_comment(self, **kwargs) -> Comment:
        return Comment(id="c-1", path=None, line=None, body="b", author="alice")

    def submit_review(self, **kwargs) -> Review:
        return Review(id="r-1", state=REVIEW_APPROVED, body="", author="alice")

    def list_checks(self, **kwargs) -> list[Check]:
        return []

    def set_branch_protection(self, **kwargs) -> None:
        return None

    def merge(self, **kwargs) -> MergeResult:
        raise MergeBlockedError("merge blocked: 0/1 required approvals")

    def mint_git_token(self, **kwargs) -> str:
        return "git-token"


def _wired_service(adapter, events=None) -> SourceControlService:
    svc = SourceControlService(adapter)
    svc.set_services(_FakeServices(events))
    return svc


def _open_proposal(svc: SourceControlService, repo_id: str) -> Proposal:
    return svc.create_proposal(
        repo_id=repo_id,
        title="Add feature",
        body="body",
        source_branch="feature",
        target_branch="main",
    )


def _seed_repo(adapter: InMemoryAdapter) -> str:
    repo = adapter.ensure_repo(owner="alice", name="proj")
    return f"{repo.owner}/{repo.name}"


def test_no_events_when_services_not_wired() -> None:
    adapter = InMemoryAdapter()
    repo_id = _seed_repo(adapter)
    svc = SourceControlService(adapter)
    proposal = _open_proposal(svc, repo_id)
    assert proposal.state == PROPOSAL_OPEN


def test_no_events_when_events_unavailable() -> None:
    adapter = InMemoryAdapter()
    repo_id = _seed_repo(adapter)
    svc = _wired_service(adapter, events=None)
    proposal = _open_proposal(svc, repo_id)
    assert proposal.state == PROPOSAL_OPEN


def test_create_proposal_emits_proposal_opened() -> None:
    adapter = InMemoryAdapter()
    repo_id = _seed_repo(adapter)
    events = _FakeEventService()
    svc = _wired_service(adapter, events)

    proposal = _open_proposal(svc, repo_id)

    opened = [e for e in events.published if isinstance(e, ProposalOpened)]
    assert len(opened) == 1
    evt = opened[0]
    assert evt.repo_id == repo_id
    assert evt.number == proposal.number
    assert evt.title == "Add feature"
    assert evt.source_branch == "feature"
    assert evt.target_branch == "main"


def test_submit_review_emits_review_submitted() -> None:
    adapter = InMemoryAdapter()
    repo_id = _seed_repo(adapter)
    events = _FakeEventService()
    svc = _wired_service(adapter, events)
    _open_proposal(svc, repo_id)

    svc.submit_review(repo_id=repo_id, number=1, event="APPROVED", body="lgtm")

    submitted = [e for e in events.published if isinstance(e, ReviewSubmitted)]
    assert len(submitted) == 1
    assert submitted[0].state == REVIEW_APPROVED
    assert submitted[0].number == 1


def test_successful_merge_emits_proposal_merged() -> None:
    adapter = InMemoryAdapter()
    repo_id = _seed_repo(adapter)
    events = _FakeEventService()
    svc = _wired_service(adapter, events)
    _open_proposal(svc, repo_id)

    result = svc.merge(repo_id=repo_id, number=1)
    assert result.merged is True

    merged = [e for e in events.published if isinstance(e, ProposalMerged)]
    assert len(merged) == 1
    assert merged[0].number == 1
    assert merged[0].sha == result.sha


def test_blocked_merge_emits_blocked_and_reraises() -> None:
    events = _FakeEventService()
    svc = _wired_service(_BlockedMergeAdapter(), events)

    with pytest.raises(MergeBlockedError):
        svc.merge(repo_id="alice/proj", number=1)

    blocked = [e for e in events.published if isinstance(e, ProposalMergeBlocked)]
    assert len(blocked) == 1
    assert blocked[0].number == 1
    assert "blocked" in (blocked[0].reason or "")
    assert not any(isinstance(e, ProposalMerged) for e in events.published)


def test_publisher_exception_does_not_break_operation() -> None:
    adapter = InMemoryAdapter()
    repo_id = _seed_repo(adapter)
    svc = _wired_service(adapter, events=_ExplodingEventService())
    # Must not raise even though every publish() throws.
    proposal = _open_proposal(svc, repo_id)
    assert proposal.state == PROPOSAL_OPEN


def test_full_review_then_merge_flow() -> None:
    adapter = InMemoryAdapter()
    repo_id = _seed_repo(adapter)
    events = _FakeEventService()
    svc = _wired_service(adapter, events)

    svc.set_branch_protection(
        repo_id=repo_id, branch="main", required_approvals=1, required_checks=[]
    )
    _open_proposal(svc, repo_id)

    with pytest.raises(MergeBlockedError):
        svc.merge(repo_id=repo_id, number=1)

    svc.submit_review(repo_id=repo_id, number=1, event="APPROVED")
    svc.merge(repo_id=repo_id, number=1)

    assert any(isinstance(e, ProposalOpened) for e in events.published)
    assert any(isinstance(e, ReviewSubmitted) for e in events.published)
    assert any(isinstance(e, ProposalMergeBlocked) for e in events.published)
    assert any(isinstance(e, ProposalMerged) for e in events.published)
