"""Module jobs as a platform super admin sees them: definitions, schedules and runs.

Definitions come from engine modules and NATS discovery (``JobCatalog``). A
workflow is a job with ``kind="workflow"``, JSON Schemas for its input and output
and a journal of steps (``StepStore``) that a run's detail carries. Runs are
the records job hosts write to the Document Service (``JobRunStore``): one per
trigger message, updated on retries. Triggering and cancelling go through
``JobControl`` (NATS) and are audited by ``JobsAdminService`` before they happen.
``JobQueue`` reads how many triggers wait in each job's JetStream consumer.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Literal, Protocol

Location = Literal["engine", "remote"]

ACTIVE_STATUSES = ("RUNNING", "RETRYING")
# SKIPPED: the handler had nothing to do (``ctx.skip``); job hosts keep these
# briefly. Lists and overviews leave them out unless asked; never a failure.
SKIPPED = "SKIPPED"
TERMINAL_STATUSES = ("SUCCEEDED", SKIPPED, "FAILED", "TIMED_OUT", "CANCELLED")
FAILED_STATUSES = ("FAILED", "TIMED_OUT")
LISTED_STATUSES = ("QUEUED", *ACTIVE_STATUSES, "SUCCEEDED", "FAILED", "TIMED_OUT", "CANCELLED")


class JobNotFound(Exception):
    def __init__(self, module_id: str, job: str, noun: str = "job") -> None:
        super().__init__(f"No {noun} {job!r} in module {module_id!r}")
        self.module_id = module_id
        self.job = job


class RunNotFound(Exception):
    def __init__(self, module_id: str, run_id: str) -> None:
        super().__init__(f"No run {run_id!r} in module {module_id!r}")
        self.module_id = module_id
        self.run_id = run_id


class WorkflowNotFound(JobNotFound):
    """The job exists under another kind, or not at all."""

    def __init__(self, module_id: str, name: str) -> None:
        super().__init__(module_id, name, "workflow")


@dataclass(frozen=True)
class SchemaIssue:
    """One way an input does not match its schema: where (a JSON pointer) and why."""

    path: str
    message: str


class InvalidInput(Exception):
    def __init__(self, issues: Sequence[SchemaIssue]) -> None:
        super().__init__("The input does not match the workflow's input schema")
        self.issues = tuple(issues)


class RunNotCancellable(Exception):
    def __init__(self, run_id: str, status: str) -> None:
        super().__init__(f"Run {run_id!r} is {status}, not running")
        self.run_id = run_id
        self.status = status


@dataclass(frozen=True)
class TriggerSpec:
    """A Cron, Every or OnEvent trigger: ``spec`` is the expression, interval or subject."""

    kind: str  # cron | every | event
    spec: str
    time_zone: str = ""
    # Cron and Every: the JSON object each tick carries as the run's payload.
    input: dict[str, Any] | None = None


@dataclass(frozen=True)
class JobDefinition:
    module_id: str
    name: str
    description: str
    location: Location
    triggers: tuple[TriggerSpec, ...] = ()
    max_concurrency: int = 1
    max_attempts: int = 1
    timeout_seconds: float | None = None
    # Remote jobs: how many live instances declare it.
    instances: int = 1
    kind: str = "job"  # job | workflow
    # Workflows: JSON Schema objects, None when the module did not declare one.
    input_schema: dict[str, Any] | None = None
    output_schema: dict[str, Any] | None = None

    @property
    def key(self) -> str:
        return f"{self.module_id}/{self.name}"

    @property
    def is_workflow(self) -> bool:
        return self.kind == "workflow"


@dataclass(frozen=True)
class RunTrigger:
    kind: str  # schedule | manual | event
    scheduler: str = ""


@dataclass(frozen=True)
class JobRun:
    """A run record. ``payload``, ``result`` and ``logs`` are the detail fields."""

    module_id: str
    job: str
    run_id: str
    status: str
    attempt: int = 1
    max_attempts: int = 1
    trigger: RunTrigger = field(default_factory=lambda: RunTrigger("manual"))
    fired_at: str | None = None
    started_at: str | None = None
    finished_at: str | None = None
    instance: str = ""
    error: str = ""
    trace_id: str = ""
    payload: Any = None
    result: Any = None
    logs: tuple[str, ...] = ()
    skip_reason: str = ""

    @property
    def key(self) -> str:
        return f"{self.module_id}/{self.run_id}"

    @property
    def duration_ms(self) -> int | None:
        if not self.started_at or not self.finished_at:
            return None
        try:
            started = datetime.fromisoformat(self.started_at)
            finished = datetime.fromisoformat(self.finished_at)
        except ValueError:
            return None
        return max(0, round((finished - started).total_seconds() * 1000))


@dataclass(frozen=True)
class ChildRun:
    """The run of another workflow a ``call`` step started: its run record is
    ``module_id``'s under ``run_id``."""

    module_id: str
    workflow: str
    run_id: str

    @property
    def key(self) -> str:
        return f"{self.module_id}/{self.run_id}"


@dataclass(frozen=True)
class RunStep:
    """One checkpointed step of a workflow run (its result is never loaded)."""

    key: str
    kind: str  # step | call
    status: str  # RUNNING | SUCCEEDED | FAILED | CANCELLED
    attempt: int = 1
    started_at: str | None = None
    finished_at: str | None = None
    duration_ms: int | None = None
    error: str = ""
    child: ChildRun | None = None
    result_bytes: int | None = None


@dataclass(frozen=True)
class WorkflowDetail:
    """What a workflow run adds to a job run: its steps in start order, and
    whether more steps exist than were read."""

    steps: tuple[RunStep, ...] = ()
    truncated: bool = False


class JobCatalog(Protocol):
    """Job definitions from one source (``source`` names it in ``sources``)."""

    source: str

    async def list_jobs(self) -> list[JobDefinition]:
        """Every job this source knows. Raises SourceUnavailable."""
        ...


class JobRunStore(Protocol):
    """Run records, newest first by ``started_at``. Raises SourceUnavailable."""

    async def list_runs(
        self,
        module_ids: Sequence[str],
        *,
        job: str | None = None,
        statuses: Sequence[str] | None = None,
        trigger_kind: str | None = None,
        before: str | None = None,
        limit: int = 50,
    ) -> list[JobRun]: ...

    async def recent(self, module_id: str, job: str, limit: int = 20) -> list[JobRun]: ...

    async def running(self, module_id: str) -> list[JobRun]:
        """Records RUNNING or RETRYING."""
        ...

    async def get_run(self, module_id: str, run_id: str) -> JobRun:
        """Raises RunNotFound."""
        ...


class StepStore(Protocol):
    async def journal(
        self, module_id: str, run_id: str, fired_at: str | None = None
    ) -> WorkflowDetail:
        """A run's steps in start order; none for a run without a journal. With
        ``fired_at`` (the run's), steps written for another trigger that reused
        the run id are left out. Raises SourceUnavailable."""
        ...


class InputValidator(Protocol):
    def validate(self, schema: dict[str, Any], payload: Any) -> list[SchemaIssue]:
        """Why ``payload`` does not match ``schema`` (empty: it does). A schema the
        validator cannot use accepts everything."""
        ...


class JobControl(Protocol):
    async def trigger(
        self,
        module_id: str,
        job: str,
        payload: dict[str, Any],
        idempotency_key: str | None = None,
    ) -> str:
        """Publish a manual trigger; the run id the host will record. A repeated
        ``idempotency_key`` within the broker's duplicate window gives the first
        trigger's run id. Raises SourceUnavailable."""
        ...

    async def cancel(self, module_id: str, job: str, run_id: str) -> None:
        """Ask the host running ``run_id`` to stop (cooperative)."""
        ...


class JobQueue(Protocol):
    async def depth(self, module_id: str, job: str) -> tuple[int, int] | None:
        """(queued, in flight) of the job's consumer, or None when it does not exist."""
        ...


# --- views -----------------------------------------------------------------------------


@dataclass(frozen=True)
class TriggerView:
    trigger: TriggerSpec
    summary: str
    next_at: str | None


@dataclass(frozen=True)
class JobView:
    definition: JobDefinition
    triggers: tuple[TriggerView, ...]
    next_at: str | None
    queued: int | None
    in_flight: int | None
    running: int
    last_run: JobRun | None
    recent: tuple[JobRun, ...]
    # The latest run that had nothing to do (not in ``recent``).
    last_skipped: JobRun | None = None


@dataclass(frozen=True)
class JobsOverview:
    project: str
    jobs: tuple[JobView, ...]
    sources: dict[str, Any]


@dataclass(frozen=True)
class RunView:
    """A run with its trace link and, for a workflow, its steps."""

    run: JobRun
    trace_url: str | None = None
    workflow: WorkflowDetail | None = None


@dataclass(frozen=True)
class RunsPage:
    runs: tuple[JobRun, ...]
    next: str | None


@dataclass(frozen=True)
class Failures:
    """Runs that failed or timed out since ``since``, newest first; ``more``
    when there were more than were read."""

    since: str
    runs: tuple[JobRun, ...]
    more: bool = False

    @property
    def count(self) -> int:
        return len(self.runs)
