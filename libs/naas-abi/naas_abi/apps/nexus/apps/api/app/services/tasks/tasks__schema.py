"""Workspace tasks: iterations, tasks, comments, activity and settings.

An iteration is a run of whole weeks of a workspace (one week by default,
Monday through Sunday), keyed by its first day. Iterations never overlap, so
"the current iteration" is whichever one the caller's today falls in. The
caller sends its own date: boundaries follow the user's timezone, not the
server's.

Each workspace's settings set the iteration length and start weekday, the
stages (Inbox and Done are fixed; custom ones go between), the priorities and
the suggested labels. A task without an iteration sits in the backlog.
Every change to a task, its deletion and its comments are recorded as events:
the task's history, and the workspace feed shown in the sidebar.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Any

# System stages: every workspace has them, first and last. They can be renamed.
INBOX_STAGE = "inbox"
DONE_STAGE = "done"
DEFAULT_STAGE = INBOX_STAGE

# Colors a stage or priority may use (the UI maps each to theme-aware classes).
PALETTE: tuple[str, ...] = (
    "slate",
    "blue",
    "amber",
    "purple",
    "cyan",
    "green",
    "red",
    "orange",
    "yellow",
    "pink",
)

MIN_ITERATION_WEEKS = 1
MAX_ITERATION_WEEKS = 4
MAX_CHOICES = 12
MAX_CHOICE_LABEL_LENGTH = 40
MAX_SUGGESTED_LABELS = 30
# Monday of ISO week 1 of 2024: weekly iterations line up with ISO weeks.
DEFAULT_ITERATION_ANCHOR = date(2024, 1, 1)

MAX_TITLE_LENGTH = 300
MAX_CONTENT_LENGTH = 20_000
MAX_LABEL_LENGTH = 40
MAX_LABELS = 20
MAX_ASSIGNEES = 50
MAX_GOAL_LENGTH = 200
MAX_COMMENT_LENGTH = 5_000
MAX_GITHUB_ISSUE_URL_LENGTH = 500

# Activity ``field`` values: what an event records.
ACTIVITY_CREATED = "created"
ACTIVITY_TITLE = "title"
ACTIVITY_CONTENT = "content"
ACTIVITY_STAGE = "stage"
ACTIVITY_ASSIGNEES = "assignees"
ACTIVITY_PRIORITY = "priority"
ACTIVITY_DUE_DATE = "due_date"
ACTIVITY_LABELS = "labels"
ACTIVITY_GITHUB_ISSUE = "github_issue"
ACTIVITY_ITERATION = "iteration"
ACTIVITY_ARCHIVED = "archived"
ACTIVITY_DELETED = "deleted"
ACTIVITY_COMMENT_ADDED = "comment_added"
ACTIVITY_COMMENT_REPLIED = "comment_replied"
ACTIVITY_COMMENT_REMOVED = "comment_removed"

# Every event kind, in the order the settings list them.
ACTIVITY_KINDS: tuple[str, ...] = (
    ACTIVITY_CREATED,
    ACTIVITY_TITLE,
    ACTIVITY_CONTENT,
    ACTIVITY_STAGE,
    ACTIVITY_ASSIGNEES,
    ACTIVITY_PRIORITY,
    ACTIVITY_DUE_DATE,
    ACTIVITY_LABELS,
    ACTIVITY_GITHUB_ISSUE,
    ACTIVITY_ITERATION,
    ACTIVITY_ARCHIVED,
    ACTIVITY_DELETED,
    ACTIVITY_COMMENT_ADDED,
    ACTIVITY_COMMENT_REPLIED,
    ACTIVITY_COMMENT_REMOVED,
)

# Sidebar feed: how many events it shows.
MIN_FEED_LIMIT = 5
MAX_FEED_LIMIT = 100
DEFAULT_FEED_LIMIT = 20
# Comment text quoted in an event.
COMMENT_EXCERPT_LENGTH = 120

# Task fields a client may change, besides archiving (its own route).
EDITABLE_TASK_FIELDS: frozenset[str] = frozenset(
    {
        "title",
        "content",
        "stage",
        "iteration_id",
        "priority",
        "due_date",
        "labels",
        "assignee_ids",
        "github_issue_url",
    }
)


class TasksError(Exception):
    """Base error of the tasks domain."""


class TasksNotFoundError(TasksError):
    """Iteration or task missing, or not in this workspace."""


class TasksValidationError(TasksError):
    """A field outside what the tasks settings accept."""


class TasksAssigneeError(TasksValidationError):
    """An assignee who is not a member of the workspace."""


class TasksForbiddenError(TasksError):
    """An action the caller's role does not allow (removing someone else's comment)."""


def week_start(day: date, start_day: int = 0) -> date:
    """First day (``start_day``: 0 = Monday … 6 = Sunday) of the week ``day`` is in."""
    return day - timedelta(days=(day.weekday() - start_day) % 7)


def iso_week_label(start: date, end: date | None = None) -> str:
    """ "2026-W43", or "2026-W43–W44" for an iteration spanning several weeks."""
    year, week, _ = start.isocalendar()
    label = f"{year}-W{week:02d}"
    if end is not None and end.isocalendar()[:2] != (year, week):
        end_year, end_week, _ = end.isocalendar()
        label += f"–W{end_week:02d}" if end_year == year else f"–{end_year}-W{end_week:02d}"
    return label


@dataclass(frozen=True)
class Choice:
    """A stage or a priority: stable key, display label, palette color."""

    key: str
    label: str
    color: str


DEFAULT_STAGES: tuple[Choice, ...] = (
    Choice("inbox", "Inbox", "slate"),
    Choice("ready", "Ready", "blue"),
    Choice("in_progress", "In progress", "amber"),
    Choice("on_hold", "On hold", "purple"),
    Choice("review", "Review", "cyan"),
    Choice("done", "Done", "green"),
)
DEFAULT_PRIORITIES: tuple[Choice, ...] = (
    Choice("urgent", "Urgent", "red"),
    Choice("high", "High", "orange"),
    Choice("medium", "Medium", "yellow"),
    Choice("low", "Low", "slate"),
)
DEFAULT_SUGGESTED_LABELS: tuple[str, ...] = (
    "Feature",
    "Bug",
    "Data",
    "Model",
    "Research",
    "Chore",
)


@dataclass(frozen=True)
class TasksSettings:
    """A workspace's tasks configuration. Workspaces without one use these defaults."""

    iteration_weeks: int = 1
    # 0 = Monday … 6 = Sunday.
    iteration_start_day: int = 0
    # Iterations repeat every ``iteration_weeks`` from this day (a start weekday).
    iteration_anchor: date = DEFAULT_ITERATION_ANCHOR
    stages: tuple[Choice, ...] = DEFAULT_STAGES
    priorities: tuple[Choice, ...] = DEFAULT_PRIORITIES
    # Stage of a task created in an iteration without an explicit stage.
    default_stage: str = "ready"
    suggested_labels: tuple[str, ...] = DEFAULT_SUGGESTED_LABELS
    # Sidebar activity feed: shown or not, which event kinds, how many events.
    feed_enabled: bool = True
    feed_events: tuple[str, ...] = ACTIVITY_KINDS
    feed_limit: int = DEFAULT_FEED_LIMIT
    updated_by: str | None = None
    updated_at: datetime | None = None

    @property
    def stage_keys(self) -> tuple[str, ...]:
        return tuple(s.key for s in self.stages)

    @property
    def priority_keys(self) -> tuple[str, ...]:
        return tuple(p.key for p in self.priorities)

    def period(self, day: date) -> tuple[date, date]:
        """First and last day of the iteration period ``day`` falls in."""
        length = 7 * self.iteration_weeks
        offset = (day - self.iteration_anchor).days // length
        start = self.iteration_anchor + timedelta(days=offset * length)
        return start, start + timedelta(days=length - 1)


@dataclass(frozen=True)
class Iteration:
    id: str
    workspace_id: str
    start_date: date
    # Last day, inclusive. Iterations made before settings existed span one week.
    end_date: date = None  # type: ignore[assignment]
    goal: str = ""
    created_by: str | None = None
    created_at: datetime | None = None
    updated_by: str | None = None
    updated_at: datetime | None = None

    def __post_init__(self) -> None:
        if self.end_date is None:
            object.__setattr__(self, "end_date", self.start_date + timedelta(days=6))

    def contains(self, day: date) -> bool:
        return self.start_date <= day <= self.end_date

    @property
    def iso_week(self) -> str:
        return iso_week_label(self.start_date, self.end_date)


@dataclass(frozen=True)
class Task:
    id: str
    workspace_id: str
    title: str
    content: str = ""
    stage: str = DEFAULT_STAGE
    iteration_id: str | None = None
    priority: str | None = None
    due_date: date | None = None
    labels: tuple[str, ...] = ()
    assignee_ids: tuple[str, ...] = ()
    # The GitHub issue the task tracks, or empty.
    github_issue_url: str = ""
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
    # The comment this one replies to (one level: replies to a reply join its thread).
    parent_id: str | None = None


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
    # The task's title when it happened: the feed names deleted tasks too.
    task_title: str = ""


@dataclass(frozen=True)
class CarryOverResult:
    iteration: Iteration
    moved: list[Task] = field(default_factory=list)
