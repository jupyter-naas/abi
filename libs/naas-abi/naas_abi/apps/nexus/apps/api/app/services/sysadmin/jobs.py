"""Module jobs as a platform super admin sees them: definitions, schedules and runs.

Definitions come from engine modules and NATS discovery (``JobCatalog``). Runs are
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
TERMINAL_STATUSES = ("SUCCEEDED", "FAILED", "TIMED_OUT", "CANCELLED")


class JobNotFound(Exception):
    def __init__(self, module_id: str, job: str) -> None:
        super().__init__(f"No job {job!r} in module {module_id!r}")
        self.module_id = module_id
        self.job = job


class RunNotFound(Exception):
    def __init__(self, module_id: str, run_id: str) -> None:
        super().__init__(f"No run {run_id!r} in module {module_id!r}")
        self.module_id = module_id
        self.run_id = run_id


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

    @property
    def key(self) -> str:
        return f"{self.module_id}/{self.name}"


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


class JobControl(Protocol):
    async def trigger(self, module_id: str, job: str, payload: dict[str, Any]) -> str:
        """Publish a manual trigger; the run id the host will record. Raises SourceUnavailable."""
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


@dataclass(frozen=True)
class JobsOverview:
    project: str
    jobs: tuple[JobView, ...]
    sources: dict[str, Any]


@dataclass(frozen=True)
class RunsPage:
    runs: tuple[JobRun, ...]
    next: str | None
