"""TasksAgent tools for Nexus Tasks (workspace tasks in weekly iterations).

Every tool goes through the same ``TasksService`` as ``/api/tasks`` and asks
IAM the same ``nexus`` actions for the user the turn acts for (the ``tasks``
feature first, then the action: ``services/iam/catalog/tasks.py``). Opening a
call reads the board (``ListTasks``); each tool then asks for what it does. The
service runs on the tool's own DB session (tools run on another event loop
than the API, so they must not use its pool).

The task open in the Tasks drawer (``?task=<id>``) arrives as the open feature
resource (kind ``task``), so the tools default to it.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import date
from typing import Any

from langchain_core.tools import BaseTool, tool

from naas_abi.agents.feature.context import active_feature_resource_id
from naas_abi.agents.feature.runtime import (
    clip,
    guarded,
    jsonable,
    matches,
    run_db,
    tool_context,
)

TASK_RESOURCE_KIND = "task"
# Tools that change tasks, comments or settings. The web mirrors this list
# (isTasksWriteTool) to reload the Tasks board after a chat turn.
TASK_WRITE_TOOLS = (
    "create_task",
    "update_task",
    "archive_task",
    "delete_task",
    "add_task_comment",
    "delete_task_comment",
    "carry_over_unfinished_tasks",
    "update_tasks_settings",
)
SCOPES = ("current", "last", "next", "inbox", "backlog")
_FEATURE = "Tasks"
_MAX_LIST = 200
_MAX_CONTENT = 4000


@dataclass
class TasksCall:
    """One tool call: the service on the tool's session, and who is asking."""

    service: Any
    workspace_id: str
    user_id: str
    members: list[Any]
    today: date

    async def may(self, action: str, id: str = "-") -> bool:
        """Whether IAM lets the user perform ``action`` (``id``: the task or
        iteration, ``-`` for the board)."""
        return await _refusal(self.user_id, self.workspace_id, action, id) is None

    async def require(self, action: str, id: str = "-") -> None:
        """Raise ``TasksForbiddenError`` (the model reads why) unless IAM lets
        the user perform ``action``: the check its route makes."""
        from naas_abi.apps.nexus.apps.api.app.services.tasks.tasks__schema import (
            TasksForbiddenError,
        )

        refused = await _refusal(self.user_id, self.workspace_id, action, id)
        if refused is not None:
            raise TasksForbiddenError(refused)

    def member_name(self, user_id: str | None) -> str:
        member = next((m for m in self.members if m.user_id == user_id), None)
        return (member and (member.name or member.email)) or "Former member"


# ---------------------------------------------------------------------------
# Session and access
# ---------------------------------------------------------------------------


def _shared_session(db: Any) -> Callable[[], Any]:
    """A session factory that hands out the tool's one session (left open)."""

    @asynccontextmanager
    async def factory() -> Any:
        yield db

    return factory


async def _refusal(
    user_id: str, workspace_id: str, action: str, id: str = "-"
) -> str | None:
    """Why IAM refuses the user ``action`` (what its route answers), or None."""
    from naas_abi.apps.nexus.apps.api.app.services.iam.authz import AUTHZ, AuthzDenied

    try:
        await AUTHZ.require(action, user=user_id, workspace=workspace_id, id=id)
    except AuthzDenied as exc:
        return str(exc.detail)
    return None


def _today() -> date:
    return date.today()


async def _board(db: Any, workspace_id: str) -> tuple[Any, list[Any]]:
    """The service on the tool's session, and the workspace's members."""
    from naas_abi.apps.nexus.apps.api.app.services.tasks.adapters.secondary.postgres import (
        PostgresTasksMemberDirectory,
        PostgresTasksStore,
    )
    from naas_abi.apps.nexus.apps.api.app.services.tasks.service import TasksService
    from naas_abi.apps.nexus.apps.api.app.services.workspaces.adapters.secondary.postgres import (
        WorkspaceSecondaryAdapterPostgres,
    )

    session = _shared_session(db)
    members = await WorkspaceSecondaryAdapterPostgres(db=db).list_workspace_members(
        workspace_id=workspace_id
    )
    service = TasksService(
        PostgresTasksStore(session), PostgresTasksMemberDirectory(session)
    )
    return service, members


async def _open_call(
    db: Any, user_id: str, workspace_id: str
) -> TasksCall | dict[str, str]:
    # Every tool reads the board (names, iterations, members) before acting.
    refused = await _refusal(user_id, workspace_id, "ListTasks")
    if refused is not None:
        return {"error": refused}
    service, members = await _board(db, workspace_id)
    return TasksCall(
        service=service,
        workspace_id=workspace_id,
        user_id=user_id,
        members=members,
        today=_today(),
    )


def _execute(op: Callable[[TasksCall], Awaitable[Any]]) -> Any:
    """Run ``op`` for this turn's user and workspace, or return why it cannot."""
    ctx = tool_context()
    if isinstance(ctx, dict):
        return ctx
    user_id, workspace_id = ctx

    async def _run(db: Any) -> Any:
        call = await _open_call(db, user_id, workspace_id)
        if isinstance(call, dict):
            return call
        return await op(call)

    return run_db(_run)


def _tasks_error(exc: Exception) -> dict[str, str] | None:
    """Domain errors are the user's to read (validation, not found, forbidden)."""
    from naas_abi.apps.nexus.apps.api.app.services.tasks.tasks__schema import TasksError

    return {"error": str(exc)} if isinstance(exc, TasksError) else None


def _call(op: Callable[[TasksCall], Awaitable[Any]]) -> Any:
    async def _safe(call: TasksCall) -> Any:
        try:
            return await op(call)
        except Exception as exc:
            known = _tasks_error(exc)
            if known is None:
                raise
            return known

    return guarded(_FEATURE, lambda: _execute(_safe))


# ---------------------------------------------------------------------------
# Lookups
# ---------------------------------------------------------------------------


async def _scope_iteration_id(call: TasksCall, scope: str) -> str | None:
    """The iteration of current / last / next, created when missing."""
    await call.require("CreateTaskIteration")
    current = await call.service.ensure_iteration(
        call.workspace_id, call.today, user_id=call.user_id
    )
    if scope == "current":
        return current.id
    direction = -1 if scope == "last" else 1
    other = await call.service.adjacent_iteration(
        call.workspace_id, current.id, direction, user_id=call.user_id
    )
    return other.id


async def _scope_by_iteration(call: TasksCall) -> dict[str, str]:
    """Iteration id -> current / last / next, for those that exist (reading never creates one)."""
    ordered = sorted(
        await call.service.list_iterations(call.workspace_id),
        key=lambda i: i.start_date,
    )
    index = next((n for n, i in enumerate(ordered) if i.contains(call.today)), None)
    if index is None:
        return {}
    named = {ordered[index].id: "current"}
    if index > 0:
        named[ordered[index - 1].id] = "last"
    if index + 1 < len(ordered):
        named[ordered[index + 1].id] = "next"
    return named


def _scope_of(task: Any, scopes: dict[str, str]) -> str:
    from naas_abi.apps.nexus.apps.api.app.services.tasks.tasks__schema import (
        INBOX_STAGE,
    )

    if task.stage == INBOX_STAGE:
        return "inbox"
    if task.iteration_id is None:
        return "backlog"
    return scopes.get(task.iteration_id, "another iteration")


def _choice(choices: Any, wanted: str, noun: str) -> str:
    """A stage or priority key from its key or label."""
    needle = wanted.strip().lower()
    for choice in choices:
        if needle in (choice.key.lower(), choice.label.lower()):
            return choice.key
    names = ", ".join(c.label for c in choices)
    raise _validation(f"Unknown {noun} {wanted!r}. Use one of: {names}.")


def _validation(message: str) -> Exception:
    from naas_abi.apps.nexus.apps.api.app.services.tasks.tasks__schema import (
        TasksValidationError,
    )

    return TasksValidationError(message)


def _member_ids(call: TasksCall, people: list[str]) -> list[str]:
    """User ids from names, emails or ids of workspace members."""
    ids: list[str] = []
    for person in people:
        needle = person.strip().lower()
        if not needle:
            continue
        if needle in ("me", "myself", "moi"):
            ids.append(call.user_id)
            continue
        found = [
            m
            for m in call.members
            if needle
            in (m.user_id.lower(), (m.email or "").lower(), (m.name or "").lower())
        ] or [m for m in call.members if needle in (m.name or "").lower()]
        if len(found) != 1:
            hint = "several members match" if found else "no workspace member matches"
            raise _validation(f"{person!r}: {hint}. See list_task_members.")
        ids.append(found[0].user_id)
    return list(dict.fromkeys(ids))


async def _resolve_task(call: TasksCall, wanted: str) -> Any:
    """A task by id or title; defaults to the task open in the drawer."""
    from naas_abi.apps.nexus.apps.api.app.services.tasks.tasks__schema import (
        TasksNotFoundError,
    )

    needle = (wanted or "").strip() or (
        active_feature_resource_id(TASK_RESOURCE_KIND) or ""
    )
    if not needle:
        raise _validation("No task is open. Pass task (its id or title).")
    tasks = await call.service.list_all_tasks(call.workspace_id, include_archived=True)
    lowered = needle.lower()
    exact = [t for t in tasks if t.id == needle or t.title.lower() == lowered]
    found = exact or [t for t in tasks if lowered in t.title.lower()]
    if len(found) == 1:
        return found[0]
    if not found:
        raise TasksNotFoundError(f"No task matches {needle!r}. See list_tasks.")
    titles = "; ".join(f"{t.title} ({t.id})" for t in found[:8])
    raise _validation(f"Several tasks match {needle!r}: {titles}. Pass the id.")


def _task_row(
    call: TasksCall, task: Any, settings: Any, scopes: dict[str, str]
) -> dict[str, Any]:
    from naas_abi.apps.nexus.apps.api.app.services.tasks.tasks__schema import Choice

    def label(choices: tuple[Choice, ...], key: str | None) -> str | None:
        return next((c.label for c in choices if c.key == key), key)

    return {
        "id": task.id,
        "title": task.title,
        "stage": label(settings.stages, task.stage),
        "priority": label(settings.priorities, task.priority),
        "assignees": [call.member_name(i) for i in task.assignee_ids],
        "labels": list(task.labels),
        "due_date": task.due_date.isoformat() if task.due_date else None,
        "scope": _scope_of(task, scopes),
        "github_issue_url": task.github_issue_url or None,
        "archived": task.archived,
        "updated_at": jsonable(task.updated_at),
        "open_in_nexus": f"/workspace/{call.workspace_id}/tasks?task={task.id}",
    }


def _event_row(call: TasksCall, entry: Any) -> dict[str, Any]:
    return {
        "event": entry.field,
        "task": entry.task_title,
        "task_id": entry.task_id,
        "by": call.member_name(entry.actor_id),
        "old": jsonable(entry.old_value),
        "new": jsonable(entry.new_value),
        "at": jsonable(entry.created_at),
    }


async def _fields(
    call: TasksCall,
    settings: Any,
    *,
    title: str | None = None,
    content: str | None = None,
    stage: str | None = None,
    priority: str | None = None,
    due_date: str | None = None,
    labels: list[str] | None = None,
    assignees: list[str] | None = None,
    github_issue_url: str | None = None,
) -> dict[str, Any]:
    """Service fields from tool arguments: None leaves a field, "" clears it."""
    fields: dict[str, Any] = {}
    if title is not None:
        fields["title"] = title
    if content is not None:
        fields["content"] = content
    if stage:
        fields["stage"] = _choice(settings.stages, stage, "stage")
    if priority is not None:
        fields["priority"] = (
            _choice(settings.priorities, priority, "priority")
            if priority.strip()
            else None
        )
    if due_date is not None:
        try:
            fields["due_date"] = (
                date.fromisoformat(due_date.strip()) if due_date.strip() else None
            )
        except ValueError:
            raise _validation("due_date is a YYYY-MM-DD date") from None
    if labels is not None:
        fields["labels"] = labels
    if assignees is not None:
        fields["assignee_ids"] = _member_ids(call, assignees)
    if github_issue_url is not None:
        fields["github_issue_url"] = github_issue_url
    return fields


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------


def tasks_tools() -> list[BaseTool]:
    @tool
    def list_tasks(
        scope: str = "all",
        query: str = "",
        stage: str = "",
        assignee: str = "",
        include_archived: bool = False,
    ) -> Any:
        """Tasks of this workspace. scope: all, current, last, next (iterations),
        inbox or backlog. Filter by query (title, labels), stage, or assignee
        (name, email, or "me"). Each row: id, title, stage, priority,
        assignees, labels, due_date, scope, github_issue_url."""
        wanted_scope = (scope or "all").strip().lower()
        if wanted_scope not in ("all", *SCOPES):
            return {
                "error": f"Unknown scope {scope!r}. Use all or one of {', '.join(SCOPES)}."
            }

        async def op(call: TasksCall) -> Any:
            settings = await call.service.get_settings(call.workspace_id)
            tasks = await call.service.list_all_tasks(
                call.workspace_id, include_archived=include_archived
            )
            stage_key = (
                _choice(settings.stages, stage, "stage") if stage.strip() else None
            )
            assignee_id = _member_ids(call, [assignee])[0] if assignee.strip() else None
            scopes = await _scope_by_iteration(call)
            rows = []
            for task in tasks:
                if stage_key and task.stage != stage_key:
                    continue
                if assignee_id and assignee_id not in task.assignee_ids:
                    continue
                if not matches(query, task.title, *task.labels):
                    continue
                row = _task_row(call, task, settings, scopes)
                if wanted_scope != "all" and row["scope"] != wanted_scope:
                    continue
                rows.append(row)
            return {"total": len(rows), "tasks": rows[:_MAX_LIST]}

        return _call(op)

    @tool
    def get_task(task: str = "") -> Any:
        """One task (id or title) with its content and its comment threads.
        Omit task to use the one open in the Tasks drawer."""

        async def op(call: TasksCall) -> Any:
            found = await _resolve_task(call, task)
            await call.require("ListTaskComments", found.id)
            settings = await call.service.get_settings(call.workspace_id)
            comments = await call.service.list_comments(call.workspace_id, found.id)

            def comment(c: Any) -> dict[str, Any]:
                return {
                    "id": c.id,
                    "by": call.member_name(c.author_id),
                    "body": clip(c.body, 1000),
                    "at": jsonable(c.created_at),
                }

            threads = [
                {
                    **comment(c),
                    "replies": [comment(r) for r in comments if r.parent_id == c.id],
                }
                for c in comments
                if not c.parent_id
            ]
            return {
                **(_task_row(call, found, settings, await _scope_by_iteration(call))),
                "content": clip(found.content, _MAX_CONTENT),
                "created_by": call.member_name(found.created_by),
                "comments": threads,
            }

        return _call(op)

    @tool
    def create_task(
        title: str,
        scope: str = "current",
        stage: str = "",
        content: str = "",
        priority: str = "",
        due_date: str = "",
        labels: list[str] | None = None,
        assignees: list[str] | None = None,
        github_issue_url: str = "",
    ) -> Any:
        """Create a task. scope: current (default), next, last, inbox (for
        triage) or backlog. stage and priority take a name or key from the
        settings; due_date is YYYY-MM-DD; assignees are member names or emails
        ("me" for you); content is Markdown; github_issue_url is
        https://github.com/<owner>/<repo>/issues/<n>."""
        wanted_scope = (scope or "current").strip().lower()
        if wanted_scope not in SCOPES:
            return {
                "error": f"Unknown scope {scope!r}. Use one of {', '.join(SCOPES)}."
            }

        async def op(call: TasksCall) -> Any:
            from naas_abi.apps.nexus.apps.api.app.services.tasks.tasks__schema import (
                INBOX_STAGE,
            )

            await call.require("CreateTask")
            settings = await call.service.get_settings(call.workspace_id)
            fields = await _fields(
                call,
                settings,
                title=title,
                content=content,
                stage=stage,
                priority=priority,
                due_date=due_date,
                labels=labels or [],
                assignees=assignees or [],
                github_issue_url=github_issue_url,
            )
            if wanted_scope == "inbox":
                fields.setdefault("stage", INBOX_STAGE)
                fields["iteration_id"] = None
            elif wanted_scope == "backlog":
                fields.setdefault("stage", settings.default_stage)
                fields["iteration_id"] = None
            else:
                fields["iteration_id"] = await _scope_iteration_id(call, wanted_scope)
            created = await call.service.create_task(
                call.workspace_id, fields, user_id=call.user_id
            )
            return {
                "created": _task_row(
                    call, created, settings, await _scope_by_iteration(call)
                )
            }

        return _call(op)

    @tool
    def update_task(
        task: str = "",
        title: str | None = None,
        content: str | None = None,
        stage: str | None = None,
        priority: str | None = None,
        due_date: str | None = None,
        labels: list[str] | None = None,
        add_labels: list[str] | None = None,
        remove_labels: list[str] | None = None,
        assignees: list[str] | None = None,
        add_assignees: list[str] | None = None,
        remove_assignees: list[str] | None = None,
        github_issue_url: str | None = None,
        scope: str | None = None,
    ) -> Any:
        """Change a task (id or title; omit for the open one). Only the
        arguments you pass change. "" clears priority, due_date or
        github_issue_url. labels / assignees replace the list; add_* and
        remove_* edit it. scope moves the task: current, last, next, inbox or
        backlog. stage moves it between board columns."""

        async def op(call: TasksCall) -> Any:
            from naas_abi.apps.nexus.apps.api.app.services.tasks.tasks__schema import (
                INBOX_STAGE,
            )

            found = await _resolve_task(call, task)
            await call.require("UpdateTask", found.id)
            settings = await call.service.get_settings(call.workspace_id)
            next_labels = list(labels) if labels is not None else list(found.labels)
            next_labels += [
                label for label in add_labels or [] if label not in next_labels
            ]
            removed = {label.lower() for label in remove_labels or []}
            next_labels = [
                label for label in next_labels if label.lower() not in removed
            ]
            people = (
                _member_ids(call, assignees)
                if assignees is not None
                else list(found.assignee_ids)
            )
            people += [
                p for p in _member_ids(call, add_assignees or []) if p not in people
            ]
            gone = set(_member_ids(call, remove_assignees or []))
            people = [p for p in people if p not in gone]

            fields = await _fields(
                call,
                settings,
                title=title,
                content=content,
                stage=stage,
                priority=priority,
                due_date=due_date,
                github_issue_url=github_issue_url,
            )
            if labels is not None or add_labels or remove_labels:
                fields["labels"] = next_labels
            if assignees is not None or add_assignees or remove_assignees:
                fields["assignee_ids"] = people
            if scope:
                wanted = scope.strip().lower()
                if wanted not in SCOPES:
                    return {
                        "error": f"Unknown scope {scope!r}. Use one of {', '.join(SCOPES)}."
                    }
                if wanted == "inbox":
                    fields["stage"] = INBOX_STAGE
                else:
                    if found.stage == INBOX_STAGE and "stage" not in fields:
                        fields["stage"] = settings.default_stage
                    fields["iteration_id"] = (
                        None
                        if wanted == "backlog"
                        else await _scope_iteration_id(call, wanted)
                    )
            if not fields:
                return {"error": "Nothing to change: pass at least one field."}
            updated = await call.service.update_task(
                call.workspace_id, found.id, fields, user_id=call.user_id
            )
            return {
                "updated": _task_row(
                    call, updated, settings, await _scope_by_iteration(call)
                )
            }

        return _call(op)

    @tool
    def archive_task(task: str = "", archived: bool = True) -> Any:
        """Archive a task (archived=True) or restore it (False). Archived tasks
        leave the board but stay recoverable."""

        async def op(call: TasksCall) -> Any:
            found = await _resolve_task(call, task)
            await call.require("UpdateTask", found.id)
            settings = await call.service.get_settings(call.workspace_id)
            updated = await call.service.set_archived(
                call.workspace_id, found.id, archived, user_id=call.user_id
            )
            return {
                "archived" if archived else "restored": _task_row(
                    call, updated, settings, await _scope_by_iteration(call)
                )
            }

        return _call(op)

    @tool
    def delete_task(task: str = "", confirm: bool = False) -> Any:
        """Delete a task with its comments, for everyone (its history stays in
        the activity feed). Ask the user first, then call with confirm=True.
        Prefer archive_task when they may want it back."""

        async def op(call: TasksCall) -> Any:
            found = await _resolve_task(call, task)
            await call.require("DeleteTask", found.id)
            if not confirm:
                return {
                    "needs_confirmation": f"Deleting {found.title!r} cannot be undone. "
                    "Ask the user, then call delete_task with confirm=True."
                }
            await call.service.delete_task(
                call.workspace_id, found.id, user_id=call.user_id
            )
            return {"deleted": {"id": found.id, "title": found.title}}

        return _call(op)

    @tool
    def add_task_comment(body: str, task: str = "", reply_to: str = "") -> Any:
        """Comment on a task (omit task for the open one). reply_to is a comment
        id from get_task: the comment joins that thread."""

        async def op(call: TasksCall) -> Any:
            found = await _resolve_task(call, task)
            await call.require("AddTaskComment", found.id)
            comment = await call.service.add_comment(
                call.workspace_id,
                found.id,
                body,
                user_id=call.user_id,
                parent_id=reply_to.strip() or None,
            )
            return {
                "commented": {
                    "task": found.title,
                    "comment_id": comment.id,
                    "reply_to": comment.parent_id,
                }
            }

        return _call(op)

    @tool
    def delete_task_comment(comment_id: str, task: str = "") -> Any:
        """Remove a comment (and its replies) by id from get_task. You may
        remove your own comments; who moderates (owners and admins by default)
        anyone's."""

        async def op(call: TasksCall) -> Any:
            found = await _resolve_task(call, task)
            await call.require("DeleteTaskComment", found.id)
            await call.service.delete_comment(
                call.workspace_id,
                found.id,
                comment_id.strip(),
                user_id=call.user_id,
                can_moderate=await call.may("ModerateTaskComments", found.id),
            )
            return {"removed": {"task": found.title, "comment_id": comment_id}}

        return _call(op)

    @tool
    def get_tasks_activity(task: str = "", limit: int = 20) -> Any:
        """What happened: one task's history (pass task) or, by default, the
        workspace's latest task events (created, changed, deleted, commented),
        newest first."""

        async def op(call: TasksCall) -> Any:
            count = max(1, min(int(limit or 20), 100))
            if task.strip():
                found = await _resolve_task(call, task)
                await call.require("ListTaskActivity", found.id)
                entries = await call.service.list_activity(call.workspace_id, found.id)
                return {
                    "task": found.title,
                    "events": [_event_row(call, e) for e in entries[-count:]],
                }
            await call.require("ListTaskActivity")
            entries = await call.service.list_recent_activity(
                call.workspace_id, limit=count
            )
            return {"events": [_event_row(call, e) for e in entries]}

        return _call(op)

    @tool
    def carry_over_unfinished_tasks(scope: str = "current") -> Any:
        """Move every task of an iteration (current or last) that is not Done to
        the iteration after it."""
        wanted = (scope or "current").strip().lower()
        if wanted not in ("current", "last"):
            return {"error": "scope is current or last."}

        async def op(call: TasksCall) -> Any:
            iteration_id = await _scope_iteration_id(call, wanted)
            await call.require("CarryOverTasks", iteration_id)
            result = await call.service.carry_over(
                call.workspace_id, iteration_id, user_id=call.user_id
            )
            return {
                "moved": [t.title for t in result.moved],
                "to_iteration": f"{result.iteration.start_date} to {result.iteration.end_date}",
            }

        return _call(op)

    @tool
    def list_task_members() -> Any:
        """Workspace members a task can be assigned to: name, email, role."""

        async def op(call: TasksCall) -> Any:
            return {
                "members": [
                    {
                        "name": m.name,
                        "email": m.email,
                        "role": m.role,
                        "you": m.user_id == call.user_id,
                    }
                    for m in call.members
                ]
            }

        return _call(op)

    @tool
    def get_tasks_settings() -> Any:
        """The tasks settings: iteration length and start day, stages,
        priorities, default stage, suggested labels, activity feed (on/off,
        event kinds, length), and whether you may change them."""

        async def op(call: TasksCall) -> Any:
            await call.require("GetTaskSettings")
            settings = await call.service.get_settings(call.workspace_id)
            out = jsonable(settings)
            out["can_edit"] = await call.may("UpdateTaskSettings")
            return out

        return _call(op)

    @tool
    def update_tasks_settings(
        iteration_weeks: int | None = None,
        iteration_start_day: int | None = None,
        stages: list[dict] | None = None,
        priorities: list[dict] | None = None,
        default_stage: str | None = None,
        suggested_labels: list[str] | None = None,
        feed_enabled: bool | None = None,
        feed_events: list[str] | None = None,
        feed_limit: int | None = None,
    ) -> Any:
        """Change the tasks settings (owners and admins by default). Only what you pass
        changes. stages / priorities are the full ordered list of
        {key, label, color}: keep each existing key, leave key empty for a new
        one; Inbox stays first and Done last. iteration_start_day: 0 = Monday.
        feed_events: event kinds shown in the sidebar feed."""

        async def op(call: TasksCall) -> Any:
            await call.require("UpdateTaskSettings")
            raw = {
                key: value
                for key, value in {
                    "iteration_weeks": iteration_weeks,
                    "iteration_start_day": iteration_start_day,
                    "stages": stages,
                    "priorities": priorities,
                    "default_stage": default_stage,
                    "suggested_labels": suggested_labels,
                    "feed_enabled": feed_enabled,
                    "feed_events": feed_events,
                    "feed_limit": feed_limit,
                }.items()
                if value is not None
            }
            if not raw:
                return {"error": "Nothing to change: pass at least one setting."}
            settings = await call.service.update_settings(
                call.workspace_id, raw, today=call.today, user_id=call.user_id
            )
            return {"saved": jsonable(settings)}

        return _call(op)

    return [
        list_tasks,
        get_task,
        create_task,
        update_task,
        archive_task,
        delete_task,
        add_task_comment,
        delete_task_comment,
        get_tasks_activity,
        carry_over_unfinished_tasks,
        list_task_members,
        get_tasks_settings,
        update_tasks_settings,
    ]
