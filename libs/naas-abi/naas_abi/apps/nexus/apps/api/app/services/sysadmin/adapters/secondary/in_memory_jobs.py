"""In-memory job catalog, run store, control and queue: test doubles for jobs.py."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from naas_abi.apps.nexus.apps.api.app.services.sysadmin.jobs import (
    ACTIVE_STATUSES,
    JobDefinition,
    JobRun,
    RunNotFound,
)
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.port import SourceUnavailable


def _newest_first(runs: list[JobRun]) -> list[JobRun]:
    return sorted(runs, key=lambda r: r.started_at or "", reverse=True)


class InMemoryJobCatalog:
    def __init__(
        self, jobs: list[JobDefinition], *, source: str = "engine", fail: str = ""
    ) -> None:
        self.jobs = list(jobs)
        self.source = source
        self.fail = fail

    async def list_jobs(self) -> list[JobDefinition]:
        if self.fail:
            raise SourceUnavailable(self.source, self.fail)
        return list(self.jobs)


class InMemoryJobRunStore:
    def __init__(self, runs: list[JobRun] | None = None, *, fail: str = "") -> None:
        self.runs = list(runs or [])
        self.fail = fail

    def _check(self) -> None:
        if self.fail:
            raise SourceUnavailable("runs", self.fail)

    async def list_runs(
        self,
        module_ids: Sequence[str],
        *,
        job: str | None = None,
        statuses: Sequence[str] | None = None,
        trigger_kind: str | None = None,
        before: str | None = None,
        limit: int = 50,
    ) -> list[JobRun]:
        self._check()
        found = [
            r
            for r in self.runs
            if r.module_id in module_ids
            and (job is None or r.job == job)
            and (not statuses or r.status in statuses)
            and (trigger_kind is None or r.trigger.kind == trigger_kind)
            and (before is None or (r.started_at or "") < before)
        ]
        return _newest_first(found)[:limit]

    async def recent(self, module_id: str, job: str, limit: int = 20) -> list[JobRun]:
        return await self.list_runs([module_id], job=job, limit=limit)

    async def running(self, module_id: str) -> list[JobRun]:
        return await self.list_runs([module_id], statuses=list(ACTIVE_STATUSES), limit=1000)

    async def get_run(self, module_id: str, run_id: str) -> JobRun:
        self._check()
        for run in self.runs:
            if run.module_id == module_id and run.run_id == run_id:
                return run
        raise RunNotFound(module_id, run_id)


class InMemoryJobControl:
    def __init__(self, *, fail: str = "", first_sequence: int = 100) -> None:
        self.triggered: list[tuple[str, str, dict[str, Any]]] = []
        self.cancelled: list[tuple[str, str, str]] = []
        self.fail = fail
        self._sequence = first_sequence

    async def trigger(self, module_id: str, job: str, payload: dict[str, Any]) -> str:
        if self.fail:
            raise SourceUnavailable("jobs", self.fail)
        self.triggered.append((module_id, job, payload))
        self._sequence += 1
        return f"{job}:{self._sequence}"

    async def cancel(self, module_id: str, job: str, run_id: str) -> None:
        if self.fail:
            raise SourceUnavailable("jobs", self.fail)
        self.cancelled.append((module_id, job, run_id))


class InMemoryJobQueue:
    def __init__(
        self, depths: dict[tuple[str, str], tuple[int, int]] | None = None, *, fail: str = ""
    ) -> None:
        self.depths = dict(depths or {})
        self.fail = fail

    async def depth(self, module_id: str, job: str) -> tuple[int, int] | None:
        if self.fail:
            raise SourceUnavailable("queue", self.fail)
        return self.depths.get((module_id, job))
