"""Code review FastAPI primary adapter (in-app, Forgejo-backed).

Exposes the `source_control` core service as the Nexus review surface so users
branch, propose, review (inline comments + approvals), see checks, and merge —
all inside Nexus, never leaving for GitHub/GitLab (the Foundry model).

`repo_id` is the ``"owner/name"`` string and is passed as a query/body field
(not a path segment) because it contains a slash. Every operation requires
membership of the given Nexus ``workspace_id`` via ``require_workspace_access``.
The core service is synchronous, so calls run in a threadpool.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.concurrency import run_in_threadpool
from naas_abi.apps.nexus.apps.api.app.api.endpoints.auth import (
    User,
    get_current_user_required,
    require_workspace_access,
)
from naas_abi_core.services.source_control.SourceControlPorts import (
    AccessDeniedError,
    Branch,
    BranchNameConflictError,
    BranchNotFoundError,
    Check,
    Comment,
    Commit,
    Diff,
    MergeBlockedError,
    MergeConflictError,
    MergeResult,
    Proposal,
    ProposalNotFoundError,
    RepoNotFoundError,
    Review,
    SourceControlError,
    ValidationError,
    WorkflowRun,
)
from naas_abi_core.services.source_control.SourceControlService import (
    SourceControlService,
)
from pydantic import BaseModel, Field

router = APIRouter(dependencies=[Depends(get_current_user_required)])


_HTTP_STATUS_BY_ERROR: dict[type[SourceControlError], int] = {
    RepoNotFoundError: 404,
    BranchNotFoundError: 404,
    ProposalNotFoundError: 404,
    BranchNameConflictError: 409,
    MergeConflictError: 409,
    MergeBlockedError: 422,
    AccessDeniedError: 403,
    ValidationError: 400,
}


def _http_error(exc: SourceControlError) -> HTTPException:
    status_code = _HTTP_STATUS_BY_ERROR.get(type(exc), 502)
    return HTTPException(status_code=status_code, detail=str(exc) or type(exc).__name__)


def _get_source_control_service(request: Request) -> SourceControlService:
    service = getattr(request.app.state, "source_control", None)
    if service is not None:
        return service
    try:
        from naas_abi import ABIModule  # noqa: PLC0415

        module = ABIModule.get_instance()
        service = module.engine.services.source_control
        request.app.state.source_control = service
        return service
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail="Source control service is not initialized.",
        ) from exc


class BranchOut(BaseModel):
    name: str
    commit_sha: str
    protected: bool


class ProposalOut(BaseModel):
    id: str
    number: int
    title: str
    body: str
    state: str
    source_branch: str
    target_branch: str
    author: str
    mergeable: bool
    approvals: int
    html_url: str


class DiffFileOut(BaseModel):
    path: str
    status: str
    additions: int
    deletions: int
    patch: str | None = None
    old_path: str | None = None


class DiffOut(BaseModel):
    files: list[DiffFileOut]


class CommentOut(BaseModel):
    id: str
    path: str | None = None
    line: int | None = None
    body: str
    author: str
    created_at: str | None = None


class ReviewOut(BaseModel):
    id: str
    state: str
    body: str
    author: str
    submitted_at: str | None = None


class CommitOut(BaseModel):
    sha: str
    message: str
    author: str
    date: str | None = None


class CheckOut(BaseModel):
    name: str
    status: str
    conclusion: str | None = None


class WorkflowRunOut(BaseModel):
    id: int
    name: str
    workflow_id: str
    display_title: str
    run_number: int
    event: str
    status: str
    head_branch: str
    head_sha: str
    url: str
    created_at: str | None = None
    run_started_at: str | None = None
    updated_at: str | None = None


class MergeOut(BaseModel):
    merged: bool
    sha: str | None = None
    message: str | None = None


class CreateBranchBody(BaseModel):
    workspace_id: str = Field(..., min_length=1, max_length=100)
    repo_id: str = Field(..., min_length=1, max_length=200)
    name: str = Field(..., min_length=1, max_length=200)
    from_ref: str = Field(..., min_length=1, max_length=200)


class CreateProposalBody(BaseModel):
    workspace_id: str = Field(..., min_length=1, max_length=100)
    repo_id: str = Field(..., min_length=1, max_length=200)
    title: str = Field(..., min_length=1, max_length=400)
    body: str = Field(default="", max_length=50_000)
    source_branch: str = Field(..., min_length=1, max_length=200)
    target_branch: str = Field(..., min_length=1, max_length=200)


class AddCommentBody(BaseModel):
    workspace_id: str = Field(..., min_length=1, max_length=100)
    repo_id: str = Field(..., min_length=1, max_length=200)
    number: int
    body: str = Field(..., min_length=1, max_length=50_000)
    path: str | None = None
    line: int | None = None


class SubmitReviewBody(BaseModel):
    workspace_id: str = Field(..., min_length=1, max_length=100)
    repo_id: str = Field(..., min_length=1, max_length=200)
    number: int
    event: str = Field(..., min_length=1, max_length=40)
    body: str = Field(default="", max_length=50_000)


class MergeBody(BaseModel):
    workspace_id: str = Field(..., min_length=1, max_length=100)
    repo_id: str = Field(..., min_length=1, max_length=200)
    number: int
    method: str = "merge"


def _to_branch(branch: Branch) -> BranchOut:
    return BranchOut(name=branch.name, commit_sha=branch.commit_sha, protected=branch.protected)


def _to_proposal(proposal: Proposal) -> ProposalOut:
    return ProposalOut(
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


def _to_diff(diff: Diff) -> DiffOut:
    return DiffOut(
        files=[
            DiffFileOut(
                path=f.path,
                status=f.status,
                additions=f.additions,
                deletions=f.deletions,
                patch=f.patch,
                old_path=f.old_path,
            )
            for f in diff.files
        ]
    )


def _to_comment(comment: Comment) -> CommentOut:
    return CommentOut(
        id=comment.id,
        path=comment.path,
        line=comment.line,
        body=comment.body,
        author=comment.author,
        created_at=comment.created_at,
    )


def _to_review(review: Review) -> ReviewOut:
    return ReviewOut(
        id=review.id,
        state=review.state,
        body=review.body,
        author=review.author,
        submitted_at=review.submitted_at,
    )


def _to_commit(commit: Commit) -> CommitOut:
    return CommitOut(
        sha=commit.sha, message=commit.message, author=commit.author, date=commit.date
    )


def _to_check(check: Check) -> CheckOut:
    return CheckOut(name=check.name, status=check.status, conclusion=check.conclusion)


def _to_workflow_run(run: WorkflowRun) -> WorkflowRunOut:
    return WorkflowRunOut(
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
        created_at=run.created_at,
        run_started_at=run.run_started_at,
        updated_at=run.updated_at,
    )


def _to_merge(result: MergeResult) -> MergeOut:
    return MergeOut(merged=result.merged, sha=result.sha, message=result.message)


@router.get("/branches")
async def list_branches(
    workspace_id: str,
    repo_id: str,
    current_user: User = Depends(get_current_user_required),
    service: SourceControlService = Depends(_get_source_control_service),
) -> list[BranchOut]:
    await require_workspace_access(current_user.id, workspace_id)
    try:
        branches = await run_in_threadpool(service.list_branches, repo_id=repo_id)
    except SourceControlError as exc:
        raise _http_error(exc) from exc
    return [_to_branch(b) for b in branches]


@router.post("/branches")
async def create_branch(
    body: CreateBranchBody,
    current_user: User = Depends(get_current_user_required),
    service: SourceControlService = Depends(_get_source_control_service),
) -> BranchOut:
    await require_workspace_access(current_user.id, body.workspace_id)
    try:
        branch = await run_in_threadpool(
            service.create_branch, repo_id=body.repo_id, name=body.name, from_ref=body.from_ref
        )
    except SourceControlError as exc:
        raise _http_error(exc) from exc
    return _to_branch(branch)


@router.get("/proposals")
async def list_proposals(
    workspace_id: str,
    repo_id: str,
    state: str = "open",
    current_user: User = Depends(get_current_user_required),
    service: SourceControlService = Depends(_get_source_control_service),
) -> list[ProposalOut]:
    await require_workspace_access(current_user.id, workspace_id)
    try:
        proposals = await run_in_threadpool(
            service.list_proposals, repo_id=repo_id, state=state
        )
    except SourceControlError as exc:
        raise _http_error(exc) from exc
    return [_to_proposal(p) for p in proposals]


@router.post("/proposals")
async def create_proposal(
    body: CreateProposalBody,
    current_user: User = Depends(get_current_user_required),
    service: SourceControlService = Depends(_get_source_control_service),
) -> ProposalOut:
    await require_workspace_access(current_user.id, body.workspace_id)
    try:
        proposal = await run_in_threadpool(
            service.create_proposal,
            repo_id=body.repo_id,
            title=body.title,
            body=body.body,
            source_branch=body.source_branch,
            target_branch=body.target_branch,
        )
    except SourceControlError as exc:
        raise _http_error(exc) from exc
    return _to_proposal(proposal)


@router.get("/proposal")
async def get_proposal(
    workspace_id: str,
    repo_id: str,
    number: int,
    current_user: User = Depends(get_current_user_required),
    service: SourceControlService = Depends(_get_source_control_service),
) -> ProposalOut:
    await require_workspace_access(current_user.id, workspace_id)
    try:
        proposal = await run_in_threadpool(
            service.get_proposal, repo_id=repo_id, number=number
        )
    except SourceControlError as exc:
        raise _http_error(exc) from exc
    return _to_proposal(proposal)


@router.get("/proposal/diff")
async def get_proposal_diff(
    workspace_id: str,
    repo_id: str,
    number: int,
    current_user: User = Depends(get_current_user_required),
    service: SourceControlService = Depends(_get_source_control_service),
) -> DiffOut:
    await require_workspace_access(current_user.id, workspace_id)
    try:
        diff = await run_in_threadpool(
            service.get_proposal_diff, repo_id=repo_id, number=number
        )
    except SourceControlError as exc:
        raise _http_error(exc) from exc
    return _to_diff(diff)


@router.get("/proposal/commits")
async def list_proposal_commits(
    workspace_id: str,
    repo_id: str,
    number: int,
    current_user: User = Depends(get_current_user_required),
    service: SourceControlService = Depends(_get_source_control_service),
) -> list[CommitOut]:
    await require_workspace_access(current_user.id, workspace_id)
    try:
        commits = await run_in_threadpool(
            service.list_proposal_commits, repo_id=repo_id, number=number
        )
    except SourceControlError as exc:
        raise _http_error(exc) from exc
    return [_to_commit(c) for c in commits]


@router.get("/proposal/comments")
async def list_comments(
    workspace_id: str,
    repo_id: str,
    number: int,
    current_user: User = Depends(get_current_user_required),
    service: SourceControlService = Depends(_get_source_control_service),
) -> list[CommentOut]:
    await require_workspace_access(current_user.id, workspace_id)
    try:
        comments = await run_in_threadpool(
            service.list_comments, repo_id=repo_id, number=number
        )
    except SourceControlError as exc:
        raise _http_error(exc) from exc
    return [_to_comment(c) for c in comments]


@router.post("/proposal/comments")
async def add_comment(
    body: AddCommentBody,
    current_user: User = Depends(get_current_user_required),
    service: SourceControlService = Depends(_get_source_control_service),
) -> CommentOut:
    await require_workspace_access(current_user.id, body.workspace_id)
    try:
        comment = await run_in_threadpool(
            service.add_comment,
            repo_id=body.repo_id,
            number=body.number,
            body=body.body,
            path=body.path,
            line=body.line,
        )
    except SourceControlError as exc:
        raise _http_error(exc) from exc
    return _to_comment(comment)


@router.get("/proposal/reviews")
async def list_reviews(
    workspace_id: str,
    repo_id: str,
    number: int,
    current_user: User = Depends(get_current_user_required),
    service: SourceControlService = Depends(_get_source_control_service),
) -> list[ReviewOut]:
    await require_workspace_access(current_user.id, workspace_id)
    try:
        reviews = await run_in_threadpool(
            service.list_reviews, repo_id=repo_id, number=number
        )
    except SourceControlError as exc:
        raise _http_error(exc) from exc
    return [_to_review(r) for r in reviews]


@router.post("/proposal/review")
async def submit_review(
    body: SubmitReviewBody,
    current_user: User = Depends(get_current_user_required),
    service: SourceControlService = Depends(_get_source_control_service),
) -> ReviewOut:
    await require_workspace_access(current_user.id, body.workspace_id)
    try:
        review = await run_in_threadpool(
            service.submit_review,
            repo_id=body.repo_id,
            number=body.number,
            event=body.event,
            body=body.body,
        )
    except SourceControlError as exc:
        raise _http_error(exc) from exc
    return _to_review(review)


@router.get("/proposal/checks")
async def list_checks(
    workspace_id: str,
    repo_id: str,
    number: int,
    current_user: User = Depends(get_current_user_required),
    service: SourceControlService = Depends(_get_source_control_service),
) -> list[CheckOut]:
    await require_workspace_access(current_user.id, workspace_id)
    try:
        checks = await run_in_threadpool(
            service.list_checks, repo_id=repo_id, number=number
        )
    except SourceControlError as exc:
        raise _http_error(exc) from exc
    return [_to_check(c) for c in checks]


@router.post("/proposal/merge")
async def merge_proposal(
    body: MergeBody,
    current_user: User = Depends(get_current_user_required),
    service: SourceControlService = Depends(_get_source_control_service),
) -> MergeOut:
    await require_workspace_access(current_user.id, body.workspace_id)
    try:
        result = await run_in_threadpool(
            service.merge, repo_id=body.repo_id, number=body.number, method=body.method
        )
    except SourceControlError as exc:
        raise _http_error(exc) from exc
    return _to_merge(result)


@router.get("/actions/runs")
async def list_workflow_runs(
    workspace_id: str,
    repo_id: str,
    limit: int = 30,
    current_user: User = Depends(get_current_user_required),
    service: SourceControlService = Depends(_get_source_control_service),
) -> list[WorkflowRunOut]:
    await require_workspace_access(current_user.id, workspace_id)
    try:
        runs = await run_in_threadpool(
            service.list_workflow_runs, repo_id=repo_id, limit=limit
        )
    except SourceControlError as exc:
        raise _http_error(exc) from exc
    return [_to_workflow_run(r) for r in runs]
