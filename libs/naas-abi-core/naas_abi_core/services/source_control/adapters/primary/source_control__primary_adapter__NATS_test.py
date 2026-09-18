"""Unit tests for SourceControlPrimaryAdapterNATS's auth/dispatch/error-mapping.

None of these need a real NATS server: each handler is invoked directly
against a minimal fake ``Request`` that records whatever gets passed to
``respond``, matching the "test the handler logic directly" option called
out for this adapter (see object_storage's identical pattern).
"""

import asyncio
from collections.abc import Sequence

from google.protobuf.message import Message
from naas_abi_core.engine.nats_auth import issue_service_token
from naas_abi_core.proto.source_control.v1 import source_control_pb2
from naas_abi_core.services.source_control.adapters.primary.source_control__primary_adapter__NATS import (
    AUTH_HEADER,
    SUBJECT_PREFIX,
    SourceControlPrimaryAdapterNATS,
)
from naas_abi_core.services.source_control.SourceControlPorts import (
    PROPOSAL_OPEN,
    REVIEW_APPROVED,
    AccessDeniedError,
    Branch,
    BranchNameConflictError,
    BranchNotFoundError,
    Check,
    Comment,
    Commit,
    ContentEntry,
    Diff,
    DiffFile,
    FileContent,
    FileWrite,
    ISourceControlAdapter,
    MergeBlockedError,
    MergeConflictError,
    MergeResult,
    Proposal,
    ProposalNotFoundError,
    Repo,
    RepoNotFoundError,
    Review,
    ValidationError,
    WorkflowRun,
)

SECRET = "test-shared-secret"


class _FakeRequest:
    """Stands in for nats.micro.request.Request: same ``.data``/``.headers``
    surface, and ``respond`` just records the payload instead of publishing
    it anywhere."""

    def __init__(
        self,
        data: bytes,
        headers: dict[str, str] | None = None,
        subject: str = "abi.svc.source_control.v1.ensure_user",
    ) -> None:
        self.data = data
        self.headers = headers
        self.subject = subject
        self.responses: list[bytes] = []

    async def respond(
        self, data: bytes = b"", headers: dict[str, str] | None = None
    ) -> None:
        self.responses.append(data)


class _StubAdapter(ISourceControlAdapter):
    """Minimal in-memory ISourceControlAdapter for driving the handlers.

    Not realistic (no real git, no real forge semantics) -- just enough
    bookkeeping to round-trip every method through the wire and to exercise
    RepoNotFoundError/ProposalNotFoundError/BranchNotFoundError/
    BranchNameConflictError/MergeBlockedError naturally.
    """

    def __init__(self) -> None:
        self.repos: dict[str, dict] = {}
        self._counter = 0

    def _next(self, prefix: str) -> str:
        self._counter += 1
        return f"{prefix}-{self._counter}"

    def _repo(self, repo_id: str) -> dict:
        try:
            return self.repos[repo_id]
        except KeyError:
            raise RepoNotFoundError(f"{repo_id} not found") from None

    def _proposal(self, repo_id: str, number: int) -> dict:
        repo = self._repo(repo_id)
        try:
            return repo["proposals"][number]
        except KeyError:
            raise ProposalNotFoundError(f"{repo_id}#{number} not found") from None

    def _to_repo(self, record: dict) -> Repo:
        repo_id = f"{record['owner']}/{record['name']}"
        return Repo(
            id=record["id"],
            name=record["name"],
            owner=record["owner"],
            default_branch=record["default_branch"],
            clone_url=f"https://forge.test/{repo_id}.git",
            html_url=f"https://forge.test/{repo_id}",
            private=record["private"],
            empty=record["empty"],
        )

    def _to_proposal(self, record: dict) -> Proposal:
        approvals = sum(1 for r in record["reviews"] if r.state == REVIEW_APPROVED)
        return Proposal(
            id=record["id"],
            number=record["number"],
            title=record["title"],
            body=record["body"],
            state=record["state"],
            source_branch=record["source_branch"],
            target_branch=record["target_branch"],
            author=record["author"],
            mergeable=record["state"] == PROPOSAL_OPEN,
            approvals=approvals,
            html_url=f"https://forge.test/pr/{record['number']}",
        )

    def ensure_user(self, *, external_id: str, email: str, username: str) -> str:
        return self._next("user")

    def ensure_repo(
        self, *, owner: str, name: str, private: bool = True, auto_init: bool = True
    ) -> Repo:
        repo_id = f"{owner}/{name}"
        if repo_id not in self.repos:
            self.repos[repo_id] = {
                "id": self._next("repo"),
                "owner": owner,
                "name": name,
                "default_branch": "main" if auto_init else "",
                "branches": {"main": self._next("sha")} if auto_init else {},
                "proposals": {},
                "next_pr_number": 1,
                "protection": {},
                "private": private,
                "empty": not auto_init,
                "files": {},
                "collaborators": {},
            }
        return self._to_repo(self.repos[repo_id])

    def list_repos(self) -> list[Repo]:
        return [self._to_repo(r) for r in self.repos.values()]

    def add_collaborator(
        self, *, repo_id: str, username: str, permission: str = "write"
    ) -> None:
        self._repo(repo_id)["collaborators"][username] = permission

    def list_contents(
        self, *, repo_id: str, path: str = "", ref: str | None = None
    ) -> list[ContentEntry]:
        files = self._repo(repo_id)["files"]
        return [
            ContentEntry(
                name=p,
                path=p,
                type="file",
                size=len(c) if isinstance(c, bytes) else len(c.encode()),
            )
            for p, c in files.items()
        ]

    def get_file(
        self, *, repo_id: str, path: str, ref: str | None = None
    ) -> FileContent:
        files = self._repo(repo_id)["files"]
        if path not in files:
            raise RepoNotFoundError(f"{repo_id}:{path} not found")
        content = files[path]
        if isinstance(content, bytes):
            return FileContent(
                path=path, name=path, size=len(content), text=None, is_binary=True, data=content
            )
        return FileContent(path=path, name=path, size=len(content), text=content)

    def upsert_file(
        self,
        *,
        repo_id: str,
        path: str,
        content: str | bytes,
        message: str,
        branch: str,
        author_name: str | None = None,
        author_email: str | None = None,
    ) -> Commit:
        repo = self._repo(repo_id)
        repo["files"][path] = content
        sha = self._next("sha")
        repo["branches"][branch] = sha
        return Commit(sha=sha, message=message, author=author_name or "stub")

    def upsert_files(
        self,
        *,
        repo_id: str,
        files: Sequence[FileWrite],
        message: str,
        branch: str,
        author_name: str | None = None,
        author_email: str | None = None,
    ) -> Commit:
        repo = self._repo(repo_id)
        for file_write in files:
            repo["files"][file_write.path] = file_write.content
        sha = self._next("sha")
        repo["branches"][branch] = sha
        return Commit(sha=sha, message=message, author=author_name or "stub")

    def list_commits(
        self, *, repo_id: str, ref: str | None = None, limit: int = 20
    ) -> list[Commit]:
        self._repo(repo_id)
        return [Commit(sha="sha-1", message="init", author="stub")][:limit]

    def list_branches(self, *, repo_id: str) -> list[Branch]:
        repo = self._repo(repo_id)
        return [
            Branch(name=name, commit_sha=sha, protected=name in repo["protection"])
            for name, sha in repo["branches"].items()
        ]

    def create_branch(self, *, repo_id: str, name: str, from_ref: str) -> Branch:
        repo = self._repo(repo_id)
        if name in repo["branches"]:
            raise BranchNameConflictError(f"branch '{name}' already exists")
        sha = self._next("sha")
        repo["branches"][name] = sha
        return Branch(name=name, commit_sha=sha)

    def delete_branch(self, *, repo_id: str, name: str) -> None:
        repo = self._repo(repo_id)
        if name not in repo["branches"]:
            raise BranchNotFoundError(f"branch '{name}' not found")
        del repo["branches"][name]

    def get_diff(self, *, repo_id: str, base: str, head: str) -> Diff:
        self._repo(repo_id)
        return Diff(files=(DiffFile(path="a.py", status="modified", additions=1, deletions=1),))

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
        repo = self._repo(repo_id)
        number = repo["next_pr_number"]
        repo["next_pr_number"] += 1
        record = {
            "id": self._next("pr"),
            "number": number,
            "title": title,
            "body": body,
            "state": PROPOSAL_OPEN,
            "source_branch": source_branch,
            "target_branch": target_branch,
            "author": "stub",
            "comments": [],
            "reviews": [],
        }
        repo["proposals"][number] = record
        return self._to_proposal(record)

    def list_proposals(self, *, repo_id: str, state: str = "open") -> list[Proposal]:
        repo = self._repo(repo_id)
        return [
            self._to_proposal(r)
            for r in repo["proposals"].values()
            if state == "all" or r["state"] == state
        ]

    def get_proposal(self, *, repo_id: str, number: int) -> Proposal:
        return self._to_proposal(self._proposal(repo_id, number))

    def get_proposal_diff(self, *, repo_id: str, number: int) -> Diff:
        self._proposal(repo_id, number)
        return Diff(files=(DiffFile(path="a.py", status="modified", additions=2, deletions=0),))

    def list_proposal_commits(self, *, repo_id: str, number: int) -> list[Commit]:
        self._proposal(repo_id, number)
        return [Commit(sha="sha-pr", message="pr commit", author="stub")]

    def list_comments(self, *, repo_id: str, number: int) -> list[Comment]:
        return list(self._proposal(repo_id, number)["comments"])

    def list_reviews(self, *, repo_id: str, number: int) -> list[Review]:
        return list(self._proposal(repo_id, number)["reviews"])

    def add_comment(
        self,
        *,
        repo_id: str,
        number: int,
        body: str,
        path: str | None = None,
        line: int | None = None,
    ) -> Comment:
        record = self._proposal(repo_id, number)
        comment = Comment(id=self._next("comment"), path=path, line=line, body=body, author="stub")
        record["comments"].append(comment)
        return comment

    def submit_review(
        self, *, repo_id: str, number: int, event: str, body: str = ""
    ) -> Review:
        record = self._proposal(repo_id, number)
        state = REVIEW_APPROVED if event.upper() == "APPROVED" else "changes_requested"
        review = Review(id=self._next("review"), state=state, body=body, author="stub")
        record["reviews"].append(review)
        return review

    def list_checks(self, *, repo_id: str, number: int) -> list[Check]:
        self._proposal(repo_id, number)
        return [Check(name="ci", status="success")]

    def set_branch_protection(
        self,
        *,
        repo_id: str,
        branch: str,
        required_approvals: int,
        required_checks: list[str],
    ) -> None:
        repo = self._repo(repo_id)
        repo["protection"][branch] = {
            "required_approvals": required_approvals,
            "required_checks": list(required_checks),
        }

    def merge(self, *, repo_id: str, number: int, method: str = "merge") -> MergeResult:
        repo = self._repo(repo_id)
        record = self._proposal(repo_id, number)
        protection = repo["protection"].get(record["target_branch"])
        if protection is not None:
            approvals = sum(1 for r in record["reviews"] if r.state == REVIEW_APPROVED)
            if approvals < protection["required_approvals"]:
                raise MergeBlockedError(
                    f"merge blocked: {approvals}/{protection['required_approvals']} required approvals"
                )
        sha = self._next("sha")
        record["state"] = "merged"
        return MergeResult(merged=True, sha=sha, message="merged")

    def list_workflow_runs(self, *, repo_id: str, limit: int = 20) -> list[WorkflowRun]:
        self._repo(repo_id)
        return [
            WorkflowRun(
                id=1,
                name="CI",
                workflow_id="ci.yml",
                display_title="t",
                run_number=1,
                event="push",
                status="success",
                head_branch="main",
                head_sha="sha-1",
                url="https://forge.test/runs/1",
            )
        ][:limit]

    def mint_git_token(self, *, user_id: str) -> str:
        return self._next("git-token")


def _valid_token() -> str:
    return issue_service_token("api", SECRET)


class _UseValidToken:
    """Sentinel distinguishing "no token argument given" from ``token=None``
    (no auth header at all) and ``token=""``/any string (an explicit header
    value, including an empty one)."""


_USE_VALID_TOKEN = _UseValidToken()


def _call(
    adapter: SourceControlPrimaryAdapterNATS,
    method: str,
    request: Message,
    response_cls: type[Message],
    *,
    token: str | None | _UseValidToken = _USE_VALID_TOKEN,
) -> Message:
    headers: dict[str, str] | None
    if isinstance(token, _UseValidToken):
        headers = {AUTH_HEADER: _valid_token()}
    elif token is None:
        headers = None
    else:
        headers = {AUTH_HEADER: token}
    fake = _FakeRequest(
        data=request.SerializeToString(),
        headers=headers,
        subject=f"{SUBJECT_PREFIX}.{method}",
    )
    asyncio.run(getattr(adapter, f"_handle_{method}")(fake))
    response = response_cls()
    response.ParseFromString(fake.responses[0])
    return response


# ---------------------------------------------------------------------------
# Auth.
# ---------------------------------------------------------------------------


def test_missing_token_returns_unauthenticated():
    adapter = SourceControlPrimaryAdapterNATS(_StubAdapter(), SECRET)
    response = _call(
        adapter,
        "ensure_user",
        source_control_pb2.EnsureUserRequest(external_id="x", email="a@b.c", username="alice"),
        source_control_pb2.EnsureUserResponse,
        token=None,
    )
    assert response.HasField("error")
    assert response.error.code == "UNAUTHENTICATED"
    assert response.error.retryable is False


def test_empty_token_header_returns_unauthenticated():
    adapter = SourceControlPrimaryAdapterNATS(_StubAdapter(), SECRET)
    response = _call(
        adapter,
        "ensure_user",
        source_control_pb2.EnsureUserRequest(external_id="x", email="a@b.c", username="alice"),
        source_control_pb2.EnsureUserResponse,
        token="",
    )
    assert response.error.code == "UNAUTHENTICATED"


def test_malformed_token_returns_unauthenticated():
    adapter = SourceControlPrimaryAdapterNATS(_StubAdapter(), SECRET)
    response = _call(
        adapter,
        "ensure_user",
        source_control_pb2.EnsureUserRequest(external_id="x", email="a@b.c", username="alice"),
        source_control_pb2.EnsureUserResponse,
        token="not-a-jwt",
    )
    assert response.error.code == "UNAUTHENTICATED"


def test_token_signed_with_wrong_secret_returns_unauthenticated():
    adapter = SourceControlPrimaryAdapterNATS(_StubAdapter(), SECRET)
    wrong_secret_token = issue_service_token("api", "a-different-secret")
    response = _call(
        adapter,
        "ensure_user",
        source_control_pb2.EnsureUserRequest(external_id="x", email="a@b.c", username="alice"),
        source_control_pb2.EnsureUserResponse,
        token=wrong_secret_token,
    )
    assert response.error.code == "UNAUTHENTICATED"


# ---------------------------------------------------------------------------
# Happy path -- at least one round trip per method (grouped where related).
# ---------------------------------------------------------------------------


def test_ensure_user_returns_user_id():
    adapter = SourceControlPrimaryAdapterNATS(_StubAdapter(), SECRET)
    response = _call(
        adapter,
        "ensure_user",
        source_control_pb2.EnsureUserRequest(external_id="x", email="a@b.c", username="alice"),
        source_control_pb2.EnsureUserResponse,
    )
    assert not response.HasField("error")
    assert response.user_id


def test_ensure_repo_returns_repo():
    adapter = SourceControlPrimaryAdapterNATS(_StubAdapter(), SECRET)
    response = _call(
        adapter,
        "ensure_repo",
        source_control_pb2.EnsureRepoRequest(
            owner="alice", name="proj", private=True, auto_init=True
        ),
        source_control_pb2.EnsureRepoResponse,
    )
    assert not response.HasField("error")
    assert response.repo.owner == "alice"
    assert response.repo.name == "proj"
    assert response.repo.default_branch == "main"


def test_list_repos_returns_created_repos():
    stub = _StubAdapter()
    stub.ensure_repo(owner="alice", name="proj")
    adapter = SourceControlPrimaryAdapterNATS(stub, SECRET)
    response = _call(
        adapter, "list_repos", source_control_pb2.ListReposRequest(), source_control_pb2.ListReposResponse
    )
    assert not response.HasField("error")
    assert len(response.repos.repos) == 1


def test_add_collaborator_succeeds():
    stub = _StubAdapter()
    stub.ensure_repo(owner="alice", name="proj")
    adapter = SourceControlPrimaryAdapterNATS(stub, SECRET)
    response = _call(
        adapter,
        "add_collaborator",
        source_control_pb2.AddCollaboratorRequest(
            repo_id="alice/proj", username="bob", permission="write"
        ),
        source_control_pb2.AddCollaboratorResponse,
    )
    assert not response.HasField("error")
    assert stub.repos["alice/proj"]["collaborators"]["bob"] == "write"


def test_upsert_file_then_get_file_and_list_contents_round_trip():
    stub = _StubAdapter()
    stub.ensure_repo(owner="alice", name="proj")
    adapter = SourceControlPrimaryAdapterNATS(stub, SECRET)

    upsert_response = _call(
        adapter,
        "upsert_file",
        source_control_pb2.UpsertFileRequest(
            repo_id="alice/proj",
            path="README.md",
            text_content="hello",
            message="add readme",
            branch="main",
            author_name="Alice",
        ),
        source_control_pb2.UpsertFileResponse,
    )
    assert not upsert_response.HasField("error")
    assert upsert_response.commit.message == "add readme"
    assert upsert_response.commit.author == "Alice"

    contents_response = _call(
        adapter,
        "list_contents",
        source_control_pb2.ListContentsRequest(repo_id="alice/proj", path=""),
        source_control_pb2.ListContentsResponse,
    )
    assert [e.name for e in contents_response.entries.entries] == ["README.md"]

    file_response = _call(
        adapter,
        "get_file",
        source_control_pb2.GetFileRequest(repo_id="alice/proj", path="README.md"),
        source_control_pb2.GetFileResponse,
    )
    assert not file_response.HasField("error")
    assert file_response.file.text == "hello"
    assert file_response.file.is_binary is False


def test_upsert_file_binary_content_round_trips():
    stub = _StubAdapter()
    stub.ensure_repo(owner="alice", name="proj")
    adapter = SourceControlPrimaryAdapterNATS(stub, SECRET)

    _call(
        adapter,
        "upsert_file",
        source_control_pb2.UpsertFileRequest(
            repo_id="alice/proj",
            path="logo.png",
            binary_content=b"\x89PNG",
            message="add logo",
            branch="main",
        ),
        source_control_pb2.UpsertFileResponse,
    )
    file_response = _call(
        adapter,
        "get_file",
        source_control_pb2.GetFileRequest(repo_id="alice/proj", path="logo.png"),
        source_control_pb2.GetFileResponse,
    )
    assert file_response.file.is_binary is True
    assert file_response.file.data == b"\x89PNG"
    assert not file_response.file.HasField("text")


def test_upsert_files_writes_many_paths_in_one_call():
    stub = _StubAdapter()
    stub.ensure_repo(owner="alice", name="proj")
    adapter = SourceControlPrimaryAdapterNATS(stub, SECRET)

    response = _call(
        adapter,
        "upsert_files",
        source_control_pb2.UpsertFilesRequest(
            repo_id="alice/proj",
            files=[
                source_control_pb2.FileWrite(path="a.txt", text_content="a"),
                source_control_pb2.FileWrite(path="b.bin", binary_content=b"\x00\x01"),
            ],
            message="seed",
            branch="main",
        ),
        source_control_pb2.UpsertFilesResponse,
    )
    assert not response.HasField("error")
    assert stub.repos["alice/proj"]["files"]["a.txt"] == "a"
    assert stub.repos["alice/proj"]["files"]["b.bin"] == b"\x00\x01"


def test_list_commits_returns_commits():
    stub = _StubAdapter()
    stub.ensure_repo(owner="alice", name="proj")
    adapter = SourceControlPrimaryAdapterNATS(stub, SECRET)
    response = _call(
        adapter,
        "list_commits",
        source_control_pb2.ListCommitsRequest(repo_id="alice/proj", limit=20),
        source_control_pb2.ListCommitsResponse,
    )
    assert not response.HasField("error")
    assert len(response.commits.commits) == 1


def test_branch_lifecycle_round_trip():
    stub = _StubAdapter()
    stub.ensure_repo(owner="alice", name="proj")
    adapter = SourceControlPrimaryAdapterNATS(stub, SECRET)

    create_response = _call(
        adapter,
        "create_branch",
        source_control_pb2.CreateBranchRequest(repo_id="alice/proj", name="feature", from_ref="main"),
        source_control_pb2.CreateBranchResponse,
    )
    assert not create_response.HasField("error")
    assert create_response.branch.name == "feature"

    list_response = _call(
        adapter,
        "list_branches",
        source_control_pb2.ListBranchesRequest(repo_id="alice/proj"),
        source_control_pb2.ListBranchesResponse,
    )
    assert {b.name for b in list_response.branches.branches} == {"main", "feature"}

    delete_response = _call(
        adapter,
        "delete_branch",
        source_control_pb2.DeleteBranchRequest(repo_id="alice/proj", name="feature"),
        source_control_pb2.DeleteBranchResponse,
    )
    assert not delete_response.HasField("error")


def test_get_diff_returns_files():
    stub = _StubAdapter()
    stub.ensure_repo(owner="alice", name="proj")
    adapter = SourceControlPrimaryAdapterNATS(stub, SECRET)
    response = _call(
        adapter,
        "get_diff",
        source_control_pb2.GetDiffRequest(repo_id="alice/proj", base="main", head="feature"),
        source_control_pb2.GetDiffResponse,
    )
    assert not response.HasField("error")
    assert len(response.diff.files) == 1


def test_proposal_lifecycle_round_trip():
    stub = _StubAdapter()
    stub.ensure_repo(owner="alice", name="proj")
    adapter = SourceControlPrimaryAdapterNATS(stub, SECRET)

    create_response = _call(
        adapter,
        "create_proposal",
        source_control_pb2.CreateProposalRequest(
            repo_id="alice/proj",
            title="Add x",
            body="body",
            source_branch="feature",
            target_branch="main",
            reviewers=["bob"],
        ),
        source_control_pb2.CreateProposalResponse,
    )
    assert not create_response.HasField("error")
    assert create_response.proposal.number == 1
    assert create_response.proposal.state == PROPOSAL_OPEN

    list_response = _call(
        adapter,
        "list_proposals",
        source_control_pb2.ListProposalsRequest(repo_id="alice/proj", state="open"),
        source_control_pb2.ListProposalsResponse,
    )
    assert len(list_response.proposals.proposals) == 1

    get_response = _call(
        adapter,
        "get_proposal",
        source_control_pb2.GetProposalRequest(repo_id="alice/proj", number=1),
        source_control_pb2.GetProposalResponse,
    )
    assert get_response.proposal.title == "Add x"

    diff_response = _call(
        adapter,
        "get_proposal_diff",
        source_control_pb2.GetProposalDiffRequest(repo_id="alice/proj", number=1),
        source_control_pb2.GetProposalDiffResponse,
    )
    assert len(diff_response.diff.files) == 1

    commits_response = _call(
        adapter,
        "list_proposal_commits",
        source_control_pb2.ListProposalCommitsRequest(repo_id="alice/proj", number=1),
        source_control_pb2.ListProposalCommitsResponse,
    )
    assert len(commits_response.commits.commits) == 1

    comment_response = _call(
        adapter,
        "add_comment",
        source_control_pb2.AddCommentRequest(
            repo_id="alice/proj", number=1, body="nice", path="a.py", line=3
        ),
        source_control_pb2.AddCommentResponse,
    )
    assert comment_response.comment.path == "a.py"
    assert comment_response.comment.line == 3

    comments_response = _call(
        adapter,
        "list_comments",
        source_control_pb2.ListCommentsRequest(repo_id="alice/proj", number=1),
        source_control_pb2.ListCommentsResponse,
    )
    assert len(comments_response.comments.comments) == 1

    review_response = _call(
        adapter,
        "submit_review",
        source_control_pb2.SubmitReviewRequest(
            repo_id="alice/proj", number=1, event="APPROVED", body="lgtm"
        ),
        source_control_pb2.SubmitReviewResponse,
    )
    assert review_response.review.state == REVIEW_APPROVED

    reviews_response = _call(
        adapter,
        "list_reviews",
        source_control_pb2.ListReviewsRequest(repo_id="alice/proj", number=1),
        source_control_pb2.ListReviewsResponse,
    )
    assert len(reviews_response.reviews.reviews) == 1

    checks_response = _call(
        adapter,
        "list_checks",
        source_control_pb2.ListChecksRequest(repo_id="alice/proj", number=1),
        source_control_pb2.ListChecksResponse,
    )
    assert len(checks_response.checks.checks) == 1

    merge_response = _call(
        adapter,
        "merge",
        source_control_pb2.MergeRequest(repo_id="alice/proj", number=1, method="merge"),
        source_control_pb2.MergeResponse,
    )
    assert not merge_response.HasField("error")
    assert merge_response.merge_result.merged is True


def test_set_branch_protection_succeeds():
    stub = _StubAdapter()
    stub.ensure_repo(owner="alice", name="proj")
    adapter = SourceControlPrimaryAdapterNATS(stub, SECRET)
    response = _call(
        adapter,
        "set_branch_protection",
        source_control_pb2.SetBranchProtectionRequest(
            repo_id="alice/proj", branch="main", required_approvals=1, required_checks=["ci"]
        ),
        source_control_pb2.SetBranchProtectionResponse,
    )
    assert not response.HasField("error")
    assert stub.repos["alice/proj"]["protection"]["main"]["required_approvals"] == 1


def test_list_workflow_runs_returns_runs():
    stub = _StubAdapter()
    stub.ensure_repo(owner="alice", name="proj")
    adapter = SourceControlPrimaryAdapterNATS(stub, SECRET)
    response = _call(
        adapter,
        "list_workflow_runs",
        source_control_pb2.ListWorkflowRunsRequest(repo_id="alice/proj", limit=20),
        source_control_pb2.ListWorkflowRunsResponse,
    )
    assert not response.HasField("error")
    assert len(response.workflow_runs.workflow_runs) == 1


def test_mint_git_token_returns_token():
    stub = _StubAdapter()
    adapter = SourceControlPrimaryAdapterNATS(stub, SECRET)
    response = _call(
        adapter,
        "mint_git_token",
        source_control_pb2.MintGitTokenRequest(user_id="user-1"),
        source_control_pb2.MintGitTokenResponse,
    )
    assert not response.HasField("error")
    assert response.token.startswith("git-token-")


# ---------------------------------------------------------------------------
# Business error mapping -- one per SourceControlError subclass, each also
# checking the CallError.status round-trip.
# ---------------------------------------------------------------------------


def test_repo_not_found_maps_to_call_error_with_status():
    class _Adapter(_StubAdapter):
        def list_branches(self, *, repo_id: str) -> list[Branch]:
            raise RepoNotFoundError("no such repo", status=404)

    adapter = SourceControlPrimaryAdapterNATS(_Adapter(), SECRET)
    response = _call(
        adapter,
        "list_branches",
        source_control_pb2.ListBranchesRequest(repo_id="nope/nope"),
        source_control_pb2.ListBranchesResponse,
    )
    assert response.error.code == "REPO_NOT_FOUND"
    assert response.error.retryable is False
    assert response.error.HasField("status")
    assert response.error.status == 404


def test_branch_not_found_maps_to_call_error_with_status():
    class _Adapter(_StubAdapter):
        def delete_branch(self, *, repo_id: str, name: str) -> None:
            raise BranchNotFoundError("no such branch", status=404)

    adapter = SourceControlPrimaryAdapterNATS(_Adapter(), SECRET)
    response = _call(
        adapter,
        "delete_branch",
        source_control_pb2.DeleteBranchRequest(repo_id="alice/proj", name="missing"),
        source_control_pb2.DeleteBranchResponse,
    )
    assert response.error.code == "BRANCH_NOT_FOUND"
    assert response.error.retryable is False
    assert response.error.status == 404


def test_proposal_not_found_maps_to_call_error_with_status():
    class _Adapter(_StubAdapter):
        def get_proposal(self, *, repo_id: str, number: int) -> Proposal:
            raise ProposalNotFoundError("no such proposal", status=404)

    adapter = SourceControlPrimaryAdapterNATS(_Adapter(), SECRET)
    response = _call(
        adapter,
        "get_proposal",
        source_control_pb2.GetProposalRequest(repo_id="alice/proj", number=999),
        source_control_pb2.GetProposalResponse,
    )
    assert response.error.code == "PROPOSAL_NOT_FOUND"
    assert response.error.retryable is False
    assert response.error.status == 404


def test_branch_name_conflict_maps_to_call_error_with_status():
    class _Adapter(_StubAdapter):
        def create_branch(self, *, repo_id: str, name: str, from_ref: str) -> Branch:
            raise BranchNameConflictError("branch exists", status=409)

    adapter = SourceControlPrimaryAdapterNATS(_Adapter(), SECRET)
    response = _call(
        adapter,
        "create_branch",
        source_control_pb2.CreateBranchRequest(repo_id="alice/proj", name="main", from_ref="main"),
        source_control_pb2.CreateBranchResponse,
    )
    assert response.error.code == "BRANCH_NAME_CONFLICT"
    assert response.error.retryable is False
    assert response.error.status == 409


def test_merge_conflict_maps_to_call_error_with_status():
    class _Adapter(_StubAdapter):
        def merge(self, *, repo_id: str, number: int, method: str = "merge") -> MergeResult:
            raise MergeConflictError("conflicting changes", status=409)

    adapter = SourceControlPrimaryAdapterNATS(_Adapter(), SECRET)
    response = _call(
        adapter,
        "merge",
        source_control_pb2.MergeRequest(repo_id="alice/proj", number=1, method="merge"),
        source_control_pb2.MergeResponse,
    )
    assert response.error.code == "MERGE_CONFLICT"
    assert response.error.retryable is False
    assert response.error.status == 409


def test_merge_blocked_maps_to_call_error_with_status():
    class _Adapter(_StubAdapter):
        def merge(self, *, repo_id: str, number: int, method: str = "merge") -> MergeResult:
            raise MergeBlockedError("not enough approvals", status=423)

    adapter = SourceControlPrimaryAdapterNATS(_Adapter(), SECRET)
    response = _call(
        adapter,
        "merge",
        source_control_pb2.MergeRequest(repo_id="alice/proj", number=1, method="merge"),
        source_control_pb2.MergeResponse,
    )
    assert response.error.code == "MERGE_BLOCKED"
    assert response.error.retryable is False
    assert response.error.status == 423


def test_access_denied_maps_to_call_error_with_status():
    class _Adapter(_StubAdapter):
        def mint_git_token(self, *, user_id: str) -> str:
            raise AccessDeniedError("forbidden", status=403)

    adapter = SourceControlPrimaryAdapterNATS(_Adapter(), SECRET)
    response = _call(
        adapter,
        "mint_git_token",
        source_control_pb2.MintGitTokenRequest(user_id="user-1"),
        source_control_pb2.MintGitTokenResponse,
    )
    assert response.error.code == "ACCESS_DENIED"
    assert response.error.retryable is False
    assert response.error.status == 403


def test_validation_error_maps_to_call_error_with_status():
    class _Adapter(_StubAdapter):
        def ensure_repo(
            self, *, owner: str, name: str, private: bool = True, auto_init: bool = True
        ) -> Repo:
            raise ValidationError("invalid repo name", status=422)

    adapter = SourceControlPrimaryAdapterNATS(_Adapter(), SECRET)
    response = _call(
        adapter,
        "ensure_repo",
        source_control_pb2.EnsureRepoRequest(owner="alice", name="!!bad!!"),
        source_control_pb2.EnsureRepoResponse,
    )
    assert response.error.code == "VALIDATION_ERROR"
    assert response.error.retryable is False
    assert response.error.status == 422


def test_business_error_without_status_leaves_status_unset():
    class _Adapter(_StubAdapter):
        def list_branches(self, *, repo_id: str) -> list[Branch]:
            raise RepoNotFoundError("no such repo")

    adapter = SourceControlPrimaryAdapterNATS(_Adapter(), SECRET)
    response = _call(
        adapter,
        "list_branches",
        source_control_pb2.ListBranchesRequest(repo_id="nope/nope"),
        source_control_pb2.ListBranchesResponse,
    )
    assert response.error.code == "REPO_NOT_FOUND"
    assert not response.error.HasField("status")


def test_unexpected_exception_maps_to_internal_and_does_not_leak_message():
    class _BoomAdapter(_StubAdapter):
        def ensure_user(self, *, external_id: str, email: str, username: str) -> str:
            raise RuntimeError("some sensitive internal detail")

    adapter = SourceControlPrimaryAdapterNATS(_BoomAdapter(), SECRET)
    response = _call(
        adapter,
        "ensure_user",
        source_control_pb2.EnsureUserRequest(external_id="x", email="a@b.c", username="alice"),
        source_control_pb2.EnsureUserResponse,
    )
    assert response.error.code == "INTERNAL"
    assert response.error.retryable is True
    assert "sensitive internal detail" not in response.error.message


# ---------------------------------------------------------------------------
# Lifecycle no-ops.
# ---------------------------------------------------------------------------


def test_stop_without_start_is_a_noop():
    adapter = SourceControlPrimaryAdapterNATS(_StubAdapter(), SECRET)
    asyncio.run(adapter.stop())  # must not raise
