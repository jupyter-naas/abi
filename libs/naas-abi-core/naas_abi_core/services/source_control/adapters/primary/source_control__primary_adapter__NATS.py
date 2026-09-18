"""NATS RPC primary adapter for the source_control kernel domain.

Exposes a real ``ISourceControlAdapter`` -- or, in practice, the real
``SourceControlService`` domain object -- as a NATS micro-service (see
``naas_abi_core/proto/source_control/v1/source_control.proto`` for the wire
contract and ``naas_abi_core/proto/README.md`` for why it lives there). This
is the server side; the matching client is
``SourceControlSecondaryAdapterNATSClient``.

Stage 1 auth model (see ``naas_abi_core.engine.nats_auth``): one shared
secret, one claim -- which known first-party process holds the token. Every
incoming request must carry a valid token in the ``Nats-Auth-Token`` header
(``AUTH_HEADER``, imported from ``source_control_nats_contract`` below --
that's a neutral module neither adapter owns, so this file and the client's
don't depend on each other; see that module's docstring for why).

This v1 contract has no streaming/callback members at all -- every
``ISourceControlAdapter`` method is plain request/response, so all 27 get an
endpoint here.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TypeVar

import nats
import nats.micro
from google.protobuf.message import Message
from naas_abi_core import logger
from naas_abi_core.engine.nats_auth import (
    InvalidServiceTokenError,
    verify_service_token,
)
from naas_abi_core.proto.common.v1 import common_pb2
from naas_abi_core.proto.source_control.v1 import source_control_pb2
from naas_abi_core.services.source_control.adapters.source_control_nats_contract import (
    AUTH_HEADER,
    SERVICE_NAME,
    SERVICE_VERSION,
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
from naas_abi_core.services.source_control.SourceControlService import (
    SourceControlService,
)
from nats.micro.request import Request
from nats.micro.service import Service

__all__ = [
    "AUTH_HEADER",
    "SERVICE_NAME",
    "SERVICE_VERSION",
    "SUBJECT_PREFIX",
    "SourceControlPrimaryAdapterNATS",
]

_RequestT = TypeVar("_RequestT", bound=Message)
_ResponseT = TypeVar("_ResponseT", bound=Message)


# ---------------------------------------------------------------------------
# DTO <-> Protobuf conversions -- mirror SourceControlPorts.py's dataclasses
# field-for-field. Optional fields are left unset rather than sent as empty
# when the adapter didn't populate them, so HasField on the client side
# reflects "the adapter didn't know this" rather than "this really is empty".
# ---------------------------------------------------------------------------


def _repo_to_pb(repo: Repo) -> source_control_pb2.Repo:
    pb = source_control_pb2.Repo(
        id=repo.id,
        name=repo.name,
        owner=repo.owner,
        default_branch=repo.default_branch,
        clone_url=repo.clone_url,
        html_url=repo.html_url,
        description=repo.description,
        private=repo.private,
        empty=repo.empty,
    )
    if repo.updated_at is not None:
        pb.updated_at = repo.updated_at
    return pb


def _content_entry_to_pb(entry: ContentEntry) -> source_control_pb2.ContentEntry:
    return source_control_pb2.ContentEntry(
        name=entry.name, path=entry.path, type=entry.type, size=entry.size
    )


def _file_content_to_pb(file_content: FileContent) -> source_control_pb2.FileContent:
    pb = source_control_pb2.FileContent(
        path=file_content.path,
        name=file_content.name,
        size=file_content.size,
        is_binary=file_content.is_binary,
    )
    if file_content.text is not None:
        pb.text = file_content.text
    if file_content.data is not None:
        pb.data = file_content.data
    return pb


def _file_write_from_pb(pb: source_control_pb2.FileWrite) -> FileWrite:
    content: str | bytes = (
        pb.binary_content if pb.WhichOneof("content") == "binary_content" else pb.text_content
    )
    return FileWrite(path=pb.path, content=content)


def _commit_to_pb(commit: Commit) -> source_control_pb2.Commit:
    pb = source_control_pb2.Commit(
        sha=commit.sha, message=commit.message, author=commit.author
    )
    if commit.date is not None:
        pb.date = commit.date
    return pb


def _branch_to_pb(branch: Branch) -> source_control_pb2.Branch:
    return source_control_pb2.Branch(
        name=branch.name, commit_sha=branch.commit_sha, protected=branch.protected
    )


def _diff_file_to_pb(diff_file: DiffFile) -> source_control_pb2.DiffFile:
    pb = source_control_pb2.DiffFile(
        path=diff_file.path,
        status=diff_file.status,
        additions=diff_file.additions,
        deletions=diff_file.deletions,
    )
    if diff_file.patch is not None:
        pb.patch = diff_file.patch
    if diff_file.old_path is not None:
        pb.old_path = diff_file.old_path
    return pb


def _diff_to_pb(diff: Diff) -> source_control_pb2.Diff:
    return source_control_pb2.Diff(files=[_diff_file_to_pb(f) for f in diff.files])


def _comment_to_pb(comment: Comment) -> source_control_pb2.Comment:
    pb = source_control_pb2.Comment(
        id=comment.id, body=comment.body, author=comment.author
    )
    if comment.path is not None:
        pb.path = comment.path
    if comment.line is not None:
        pb.line = comment.line
    if comment.created_at is not None:
        pb.created_at = comment.created_at
    return pb


def _review_to_pb(review: Review) -> source_control_pb2.Review:
    pb = source_control_pb2.Review(
        id=review.id, state=review.state, body=review.body, author=review.author
    )
    if review.submitted_at is not None:
        pb.submitted_at = review.submitted_at
    return pb


def _check_to_pb(check: Check) -> source_control_pb2.Check:
    pb = source_control_pb2.Check(name=check.name, status=check.status)
    if check.conclusion is not None:
        pb.conclusion = check.conclusion
    return pb


def _proposal_to_pb(proposal: Proposal) -> source_control_pb2.Proposal:
    return source_control_pb2.Proposal(
        id=proposal.id,
        number=proposal.number,
        title=proposal.title,
        body=proposal.body,
        state=proposal.state,
        source_branch=proposal.source_branch,
        target_branch=proposal.target_branch,
        author=proposal.author,
        mergeable=proposal.mergeable,
        approvals=proposal.approvals,
        html_url=proposal.html_url,
    )


def _workflow_run_to_pb(run: WorkflowRun) -> source_control_pb2.WorkflowRun:
    pb = source_control_pb2.WorkflowRun(
        id=run.id,
        name=run.name,
        workflow_id=run.workflow_id,
        display_title=run.display_title,
        run_number=run.run_number,
        event=run.event,
        status=run.status,
        head_branch=run.head_branch,
        head_sha=run.head_sha,
        url=run.url,
    )
    if run.created_at is not None:
        pb.created_at = run.created_at
    if run.run_started_at is not None:
        pb.run_started_at = run.run_started_at
    if run.updated_at is not None:
        pb.updated_at = run.updated_at
    return pb


def _merge_result_to_pb(result: MergeResult) -> source_control_pb2.MergeResult:
    pb = source_control_pb2.MergeResult(merged=result.merged)
    if result.sha is not None:
        pb.sha = result.sha
    if result.message is not None:
        pb.message = result.message
    return pb


class SourceControlPrimaryAdapterNATS:
    """Serves source_control over NATS RPC (request/reply).

    Wraps a real adapter *or* the domain service and registers one NATS
    micro-service endpoint per method (all 27 -- this port has no
    streaming/callback members). Each endpoint authenticates the caller via
    ``Nats-Auth-Token`` before doing anything else, then decodes the
    Protobuf request, calls straight through to the wrapped object, and
    encodes a Protobuf response. Errors -- auth failures, known domain
    exceptions, anything unexpected -- are always reported as a normal
    response carrying a populated ``CallError``, never as a crashed handler
    or a raw NATS-level error.

    Accepts either an ``ISourceControlAdapter`` (a bare secondary adapter,
    e.g. in tests) or a ``SourceControlService`` (the real engine-loaded
    domain service) -- deliberately, not for convenience: wrapping the raw
    adapter instead of the domain service would silently skip
    ``SourceControlService``'s event publishing
    (``ProposalOpened``/``ReviewSubmitted``/``ProposalMerged``/
    ``ProposalMergeBlocked``) for every remote caller, which would only
    diverge from in-process behaviour, not match it. ``EngineNATSLoader``
    always passes the domain service.
    """

    def __init__(
        self,
        adapter: ISourceControlAdapter | SourceControlService,
        jwt_secret: str,
    ) -> None:
        self._adapter = adapter
        self._jwt_secret = jwt_secret
        self._service: Service | None = None

    async def start(self, nc: nats.NATS) -> None:
        """Register the ``source_control`` NATS service on ``nc``.

        ``nc`` must already be connected -- this adapter never manages the
        connection lifecycle itself, only the service/endpoints layered on
        top of it. Calling this more than once is a no-op.
        """
        if self._service is not None:
            return

        service = await nats.micro.add_service(
            nc,
            name=SERVICE_NAME,
            version=SERVICE_VERSION,
            description="ABI kernel source_control domain, exposed over NATS RPC (v1).",
        )
        await service.add_endpoint(
            name="ensure_user",
            subject=f"{SUBJECT_PREFIX}.ensure_user",
            handler=self._handle_ensure_user,
        )
        await service.add_endpoint(
            name="ensure_repo",
            subject=f"{SUBJECT_PREFIX}.ensure_repo",
            handler=self._handle_ensure_repo,
        )
        await service.add_endpoint(
            name="list_repos",
            subject=f"{SUBJECT_PREFIX}.list_repos",
            handler=self._handle_list_repos,
        )
        await service.add_endpoint(
            name="add_collaborator",
            subject=f"{SUBJECT_PREFIX}.add_collaborator",
            handler=self._handle_add_collaborator,
        )
        await service.add_endpoint(
            name="list_contents",
            subject=f"{SUBJECT_PREFIX}.list_contents",
            handler=self._handle_list_contents,
        )
        await service.add_endpoint(
            name="get_file",
            subject=f"{SUBJECT_PREFIX}.get_file",
            handler=self._handle_get_file,
        )
        await service.add_endpoint(
            name="upsert_file",
            subject=f"{SUBJECT_PREFIX}.upsert_file",
            handler=self._handle_upsert_file,
        )
        await service.add_endpoint(
            name="upsert_files",
            subject=f"{SUBJECT_PREFIX}.upsert_files",
            handler=self._handle_upsert_files,
        )
        await service.add_endpoint(
            name="list_commits",
            subject=f"{SUBJECT_PREFIX}.list_commits",
            handler=self._handle_list_commits,
        )
        await service.add_endpoint(
            name="list_branches",
            subject=f"{SUBJECT_PREFIX}.list_branches",
            handler=self._handle_list_branches,
        )
        await service.add_endpoint(
            name="create_branch",
            subject=f"{SUBJECT_PREFIX}.create_branch",
            handler=self._handle_create_branch,
        )
        await service.add_endpoint(
            name="delete_branch",
            subject=f"{SUBJECT_PREFIX}.delete_branch",
            handler=self._handle_delete_branch,
        )
        await service.add_endpoint(
            name="get_diff",
            subject=f"{SUBJECT_PREFIX}.get_diff",
            handler=self._handle_get_diff,
        )
        await service.add_endpoint(
            name="create_proposal",
            subject=f"{SUBJECT_PREFIX}.create_proposal",
            handler=self._handle_create_proposal,
        )
        await service.add_endpoint(
            name="list_proposals",
            subject=f"{SUBJECT_PREFIX}.list_proposals",
            handler=self._handle_list_proposals,
        )
        await service.add_endpoint(
            name="get_proposal",
            subject=f"{SUBJECT_PREFIX}.get_proposal",
            handler=self._handle_get_proposal,
        )
        await service.add_endpoint(
            name="get_proposal_diff",
            subject=f"{SUBJECT_PREFIX}.get_proposal_diff",
            handler=self._handle_get_proposal_diff,
        )
        await service.add_endpoint(
            name="list_proposal_commits",
            subject=f"{SUBJECT_PREFIX}.list_proposal_commits",
            handler=self._handle_list_proposal_commits,
        )
        await service.add_endpoint(
            name="list_comments",
            subject=f"{SUBJECT_PREFIX}.list_comments",
            handler=self._handle_list_comments,
        )
        await service.add_endpoint(
            name="list_reviews",
            subject=f"{SUBJECT_PREFIX}.list_reviews",
            handler=self._handle_list_reviews,
        )
        await service.add_endpoint(
            name="add_comment",
            subject=f"{SUBJECT_PREFIX}.add_comment",
            handler=self._handle_add_comment,
        )
        await service.add_endpoint(
            name="submit_review",
            subject=f"{SUBJECT_PREFIX}.submit_review",
            handler=self._handle_submit_review,
        )
        await service.add_endpoint(
            name="list_checks",
            subject=f"{SUBJECT_PREFIX}.list_checks",
            handler=self._handle_list_checks,
        )
        await service.add_endpoint(
            name="set_branch_protection",
            subject=f"{SUBJECT_PREFIX}.set_branch_protection",
            handler=self._handle_set_branch_protection,
        )
        await service.add_endpoint(
            name="merge",
            subject=f"{SUBJECT_PREFIX}.merge",
            handler=self._handle_merge,
        )
        await service.add_endpoint(
            name="list_workflow_runs",
            subject=f"{SUBJECT_PREFIX}.list_workflow_runs",
            handler=self._handle_list_workflow_runs,
        )
        await service.add_endpoint(
            name="mint_git_token",
            subject=f"{SUBJECT_PREFIX}.mint_git_token",
            handler=self._handle_mint_git_token,
        )
        self._service = service

    async def stop(self) -> None:
        """Deregister the service, draining its subscriptions."""
        service = self._service
        self._service = None
        if service is not None:
            await service.stop()

    # ------------------------------------------------------------------
    # Shared request handling: auth, decode, dispatch, encode.
    # ------------------------------------------------------------------

    async def _handle(
        self,
        request: Request,
        request_cls: type[_RequestT],
        response_cls: Callable[..., _ResponseT],
        call: Callable[[_RequestT], _ResponseT],
    ) -> None:
        if not self._is_authenticated(request):
            await self._respond_error(
                request,
                response_cls,
                "UNAUTHENTICATED",
                "missing or invalid auth token",
                retryable=False,
            )
            return

        parsed_request = request_cls()
        parsed_request.ParseFromString(request.data)

        try:
            response = call(parsed_request)
        except RepoNotFoundError as exc:
            await self._respond_error(
                request,
                response_cls,
                "REPO_NOT_FOUND",
                str(exc),
                retryable=False,
                status=exc.status,
            )
            return
        except BranchNotFoundError as exc:
            await self._respond_error(
                request,
                response_cls,
                "BRANCH_NOT_FOUND",
                str(exc),
                retryable=False,
                status=exc.status,
            )
            return
        except ProposalNotFoundError as exc:
            await self._respond_error(
                request,
                response_cls,
                "PROPOSAL_NOT_FOUND",
                str(exc),
                retryable=False,
                status=exc.status,
            )
            return
        except BranchNameConflictError as exc:
            await self._respond_error(
                request,
                response_cls,
                "BRANCH_NAME_CONFLICT",
                str(exc),
                retryable=False,
                status=exc.status,
            )
            return
        except MergeConflictError as exc:
            await self._respond_error(
                request,
                response_cls,
                "MERGE_CONFLICT",
                str(exc),
                retryable=False,
                status=exc.status,
            )
            return
        except MergeBlockedError as exc:
            await self._respond_error(
                request,
                response_cls,
                "MERGE_BLOCKED",
                str(exc),
                retryable=False,
                status=exc.status,
            )
            return
        except AccessDeniedError as exc:
            await self._respond_error(
                request,
                response_cls,
                "ACCESS_DENIED",
                str(exc),
                retryable=False,
                status=exc.status,
            )
            return
        except ValidationError as exc:
            await self._respond_error(
                request,
                response_cls,
                "VALIDATION_ERROR",
                str(exc),
                retryable=False,
                status=exc.status,
            )
            return
        except Exception:  # noqa: BLE001 - a handler must never crash the service
            logger.opt(exception=True).error(
                f"SourceControlPrimaryAdapterNATS: unexpected error handling {request.subject!r}"
            )
            await self._respond_error(
                request, response_cls, "INTERNAL", "internal error", retryable=True
            )
            return

        await request.respond(response.SerializeToString())

    def _is_authenticated(self, request: Request) -> bool:
        headers = request.headers or {}
        token = headers.get(AUTH_HEADER)
        if not token:
            return False
        try:
            verify_service_token(token, self._jwt_secret)
        except InvalidServiceTokenError:
            return False
        return True

    @staticmethod
    async def _respond_error(
        request: Request,
        response_cls: Callable[..., Message],
        code: str,
        message: str,
        *,
        retryable: bool,
        status: int | None = None,
    ) -> None:
        error = common_pb2.CallError(code=code, message=message, retryable=retryable)
        if status is not None:
            error.status = status
        response = response_cls(error=error)
        await request.respond(response.SerializeToString())

    # ------------------------------------------------------------------
    # Endpoint handlers -- one per ISourceControlAdapter method.
    # ------------------------------------------------------------------

    async def _handle_ensure_user(self, request: Request) -> None:
        await self._handle(
            request,
            source_control_pb2.EnsureUserRequest,
            source_control_pb2.EnsureUserResponse,
            self._call_ensure_user,
        )

    def _call_ensure_user(
        self, req: source_control_pb2.EnsureUserRequest
    ) -> source_control_pb2.EnsureUserResponse:
        user_id = self._adapter.ensure_user(
            external_id=req.external_id, email=req.email, username=req.username
        )
        return source_control_pb2.EnsureUserResponse(user_id=user_id)

    async def _handle_ensure_repo(self, request: Request) -> None:
        await self._handle(
            request,
            source_control_pb2.EnsureRepoRequest,
            source_control_pb2.EnsureRepoResponse,
            self._call_ensure_repo,
        )

    def _call_ensure_repo(
        self, req: source_control_pb2.EnsureRepoRequest
    ) -> source_control_pb2.EnsureRepoResponse:
        repo = self._adapter.ensure_repo(
            owner=req.owner, name=req.name, private=req.private, auto_init=req.auto_init
        )
        return source_control_pb2.EnsureRepoResponse(repo=_repo_to_pb(repo))

    async def _handle_list_repos(self, request: Request) -> None:
        await self._handle(
            request,
            source_control_pb2.ListReposRequest,
            source_control_pb2.ListReposResponse,
            self._call_list_repos,
        )

    def _call_list_repos(
        self, req: source_control_pb2.ListReposRequest
    ) -> source_control_pb2.ListReposResponse:
        repos = self._adapter.list_repos()
        return source_control_pb2.ListReposResponse(
            repos=source_control_pb2.Repos(repos=[_repo_to_pb(r) for r in repos])
        )

    async def _handle_add_collaborator(self, request: Request) -> None:
        await self._handle(
            request,
            source_control_pb2.AddCollaboratorRequest,
            source_control_pb2.AddCollaboratorResponse,
            self._call_add_collaborator,
        )

    def _call_add_collaborator(
        self, req: source_control_pb2.AddCollaboratorRequest
    ) -> source_control_pb2.AddCollaboratorResponse:
        self._adapter.add_collaborator(
            repo_id=req.repo_id, username=req.username, permission=req.permission
        )
        return source_control_pb2.AddCollaboratorResponse()

    async def _handle_list_contents(self, request: Request) -> None:
        await self._handle(
            request,
            source_control_pb2.ListContentsRequest,
            source_control_pb2.ListContentsResponse,
            self._call_list_contents,
        )

    def _call_list_contents(
        self, req: source_control_pb2.ListContentsRequest
    ) -> source_control_pb2.ListContentsResponse:
        entries = self._adapter.list_contents(
            repo_id=req.repo_id,
            path=req.path,
            ref=req.ref if req.HasField("ref") else None,
        )
        return source_control_pb2.ListContentsResponse(
            entries=source_control_pb2.ContentEntries(
                entries=[_content_entry_to_pb(e) for e in entries]
            )
        )

    async def _handle_get_file(self, request: Request) -> None:
        await self._handle(
            request,
            source_control_pb2.GetFileRequest,
            source_control_pb2.GetFileResponse,
            self._call_get_file,
        )

    def _call_get_file(
        self, req: source_control_pb2.GetFileRequest
    ) -> source_control_pb2.GetFileResponse:
        file_content = self._adapter.get_file(
            repo_id=req.repo_id,
            path=req.path,
            ref=req.ref if req.HasField("ref") else None,
        )
        return source_control_pb2.GetFileResponse(file=_file_content_to_pb(file_content))

    async def _handle_upsert_file(self, request: Request) -> None:
        await self._handle(
            request,
            source_control_pb2.UpsertFileRequest,
            source_control_pb2.UpsertFileResponse,
            self._call_upsert_file,
        )

    def _call_upsert_file(
        self, req: source_control_pb2.UpsertFileRequest
    ) -> source_control_pb2.UpsertFileResponse:
        content: str | bytes = (
            req.binary_content
            if req.WhichOneof("content") == "binary_content"
            else req.text_content
        )
        commit = self._adapter.upsert_file(
            repo_id=req.repo_id,
            path=req.path,
            content=content,
            message=req.message,
            branch=req.branch,
            author_name=req.author_name if req.HasField("author_name") else None,
            author_email=req.author_email if req.HasField("author_email") else None,
        )
        return source_control_pb2.UpsertFileResponse(commit=_commit_to_pb(commit))

    async def _handle_upsert_files(self, request: Request) -> None:
        await self._handle(
            request,
            source_control_pb2.UpsertFilesRequest,
            source_control_pb2.UpsertFilesResponse,
            self._call_upsert_files,
        )

    def _call_upsert_files(
        self, req: source_control_pb2.UpsertFilesRequest
    ) -> source_control_pb2.UpsertFilesResponse:
        files = [_file_write_from_pb(f) for f in req.files]
        commit = self._adapter.upsert_files(
            repo_id=req.repo_id,
            files=files,
            message=req.message,
            branch=req.branch,
            author_name=req.author_name if req.HasField("author_name") else None,
            author_email=req.author_email if req.HasField("author_email") else None,
        )
        return source_control_pb2.UpsertFilesResponse(commit=_commit_to_pb(commit))

    async def _handle_list_commits(self, request: Request) -> None:
        await self._handle(
            request,
            source_control_pb2.ListCommitsRequest,
            source_control_pb2.ListCommitsResponse,
            self._call_list_commits,
        )

    def _call_list_commits(
        self, req: source_control_pb2.ListCommitsRequest
    ) -> source_control_pb2.ListCommitsResponse:
        commits = self._adapter.list_commits(
            repo_id=req.repo_id,
            ref=req.ref if req.HasField("ref") else None,
            limit=req.limit,
        )
        return source_control_pb2.ListCommitsResponse(
            commits=source_control_pb2.Commits(commits=[_commit_to_pb(c) for c in commits])
        )

    async def _handle_list_branches(self, request: Request) -> None:
        await self._handle(
            request,
            source_control_pb2.ListBranchesRequest,
            source_control_pb2.ListBranchesResponse,
            self._call_list_branches,
        )

    def _call_list_branches(
        self, req: source_control_pb2.ListBranchesRequest
    ) -> source_control_pb2.ListBranchesResponse:
        branches = self._adapter.list_branches(repo_id=req.repo_id)
        return source_control_pb2.ListBranchesResponse(
            branches=source_control_pb2.Branches(
                branches=[_branch_to_pb(b) for b in branches]
            )
        )

    async def _handle_create_branch(self, request: Request) -> None:
        await self._handle(
            request,
            source_control_pb2.CreateBranchRequest,
            source_control_pb2.CreateBranchResponse,
            self._call_create_branch,
        )

    def _call_create_branch(
        self, req: source_control_pb2.CreateBranchRequest
    ) -> source_control_pb2.CreateBranchResponse:
        branch = self._adapter.create_branch(
            repo_id=req.repo_id, name=req.name, from_ref=req.from_ref
        )
        return source_control_pb2.CreateBranchResponse(branch=_branch_to_pb(branch))

    async def _handle_delete_branch(self, request: Request) -> None:
        await self._handle(
            request,
            source_control_pb2.DeleteBranchRequest,
            source_control_pb2.DeleteBranchResponse,
            self._call_delete_branch,
        )

    def _call_delete_branch(
        self, req: source_control_pb2.DeleteBranchRequest
    ) -> source_control_pb2.DeleteBranchResponse:
        self._adapter.delete_branch(repo_id=req.repo_id, name=req.name)
        return source_control_pb2.DeleteBranchResponse()

    async def _handle_get_diff(self, request: Request) -> None:
        await self._handle(
            request,
            source_control_pb2.GetDiffRequest,
            source_control_pb2.GetDiffResponse,
            self._call_get_diff,
        )

    def _call_get_diff(
        self, req: source_control_pb2.GetDiffRequest
    ) -> source_control_pb2.GetDiffResponse:
        diff = self._adapter.get_diff(repo_id=req.repo_id, base=req.base, head=req.head)
        return source_control_pb2.GetDiffResponse(diff=_diff_to_pb(diff))

    async def _handle_create_proposal(self, request: Request) -> None:
        await self._handle(
            request,
            source_control_pb2.CreateProposalRequest,
            source_control_pb2.CreateProposalResponse,
            self._call_create_proposal,
        )

    def _call_create_proposal(
        self, req: source_control_pb2.CreateProposalRequest
    ) -> source_control_pb2.CreateProposalResponse:
        proposal = self._adapter.create_proposal(
            repo_id=req.repo_id,
            title=req.title,
            body=req.body,
            source_branch=req.source_branch,
            target_branch=req.target_branch,
            reviewers=list(req.reviewers) or None,
        )
        return source_control_pb2.CreateProposalResponse(proposal=_proposal_to_pb(proposal))

    async def _handle_list_proposals(self, request: Request) -> None:
        await self._handle(
            request,
            source_control_pb2.ListProposalsRequest,
            source_control_pb2.ListProposalsResponse,
            self._call_list_proposals,
        )

    def _call_list_proposals(
        self, req: source_control_pb2.ListProposalsRequest
    ) -> source_control_pb2.ListProposalsResponse:
        proposals = self._adapter.list_proposals(repo_id=req.repo_id, state=req.state)
        return source_control_pb2.ListProposalsResponse(
            proposals=source_control_pb2.Proposals(
                proposals=[_proposal_to_pb(p) for p in proposals]
            )
        )

    async def _handle_get_proposal(self, request: Request) -> None:
        await self._handle(
            request,
            source_control_pb2.GetProposalRequest,
            source_control_pb2.GetProposalResponse,
            self._call_get_proposal,
        )

    def _call_get_proposal(
        self, req: source_control_pb2.GetProposalRequest
    ) -> source_control_pb2.GetProposalResponse:
        proposal = self._adapter.get_proposal(repo_id=req.repo_id, number=req.number)
        return source_control_pb2.GetProposalResponse(proposal=_proposal_to_pb(proposal))

    async def _handle_get_proposal_diff(self, request: Request) -> None:
        await self._handle(
            request,
            source_control_pb2.GetProposalDiffRequest,
            source_control_pb2.GetProposalDiffResponse,
            self._call_get_proposal_diff,
        )

    def _call_get_proposal_diff(
        self, req: source_control_pb2.GetProposalDiffRequest
    ) -> source_control_pb2.GetProposalDiffResponse:
        diff = self._adapter.get_proposal_diff(repo_id=req.repo_id, number=req.number)
        return source_control_pb2.GetProposalDiffResponse(diff=_diff_to_pb(diff))

    async def _handle_list_proposal_commits(self, request: Request) -> None:
        await self._handle(
            request,
            source_control_pb2.ListProposalCommitsRequest,
            source_control_pb2.ListProposalCommitsResponse,
            self._call_list_proposal_commits,
        )

    def _call_list_proposal_commits(
        self, req: source_control_pb2.ListProposalCommitsRequest
    ) -> source_control_pb2.ListProposalCommitsResponse:
        commits = self._adapter.list_proposal_commits(
            repo_id=req.repo_id, number=req.number
        )
        return source_control_pb2.ListProposalCommitsResponse(
            commits=source_control_pb2.Commits(commits=[_commit_to_pb(c) for c in commits])
        )

    async def _handle_list_comments(self, request: Request) -> None:
        await self._handle(
            request,
            source_control_pb2.ListCommentsRequest,
            source_control_pb2.ListCommentsResponse,
            self._call_list_comments,
        )

    def _call_list_comments(
        self, req: source_control_pb2.ListCommentsRequest
    ) -> source_control_pb2.ListCommentsResponse:
        comments = self._adapter.list_comments(repo_id=req.repo_id, number=req.number)
        return source_control_pb2.ListCommentsResponse(
            comments=source_control_pb2.Comments(
                comments=[_comment_to_pb(c) for c in comments]
            )
        )

    async def _handle_list_reviews(self, request: Request) -> None:
        await self._handle(
            request,
            source_control_pb2.ListReviewsRequest,
            source_control_pb2.ListReviewsResponse,
            self._call_list_reviews,
        )

    def _call_list_reviews(
        self, req: source_control_pb2.ListReviewsRequest
    ) -> source_control_pb2.ListReviewsResponse:
        reviews = self._adapter.list_reviews(repo_id=req.repo_id, number=req.number)
        return source_control_pb2.ListReviewsResponse(
            reviews=source_control_pb2.Reviews(reviews=[_review_to_pb(r) for r in reviews])
        )

    async def _handle_add_comment(self, request: Request) -> None:
        await self._handle(
            request,
            source_control_pb2.AddCommentRequest,
            source_control_pb2.AddCommentResponse,
            self._call_add_comment,
        )

    def _call_add_comment(
        self, req: source_control_pb2.AddCommentRequest
    ) -> source_control_pb2.AddCommentResponse:
        comment = self._adapter.add_comment(
            repo_id=req.repo_id,
            number=req.number,
            body=req.body,
            path=req.path if req.HasField("path") else None,
            line=req.line if req.HasField("line") else None,
        )
        return source_control_pb2.AddCommentResponse(comment=_comment_to_pb(comment))

    async def _handle_submit_review(self, request: Request) -> None:
        await self._handle(
            request,
            source_control_pb2.SubmitReviewRequest,
            source_control_pb2.SubmitReviewResponse,
            self._call_submit_review,
        )

    def _call_submit_review(
        self, req: source_control_pb2.SubmitReviewRequest
    ) -> source_control_pb2.SubmitReviewResponse:
        review = self._adapter.submit_review(
            repo_id=req.repo_id, number=req.number, event=req.event, body=req.body
        )
        return source_control_pb2.SubmitReviewResponse(review=_review_to_pb(review))

    async def _handle_list_checks(self, request: Request) -> None:
        await self._handle(
            request,
            source_control_pb2.ListChecksRequest,
            source_control_pb2.ListChecksResponse,
            self._call_list_checks,
        )

    def _call_list_checks(
        self, req: source_control_pb2.ListChecksRequest
    ) -> source_control_pb2.ListChecksResponse:
        checks = self._adapter.list_checks(repo_id=req.repo_id, number=req.number)
        return source_control_pb2.ListChecksResponse(
            checks=source_control_pb2.Checks(checks=[_check_to_pb(c) for c in checks])
        )

    async def _handle_set_branch_protection(self, request: Request) -> None:
        await self._handle(
            request,
            source_control_pb2.SetBranchProtectionRequest,
            source_control_pb2.SetBranchProtectionResponse,
            self._call_set_branch_protection,
        )

    def _call_set_branch_protection(
        self, req: source_control_pb2.SetBranchProtectionRequest
    ) -> source_control_pb2.SetBranchProtectionResponse:
        self._adapter.set_branch_protection(
            repo_id=req.repo_id,
            branch=req.branch,
            required_approvals=req.required_approvals,
            required_checks=list(req.required_checks),
        )
        return source_control_pb2.SetBranchProtectionResponse()

    async def _handle_merge(self, request: Request) -> None:
        await self._handle(
            request,
            source_control_pb2.MergeRequest,
            source_control_pb2.MergeResponse,
            self._call_merge,
        )

    def _call_merge(
        self, req: source_control_pb2.MergeRequest
    ) -> source_control_pb2.MergeResponse:
        result = self._adapter.merge(
            repo_id=req.repo_id, number=req.number, method=req.method
        )
        return source_control_pb2.MergeResponse(merge_result=_merge_result_to_pb(result))

    async def _handle_list_workflow_runs(self, request: Request) -> None:
        await self._handle(
            request,
            source_control_pb2.ListWorkflowRunsRequest,
            source_control_pb2.ListWorkflowRunsResponse,
            self._call_list_workflow_runs,
        )

    def _call_list_workflow_runs(
        self, req: source_control_pb2.ListWorkflowRunsRequest
    ) -> source_control_pb2.ListWorkflowRunsResponse:
        runs = self._adapter.list_workflow_runs(repo_id=req.repo_id, limit=req.limit)
        return source_control_pb2.ListWorkflowRunsResponse(
            workflow_runs=source_control_pb2.WorkflowRuns(
                workflow_runs=[_workflow_run_to_pb(r) for r in runs]
            )
        )

    async def _handle_mint_git_token(self, request: Request) -> None:
        await self._handle(
            request,
            source_control_pb2.MintGitTokenRequest,
            source_control_pb2.MintGitTokenResponse,
            self._call_mint_git_token,
        )

    def _call_mint_git_token(
        self, req: source_control_pb2.MintGitTokenRequest
    ) -> source_control_pb2.MintGitTokenResponse:
        token = self._adapter.mint_git_token(user_id=req.user_id)
        return source_control_pb2.MintGitTokenResponse(token=token)
