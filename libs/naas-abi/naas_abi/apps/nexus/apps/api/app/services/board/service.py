"""Board domain logic: iterations, task lifecycle, carry-over, comments, activity.

Every operation is scoped to a workspace: a record of another workspace is
reported missing, never read or changed. Access (workspace membership and the
``board`` feature) is checked by the HTTP adapter before calling in.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Iterable, Mapping
from dataclasses import replace
from datetime import date, datetime, timedelta
from typing import Any
from uuid import uuid4

from naas_abi.apps.nexus.apps.api.app.core.datetime_compat import UTC
from naas_abi.apps.nexus.apps.api.app.services.board.board__schema import (
    ACTIVITY_ARCHIVED,
    ACTIVITY_ASSIGNEES,
    ACTIVITY_CREATED,
    ACTIVITY_ITERATION,
    ACTIVITY_STAGE,
    DEFAULT_STAGE,
    DONE_STAGE,
    EDITABLE_TASK_FIELDS,
    INBOX_STAGE,
    MAX_ASSIGNEES,
    MAX_CHOICE_LABEL_LENGTH,
    MAX_CHOICES,
    MAX_COMMENT_LENGTH,
    MAX_CONTENT_LENGTH,
    MAX_GOAL_LENGTH,
    MAX_ITERATION_WEEKS,
    MAX_LABEL_LENGTH,
    MAX_LABELS,
    MAX_PROJECT_LENGTH,
    MAX_SUGGESTED_LABELS,
    MAX_TITLE_LENGTH,
    MIN_ITERATION_WEEKS,
    PALETTE,
    ActivityEntry,
    BoardAssigneeError,
    BoardNotFoundError,
    BoardSettings,
    BoardValidationError,
    CarryOverResult,
    Choice,
    Comment,
    Iteration,
    Task,
    week_start,
)
from naas_abi.apps.nexus.apps.api.app.services.board.port import (
    BoardMemberDirectoryPort,
    BoardStorePort,
)


def _utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _new_id() -> str:
    return uuid4().hex


class BoardService:
    def __init__(
        self,
        store: BoardStorePort,
        members: BoardMemberDirectoryPort,
        *,
        clock: Callable[[], datetime] = _utcnow,
    ) -> None:
        self._store = store
        self._members = members
        self._clock = clock

    # ------------------------------------------------------------------
    # Iterations
    # ------------------------------------------------------------------

    async def list_iterations(self, workspace_id: str) -> list[Iteration]:
        iterations = await self._store.list_iterations(workspace_id)
        return sorted(iterations, key=lambda i: i.start_date)

    async def get_iteration(self, workspace_id: str, iteration_id: str) -> Iteration:
        iteration = await self._store.get_iteration(workspace_id, iteration_id)
        if iteration is None:
            raise BoardNotFoundError(f"Iteration {iteration_id} not found")
        return iteration

    async def ensure_iteration(self, workspace_id: str, day: date, *, user_id: str) -> Iteration:
        """The iteration ``day`` falls in, created when missing.

        A new iteration covers the settings' period for ``day``, trimmed so it
        never overlaps an iteration made under earlier settings.
        """
        iterations = await self._store.list_iterations(workspace_id)
        existing = next((i for i in iterations if i.contains(day)), None)
        if existing is not None:
            return existing
        start, end = (await self.get_settings(workspace_id)).period(day)
        for other in iterations:
            if other.start_date <= end and other.end_date >= start:
                if other.end_date < day:
                    start = max(start, other.end_date + timedelta(days=1))
                else:
                    end = min(end, other.start_date - timedelta(days=1))
        now = self._clock()
        return await self._store.save_iteration(
            Iteration(
                id=_new_id(),
                workspace_id=workspace_id,
                start_date=start,
                end_date=end,
                created_by=user_id,
                created_at=now,
                updated_by=user_id,
                updated_at=now,
            )
        )

    async def adjacent_iteration(
        self, workspace_id: str, iteration_id: str, direction: int, *, user_id: str
    ) -> Iteration:
        """The iteration right before (-1) or after (1) this one, created when missing."""
        if direction not in (-1, 1):
            raise BoardValidationError("direction must be -1 or 1")
        iteration = await self.get_iteration(workspace_id, iteration_id)
        day = (
            iteration.end_date + timedelta(days=1)
            if direction == 1
            else iteration.start_date - timedelta(days=1)
        )
        return await self.ensure_iteration(workspace_id, day, user_id=user_id)

    async def update_iteration_goal(
        self, workspace_id: str, iteration_id: str, goal: str, *, user_id: str
    ) -> Iteration:
        iteration = await self.get_iteration(workspace_id, iteration_id)
        cleaned = " ".join(goal.split())
        if len(cleaned) > MAX_GOAL_LENGTH:
            raise BoardValidationError(f"Goal is limited to {MAX_GOAL_LENGTH} characters")
        updated = replace(iteration, goal=cleaned, updated_by=user_id, updated_at=self._clock())
        return await self._store.save_iteration(updated)

    # ------------------------------------------------------------------
    # Settings
    # ------------------------------------------------------------------

    async def get_settings(self, workspace_id: str) -> BoardSettings:
        return await self._store.get_settings(workspace_id) or BoardSettings()

    async def update_settings(
        self, workspace_id: str, raw: Mapping[str, Any], *, today: date, user_id: str
    ) -> BoardSettings:
        """Validate and store new settings.

        A new iteration length or start day applies from the end of the
        iteration ``today`` falls in: existing iterations keep their dates.
        Removing a stage or a priority that tasks still use is refused.
        """
        current = await self.get_settings(workspace_id)
        weeks = _int_in(
            raw.get("iteration_weeks", current.iteration_weeks),
            "Iteration length",
            MIN_ITERATION_WEEKS,
            MAX_ITERATION_WEEKS,
        )
        start_day = _int_in(
            raw.get("iteration_start_day", current.iteration_start_day), "Iteration start day", 0, 6
        )
        stages = _clean_choices(raw.get("stages", current.stages), "stage", current.stages)
        if stages[0].key != INBOX_STAGE or stages[-1].key != DONE_STAGE:
            raise BoardValidationError("Inbox must be the first stage and Done the last")
        priorities = _clean_choices(
            raw.get("priorities", current.priorities), "priority", current.priorities
        )
        default_stage = str(raw.get("default_stage", current.default_stage))
        if default_stage not in {s.key for s in stages} or default_stage == INBOX_STAGE:
            raise BoardValidationError("New iteration tasks need a stage other than Inbox")
        labels = _unique(
            " ".join(str(label).split())
            for label in raw.get("suggested_labels", current.suggested_labels)
        )
        if len(labels) > MAX_SUGGESTED_LABELS or any(len(x) > MAX_LABEL_LENGTH for x in labels):
            raise BoardValidationError(
                f"Up to {MAX_SUGGESTED_LABELS} labels of {MAX_LABEL_LENGTH} characters"
            )

        await self._refuse_removed_in_use(
            workspace_id,
            removed_stages=set(current.stage_keys) - {s.key for s in stages},
            removed_priorities=set(current.priority_keys) - {p.key for p in priorities},
        )

        anchor = current.iteration_anchor
        if (weeks, start_day) != (current.iteration_weeks, current.iteration_start_day):
            ongoing = next(
                (i for i in await self._store.list_iterations(workspace_id) if i.contains(today)),
                None,
            )
            # The new rhythm starts on the first start weekday after the ongoing
            # iteration (week_start of end + 7 days lands in (end, end + 7]).
            anchor = (
                week_start(ongoing.end_date + timedelta(days=7), start_day)
                if ongoing
                else week_start(today, start_day)
            )

        settings = BoardSettings(
            iteration_weeks=weeks,
            iteration_start_day=start_day,
            iteration_anchor=anchor,
            stages=stages,
            priorities=priorities,
            default_stage=default_stage,
            suggested_labels=labels,
            updated_by=user_id,
            updated_at=self._clock(),
        )
        await self._store.save_settings(workspace_id, settings)
        return settings

    async def _refuse_removed_in_use(
        self, workspace_id: str, *, removed_stages: set[str], removed_priorities: set[str]
    ) -> None:
        if not removed_stages and not removed_priorities:
            return
        tasks = await self._store.list_workspace_tasks(workspace_id, include_archived=True)
        problems = []
        for key in sorted(removed_stages):
            count = sum(1 for t in tasks if t.stage == key)
            if count:
                problems.append(f"{count} task{'s' if count > 1 else ''} in stage {key}")
        for key in sorted(removed_priorities):
            count = sum(1 for t in tasks if t.priority == key)
            if count:
                problems.append(f"{count} task{'s' if count > 1 else ''} with priority {key}")
        if problems:
            raise BoardValidationError(
                "Move these tasks before removing their stage or priority: " + "; ".join(problems)
            )

    # ------------------------------------------------------------------
    # Tasks
    # ------------------------------------------------------------------

    async def list_tasks(
        self,
        workspace_id: str,
        *,
        iteration_id: str | None,
        include_archived: bool = False,
    ) -> list[Task]:
        """Tasks of an iteration, or of the backlog when ``iteration_id`` is None."""
        if iteration_id is not None:
            await self.get_iteration(workspace_id, iteration_id)
        tasks = await self._store.list_tasks(
            workspace_id, iteration_id=iteration_id, include_archived=include_archived
        )
        return sorted(tasks, key=lambda t: (t.created_at or datetime.min, t.id))

    async def list_all_tasks(
        self, workspace_id: str, *, include_archived: bool = False
    ) -> list[Task]:
        """Every task of the workspace, newest first."""
        tasks = await self._store.list_workspace_tasks(
            workspace_id, include_archived=include_archived
        )
        return sorted(tasks, key=lambda t: (t.created_at or datetime.min, t.id), reverse=True)

    async def get_task(self, workspace_id: str, task_id: str) -> Task:
        task = await self._store.get_task(workspace_id, task_id)
        if task is None:
            raise BoardNotFoundError(f"Task {task_id} not found")
        return task

    async def create_task(
        self, workspace_id: str, fields: Mapping[str, Any], *, user_id: str
    ) -> Task:
        values = await self._clean_task_fields(workspace_id, fields)
        if "title" not in values:
            raise BoardValidationError("A task needs a title")
        if "stage" not in values and values.get("iteration_id"):
            values["stage"] = (await self.get_settings(workspace_id)).default_stage
        now = self._clock()
        task = Task(
            id=_new_id(),
            workspace_id=workspace_id,
            created_by=user_id,
            created_at=now,
            updated_by=user_id,
            updated_at=now,
            **values,
        )
        await self._store.save_task(task)
        await self._store.add_activity([self._activity(task, user_id, ACTIVITY_CREATED, now=now)])
        return task

    async def update_task(
        self, workspace_id: str, task_id: str, changes: Mapping[str, Any], *, user_id: str
    ) -> Task:
        task = await self.get_task(workspace_id, task_id)
        values = await self._clean_task_fields(workspace_id, changes)
        now = self._clock()
        updated = replace(task, **values, updated_by=user_id, updated_at=now)
        await self._store.save_task(updated)
        await self._store.add_activity(self._tracked_changes(task, updated, user_id, now))
        return updated

    async def set_archived(
        self, workspace_id: str, task_id: str, archived: bool, *, user_id: str
    ) -> Task:
        task = await self.get_task(workspace_id, task_id)
        if task.archived == archived:
            return task
        now = self._clock()
        updated = replace(
            task, archived_at=now if archived else None, updated_by=user_id, updated_at=now
        )
        await self._store.save_task(updated)
        await self._store.add_activity(
            [self._activity(task, user_id, ACTIVITY_ARCHIVED, not archived, archived, now=now)]
        )
        return updated

    async def delete_task(self, workspace_id: str, task_id: str) -> None:
        if not await self._store.delete_task(workspace_id, task_id):
            raise BoardNotFoundError(f"Task {task_id} not found")

    async def carry_over(
        self, workspace_id: str, iteration_id: str, *, user_id: str
    ) -> CarryOverResult:
        """Move every task of the iteration that is not done (nor archived) to the next one."""
        following = await self.adjacent_iteration(workspace_id, iteration_id, 1, user_id=user_id)
        tasks = await self.list_tasks(workspace_id, iteration_id=iteration_id)
        moved: list[Task] = []
        for task in tasks:
            if task.stage == DONE_STAGE:
                continue
            moved.append(
                await self.update_task(
                    workspace_id, task.id, {"iteration_id": following.id}, user_id=user_id
                )
            )
        return CarryOverResult(iteration=following, moved=moved)

    # ------------------------------------------------------------------
    # Comments and activity
    # ------------------------------------------------------------------

    async def list_comments(self, workspace_id: str, task_id: str) -> list[Comment]:
        await self.get_task(workspace_id, task_id)
        comments = await self._store.list_comments(workspace_id, task_id)
        return sorted(comments, key=lambda c: (c.created_at, c.id))

    async def add_comment(
        self, workspace_id: str, task_id: str, body: str, *, user_id: str
    ) -> Comment:
        await self.get_task(workspace_id, task_id)
        cleaned = body.strip()
        if not cleaned:
            raise BoardValidationError("A comment cannot be empty")
        if len(cleaned) > MAX_COMMENT_LENGTH:
            raise BoardValidationError(f"Comments are limited to {MAX_COMMENT_LENGTH} characters")
        comment = Comment(
            id=_new_id(),
            workspace_id=workspace_id,
            task_id=task_id,
            author_id=user_id,
            body=cleaned,
            created_at=self._clock(),
        )
        await self._store.add_comment(comment)
        return comment

    async def list_activity(self, workspace_id: str, task_id: str) -> list[ActivityEntry]:
        await self.get_task(workspace_id, task_id)
        entries = await self._store.list_activity(workspace_id, task_id)
        return sorted(entries, key=lambda a: a.created_at or datetime.min)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    async def _clean_task_fields(
        self, workspace_id: str, fields: Mapping[str, Any]
    ) -> dict[str, Any]:
        unknown = sorted(set(fields) - EDITABLE_TASK_FIELDS)
        if unknown:
            raise BoardValidationError(f"Unknown task fields: {', '.join(unknown)}")
        values: dict[str, Any] = {}
        settings = (
            await self.get_settings(workspace_id) if {"stage", "priority"} & set(fields) else None
        )
        for key, raw in fields.items():
            if key == "title":
                title = " ".join(str(raw or "").split())
                if not title:
                    raise BoardValidationError("A task needs a title")
                if len(title) > MAX_TITLE_LENGTH:
                    raise BoardValidationError(
                        f"Titles are limited to {MAX_TITLE_LENGTH} characters"
                    )
                values[key] = title
            elif key == "content":
                content = str(raw or "")
                if len(content) > MAX_CONTENT_LENGTH:
                    raise BoardValidationError(
                        f"Content is limited to {MAX_CONTENT_LENGTH} characters"
                    )
                values[key] = content
            elif key == "stage":
                stage = raw or DEFAULT_STAGE
                if settings is None or stage not in settings.stage_keys:
                    raise BoardValidationError(f"Unknown stage: {stage}")
                values[key] = stage
            elif key == "iteration_id":
                if raw:
                    await self.get_iteration(workspace_id, str(raw))
                values[key] = str(raw) if raw else None
            elif key == "project":
                project = " ".join(str(raw or "").split())
                if len(project) > MAX_PROJECT_LENGTH:
                    raise BoardValidationError(
                        f"Projects are limited to {MAX_PROJECT_LENGTH} characters"
                    )
                values[key] = project
            elif key == "priority":
                if raw and (settings is None or raw not in settings.priority_keys):
                    raise BoardValidationError(f"Unknown priority: {raw}")
                values[key] = raw or None
            elif key == "due_date":
                if raw is not None and not isinstance(raw, date):
                    raise BoardValidationError("due_date must be a date")
                values[key] = raw
            elif key == "labels":
                labels = _unique(" ".join(str(label).split()) for label in raw or [])
                if len(labels) > MAX_LABELS:
                    raise BoardValidationError(f"A task has at most {MAX_LABELS} labels")
                if any(len(label) > MAX_LABEL_LENGTH for label in labels):
                    raise BoardValidationError(
                        f"Labels are limited to {MAX_LABEL_LENGTH} characters"
                    )
                values[key] = labels
            elif key == "assignee_ids":
                assignees = _unique(str(user) for user in raw or [])
                if len(assignees) > MAX_ASSIGNEES:
                    raise BoardValidationError(f"A task has at most {MAX_ASSIGNEES} assignees")
                if assignees:
                    outside = set(assignees) - await self._members.member_ids(workspace_id)
                    if outside:
                        raise BoardAssigneeError(
                            "Assignees must be members of the workspace: "
                            + ", ".join(sorted(outside))
                        )
                values[key] = assignees
        return values

    def _tracked_changes(
        self, before: Task, after: Task, user_id: str, now: datetime
    ) -> list[ActivityEntry]:
        entries: list[ActivityEntry] = []
        if before.stage != after.stage:
            entries.append(
                self._activity(before, user_id, ACTIVITY_STAGE, before.stage, after.stage, now=now)
            )
        if before.assignee_ids != after.assignee_ids:
            entries.append(
                self._activity(
                    before,
                    user_id,
                    ACTIVITY_ASSIGNEES,
                    list(before.assignee_ids),
                    list(after.assignee_ids),
                    now=now,
                )
            )
        if before.iteration_id != after.iteration_id:
            entries.append(
                self._activity(
                    before,
                    user_id,
                    ACTIVITY_ITERATION,
                    before.iteration_id,
                    after.iteration_id,
                    now=now,
                )
            )
        return entries

    @staticmethod
    def _activity(
        task: Task,
        user_id: str,
        field: str,
        old_value: Any = None,
        new_value: Any = None,
        *,
        now: datetime,
    ) -> ActivityEntry:
        return ActivityEntry(
            id=_new_id(),
            workspace_id=task.workspace_id,
            task_id=task.id,
            actor_id=user_id,
            field=field,
            old_value=old_value,
            new_value=new_value,
            created_at=now,
        )


def _unique(values: Iterable[str]) -> tuple[str, ...]:
    """Non-empty values, first occurrence kept, order preserved."""
    return tuple(dict.fromkeys(v for v in values if v))


def _int_in(raw: Any, name: str, low: int, high: int) -> int:
    try:
        value = int(raw)
    except (TypeError, ValueError):
        raise BoardValidationError(f"{name} must be a number") from None
    if not low <= value <= high:
        raise BoardValidationError(f"{name} must be between {low} and {high}")
    return value


def _slug(label: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", label.lower()).strip("_")[:24] or "item"


def _clean_choices(raw: Any, noun: str, previous: Iterable[Choice]) -> tuple[Choice, ...]:
    """Ordered stages or priorities. Entries without a key get one from their label."""
    if not isinstance(raw, (list, tuple)) or not raw:
        raise BoardValidationError(f"Keep at least one {noun}")
    if len(raw) > MAX_CHOICES:
        raise BoardValidationError(f"Up to {MAX_CHOICES} {noun} options")
    known = {c.key for c in previous}
    choices: list[Choice] = []
    for item in raw:
        data = item if isinstance(item, Mapping) else vars(item)
        label = " ".join(str(data.get("label") or "").split())
        if not label or len(label) > MAX_CHOICE_LABEL_LENGTH:
            raise BoardValidationError(
                f"Every {noun} needs a name of up to {MAX_CHOICE_LABEL_LENGTH} characters"
            )
        color = str(data.get("color") or "slate")
        if color not in PALETTE:
            raise BoardValidationError(f"Unknown color: {color}")
        key = str(data.get("key") or "")
        if key and key not in known:
            raise BoardValidationError(f"Unknown {noun}: {key}")
        if not key:
            base = _slug(label)
            key, n = base, 2
            taken = known | {c.key for c in choices}
            while key in taken:
                key, n = f"{base}_{n}", n + 1
        if any(c.key == key for c in choices):
            raise BoardValidationError(f"{noun.capitalize()} {key} is listed twice")
        choices.append(Choice(key=key, label=label, color=color))
    return tuple(choices)
