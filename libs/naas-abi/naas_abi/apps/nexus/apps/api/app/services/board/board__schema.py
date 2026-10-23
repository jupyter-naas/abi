"""Workspace project board: weekly iterations, tasks, comments and activity.

An iteration is one ISO week (Monday through Sunday) of a workspace, keyed by
its Monday, so a week has at most one iteration and "the current iteration" is
whatever week the caller's today falls in. The caller sends its own date: the
week boundary follows the user's timezone, not the server's.

A task without an iteration sits in the backlog. Stages are fixed and ordered;
custom stages are out of scope. Changes to a task's stage, assignees,
iteration and archive state are recorded as activity.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Any

STAGES: tuple[str, ...] = ("inbox", "ready", "in_progress", "on_hold", "review", "done")
DEFAULT_STAGE = "inbox"
DONE_STAGE = "done"
PRIORITIES: tuple[str, ...] = ("urgent", "high", "medium", "low")

MAX_TITLE_LENGTH = 300
MAX_CONTENT_LENGTH = 20_000
MAX_PROJECT_LENGTH = 120
MAX_LABEL_LENGTH = 40
MAX_LABELS = 20
MAX_ASSIGNEES = 50
MAX_GOAL_LENGTH = 200
MAX_COMMENT_LENGTH = 5_000

# Activity ``field`` values.
ACTIVITY_CREATED = "created"
ACTIVITY_STAGE = "stage"
ACTIVITY_ASSIGNEES = "assignees"
ACTIVITY_ITERATION = "iteration"
ACTIVITY_ARCHIVED = "archived"

# Task fields a client may change, besides archiving (its own route).
EDITABLE_TASK_FIELDS: frozenset[str] = frozenset(
    {
        "title",
        "content",
        "stage",
        "iteration_id",
        "project",
        "priority",
        "due_date",
        "labels",
        "assignee_ids",
    }
)


class BoardError(Exception):
    """Base error of the board domain."""


class BoardNotFoundError(BoardError):
    """Iteration or task missing, or not in this workspace."""


class BoardValidationError(BoardError):
    """A field outside what the board accepts."""


class BoardAssigneeError(BoardValidationError):
    """An assignee who is not a member of the workspace."""


def week_start(day: date) -> date:
    """Monday of the ISO week ``day`` falls in."""
    return day - timedelta(days=day.weekday())


def iso_week_label(start: date) -> str:
    year, week, _ = start.isocalendar()
    return f"{year}-W{week:02d}"


@dataclass(frozen=True)
class Iteration:
    id: str
    workspace_id: str
    start_date: date
    goal: str = ""
    created_by: str | None = None
    created_at: datetime | None = None
    updated_by: str | None = None
    updated_at: datetime | None = None

    @property
    def end_date(self) -> date:
        return self.start_date + timedelta(days=6)

    @property
    def iso_week(self) -> str:
        return iso_week_label(self.start_date)


@dataclass(frozen=True)
class Task:
    id: str
    workspace_id: str
    title: str
    content: str = ""
    stage: str = DEFAULT_STAGE
    iteration_id: str | None = None
    project: str = ""
    priority: str | None = None
    due_date: date | None = None
    labels: tuple[str, ...] = ()
    assignee_ids: tuple[str, ...] = ()
    archived_at: datetime | None = None
    created_by: str | None = None
    created_at: datetime | None = None
    updated_by: str | None = None
    updated_at: datetime | None = None

    @property
    def archived(self) -> bool:
        return self.archived_at is not None


@dataclass(frozen=True)
class Comment:
    id: str
    workspace_id: str
    task_id: str
    author_id: str | None
    body: str
    created_at: datetime


@dataclass(frozen=True)
class ActivityEntry:
    id: str
    workspace_id: str
    task_id: str
    actor_id: str | None
    field: str
    old_value: Any = None
    new_value: Any = None
    created_at: datetime | None = None


@dataclass(frozen=True)
class CarryOverResult:
    iteration: Iteration
    moved: list[Task] = field(default_factory=list)
