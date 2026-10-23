from __future__ import annotations

import json
from datetime import date
from typing import Any

from naas_abi.apps.nexus.apps.api.app.core.database import AsyncSessionLocal
from naas_abi.apps.nexus.apps.api.app.models import (
    TaskActivityModel,
    TaskCommentModel,
    TaskIterationModel,
    TaskModel,
    TasksSettingsModel,
)
from naas_abi.apps.nexus.apps.api.app.services.tasks.port import (
    TasksMemberDirectoryPort,
    TasksStorePort,
)
from naas_abi.apps.nexus.apps.api.app.services.tasks.tasks__schema import (
    ActivityEntry,
    Choice,
    Comment,
    Iteration,
    Task,
    TasksSettings,
)
from naas_abi.apps.nexus.apps.api.app.services.workspaces.adapters.secondary.postgres import (
    WorkspaceSecondaryAdapterPostgres,
)
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError


def _json_list(raw: Any) -> tuple[str, ...]:
    try:
        data = json.loads(str(raw or "[]"))
    except ValueError:
        return ()
    return tuple(str(v) for v in data) if isinstance(data, list) else ()


def _json_value(raw: Any) -> Any:
    if raw is None:
        return None
    try:
        return json.loads(str(raw))
    except ValueError:
        return None


def _iteration(row: TaskIterationModel) -> Iteration:
    return Iteration(
        id=str(row.id),
        workspace_id=str(row.workspace_id),
        start_date=row.start_date,  # type: ignore[arg-type]
        end_date=row.end_date,  # type: ignore[arg-type]
        goal=str(row.goal or ""),
        created_by=row.created_by,  # type: ignore[arg-type]
        created_at=row.created_at,  # type: ignore[arg-type]
        updated_by=row.updated_by,  # type: ignore[arg-type]
        updated_at=row.updated_at,  # type: ignore[arg-type]
    )


def _settings_to_json(settings: TasksSettings) -> str:
    return json.dumps(
        {
            "iteration_weeks": settings.iteration_weeks,
            "iteration_start_day": settings.iteration_start_day,
            "iteration_anchor": settings.iteration_anchor.isoformat(),
            "stages": [vars(c) for c in settings.stages],
            "priorities": [vars(c) for c in settings.priorities],
            "default_stage": settings.default_stage,
            "suggested_labels": list(settings.suggested_labels),
        }
    )


def _settings(row: TasksSettingsModel) -> TasksSettings:
    data = _json_value(row.data) or {}
    defaults = TasksSettings()

    def choices(raw: Any, fallback: tuple[Choice, ...]) -> tuple[Choice, ...]:
        if not isinstance(raw, list) or not raw:
            return fallback
        return tuple(Choice(str(c["key"]), str(c["label"]), str(c["color"])) for c in raw)

    return TasksSettings(
        iteration_weeks=int(data.get("iteration_weeks", defaults.iteration_weeks)),
        iteration_start_day=int(data.get("iteration_start_day", defaults.iteration_start_day)),
        iteration_anchor=date.fromisoformat(
            data.get("iteration_anchor", defaults.iteration_anchor.isoformat())
        ),
        stages=choices(data.get("stages"), defaults.stages),
        priorities=choices(data.get("priorities"), defaults.priorities),
        default_stage=str(data.get("default_stage", defaults.default_stage)),
        suggested_labels=_json_list(json.dumps(data.get("suggested_labels", []))),
        updated_by=row.updated_by,  # type: ignore[arg-type]
        updated_at=row.updated_at,  # type: ignore[arg-type]
    )


def _task(row: TaskModel) -> Task:
    return Task(
        id=str(row.id),
        workspace_id=str(row.workspace_id),
        title=str(row.title),
        content=str(row.content or ""),
        stage=str(row.stage),
        iteration_id=row.iteration_id,  # type: ignore[arg-type]
        project=str(row.project or ""),
        priority=row.priority,  # type: ignore[arg-type]
        due_date=row.due_date,  # type: ignore[arg-type]
        labels=_json_list(row.labels),
        assignee_ids=_json_list(row.assignee_ids),
        archived_at=row.archived_at,  # type: ignore[arg-type]
        created_by=row.created_by,  # type: ignore[arg-type]
        created_at=row.created_at,  # type: ignore[arg-type]
        updated_by=row.updated_by,  # type: ignore[arg-type]
        updated_at=row.updated_at,  # type: ignore[arg-type]
    )


class PostgresTasksStore(TasksStorePort):
    async def get_settings(self, workspace_id: str) -> TasksSettings | None:
        async with AsyncSessionLocal() as db:
            row = await db.get(TasksSettingsModel, workspace_id)
            return _settings(row) if row is not None else None

    async def save_settings(self, workspace_id: str, settings: TasksSettings) -> None:
        async with AsyncSessionLocal() as db:
            row = await db.get(TasksSettingsModel, workspace_id)
            if row is None:
                row = TasksSettingsModel(workspace_id=workspace_id)
                db.add(row)
            row.data = _settings_to_json(settings)  # type: ignore[assignment]
            row.updated_by = settings.updated_by  # type: ignore[assignment]
            row.updated_at = settings.updated_at  # type: ignore[assignment]
            await db.commit()

    async def list_iterations(self, workspace_id: str) -> list[Iteration]:
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(TaskIterationModel).where(TaskIterationModel.workspace_id == workspace_id)
            )
            return [_iteration(row) for row in result.scalars().all()]

    async def get_iteration(self, workspace_id: str, iteration_id: str) -> Iteration | None:
        async with AsyncSessionLocal() as db:
            row = await db.get(TaskIterationModel, iteration_id)
            if row is None or row.workspace_id != workspace_id:
                return None
            return _iteration(row)

    async def get_iteration_by_start(self, workspace_id: str, start: date) -> Iteration | None:
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(TaskIterationModel).where(
                    (TaskIterationModel.workspace_id == workspace_id)
                    & (TaskIterationModel.start_date == start)
                )
            )
            row = result.scalars().first()
            return _iteration(row) if row is not None else None

    async def save_iteration(self, iteration: Iteration) -> Iteration:
        async with AsyncSessionLocal() as db:
            row = await db.get(TaskIterationModel, iteration.id)
            if row is None:
                db.add(
                    TaskIterationModel(
                        id=iteration.id,
                        workspace_id=iteration.workspace_id,
                        start_date=iteration.start_date,
                        end_date=iteration.end_date,
                        goal=iteration.goal,
                        created_by=iteration.created_by,
                        created_at=iteration.created_at,
                        updated_by=iteration.updated_by,
                        updated_at=iteration.updated_at,
                    )
                )
            else:
                row.goal = iteration.goal  # type: ignore[assignment]
                row.updated_by = iteration.updated_by  # type: ignore[assignment]
                row.updated_at = iteration.updated_at  # type: ignore[assignment]
            try:
                await db.commit()
            except IntegrityError:
                # Two members opened the same week at once: the first insert wins.
                await db.rollback()
                existing = await self.get_iteration_by_start(
                    iteration.workspace_id, iteration.start_date
                )
                if existing is None:
                    raise
                return existing
        return iteration

    async def list_tasks(
        self,
        workspace_id: str,
        *,
        iteration_id: str | None,
        include_archived: bool,
    ) -> list[Task]:
        query = select(TaskModel).where(TaskModel.workspace_id == workspace_id)
        if iteration_id is None:
            query = query.where(TaskModel.iteration_id.is_(None))
        else:
            query = query.where(TaskModel.iteration_id == iteration_id)
        if not include_archived:
            query = query.where(TaskModel.archived_at.is_(None))
        async with AsyncSessionLocal() as db:
            result = await db.execute(query)
            return [_task(row) for row in result.scalars().all()]

    async def list_workspace_tasks(
        self, workspace_id: str, *, include_archived: bool
    ) -> list[Task]:
        query = select(TaskModel).where(TaskModel.workspace_id == workspace_id)
        if not include_archived:
            query = query.where(TaskModel.archived_at.is_(None))
        async with AsyncSessionLocal() as db:
            result = await db.execute(query)
            return [_task(row) for row in result.scalars().all()]

    async def get_task(self, workspace_id: str, task_id: str) -> Task | None:
        async with AsyncSessionLocal() as db:
            row = await db.get(TaskModel, task_id)
            if row is None or row.workspace_id != workspace_id:
                return None
            return _task(row)

    async def save_task(self, task: Task) -> None:
        values = {
            "workspace_id": task.workspace_id,
            "iteration_id": task.iteration_id,
            "title": task.title,
            "content": task.content,
            "stage": task.stage,
            "project": task.project,
            "priority": task.priority,
            "due_date": task.due_date,
            "labels": json.dumps(list(task.labels)),
            "assignee_ids": json.dumps(list(task.assignee_ids)),
            "archived_at": task.archived_at,
            "created_by": task.created_by,
            "created_at": task.created_at,
            "updated_by": task.updated_by,
            "updated_at": task.updated_at,
        }
        async with AsyncSessionLocal() as db:
            row = await db.get(TaskModel, task.id)
            if row is None:
                db.add(TaskModel(id=task.id, **values))
            else:
                for key, value in values.items():
                    setattr(row, key, value)
            await db.commit()

    async def delete_task(self, workspace_id: str, task_id: str) -> bool:
        async with AsyncSessionLocal() as db:
            scope = (TaskModel.workspace_id == workspace_id) & (TaskModel.id == task_id)
            exists = (await db.execute(select(TaskModel.id).where(scope))).first()
            if exists is None:
                return False
            # Explicit deletes: SQLite test databases do not enforce ON DELETE CASCADE.
            await db.execute(delete(TaskCommentModel).where(TaskCommentModel.task_id == task_id))
            await db.execute(delete(TaskActivityModel).where(TaskActivityModel.task_id == task_id))
            await db.execute(delete(TaskModel).where(scope))
            await db.commit()
            return True

    async def list_comments(self, workspace_id: str, task_id: str) -> list[Comment]:
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(TaskCommentModel).where(
                    (TaskCommentModel.workspace_id == workspace_id)
                    & (TaskCommentModel.task_id == task_id)
                )
            )
            return [
                Comment(
                    id=str(row.id),
                    workspace_id=str(row.workspace_id),
                    task_id=str(row.task_id),
                    author_id=row.author_id,  # type: ignore[arg-type]
                    body=str(row.body),
                    created_at=row.created_at,  # type: ignore[arg-type]
                )
                for row in result.scalars().all()
            ]

    async def add_comment(self, comment: Comment) -> None:
        async with AsyncSessionLocal() as db:
            db.add(
                TaskCommentModel(
                    id=comment.id,
                    workspace_id=comment.workspace_id,
                    task_id=comment.task_id,
                    author_id=comment.author_id,
                    body=comment.body,
                    created_at=comment.created_at,
                )
            )
            await db.commit()

    async def list_activity(self, workspace_id: str, task_id: str) -> list[ActivityEntry]:
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(TaskActivityModel).where(
                    (TaskActivityModel.workspace_id == workspace_id)
                    & (TaskActivityModel.task_id == task_id)
                )
            )
            return [
                ActivityEntry(
                    id=str(row.id),
                    workspace_id=str(row.workspace_id),
                    task_id=str(row.task_id),
                    actor_id=row.actor_id,  # type: ignore[arg-type]
                    field=str(row.field),
                    old_value=_json_value(row.old_value),
                    new_value=_json_value(row.new_value),
                    created_at=row.created_at,  # type: ignore[arg-type]
                )
                for row in result.scalars().all()
            ]

    async def add_activity(self, entries: list[ActivityEntry]) -> None:
        if not entries:
            return
        async with AsyncSessionLocal() as db:
            for entry in entries:
                db.add(
                    TaskActivityModel(
                        id=entry.id,
                        workspace_id=entry.workspace_id,
                        task_id=entry.task_id,
                        actor_id=entry.actor_id,
                        field=entry.field,
                        old_value=json.dumps(entry.old_value),
                        new_value=json.dumps(entry.new_value),
                        created_at=entry.created_at,
                    )
                )
            await db.commit()


class PostgresTasksMemberDirectory(TasksMemberDirectoryPort):
    """The workspace member listing, including members inherited from the organization."""

    async def member_ids(self, workspace_id: str) -> set[str]:
        async with AsyncSessionLocal() as db:
            adapter = WorkspaceSecondaryAdapterPostgres(db=db)
            members = await adapter.list_workspace_members(workspace_id=workspace_id)
            return {member.user_id for member in members}
