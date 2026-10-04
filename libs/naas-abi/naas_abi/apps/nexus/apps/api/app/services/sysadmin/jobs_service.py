"""Use cases over module jobs: the overview, run history, and audited actions.

The overview degrades per source (engine catalog, discovery, run store, queue)
and reports ``sources``. Triggering and cancelling are audited like data
changes (``run_audited``): a ``requested`` record first, nothing happens if it
cannot be written, then ``succeeded`` or ``failed``.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Sequence
from datetime import UTC, datetime, timedelta
from typing import Any

from naas_abi.apps.nexus.apps.api.app.services.sysadmin.jobs import (
    ACTIVE_STATUSES,
    FAILED_STATUSES,
    LISTED_STATUSES,
    SKIPPED,
    Failures,
    JobCatalog,
    JobControl,
    JobDefinition,
    JobNotFound,
    JobQueue,
    JobRun,
    JobRunStore,
    JobsOverview,
    JobView,
    RunNotCancellable,
    RunsPage,
    TriggerView,
)
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.jobs_schedule import (
    describe,
    next_cron,
    next_every,
)
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.port import (
    SourceStatus,
    SourceUnavailable,
)
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.resources import (
    AdminAction,
    AdminAuditLog,
)
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.resources_service import (
    run_audited,
)

RECENT_RUNS = 20
# Failures read for the notification badge, and how far back by default.
MAX_FAILURES = 200
FAILURES_WINDOW = timedelta(days=1)


def _parse(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def _iso(value: datetime | None) -> str | None:
    return value.astimezone(UTC).isoformat() if value else None


class JobsAdminService:
    def __init__(
        self,
        *,
        catalogs: Sequence[JobCatalog | SourceUnavailable],
        runs: JobRunStore | SourceUnavailable,
        control: JobControl | SourceUnavailable,
        queue: JobQueue | SourceUnavailable,
        audit: AdminAuditLog,
        project: str,
        trace_ui_url: str | None = None,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._catalogs = list(catalogs)
        self._runs = runs
        self._control = control
        self._queue = queue
        self._audit = audit
        self.project = project
        self._trace_ui_url = trace_ui_url.rstrip("/") if trace_ui_url else None
        self._clock = clock

    # --- definitions ---------------------------------------------------------------------

    async def _definitions(self, sources: dict[str, SourceStatus]) -> list[JobDefinition]:
        found: list[JobDefinition] = []
        for catalog in self._catalogs:
            if isinstance(catalog, SourceUnavailable):
                sources[catalog.source] = SourceStatus(False, catalog.reason)
                continue
            try:
                found.extend(await catalog.list_jobs())
                sources[catalog.source] = SourceStatus(True)
            except SourceUnavailable as exc:
                sources[catalog.source] = SourceStatus(False, exc.reason)
        unique = {d.key: d for d in found}
        return sorted(unique.values(), key=lambda d: (d.module_id, d.name))

    async def _find(self, module_id: str, job: str) -> JobDefinition:
        for definition in await self._definitions({}):
            if definition.module_id == module_id and definition.name == job:
                return definition
        raise JobNotFound(module_id, job)

    # --- overview ------------------------------------------------------------------------

    def _trigger_views(
        self, definition: JobDefinition, recent: Sequence[JobRun], now: datetime
    ) -> tuple[TriggerView, ...]:
        # When the last scheduled tick fired; runs recorded before ``fired_at``
        # existed only have their start, a close enough anchor for an interval.
        last_scheduled = max(
            (
                fired
                for r in recent
                if r.trigger.kind == "schedule"
                and (fired := _parse(r.fired_at) or _parse(r.started_at)) is not None
            ),
            default=None,
        )
        views = []
        for trigger in definition.triggers:
            if trigger.kind == "cron":
                next_at = next_cron(trigger.spec, trigger.time_zone, now)
            elif trigger.kind == "every":
                next_at = next_every(trigger.spec, last_scheduled, now=now)
            else:
                next_at = None
            views.append(TriggerView(trigger, describe(trigger), _iso(next_at)))
        return tuple(views)

    async def overview(self) -> JobsOverview:
        sources: dict[str, SourceStatus] = {}
        definitions = await self._definitions(sources)
        now = self._clock()

        recent: dict[str, list[JobRun]] = {d.key: [] for d in definitions}
        skipped: dict[str, JobRun | None] = {d.key: None for d in definitions}
        running: dict[str, int] = {d.key: 0 for d in definitions}
        if isinstance(self._runs, SourceUnavailable):
            sources["runs"] = SourceStatus(False, self._runs.reason)
        else:
            store = self._runs
            try:
                recents = await asyncio.gather(
                    *(
                        store.list_runs(
                            [d.module_id],
                            job=d.name,
                            statuses=list(LISTED_STATUSES),
                            limit=RECENT_RUNS,
                        )
                        for d in definitions
                    )
                )
                lasts = await asyncio.gather(
                    *(
                        store.list_runs([d.module_id], job=d.name, statuses=[SKIPPED], limit=1)
                        for d in definitions
                    )
                )
                modules = sorted({d.module_id for d in definitions})
                actives = await asyncio.gather(*(store.running(m) for m in modules))
                for definition, runs, last in zip(definitions, recents, lasts, strict=True):
                    recent[definition.key] = runs
                    skipped[definition.key] = last[0] if last else None
                for active in actives:
                    for r in active:
                        key = f"{r.module_id}/{r.job}"
                        if key in running:
                            running[key] += 1
                sources["runs"] = SourceStatus(True)
            except SourceUnavailable as exc:
                sources["runs"] = SourceStatus(False, exc.reason)
                recent = {d.key: [] for d in definitions}

        depths: dict[str, tuple[int, int] | None] = {d.key: None for d in definitions}
        if isinstance(self._queue, SourceUnavailable):
            sources["queue"] = SourceStatus(False, self._queue.reason)
        else:
            queue = self._queue
            try:
                found = await asyncio.gather(
                    *(queue.depth(d.module_id, d.name) for d in definitions)
                )
                depths = {d.key: depth for d, depth in zip(definitions, found, strict=True)}
                sources["queue"] = SourceStatus(True)
            except SourceUnavailable as exc:
                sources["queue"] = SourceStatus(False, exc.reason)

        views = []
        for definition in definitions:
            runs = recent[definition.key]
            triggers = self._trigger_views(definition, runs, now)
            ticks = [t.next_at for t in triggers if t.next_at]
            depth = depths[definition.key]
            views.append(
                JobView(
                    definition=definition,
                    triggers=triggers,
                    next_at=min(ticks) if ticks else None,
                    queued=depth[0] if depth else None,
                    in_flight=depth[1] if depth else None,
                    running=running[definition.key],
                    last_run=runs[0] if runs else None,
                    recent=tuple(runs),
                    last_skipped=skipped[definition.key],
                )
            )
        return JobsOverview(self.project, tuple(views), sources)

    # --- runs ----------------------------------------------------------------------------

    def _store(self) -> JobRunStore:
        if isinstance(self._runs, SourceUnavailable):
            raise self._runs
        return self._runs

    async def runs(
        self,
        *,
        module: str | None = None,
        job: str | None = None,
        statuses: Sequence[str] | None = None,
        trigger_kind: str | None = None,
        before: str | None = None,
        limit: int = 50,
        include_skipped: bool = False,
    ) -> RunsPage:
        """Runs, newest first. Without ``statuses``, runs that had nothing to do
        (SKIPPED) are left out unless ``include_skipped``."""
        store = self._store()
        if not statuses and not include_skipped:
            statuses = list(LISTED_STATUSES)
        if module:
            module_ids = [module]
        else:
            module_ids = sorted({d.module_id for d in await self._definitions({})})
        found = await store.list_runs(
            module_ids,
            job=job,
            statuses=statuses,
            trigger_kind=trigger_kind,
            before=before,
            limit=limit,
        )
        next_cursor = found[-1].started_at if len(found) == limit and found else None
        return RunsPage(tuple(found), next_cursor)

    async def failures(self, *, since: str | None = None) -> Failures:
        """Runs that failed or timed out since ``since`` (default: the last day),
        newest first: what the Jobs tab's notification counts."""
        start = _parse(since) or self._clock() - FAILURES_WINDOW
        store = self._store()
        module_ids = sorted({d.module_id for d in await self._definitions({})})
        found = await store.list_runs(
            module_ids, statuses=list(FAILED_STATUSES), limit=MAX_FAILURES
        )
        recent = tuple(r for r in found if (_parse(r.started_at) or start) >= start)
        capped = len(found) == MAX_FAILURES and len(recent) == len(found)
        return Failures(_iso(start) or "", recent, more=capped)

    async def run(self, module_id: str, run_id: str) -> tuple[JobRun, str | None]:
        found = await self._store().get_run(module_id, run_id)
        trace_url = (
            f"{self._trace_ui_url}/trace/{found.trace_id}"
            if self._trace_ui_url and found.trace_id
            else None
        )
        return found, trace_url

    # --- actions (audited) ----------------------------------------------------------------

    def _controller(self) -> JobControl:
        if isinstance(self._control, SourceUnavailable):
            raise self._control
        return self._control

    async def trigger(
        self, actor_id: str, module_id: str, job: str, payload: dict[str, Any]
    ) -> str:
        await self._find(module_id, job)
        control = self._controller()
        action = AdminAction(actor_id, "jobs", "trigger", f"{module_id}/{job}")
        return await run_audited(
            self._audit, action, lambda: control.trigger(module_id, job, payload)
        )

    async def cancel(self, actor_id: str, module_id: str, run_id: str) -> None:
        found = await self._store().get_run(module_id, run_id)
        if found.status not in ACTIVE_STATUSES:
            raise RunNotCancellable(run_id, found.status)
        control = self._controller()
        action = AdminAction(actor_id, "jobs", "cancel", f"{module_id}/{run_id}")
        await run_audited(self._audit, action, lambda: control.cancel(module_id, found.job, run_id))
