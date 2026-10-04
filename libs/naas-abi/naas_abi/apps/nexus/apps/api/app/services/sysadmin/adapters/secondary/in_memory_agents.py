"""In-memory agent runs and control, for tests and the dev console."""

from __future__ import annotations

from collections.abc import Sequence

from naas_abi.apps.nexus.apps.api.app.services.sysadmin.agents import (
    EVENT_PREVIEW,
    MAX_EVENTS,
    AgentEvent,
    AgentRun,
    AgentRunNotFound,
)
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.port import SourceUnavailable


class InMemoryAgentRunStore:
    def __init__(
        self,
        runs: list[AgentRun] | None = None,
        events: dict[tuple[str, str], list[tuple[str, str]]] | None = None,
        *,
        fail: str = "",
    ) -> None:
        self.runs = list(runs or [])
        self._events = dict(events or {})
        self.fail = fail

    def _check(self) -> None:
        if self.fail:
            raise SourceUnavailable("agent_runs", self.fail)

    async def list_runs(
        self,
        module_ids: Sequence[str],
        *,
        agent: str | None = None,
        statuses: Sequence[str] | None = None,
        before: str | None = None,
        limit: int = 50,
    ) -> list[AgentRun]:
        self._check()
        found = [
            r
            for r in self.runs
            if r.module_id in module_ids
            and (agent is None or r.agent == agent)
            and (not statuses or r.status in statuses)
            and (before is None or (r.submitted_at or "") < before)
        ]
        found.sort(key=lambda r: r.submitted_at or "", reverse=True)
        return found[:limit]

    async def get_run(self, module_id: str, run_id: str) -> AgentRun:
        self._check()
        for run in self.runs:
            if run.module_id == module_id and run.run_id == run_id:
                return run
        raise AgentRunNotFound(module_id, run_id)

    async def events(
        self, module_id: str, run_id: str, *, limit: int = MAX_EVENTS
    ) -> list[AgentEvent]:
        await self.get_run(module_id, run_id)
        return [
            AgentEvent(i, event, text[:EVENT_PREVIEW], len(text) > EVENT_PREVIEW)
            for i, (event, text) in enumerate(self._events.get((module_id, run_id), [])[:limit], 1)
        ]


class InMemoryAgentControl:
    def __init__(self, *, fail: str = "") -> None:
        self.cancelled: list[str] = []
        self.fail = fail

    async def cancel(self, run: AgentRun) -> None:
        if self.fail:
            raise SourceUnavailable("agents", self.fail)
        self.cancelled.append(run.key)
