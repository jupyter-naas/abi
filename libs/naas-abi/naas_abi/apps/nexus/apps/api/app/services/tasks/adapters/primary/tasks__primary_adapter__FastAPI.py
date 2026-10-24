"""HTTP routes for workspace tasks, mounted under ``/api/tasks``.

Every route takes ``workspace_id`` and needs workspace access plus the
``tasks`` feature for the caller's role. By default only workspace owners and
admins have it; an organization or workspace override can open it to members.
Changing the tasks settings also takes the owner or admin role.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from naas_abi.apps.nexus.apps.api.app.api.endpoints.auth import User, get_current_user_required
from naas_abi.apps.nexus.apps.api.app.core.agent_feature_access import caller_feature_flags
from naas_abi.apps.nexus.apps.api.app.core.database import AsyncSessionLocal
from naas_abi.apps.nexus.apps.api.app.services.auth.adapters.primary.auth__primary_adapter__dependencies import (  # noqa: E501
    require_workspace_access,
)
from naas_abi.apps.nexus.apps.api.app.services.tasks.adapters.secondary.postgres import (
    PostgresTasksMemberDirectory,
    PostgresTasksStore,
)
from naas_abi.apps.nexus.apps.api.app.services.tasks.service import TasksService
from naas_abi.apps.nexus.apps.api.app.services.tasks.tasks__schema import (
    MAX_COMMENT_LENGTH,
    MAX_CONTENT_LENGTH,
    MAX_GOAL_LENGTH,
    MAX_TITLE_LENGTH,
    ActivityEntry,
    Comment,
    Iteration,
    Task,
    TasksNotFoundError,
    TasksSettings,
    TasksValidationError,
)
from pydantic import BaseModel, Field

router = APIRouter()

_service = TasksService(PostgresTasksStore(), PostgresTasksMemberDirectory())

TASKS_FEATURE = "tasks"
SETTINGS_ROLES = frozenset({"owner", "admin"})


def get_tasks_service() -> TasksService:
    return _service


async def _caller_flags(workspace_id: str, role: str) -> dict[str, bool]:
    async with AsyncSessionLocal() as db:
        return await caller_feature_flags(db, workspace_id, role)


async def _require_tasks(user_id: str, workspace_id: str) -> str:
    """The caller's workspace role, once workspace access and the feature are checked."""
    role = await require_workspace_access(user_id, workspace_id)
    flags = await _caller_flags(workspace_id, role)
    if not flags.get(TASKS_FEATURE, False):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tasks are not enabled for your role in this workspace",
        )
    return role


def _http_error(exc: Exception) -> HTTPException:
    if isinstance(exc, TasksNotFoundError):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    return HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class IterationOut(BaseModel):
    id: str
    workspace_id: str
    start_date: date
    end_date: date
    iso_week: str
    goal: str
    created_by: str | None
    created_at: datetime | None
    updated_by: str | None
    updated_at: datetime | None


class TaskOut(BaseModel):
    id: str
    workspace_id: str
    title: str
    content: str
    stage: str
    iteration_id: str | None
    priority: str | None
    due_date: date | None
    labels: list[str]
    assignee_ids: list[str]
    archived: bool
    archived_at: datetime | None
    created_by: str | None
    created_at: datetime | None
    updated_by: str | None
    updated_at: datetime | None


class CommentOut(BaseModel):
    id: str
    task_id: str
    author_id: str | None
    body: str
    created_at: datetime


class ActivityOut(BaseModel):
    id: str
    task_id: str
    actor_id: str | None
    field: str
    old_value: Any = None
    new_value: Any = None
    created_at: datetime | None


class CarryOverOut(BaseModel):
    iteration: IterationOut
    moved: list[TaskOut]


class EnsureIterationIn(BaseModel):
    # The caller's local date: the week boundary follows the user's timezone.
    date: date


class GoalIn(BaseModel):
    goal: str = Field(default="", max_length=MAX_GOAL_LENGTH * 2)


class TaskCreateIn(BaseModel):
    title: str = Field(max_length=MAX_TITLE_LENGTH * 2)
    content: str = Field(default="", max_length=MAX_CONTENT_LENGTH)
    stage: str | None = None
    iteration_id: str | None = None
    priority: str | None = None
    due_date: date | None = None
    labels: list[str] = Field(default_factory=list, max_length=100)
    assignee_ids: list[str] = Field(default_factory=list, max_length=100)


class TaskPatchIn(BaseModel):
    """Only the fields sent are changed; ``null`` clears an optional field."""

    title: str | None = Field(default=None, max_length=MAX_TITLE_LENGTH * 2)
    content: str | None = Field(default=None, max_length=MAX_CONTENT_LENGTH)
    stage: str | None = None
    iteration_id: str | None = None
    priority: str | None = None
    due_date: date | None = None
    labels: list[str] | None = Field(default=None, max_length=100)
    assignee_ids: list[str] | None = Field(default=None, max_length=100)


class ChoiceIO(BaseModel):
    # Empty for a new stage or priority: the server derives one from the label.
    key: str = ""
    label: str
    color: str = "slate"


class SettingsOut(BaseModel):
    iteration_weeks: int
    iteration_start_day: int
    iteration_anchor: date
    stages: list[ChoiceIO]
    priorities: list[ChoiceIO]
    default_stage: str
    suggested_labels: list[str]
    updated_by: str | None
    updated_at: datetime | None
    # Whether the caller may save changes (owners and admins).
    can_edit: bool


class SettingsIn(BaseModel):
    iteration_weeks: int
    iteration_start_day: int
    stages: list[ChoiceIO] = Field(max_length=50)
    priorities: list[ChoiceIO] = Field(max_length=50)
    default_stage: str
    suggested_labels: list[str] = Field(default_factory=list, max_length=100)
    # The caller's local date: a new iteration rhythm starts after its ongoing iteration.
    today: date


class CommentIn(BaseModel):
    body: str = Field(max_length=MAX_COMMENT_LENGTH * 2)


def _settings_out(settings: TasksSettings, *, can_edit: bool) -> SettingsOut:
    return SettingsOut(
        iteration_weeks=settings.iteration_weeks,
        iteration_start_day=settings.iteration_start_day,
        iteration_anchor=settings.iteration_anchor,
        stages=[ChoiceIO(key=c.key, label=c.label, color=c.color) for c in settings.stages],
        priorities=[ChoiceIO(key=c.key, label=c.label, color=c.color) for c in settings.priorities],
        default_stage=settings.default_stage,
        suggested_labels=list(settings.suggested_labels),
        updated_by=settings.updated_by,
        updated_at=settings.updated_at,
        can_edit=can_edit,
    )


def _iteration_out(iteration: Iteration) -> IterationOut:
    return IterationOut(
        id=iteration.id,
        workspace_id=iteration.workspace_id,
        start_date=iteration.start_date,
        end_date=iteration.end_date,
        iso_week=iteration.iso_week,
        goal=iteration.goal,
        created_by=iteration.created_by,
        created_at=iteration.created_at,
        updated_by=iteration.updated_by,
        updated_at=iteration.updated_at,
    )


def _task_out(task: Task) -> TaskOut:
    return TaskOut(
        id=task.id,
        workspace_id=task.workspace_id,
        title=task.title,
        content=task.content,
        stage=task.stage,
        iteration_id=task.iteration_id,
        priority=task.priority,
        due_date=task.due_date,
        labels=list(task.labels),
        assignee_ids=list(task.assignee_ids),
        archived=task.archived,
        archived_at=task.archived_at,
        created_by=task.created_by,
        created_at=task.created_at,
        updated_by=task.updated_by,
        updated_at=task.updated_at,
    )


def _comment_out(comment: Comment) -> CommentOut:
    return CommentOut(
        id=comment.id,
        task_id=comment.task_id,
        author_id=comment.author_id,
        body=comment.body,
        created_at=comment.created_at,
    )


def _activity_out(entry: ActivityEntry) -> ActivityOut:
    return ActivityOut(
        id=entry.id,
        task_id=entry.task_id,
        actor_id=entry.actor_id,
        field=entry.field,
        old_value=entry.old_value,
        new_value=entry.new_value,
        created_at=entry.created_at,
    )


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------


@router.get("/settings")
async def get_settings(
    workspace_id: str = Query(...),
    current_user: User = Depends(get_current_user_required),
    service: TasksService = Depends(get_tasks_service),
) -> SettingsOut:
    role = await _require_tasks(current_user.id, workspace_id)
    settings = await service.get_settings(workspace_id)
    return _settings_out(settings, can_edit=role in SETTINGS_ROLES)


@router.put("/settings")
async def update_settings(
    body: SettingsIn,
    workspace_id: str = Query(...),
    current_user: User = Depends(get_current_user_required),
    service: TasksService = Depends(get_tasks_service),
) -> SettingsOut:
    role = await _require_tasks(current_user.id, workspace_id)
    if role not in SETTINGS_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only workspace owners and admins can change the tasks settings",
        )
    try:
        settings = await service.update_settings(
            workspace_id,
            body.model_dump(exclude={"today"}),
            today=body.today,
            user_id=current_user.id,
        )
    except TasksValidationError as exc:
        raise _http_error(exc) from exc
    return _settings_out(settings, can_edit=True)


# ---------------------------------------------------------------------------
# Iterations
# ---------------------------------------------------------------------------


@router.get("/iterations")
async def list_iterations(
    workspace_id: str = Query(...),
    current_user: User = Depends(get_current_user_required),
    service: TasksService = Depends(get_tasks_service),
) -> list[IterationOut]:
    await _require_tasks(current_user.id, workspace_id)
    return [_iteration_out(i) for i in await service.list_iterations(workspace_id)]


@router.post("/iterations")
async def ensure_iteration(
    body: EnsureIterationIn,
    workspace_id: str = Query(...),
    current_user: User = Depends(get_current_user_required),
    service: TasksService = Depends(get_tasks_service),
) -> IterationOut:
    """The iteration ``date`` falls in, created when missing."""
    await _require_tasks(current_user.id, workspace_id)
    iteration = await service.ensure_iteration(workspace_id, body.date, user_id=current_user.id)
    return _iteration_out(iteration)


@router.patch("/iterations/{iteration_id}")
async def update_iteration(
    iteration_id: str,
    body: GoalIn,
    workspace_id: str = Query(...),
    current_user: User = Depends(get_current_user_required),
    service: TasksService = Depends(get_tasks_service),
) -> IterationOut:
    await _require_tasks(current_user.id, workspace_id)
    try:
        iteration = await service.update_iteration_goal(
            workspace_id, iteration_id, body.goal, user_id=current_user.id
        )
    except (TasksNotFoundError, TasksValidationError) as exc:
        raise _http_error(exc) from exc
    return _iteration_out(iteration)


@router.post("/iterations/{iteration_id}/carry-over")
async def carry_over(
    iteration_id: str,
    workspace_id: str = Query(...),
    current_user: User = Depends(get_current_user_required),
    service: TasksService = Depends(get_tasks_service),
) -> CarryOverOut:
    """Move the iteration's unfinished tasks to the iteration after it."""
    await _require_tasks(current_user.id, workspace_id)
    try:
        result = await service.carry_over(workspace_id, iteration_id, user_id=current_user.id)
    except (TasksNotFoundError, TasksValidationError) as exc:
        raise _http_error(exc) from exc
    return CarryOverOut(
        iteration=_iteration_out(result.iteration),
        moved=[_task_out(t) for t in result.moved],
    )


# ---------------------------------------------------------------------------
# Tasks
# ---------------------------------------------------------------------------


@router.get("")
async def list_tasks(
    workspace_id: str = Query(...),
    iteration_id: str | None = Query(default=None),
    backlog: bool = Query(default=False),
    include_archived: bool = Query(default=False),
    current_user: User = Depends(get_current_user_required),
    service: TasksService = Depends(get_tasks_service),
) -> list[TaskOut]:
    """Tasks of ``iteration_id``, of the backlog with ``backlog=true``, or every
    task of the workspace (newest first) when neither is given."""
    await _require_tasks(current_user.id, workspace_id)
    if iteration_id and backlog:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Pass iteration_id or backlog=true, not both",
        )
    if not iteration_id and not backlog:
        tasks = await service.list_all_tasks(workspace_id, include_archived=include_archived)
        return [_task_out(t) for t in tasks]
    try:
        tasks = await service.list_tasks(
            workspace_id,
            iteration_id=None if backlog else iteration_id,
            include_archived=include_archived,
        )
    except TasksNotFoundError as exc:
        raise _http_error(exc) from exc
    return [_task_out(t) for t in tasks]


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_task(
    body: TaskCreateIn,
    workspace_id: str = Query(...),
    current_user: User = Depends(get_current_user_required),
    service: TasksService = Depends(get_tasks_service),
) -> TaskOut:
    await _require_tasks(current_user.id, workspace_id)
    fields = body.model_dump(exclude_none=True)
    try:
        task = await service.create_task(workspace_id, fields, user_id=current_user.id)
    except (TasksNotFoundError, TasksValidationError) as exc:
        raise _http_error(exc) from exc
    return _task_out(task)


@router.patch("/{task_id}")
async def update_task(
    task_id: str,
    body: TaskPatchIn,
    workspace_id: str = Query(...),
    current_user: User = Depends(get_current_user_required),
    service: TasksService = Depends(get_tasks_service),
) -> TaskOut:
    await _require_tasks(current_user.id, workspace_id)
    changes = body.model_dump(exclude_unset=True)
    try:
        task = await service.update_task(workspace_id, task_id, changes, user_id=current_user.id)
    except (TasksNotFoundError, TasksValidationError) as exc:
        raise _http_error(exc) from exc
    return _task_out(task)


@router.post("/{task_id}/archive")
async def archive_task(
    task_id: str,
    workspace_id: str = Query(...),
    current_user: User = Depends(get_current_user_required),
    service: TasksService = Depends(get_tasks_service),
) -> TaskOut:
    await _require_tasks(current_user.id, workspace_id)
    try:
        task = await service.set_archived(workspace_id, task_id, True, user_id=current_user.id)
    except TasksNotFoundError as exc:
        raise _http_error(exc) from exc
    return _task_out(task)


@router.post("/{task_id}/restore")
async def restore_task(
    task_id: str,
    workspace_id: str = Query(...),
    current_user: User = Depends(get_current_user_required),
    service: TasksService = Depends(get_tasks_service),
) -> TaskOut:
    await _require_tasks(current_user.id, workspace_id)
    try:
        task = await service.set_archived(workspace_id, task_id, False, user_id=current_user.id)
    except TasksNotFoundError as exc:
        raise _http_error(exc) from exc
    return _task_out(task)


@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_task(
    task_id: str,
    workspace_id: str = Query(...),
    current_user: User = Depends(get_current_user_required),
    service: TasksService = Depends(get_tasks_service),
) -> Response:
    await _require_tasks(current_user.id, workspace_id)
    try:
        await service.delete_task(workspace_id, task_id)
    except TasksNotFoundError as exc:
        raise _http_error(exc) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ---------------------------------------------------------------------------
# Comments and activity
# ---------------------------------------------------------------------------


@router.get("/{task_id}/comments")
async def list_comments(
    task_id: str,
    workspace_id: str = Query(...),
    current_user: User = Depends(get_current_user_required),
    service: TasksService = Depends(get_tasks_service),
) -> list[CommentOut]:
    await _require_tasks(current_user.id, workspace_id)
    try:
        comments = await service.list_comments(workspace_id, task_id)
    except TasksNotFoundError as exc:
        raise _http_error(exc) from exc
    return [_comment_out(c) for c in comments]


@router.post("/{task_id}/comments", status_code=status.HTTP_201_CREATED)
async def add_comment(
    task_id: str,
    body: CommentIn,
    workspace_id: str = Query(...),
    current_user: User = Depends(get_current_user_required),
    service: TasksService = Depends(get_tasks_service),
) -> CommentOut:
    await _require_tasks(current_user.id, workspace_id)
    try:
        comment = await service.add_comment(
            workspace_id, task_id, body.body, user_id=current_user.id
        )
    except (TasksNotFoundError, TasksValidationError) as exc:
        raise _http_error(exc) from exc
    return _comment_out(comment)


@router.get("/{task_id}/activity")
async def list_activity(
    task_id: str,
    workspace_id: str = Query(...),
    current_user: User = Depends(get_current_user_required),
    service: TasksService = Depends(get_tasks_service),
) -> list[ActivityOut]:
    await _require_tasks(current_user.id, workspace_id)
    try:
        entries = await service.list_activity(workspace_id, task_id)
    except TasksNotFoundError as exc:
        raise _http_error(exc) from exc
    return [_activity_out(e) for e in entries]
