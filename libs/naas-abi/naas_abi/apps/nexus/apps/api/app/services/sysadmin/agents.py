"""Remote agent runs as a platform super admin sees them: list, inspect, cancel.

SDK agent hosts keep one record per invocation in their module's document
namespace (``agent_runs_collection(project)``) and its events in
``agent_events_collection(project)`` (``naas_abi_sdk.agent_host``). Runs are
read from there (``AgentRunStore``); cancelling goes to the host that owns the
run over NATS (``AgentControl``), which lets a platform administrator cancel
any caller's run, and is audited by ``AgentsAdminService`` before it happens.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

ACTIVE_STATUSES = ("ACCEPTED", "RUNNING", "CANCELLING")
TERMINAL_STATUSES = ("SUCCEEDED", "FAILED", "CANCELLED", "TIMED_OUT")
# Events a run detail shows, and the characters of each event's text kept.
MAX_EVENTS = 64
EVENT_PREVIEW = 1000


class AgentRunNotFound(Exception):
    def __init__(self, module_id: str, run_id: str) -> None:
        super().__init__(f"No agent run {run_id!r} in module {module_id!r}")
        self.module_id = module_id
        self.run_id = run_id


class AgentRunNotCancellable(Exception):
    def __init__(self, run_id: str, status: str) -> None:
        super().__init__(f"Agent run {run_id!r} is {status}, not running")
        self.run_id = run_id
        self.status = status


@dataclass(frozen=True)
class AgentRun:
    """One invocation record. ``run_id`` is its document id in the module."""

    module_id: str
    run_id: str
    agent: str
    invocation_id: str
    status: str
    thread_id: str = ""
    caller: str = ""
    owner: str = ""
    submitted_at: str | None = None
    finished_at: str | None = None
    error_code: str = ""
    error_message: str = ""
    trace_id: str = ""
    events: int = 0

    @property
    def key(self) -> str:
        return f"{self.module_id}/{self.run_id}"

    @property
    def duration_ms(self) -> int | None:
        if not self.submitted_at or not self.finished_at:
            return None
        try:
            started = datetime.fromisoformat(self.submitted_at)
            finished = datetime.fromisoformat(self.finished_at)
        except ValueError:
            return None
        return max(0, round((finished - started).total_seconds() * 1000))


@dataclass(frozen=True)
class AgentEvent:
    """One event a run emitted: its kind and the start of its text."""

    sequence: int
    event: str
    preview: str
    truncated: bool = False


@dataclass(frozen=True)
class AgentRunsPage:
    runs: tuple[AgentRun, ...]
    next: str | None


class AgentRunStore(Protocol):
    """Run records, newest first by ``submitted_at``. Raises SourceUnavailable."""

    async def list_runs(
        self,
        module_ids: Sequence[str],
        *,
        agent: str | None = None,
        statuses: Sequence[str] | None = None,
        before: str | None = None,
        limit: int = 50,
    ) -> list[AgentRun]: ...

    async def get_run(self, module_id: str, run_id: str) -> AgentRun:
        """Raises AgentRunNotFound."""
        ...

    async def events(
        self, module_id: str, run_id: str, *, limit: int = MAX_EVENTS
    ) -> list[AgentEvent]:
        """The run's first ``limit`` events, in order. Raises AgentRunNotFound."""
        ...


class AgentControl(Protocol):
    async def cancel(self, run: AgentRun) -> None:
        """Ask the host that owns ``run`` to stop it. Raises SourceUnavailable."""
        ...
