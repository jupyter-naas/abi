from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

# ---------------------------------------------------------------------------
# Normalized, backend-agnostic DTOs
# ---------------------------------------------------------------------------
# These deliberately collapse the backing forge's enums into a small, stable
# vocabulary so a future adapter (GitHub, GitLab, Bitbucket, ...) can satisfy
# the same port without leaking Forgejo/Gitea concepts into the domain.

# Normalized proposal (pull/merge request) states.
PROPOSAL_OPEN = "open"
PROPOSAL_MERGED = "merged"
PROPOSAL_CLOSED = "closed"

# Normalized review states.
REVIEW_APPROVED = "approved"
REVIEW_CHANGES_REQUESTED = "changes_requested"
REVIEW_COMMENT = "comment"
REVIEW_PENDING = "pending"

# Normalized check states.
CHECK_SUCCESS = "success"
CHECK_FAILURE = "failure"
CHECK_PENDING = "pending"


@dataclass(frozen=True)
class Repo:
    id: str
    name: str
    owner: str
    default_branch: str
    clone_url: str
    html_url: str


@dataclass(frozen=True)
class Branch:
    name: str
    commit_sha: str
    protected: bool = False


@dataclass(frozen=True)
class DiffFile:
    path: str
    status: str
    additions: int
    deletions: int
    patch: str | None = None
    old_path: str | None = None


@dataclass(frozen=True)
class Diff:
    files: tuple[DiffFile, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class Comment:
    id: str
    path: str | None
    line: int | None
    body: str
    author: str
    created_at: str | None = None


@dataclass(frozen=True)
class Review:
    id: str
    state: str  # one of REVIEW_*
    body: str
    author: str
    submitted_at: str | None = None


@dataclass(frozen=True)
class Check:
    name: str
    status: str  # one of CHECK_*
    conclusion: str | None = None


@dataclass(frozen=True)
class Proposal:
    """A normalized pull/merge request ("change proposal")."""

    id: str
    number: int
    title: str
    body: str
    state: str  # one of PROPOSAL_*
    source_branch: str
    target_branch: str
    author: str
    mergeable: bool
    approvals: int
    html_url: str


@dataclass(frozen=True)
class MergeResult:
    merged: bool
    sha: str | None = None
    message: str | None = None


# ---------------------------------------------------------------------------
# Normalized error taxonomy (part of the port contract)
# ---------------------------------------------------------------------------
# A swappable port needs a normalized *error* contract, not just normalized
# states. Every adapter maps its backend's failures onto these.


class SourceControlError(Exception):
    def __init__(self, message: str = "", *, status: int | None = None) -> None:
        super().__init__(message)
        self.status = status


class RepoNotFoundError(SourceControlError):
    """The requested repository does not exist."""


class BranchNotFoundError(SourceControlError):
    """The requested branch does not exist."""


class ProposalNotFoundError(SourceControlError):
    """The requested proposal (pull/merge request) does not exist."""


class BranchNameConflictError(SourceControlError):
    """A branch with that name already exists."""


class MergeConflictError(SourceControlError):
    """The proposal cannot be merged because of conflicting changes."""


class MergeBlockedError(SourceControlError):
    """The merge is blocked by branch protection (approvals/checks)."""


class AccessDeniedError(SourceControlError):
    """RBAC / scope denial (401/403)."""


class ValidationError(SourceControlError):
    """The request was rejected as invalid (422)."""


class ISourceControlAdapter(ABC):
    """Secondary (driven) port for a git forge with in-app code review.

    ``repo_id`` is always the ``"owner/name"`` string.
    """

    @abstractmethod
    def ensure_user(self, *, external_id: str, email: str, username: str) -> str:
        """Idempotently ensure a forge user exists; return its id."""
        raise NotImplementedError()

    @abstractmethod
    def ensure_repo(
        self, *, owner: str, name: str, private: bool = True, auto_init: bool = True
    ) -> Repo:
        """Idempotently ensure a repository exists; return it.

        ``auto_init=False`` creates a truly empty repo (no initial commit) so an
        existing local history can be pushed to it.
        """
        raise NotImplementedError()

    @abstractmethod
    def list_repos(self) -> list[Repo]:
        """List the repositories the backend can manage."""
        raise NotImplementedError()

    @abstractmethod
    def add_collaborator(
        self, *, repo_id: str, username: str, permission: str = "write"
    ) -> None:
        """Idempotently grant ``username`` access to ``repo_id``.

        Required so per-user workspaces can push their branch-per-workspace
        changes to a shared monorepo they don't own.
        """
        raise NotImplementedError()

    @abstractmethod
    def list_branches(self, *, repo_id: str) -> list[Branch]:
        raise NotImplementedError()

    @abstractmethod
    def create_branch(self, *, repo_id: str, name: str, from_ref: str) -> Branch:
        raise NotImplementedError()

    @abstractmethod
    def delete_branch(self, *, repo_id: str, name: str) -> None:
        """Delete a branch; raise BranchNotFoundError if it does not exist."""
        raise NotImplementedError()

    @abstractmethod
    def get_diff(self, *, repo_id: str, base: str, head: str) -> Diff:
        """Return the diff between ``base`` and ``head`` refs."""
        raise NotImplementedError()

    @abstractmethod
    def create_proposal(
        self,
        *,
        repo_id: str,
        title: str,
        body: str,
        source_branch: str,
        target_branch: str,
        reviewers: list[str] | None = None,
    ) -> Proposal:
        """Open a change proposal (pull/merge request)."""
        raise NotImplementedError()

    @abstractmethod
    def list_proposals(self, *, repo_id: str, state: str = "open") -> list[Proposal]:
        raise NotImplementedError()

    @abstractmethod
    def get_proposal(self, *, repo_id: str, number: int) -> Proposal:
        raise NotImplementedError()

    @abstractmethod
    def get_proposal_diff(self, *, repo_id: str, number: int) -> Diff:
        raise NotImplementedError()

    @abstractmethod
    def list_comments(self, *, repo_id: str, number: int) -> list[Comment]:
        raise NotImplementedError()

    @abstractmethod
    def add_comment(
        self,
        *,
        repo_id: str,
        number: int,
        body: str,
        path: str | None = None,
        line: int | None = None,
    ) -> Comment:
        raise NotImplementedError()

    @abstractmethod
    def submit_review(
        self, *, repo_id: str, number: int, event: str, body: str = ""
    ) -> Review:
        """Submit a review with ``event`` mapped to a normalized REVIEW_* state."""
        raise NotImplementedError()

    @abstractmethod
    def list_checks(self, *, repo_id: str, number: int) -> list[Check]:
        raise NotImplementedError()

    @abstractmethod
    def set_branch_protection(
        self,
        *,
        repo_id: str,
        branch: str,
        required_approvals: int,
        required_checks: list[str],
    ) -> None:
        raise NotImplementedError()

    @abstractmethod
    def merge(self, *, repo_id: str, number: int, method: str = "merge") -> MergeResult:
        """Merge a proposal; raise MergeBlockedError if protection forbids it."""
        raise NotImplementedError()

    @abstractmethod
    def mint_git_token(self, *, user_id: str) -> str:
        """Mint a scoped git access token for ``user_id``."""
        raise NotImplementedError()
