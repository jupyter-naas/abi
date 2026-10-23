"""Secondary ports of the board: where board records live, who may be assigned."""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date

from naas_abi.apps.nexus.apps.api.app.services.board.board__schema import (
    ActivityEntry,
    BoardSettings,
    Comment,
    Iteration,
    Task,
)


class BoardStorePort(ABC):
    @abstractmethod
    async def get_settings(self, workspace_id: str) -> BoardSettings | None:
        """The workspace's saved settings, or None when it uses the defaults."""

    @abstractmethod
    async def save_settings(self, workspace_id: str, settings: BoardSettings) -> None:
        """Insert or replace the workspace's settings."""

    @abstractmethod
    async def list_iterations(self, workspace_id: str) -> list[Iteration]:
        """Every iteration of the workspace, in any order."""

    @abstractmethod
    async def get_iteration(self, workspace_id: str, iteration_id: str) -> Iteration | None:
        """The iteration, or None when missing or in another workspace."""

    @abstractmethod
    async def get_iteration_by_start(self, workspace_id: str, start: date) -> Iteration | None:
        """The workspace's iteration starting on that Monday, if any."""

    @abstractmethod
    async def save_iteration(self, iteration: Iteration) -> Iteration:
        """Insert or update. Returns the stored iteration: when another one
        already starts on the same Monday, that one wins and is returned."""

    @abstractmethod
    async def list_tasks(
        self,
        workspace_id: str,
        *,
        iteration_id: str | None,
        include_archived: bool,
    ) -> list[Task]:
        """Tasks of one iteration, or of the backlog when ``iteration_id`` is None."""

    @abstractmethod
    async def list_workspace_tasks(
        self, workspace_id: str, *, include_archived: bool
    ) -> list[Task]:
        """Every task of the workspace, scheduled or not."""

    @abstractmethod
    async def get_task(self, workspace_id: str, task_id: str) -> Task | None:
        """The task, or None when missing or in another workspace."""

    @abstractmethod
    async def save_task(self, task: Task) -> None:
        """Insert or replace the task with the same id."""

    @abstractmethod
    async def delete_task(self, workspace_id: str, task_id: str) -> bool:
        """Remove a task with its comments and activity. False when nothing was stored."""

    @abstractmethod
    async def list_comments(self, workspace_id: str, task_id: str) -> list[Comment]:
        """Comments of a task, oldest first."""

    @abstractmethod
    async def add_comment(self, comment: Comment) -> None:
        """Store a new comment."""

    @abstractmethod
    async def list_activity(self, workspace_id: str, task_id: str) -> list[ActivityEntry]:
        """Activity of a task, oldest first."""

    @abstractmethod
    async def add_activity(self, entries: list[ActivityEntry]) -> None:
        """Store new activity entries."""


class BoardMemberDirectoryPort(ABC):
    @abstractmethod
    async def member_ids(self, workspace_id: str) -> set[str]:
        """Users who may be assigned in this workspace: its members, explicit
        or inherited from the organization."""
