"""NATS RPC client adapter for the source_control kernel domain.

Implements ``ISourceControlAdapter`` by calling out to a remote
``SourceControlPrimaryAdapterNATS`` over NATS request/reply -- see
``naas_abi_core/proto/source_control/v1/source_control.proto`` for the wire
contract and ``naas_abi_core/proto/README.md`` for why it lives there.

Shared connection, token, timeout, and reply handling live in
``naas_abi_core.engine.nats_rpc.NatsRPCClient``. Calls are never replayed
by the transport after failure; a timeout may hide a completed operation.

Stage 1 auth model (see ``naas_abi_core.engine.nats_auth``): a JWT asserting
``service_identity`` is issued once and attached on the ``Nats-Auth-Token``
header of every request, reissued only when it is close to expiry rather
than on every call. ``SourceControlPrimaryAdapterNATS`` must read the token
from that exact header -- both sides read ``AUTH_HEADER`` from
``source_control_nats_contract``, a neutral module neither adapter owns, so
this file never has to import from the primary adapter's module (or vice
versa) just to agree on a header name.
"""

from __future__ import annotations

from collections.abc import Sequence

from naas_abi_core.engine.nats_rpc import NatsRPCClient
from naas_abi_core.proto.common.v1 import common_pb2
from naas_abi_core.proto.source_control.v1 import source_control_pb2
from naas_abi_core.services.source_control.adapters.source_control_nats_contract import (
    AUTH_HEADER,
    SUBJECT_PREFIX,
)
from naas_abi_core.services.source_control.SourceControlPorts import (
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

# ---------------------------------------------------------------------------
# Protobuf <-> DTO conversions -- the client-side mirror of the ones in
# source_control__primary_adapter__NATS.py.
# ---------------------------------------------------------------------------


def _pb_to_repo(pb: source_control_pb2.Repo) -> Repo:
    return Repo(
        id=pb.id,
        name=pb.name,
        owner=pb.owner,
        default_branch=pb.default_branch,
        clone_url=pb.clone_url,
        html_url=pb.html_url,
        description=pb.description,
        private=pb.private,
        empty=pb.empty,
        updated_at=pb.updated_at if pb.HasField("updated_at") else None,
    )


def _pb_to_content_entry(pb: source_control_pb2.ContentEntry) -> ContentEntry:
    return ContentEntry(name=pb.name, path=pb.path, type=pb.type, size=pb.size)


def _pb_to_file_content(pb: source_control_pb2.FileContent) -> FileContent:
    return FileContent(
        path=pb.path,
        name=pb.name,
        size=pb.size,
        text=pb.text if pb.HasField("text") else None,
        is_binary=pb.is_binary,
        data=pb.data if pb.HasField("data") else None,
    )


def _file_write_to_pb(file_write: FileWrite) -> source_control_pb2.FileWrite:
    if isinstance(file_write.content, bytes):
        return source_control_pb2.FileWrite(
            path=file_write.path, binary_content=file_write.content
        )
    return source_control_pb2.FileWrite(
        path=file_write.path, text_content=file_write.content
    )


def _pb_to_commit(pb: source_control_pb2.Commit) -> Commit:
    return Commit(
        sha=pb.sha,
        message=pb.message,
        author=pb.author,
        date=pb.date if pb.HasField("date") else None,
    )


def _pb_to_branch(pb: source_control_pb2.Branch) -> Branch:
    return Branch(name=pb.name, commit_sha=pb.commit_sha, protected=pb.protected)


def _pb_to_diff_file(pb: source_control_pb2.DiffFile) -> DiffFile:
    return DiffFile(
        path=pb.path,
        status=pb.status,
        additions=pb.additions,
        deletions=pb.deletions,
        patch=pb.patch if pb.HasField("patch") else None,
        old_path=pb.old_path if pb.HasField("old_path") else None,
    )


def _pb_to_diff(pb: source_control_pb2.Diff) -> Diff:
    return Diff(files=tuple(_pb_to_diff_file(f) for f in pb.files))


def _pb_to_comment(pb: source_control_pb2.Comment) -> Comment:
    return Comment(
        id=pb.id,
        path=pb.path if pb.HasField("path") else None,
        line=pb.line if pb.HasField("line") else None,
        body=pb.body,
        author=pb.author,
        created_at=pb.created_at if pb.HasField("created_at") else None,
    )


def _pb_to_review(pb: source_control_pb2.Review) -> Review:
    return Review(
        id=pb.id,
        state=pb.state,
        body=pb.body,
        author=pb.author,
        submitted_at=pb.submitted_at if pb.HasField("submitted_at") else None,
    )


def _pb_to_check(pb: source_control_pb2.Check) -> Check:
    return Check(
        name=pb.name,
        status=pb.status,
        conclusion=pb.conclusion if pb.HasField("conclusion") else None,
    )


def _pb_to_proposal(pb: source_control_pb2.Proposal) -> Proposal:
    return Proposal(
        id=pb.id,
        number=pb.number,
        title=pb.title,
        body=pb.body,
        state=pb.state,
        source_branch=pb.source_branch,
        target_branch=pb.target_branch,
        author=pb.author,
        mergeable=pb.mergeable,
        approvals=pb.approvals,
        html_url=pb.html_url,
    )


def _pb_to_workflow_run(pb: source_control_pb2.WorkflowRun) -> WorkflowRun:
    return WorkflowRun(
        id=pb.id,
        name=pb.name,
        workflow_id=pb.workflow_id,
        display_title=pb.display_title,
        run_number=pb.run_number,
        event=pb.event,
        status=pb.status,
        head_branch=pb.head_branch,
        head_sha=pb.head_sha,
        url=pb.url,
        created_at=pb.created_at if pb.HasField("created_at") else None,
        run_started_at=pb.run_started_at if pb.HasField("run_started_at") else None,
        updated_at=pb.updated_at if pb.HasField("updated_at") else None,
    )


def _pb_to_merge_result(pb: source_control_pb2.MergeResult) -> MergeResult:
    return MergeResult(
        merged=pb.merged,
        sha=pb.sha if pb.HasField("sha") else None,
        message=pb.message if pb.HasField("message") else None,
    )


def _raise_for_error(error: common_pb2.CallError) -> None:
    """Raise the exception matching ``error.code``.

    Must stay exactly symmetric with how ``SourceControlPrimaryAdapterNATS``
    encodes errors -- the generic adapter contract test asserts on the real
    exception types, not on the wire code.
    """
    status = error.status if error.HasField("status") else None
    if error.code == "REPO_NOT_FOUND":
        raise RepoNotFoundError(error.message, status=status)
    if error.code == "BRANCH_NOT_FOUND":
        raise BranchNotFoundError(error.message, status=status)
    if error.code == "PROPOSAL_NOT_FOUND":
        raise ProposalNotFoundError(error.message, status=status)
    if error.code == "BRANCH_NAME_CONFLICT":
        raise BranchNameConflictError(error.message, status=status)
    if error.code == "MERGE_CONFLICT":
        raise MergeConflictError(error.message, status=status)
    if error.code == "MERGE_BLOCKED":
        raise MergeBlockedError(error.message, status=status)
    if error.code == "ACCESS_DENIED":
        raise AccessDeniedError(error.message, status=status)
    if error.code == "VALIDATION_ERROR":
        raise ValidationError(error.message, status=status)
    raise RuntimeError(
        f"source_control NATS RPC failed ({error.code}): {error.message}"
    )


class SourceControlSecondaryAdapterNATSClient(NatsRPCClient, ISourceControlAdapter):
    """Calls a remote ``SourceControlPrimaryAdapterNATS`` over NATS RPC."""

    def __init__(
        self,
        nats_url: str,
        jwt_secret: str,
        service_identity: str,
        timeout_seconds: float = 10.0,
    ) -> None:
        super().__init__(
            nats_url,
            jwt_secret,
            service_identity,
            timeout_seconds,
            auth_header=AUTH_HEADER,
        )

    # ------------------------------------------------------------------
    # ISourceControlAdapter.
    # ------------------------------------------------------------------

    def ensure_user(self, *, external_id: str, email: str, username: str) -> str:
        request = source_control_pb2.EnsureUserRequest(
            context=self._context(),
            external_id=external_id,
            email=email,
            username=username,
        )
        response = self._call(
            f"{SUBJECT_PREFIX}.ensure_user",
            request,
            source_control_pb2.EnsureUserResponse,
        )
        if response.HasField("error"):
            _raise_for_error(response.error)
        return response.user_id

    def ensure_repo(
        self, *, owner: str, name: str, private: bool = True, auto_init: bool = True
    ) -> Repo:
        request = source_control_pb2.EnsureRepoRequest(
            context=self._context(),
            owner=owner,
            name=name,
            private=private,
            auto_init=auto_init,
        )
        response = self._call(
            f"{SUBJECT_PREFIX}.ensure_repo",
            request,
            source_control_pb2.EnsureRepoResponse,
        )
        if response.HasField("error"):
            _raise_for_error(response.error)
        return _pb_to_repo(response.repo)

    def list_repos(self) -> list[Repo]:
        request = source_control_pb2.ListReposRequest(context=self._context())
        response = self._call(
            f"{SUBJECT_PREFIX}.list_repos",
            request,
            source_control_pb2.ListReposResponse,
        )
        if response.HasField("error"):
            _raise_for_error(response.error)
        return [_pb_to_repo(r) for r in response.repos.repos]

    def add_collaborator(
        self, *, repo_id: str, username: str, permission: str = "write"
    ) -> None:
        request = source_control_pb2.AddCollaboratorRequest(
            context=self._context(),
            repo_id=repo_id,
            username=username,
            permission=permission,
        )
        response = self._call(
            f"{SUBJECT_PREFIX}.add_collaborator",
            request,
            source_control_pb2.AddCollaboratorResponse,
        )
        if response.HasField("error"):
            _raise_for_error(response.error)

    def list_contents(
        self, *, repo_id: str, path: str = "", ref: str | None = None
    ) -> list[ContentEntry]:
        request = source_control_pb2.ListContentsRequest(
            context=self._context(), repo_id=repo_id, path=path
        )
        if ref is not None:
            request.ref = ref
        response = self._call(
            f"{SUBJECT_PREFIX}.list_contents",
            request,
            source_control_pb2.ListContentsResponse,
        )
        if response.HasField("error"):
            _raise_for_error(response.error)
        return [_pb_to_content_entry(e) for e in response.entries.entries]

    def get_file(
        self, *, repo_id: str, path: str, ref: str | None = None
    ) -> FileContent:
        request = source_control_pb2.GetFileRequest(
            context=self._context(), repo_id=repo_id, path=path
        )
        if ref is not None:
            request.ref = ref
        response = self._call(
            f"{SUBJECT_PREFIX}.get_file", request, source_control_pb2.GetFileResponse
        )
        if response.HasField("error"):
            _raise_for_error(response.error)
        return _pb_to_file_content(response.file)

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
        if isinstance(content, bytes):
            request = source_control_pb2.UpsertFileRequest(
                context=self._context(),
                repo_id=repo_id,
                path=path,
                binary_content=content,
                message=message,
                branch=branch,
            )
        else:
            request = source_control_pb2.UpsertFileRequest(
                context=self._context(),
                repo_id=repo_id,
                path=path,
                text_content=content,
                message=message,
                branch=branch,
            )
        if author_name is not None:
            request.author_name = author_name
        if author_email is not None:
            request.author_email = author_email
        response = self._call(
            f"{SUBJECT_PREFIX}.upsert_file",
            request,
            source_control_pb2.UpsertFileResponse,
        )
        if response.HasField("error"):
            _raise_for_error(response.error)
        return _pb_to_commit(response.commit)

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
        request = source_control_pb2.UpsertFilesRequest(
            context=self._context(),
            repo_id=repo_id,
            files=[_file_write_to_pb(f) for f in files],
            message=message,
            branch=branch,
        )
        if author_name is not None:
            request.author_name = author_name
        if author_email is not None:
            request.author_email = author_email
        response = self._call(
            f"{SUBJECT_PREFIX}.upsert_files",
            request,
            source_control_pb2.UpsertFilesResponse,
        )
        if response.HasField("error"):
            _raise_for_error(response.error)
        return _pb_to_commit(response.commit)

    def list_commits(
        self, *, repo_id: str, ref: str | None = None, limit: int = 20
    ) -> list[Commit]:
        request = source_control_pb2.ListCommitsRequest(
            context=self._context(), repo_id=repo_id, limit=limit
        )
        if ref is not None:
            request.ref = ref
        response = self._call(
            f"{SUBJECT_PREFIX}.list_commits",
            request,
            source_control_pb2.ListCommitsResponse,
        )
        if response.HasField("error"):
            _raise_for_error(response.error)
        return [_pb_to_commit(c) for c in response.commits.commits]

    def list_branches(self, *, repo_id: str) -> list[Branch]:
        request = source_control_pb2.ListBranchesRequest(
            context=self._context(), repo_id=repo_id
        )
        response = self._call(
            f"{SUBJECT_PREFIX}.list_branches",
            request,
            source_control_pb2.ListBranchesResponse,
        )
        if response.HasField("error"):
            _raise_for_error(response.error)
        return [_pb_to_branch(b) for b in response.branches.branches]

    def create_branch(self, *, repo_id: str, name: str, from_ref: str) -> Branch:
        request = source_control_pb2.CreateBranchRequest(
            context=self._context(), repo_id=repo_id, name=name, from_ref=from_ref
        )
        response = self._call(
            f"{SUBJECT_PREFIX}.create_branch",
            request,
            source_control_pb2.CreateBranchResponse,
        )
        if response.HasField("error"):
            _raise_for_error(response.error)
        return _pb_to_branch(response.branch)

    def delete_branch(self, *, repo_id: str, name: str) -> None:
        request = source_control_pb2.DeleteBranchRequest(
            context=self._context(), repo_id=repo_id, name=name
        )
        response = self._call(
            f"{SUBJECT_PREFIX}.delete_branch",
            request,
            source_control_pb2.DeleteBranchResponse,
        )
        if response.HasField("error"):
            _raise_for_error(response.error)

    def get_diff(self, *, repo_id: str, base: str, head: str) -> Diff:
        request = source_control_pb2.GetDiffRequest(
            context=self._context(), repo_id=repo_id, base=base, head=head
        )
        response = self._call(
            f"{SUBJECT_PREFIX}.get_diff", request, source_control_pb2.GetDiffResponse
        )
        if response.HasField("error"):
            _raise_for_error(response.error)
        return _pb_to_diff(response.diff)

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
        request = source_control_pb2.CreateProposalRequest(
            context=self._context(),
            repo_id=repo_id,
            title=title,
            body=body,
            source_branch=source_branch,
            target_branch=target_branch,
            reviewers=reviewers or [],
        )
        response = self._call(
            f"{SUBJECT_PREFIX}.create_proposal",
            request,
            source_control_pb2.CreateProposalResponse,
        )
        if response.HasField("error"):
            _raise_for_error(response.error)
        return _pb_to_proposal(response.proposal)

    def list_proposals(self, *, repo_id: str, state: str = "open") -> list[Proposal]:
        request = source_control_pb2.ListProposalsRequest(
            context=self._context(), repo_id=repo_id, state=state
        )
        response = self._call(
            f"{SUBJECT_PREFIX}.list_proposals",
            request,
            source_control_pb2.ListProposalsResponse,
        )
        if response.HasField("error"):
            _raise_for_error(response.error)
        return [_pb_to_proposal(p) for p in response.proposals.proposals]

    def get_proposal(self, *, repo_id: str, number: int) -> Proposal:
        request = source_control_pb2.GetProposalRequest(
            context=self._context(), repo_id=repo_id, number=number
        )
        response = self._call(
            f"{SUBJECT_PREFIX}.get_proposal",
            request,
            source_control_pb2.GetProposalResponse,
        )
        if response.HasField("error"):
            _raise_for_error(response.error)
        return _pb_to_proposal(response.proposal)

    def get_proposal_diff(self, *, repo_id: str, number: int) -> Diff:
        request = source_control_pb2.GetProposalDiffRequest(
            context=self._context(), repo_id=repo_id, number=number
        )
        response = self._call(
            f"{SUBJECT_PREFIX}.get_proposal_diff",
            request,
            source_control_pb2.GetProposalDiffResponse,
        )
        if response.HasField("error"):
            _raise_for_error(response.error)
        return _pb_to_diff(response.diff)

    def list_proposal_commits(self, *, repo_id: str, number: int) -> list[Commit]:
        request = source_control_pb2.ListProposalCommitsRequest(
            context=self._context(), repo_id=repo_id, number=number
        )
        response = self._call(
            f"{SUBJECT_PREFIX}.list_proposal_commits",
            request,
            source_control_pb2.ListProposalCommitsResponse,
        )
        if response.HasField("error"):
            _raise_for_error(response.error)
        return [_pb_to_commit(c) for c in response.commits.commits]

    def list_comments(self, *, repo_id: str, number: int) -> list[Comment]:
        request = source_control_pb2.ListCommentsRequest(
            context=self._context(), repo_id=repo_id, number=number
        )
        response = self._call(
            f"{SUBJECT_PREFIX}.list_comments",
            request,
            source_control_pb2.ListCommentsResponse,
        )
        if response.HasField("error"):
            _raise_for_error(response.error)
        return [_pb_to_comment(c) for c in response.comments.comments]

    def list_reviews(self, *, repo_id: str, number: int) -> list[Review]:
        request = source_control_pb2.ListReviewsRequest(
            context=self._context(), repo_id=repo_id, number=number
        )
        response = self._call(
            f"{SUBJECT_PREFIX}.list_reviews",
            request,
            source_control_pb2.ListReviewsResponse,
        )
        if response.HasField("error"):
            _raise_for_error(response.error)
        return [_pb_to_review(r) for r in response.reviews.reviews]

    def add_comment(
        self,
        *,
        repo_id: str,
        number: int,
        body: str,
        path: str | None = None,
        line: int | None = None,
    ) -> Comment:
        request = source_control_pb2.AddCommentRequest(
            context=self._context(), repo_id=repo_id, number=number, body=body
        )
        if path is not None:
            request.path = path
        if line is not None:
            request.line = line
        response = self._call(
            f"{SUBJECT_PREFIX}.add_comment",
            request,
            source_control_pb2.AddCommentResponse,
        )
        if response.HasField("error"):
            _raise_for_error(response.error)
        return _pb_to_comment(response.comment)

    def submit_review(
        self, *, repo_id: str, number: int, event: str, body: str = ""
    ) -> Review:
        request = source_control_pb2.SubmitReviewRequest(
            context=self._context(),
            repo_id=repo_id,
            number=number,
            event=event,
            body=body,
        )
        response = self._call(
            f"{SUBJECT_PREFIX}.submit_review",
            request,
            source_control_pb2.SubmitReviewResponse,
        )
        if response.HasField("error"):
            _raise_for_error(response.error)
        return _pb_to_review(response.review)

    def list_checks(self, *, repo_id: str, number: int) -> list[Check]:
        request = source_control_pb2.ListChecksRequest(
            context=self._context(), repo_id=repo_id, number=number
        )
        response = self._call(
            f"{SUBJECT_PREFIX}.list_checks",
            request,
            source_control_pb2.ListChecksResponse,
        )
        if response.HasField("error"):
            _raise_for_error(response.error)
        return [_pb_to_check(c) for c in response.checks.checks]

    def set_branch_protection(
        self,
        *,
        repo_id: str,
        branch: str,
        required_approvals: int,
        required_checks: list[str],
    ) -> None:
        request = source_control_pb2.SetBranchProtectionRequest(
            context=self._context(),
            repo_id=repo_id,
            branch=branch,
            required_approvals=required_approvals,
            required_checks=list(required_checks),
        )
        response = self._call(
            f"{SUBJECT_PREFIX}.set_branch_protection",
            request,
            source_control_pb2.SetBranchProtectionResponse,
        )
        if response.HasField("error"):
            _raise_for_error(response.error)

    def merge(self, *, repo_id: str, number: int, method: str = "merge") -> MergeResult:
        request = source_control_pb2.MergeRequest(
            context=self._context(), repo_id=repo_id, number=number, method=method
        )
        response = self._call(
            f"{SUBJECT_PREFIX}.merge", request, source_control_pb2.MergeResponse
        )
        if response.HasField("error"):
            _raise_for_error(response.error)
        return _pb_to_merge_result(response.merge_result)

    def list_workflow_runs(self, *, repo_id: str, limit: int = 20) -> list[WorkflowRun]:
        request = source_control_pb2.ListWorkflowRunsRequest(
            context=self._context(), repo_id=repo_id, limit=limit
        )
        response = self._call(
            f"{SUBJECT_PREFIX}.list_workflow_runs",
            request,
            source_control_pb2.ListWorkflowRunsResponse,
        )
        if response.HasField("error"):
            _raise_for_error(response.error)
        return [_pb_to_workflow_run(r) for r in response.workflow_runs.workflow_runs]

    def mint_git_token(self, *, user_id: str) -> str:
        request = source_control_pb2.MintGitTokenRequest(
            context=self._context(), user_id=user_id
        )
        response = self._call(
            f"{SUBJECT_PREFIX}.mint_git_token",
            request,
            source_control_pb2.MintGitTokenResponse,
        )
        if response.HasField("error"):
            _raise_for_error(response.error)
        return response.token
