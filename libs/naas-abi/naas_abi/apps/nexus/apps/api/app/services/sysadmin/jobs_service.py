"""Use cases over module jobs: the overview, run history, and audited actions.

The overview degrades per source (engine catalog, discovery, run store, queue)
and reports ``sources``. Triggering and cancelling are audited like data
changes (``run_audited``): a ``requested`` record first, nothing happens if it
cannot be written, then ``succeeded`` or ``failed``.
"""

from __future__ import annotations

import asyncio
import json
import time
from collections.abc import Callable, Sequence
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from typing import Any

from naas_abi.apps.nexus.apps.api.app.services.sysadmin.jobs import (
    ACTIVE_STATUSES,
    FAILED_STATUSES,
    LISTED_STATUSES,
    SKIPPED,
    Failures,
    InputValidator,
    InvalidInput,
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
    RunNotFound,
    RunsPage,
    RunView,
    StepStore,
    TriggerView,
    WorkflowDetail,
    WorkflowNotFound,
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
# A workflow run's result as the Jobs tab shows it: above this many bytes of JSON
# it is cut to a text preview (the run record keeps all of it).
RESULT_PREVIEW_BYTES = 16 * 1024
# How long a job's kind is remembered: an open run is read every second or so, and
# each read would list every catalog again.
KIND_TTL_SECONDS = 30.0
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
        steps: StepStore | SourceUnavailable | None = None,
        validator: InputValidator | None = None,
    ) -> None:
        self._catalogs = list(catalogs)
        self._runs = runs
        self._control = control
        self._queue = queue
        self._audit = audit
        self.project = project
        self._trace_ui_url = trace_ui_url.rstrip("/") if trace_ui_url else None
        self._clock = clock
        self._steps = steps
        self._validator = validator
        self._kinds: dict[tuple[str, str], tuple[bool, float]] = {}

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

    async def definitions(self) -> tuple[list[JobDefinition], dict[str, SourceStatus]]:
        """Every job and workflow, and how each source answered."""
        sources: dict[str, SourceStatus] = {}
        return await self._definitions(sources), sources

    async def _find(self, module_id: str, job: str) -> JobDefinition:
        for definition in await self._definitions({}):
            if definition.module_id == module_id and definition.name == job:
                return definition
        raise JobNotFound(module_id, job)

    async def find_workflow(self, module_id: str, name: str) -> JobDefinition:
        """The workflow ``name`` of ``module_id``; WorkflowNotFound for a plain job."""
        try:
            definition = await self._find(module_id, name)
        except JobNotFound:
            raise WorkflowNotFound(module_id, name) from None
        if not definition.is_workflow:
            raise WorkflowNotFound(module_id, name)
        return definition

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

    async def journal(self, run: JobRun) -> WorkflowDetail:
        """The steps of ``run``'s journal; none when the journal cannot be read
        (the run's own record still answers)."""
        if self._steps is None or isinstance(self._steps, SourceUnavailable):
            return WorkflowDetail()
        try:
            return await self._steps.journal(run.module_id, run.run_id, run.fired_at)
        except SourceUnavailable:
            return WorkflowDetail()

    async def is_workflow_run(self, run: JobRun) -> bool:
        """Whether ``run`` is a workflow's: by its job's definition, else (the module
        is not registered right now) by having a journal."""
        key = (run.module_id, run.job)
        known = self._kinds.get(key)
        if known and known[1] > time.monotonic():
            return known[0]
        for definition in await self._definitions({}):
            if definition.module_id == run.module_id and definition.name == run.job:
                self._kinds[key] = (definition.is_workflow, time.monotonic() + KIND_TTL_SECONDS)
                return definition.is_workflow
        return bool((await self.journal(run)).steps)

    async def run(self, module_id: str, run_id: str, *, preview: bool = True) -> RunView:
        """One run with its trace link and, for a workflow, its steps. With
        ``preview`` a workflow's result over ``RESULT_PREVIEW_BYTES`` is cut."""
        found = await self._store().get_run(module_id, run_id)
        trace_url = (
            f"{self._trace_ui_url}/trace/{found.trace_id}"
            if self._trace_ui_url and found.trace_id
            else None
        )
        if not await self.is_workflow_run(found):
            return RunView(found, trace_url)
        if preview:
            found = replace(found, result=preview_result(found.result))
        return RunView(found, trace_url, await self.journal(found))

    # --- actions (audited) ----------------------------------------------------------------

    def _controller(self) -> JobControl:
        if isinstance(self._control, SourceUnavailable):
            raise self._control
        return self._control

    async def trigger(
        self,
        actor_id: str,
        module_id: str,
        job: str,
        payload: dict[str, Any],
        *,
        via: str = "user",
        idempotency_key: str | None = None,
        workflow_only: bool = False,
    ) -> str:
        """Start a run. ``actor_id`` is a user id, empty for ``via="api_key"``. A
        workflow's payload is checked against its input schema first (InvalidInput,
        nothing audited, nothing sent); ``workflow_only`` refuses a plain job."""
        definition = (
            await self.find_workflow(module_id, job)
            if workflow_only
            else await self._find(module_id, job)
        )
        if definition.is_workflow and definition.input_schema and self._validator:
            issues = self._validator.validate(definition.input_schema, payload)
            if issues:
                raise InvalidInput(issues)
        control = self._controller()
        action = AdminAction(actor_id, "jobs", "trigger", f"{module_id}/{job}", via)
        return await run_audited(
            self._audit,
            action,
            lambda: control.trigger(module_id, job, payload, idempotency_key),
        )

    async def cancel(
        self,
        actor_id: str,
        module_id: str,
        run_id: str,
        *,
        via: str = "user",
        workflow_only: bool = False,
    ) -> None:
        found = await self._store().get_run(module_id, run_id)
        if workflow_only and not await self.is_workflow_run(found):
            raise RunNotFound(module_id, run_id)
        if found.status not in ACTIVE_STATUSES:
            raise RunNotCancellable(run_id, found.status)
        control = self._controller()
        action = AdminAction(actor_id, "jobs", "cancel", f"{module_id}/{run_id}", via)
        await run_audited(self._audit, action, lambda: control.cancel(module_id, found.job, run_id))


def preview_result(result: Any) -> Any:
    """``result``, or for a large one ``{"truncated": true, "bytes", "preview"}``."""
    if result is None:
        return None
    try:
        text = json.dumps(result, default=str)
    except (TypeError, ValueError):
        text = str(result)
    size = len(text.encode())
    if size <= RESULT_PREVIEW_BYTES:
        return result
    return {"truncated": True, "bytes": size, "preview": text[:RESULT_PREVIEW_BYTES]}
