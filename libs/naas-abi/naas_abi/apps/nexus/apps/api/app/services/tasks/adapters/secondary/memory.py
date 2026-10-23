from __future__ import annotations

from datetime import date

from naas_abi.apps.nexus.apps.api.app.services.tasks.port import (
    TasksMemberDirectoryPort,
    TasksStorePort,
)
from naas_abi.apps.nexus.apps.api.app.services.tasks.tasks__schema import (
    ActivityEntry,
    Comment,
    Iteration,
    Task,
    TasksSettings,
)


class InMemoryTasksStore(TasksStorePort):
    """For tests and local runs without Postgres."""

    def __init__(self) -> None:
        self._iterations: dict[str, Iteration] = {}
        self._tasks: dict[str, Task] = {}
        self._comments: list[Comment] = []
        self._activity: list[ActivityEntry] = []
        self._settings: dict[str, TasksSettings] = {}

    async def get_settings(self, workspace_id: str) -> TasksSettings | None:
        return self._settings.get(workspace_id)

    async def save_settings(self, workspace_id: str, settings: TasksSettings) -> None:
        self._settings[workspace_id] = settings

    async def list_iterations(self, workspace_id: str) -> list[Iteration]:
        return [i for i in self._iterations.values() if i.workspace_id == workspace_id]

    async def get_iteration(self, workspace_id: str, iteration_id: str) -> Iteration | None:
        iteration = self._iterations.get(iteration_id)
        return iteration if iteration and iteration.workspace_id == workspace_id else None

    async def get_iteration_by_start(self, workspace_id: str, start: date) -> Iteration | None:
        return next(
            (
                i
                for i in self._iterations.values()
                if i.workspace_id == workspace_id and i.start_date == start
            ),
            None,
        )

    async def save_iteration(self, iteration: Iteration) -> Iteration:
        existing = await self.get_iteration_by_start(iteration.workspace_id, iteration.start_date)
        if existing is not None and existing.id != iteration.id:
            return existing
        self._iterations[iteration.id] = iteration
        return iteration

    async def list_tasks(
        self,
        workspace_id: str,
        *,
        iteration_id: str | None,
        include_archived: bool,
    ) -> list[Task]:
        return [
            t
            for t in self._tasks.values()
            if t.workspace_id == workspace_id
            and t.iteration_id == iteration_id
            and (include_archived or not t.archived)
        ]

    async def list_workspace_tasks(
        self, workspace_id: str, *, include_archived: bool
    ) -> list[Task]:
        return [
            t
            for t in self._tasks.values()
            if t.workspace_id == workspace_id and (include_archived or not t.archived)
        ]

    async def get_task(self, workspace_id: str, task_id: str) -> Task | None:
        task = self._tasks.get(task_id)
        return task if task and task.workspace_id == workspace_id else None

    async def save_task(self, task: Task) -> None:
        self._tasks[task.id] = task

    async def delete_task(self, workspace_id: str, task_id: str) -> bool:
        if await self.get_task(workspace_id, task_id) is None:
            return False
        del self._tasks[task_id]
        self._comments = [c for c in self._comments if c.task_id != task_id]
        self._activity = [a for a in self._activity if a.task_id != task_id]
        return True

    async def list_comments(self, workspace_id: str, task_id: str) -> list[Comment]:
        return [
            c for c in self._comments if c.workspace_id == workspace_id and c.task_id == task_id
        ]

    async def add_comment(self, comment: Comment) -> None:
        self._comments.append(comment)

    async def list_activity(self, workspace_id: str, task_id: str) -> list[ActivityEntry]:
        return [
            a for a in self._activity if a.workspace_id == workspace_id and a.task_id == task_id
        ]

    async def add_activity(self, entries: list[ActivityEntry]) -> None:
        self._activity.extend(entries)


class InMemoryTasksMemberDirectory(TasksMemberDirectoryPort):
    def __init__(self, members: dict[str, set[str]] | None = None) -> None:
        self._members = members or {}

    async def member_ids(self, workspace_id: str) -> set[str]:
        return set(self._members.get(workspace_id, set()))
