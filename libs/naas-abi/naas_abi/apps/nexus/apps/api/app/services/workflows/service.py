"""Use cases of the workflows REST API, over the jobs admin service.

Starts and cancels are audited by it before anything happens (service ``jobs``,
operations ``trigger`` / ``cancel``, with how the caller authenticated), so a
start from a script is on the same record as one from the Jobs tab. An input that
does not match the workflow's schema is refused first (``InvalidInput``): no
trigger, no audit record.
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta
from typing import Any

from naas_abi.apps.nexus.apps.api.app.services.sysadmin.jobs import (
    JobRun,
    RunNotFound,
    WorkflowDetail,
)
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.jobs_service import JobsAdminService
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.port import SourceUnavailable
from naas_abi.apps.nexus.apps.api.app.services.workflows.workflows import (
    MAX_WAIT_SECONDS,
    Caller,
    Started,
    WorkflowList,
    WorkflowRunView,
    check_idempotency_key,
)

# Waiting reads the run record: quickly at first, then about once a second.
POLL_FIRST_SECONDS = 0.2
POLL_MAX_SECONDS = 1.0
# Run ids reuse stream sequences: after the jobs stream is recreated, a new start can
# get the id of an old run whose record is still stored. A record fired before the
# start, by more than the clocks can disagree, is that old run, not this one. With an
# idempotency key the start may be a repeat of one inside JetStream's duplicate
# window (2 minutes), which answers with the first start's run.
CLOCK_SKEW = timedelta(seconds=30)
DUPLICATE_WINDOW = timedelta(minutes=2)


class WorkflowsService:
    def __init__(
        self,
        jobs: JobsAdminService,
        *,
        sleep: Callable[[float], Awaitable[Any]] = asyncio.sleep,
        monotonic: Callable[[], float] = time.monotonic,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._jobs = jobs
        self._sleep = sleep
        self._monotonic = monotonic
        self._clock = clock

    async def list(self) -> WorkflowList:
        definitions, sources = await self._jobs.definitions()
        return WorkflowList(tuple(d for d in definitions if d.is_workflow), sources)

    async def _view(self, module_id: str, run_id: str) -> WorkflowRunView:
        """The run's record and steps; ``RunNotFound`` when no host has one (a pruned
        run, a mistyped id, a plain job's run). A run just started has no record
        until a host takes it: ``start`` reports it as QUEUED itself."""
        found = await self._jobs.run(module_id, run_id, preview=False)
        if found.workflow is None:  # a plain job's run
            raise RunNotFound(module_id, run_id)
        return WorkflowRunView(found.run, found.workflow)

    async def status(self, module_id: str, run_id: str) -> WorkflowRunView:
        return await self._view(module_id, run_id)

    async def start(
        self,
        caller: Caller,
        module_id: str,
        name: str,
        payload: dict[str, Any],
        *,
        wait: float | None = None,
        idempotency_key: str | None = None,
    ) -> Started:
        """Start a run of ``name``. With ``wait`` (seconds, at most MAX_WAIT_SECONDS)
        the call returns once the run ended or the time is up, whichever is first;
        the run goes on either way."""
        key = check_idempotency_key(idempotency_key)
        earliest = self._clock() - CLOCK_SKEW - (DUPLICATE_WINDOW if key else timedelta(0))
        run_id = await self._jobs.trigger(
            caller.user_id,
            module_id,
            name,
            payload,
            via=caller.via,
            idempotency_key=key,
            workflow_only=True,
        )
        queued = WorkflowRunView(JobRun(module_id, name, run_id, "QUEUED"), WorkflowDetail())
        if not wait or wait <= 0:
            return Started(run_id, await self._peek(module_id, run_id, queued, earliest))
        return Started(
            run_id,
            await self._wait(module_id, run_id, min(wait, MAX_WAIT_SECONDS), queued, earliest),
        )

    async def _peek(
        self, module_id: str, run_id: str, queued: WorkflowRunView, earliest: datetime
    ) -> WorkflowRunView:
        """The run's record if a host has one already (a repeated idempotency key
        answers with the first start's run, maybe long finished), else ``queued``."""
        try:
            found = await self._jobs.run(module_id, run_id, preview=False)
        except (SourceUnavailable, RunNotFound):
            return queued
        if not _fired_since(found.run.fired_at, earliest):
            return queued
        return WorkflowRunView(found.run, found.workflow or WorkflowDetail())

    async def _wait(
        self,
        module_id: str,
        run_id: str,
        seconds: float,
        last: WorkflowRunView,
        earliest: datetime,
    ) -> WorkflowRunView:
        deadline = self._monotonic() + seconds
        delay = POLL_FIRST_SECONDS
        while True:
            try:
                view = await self._view(module_id, run_id)
            except (SourceUnavailable, RunNotFound):
                pass  # the run is started: report what we last knew, not an error
            else:
                if _fired_since(view.run.fired_at, earliest):
                    last = view  # else an old run under the same id: still queued
            if last.finished:
                return last
            remaining = deadline - self._monotonic()
            if remaining <= 0:
                return last
            await self._sleep(min(delay, remaining))
            delay = min(delay * 1.5, POLL_MAX_SECONDS)

    async def cancel(self, caller: Caller, module_id: str, run_id: str) -> None:
        await self._jobs.cancel(
            caller.user_id, module_id, run_id, via=caller.via, workflow_only=True
        )


def _fired_since(fired_at: str | None, earliest: datetime) -> bool:
    """Whether a record fired at ``fired_at`` can be the run just started. A record
    without a readable ``fired_at`` (written before it existed) counts as one."""
    if not fired_at:
        return True
    try:
        stamp = datetime.fromisoformat(fired_at)
    except ValueError:
        return True
    if stamp.tzinfo is None:
        stamp = stamp.replace(tzinfo=UTC)
    return stamp >= earliest
