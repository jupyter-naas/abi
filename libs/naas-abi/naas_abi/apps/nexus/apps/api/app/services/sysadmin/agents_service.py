"""Use cases over remote agent runs: run history, one run, and an audited cancel.

Runs are listed across the modules discovery says host agents (or one module
named by the caller, which needs no discovery). Cancelling is audited like a
data change (``run_audited``): a ``requested`` record first, nothing happens if
it cannot be written, then ``succeeded`` or ``failed``.
"""

from __future__ import annotations

from collections.abc import Sequence

from naas_abi.apps.nexus.apps.api.app.services.sysadmin.agents import (
    AgentControl,
    AgentEvent,
    AgentRun,
    AgentRunNotCancellable,
    AgentRunsPage,
    AgentRunStore,
)
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.port import (
    ModuleRegistry,
    SourceUnavailable,
)
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.resources import (
    AdminAction,
    AdminAuditLog,
)
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.resources_service import (
    run_audited,
)

# A run the host still executes; CANCELLING has been asked already.
CANCELLABLE = ("ACCEPTED", "RUNNING")


class AgentsAdminService:
    def __init__(
        self,
        *,
        registry: ModuleRegistry | SourceUnavailable,
        runs: AgentRunStore | SourceUnavailable,
        control: AgentControl | SourceUnavailable,
        audit: AdminAuditLog,
        trace_ui_url: str | None = None,
    ) -> None:
        self._registry = registry
        self._runs = runs
        self._control = control
        self._audit = audit
        self._trace_ui_url = trace_ui_url.rstrip("/") if trace_ui_url else None

    @staticmethod
    def _ready(source):
        if isinstance(source, SourceUnavailable):
            raise source
        return source

    async def modules(self) -> list[str]:
        """Modules with a live instance that hosts agents. Raises SourceUnavailable."""
        instances = await self._ready(self._registry).list_instances()
        return sorted({i.module_id for i in instances if i.agents})

    async def runs(
        self,
        *,
        module: str | None = None,
        agent: str | None = None,
        statuses: Sequence[str] | None = None,
        before: str | None = None,
        limit: int = 50,
    ) -> AgentRunsPage:
        store = self._ready(self._runs)
        module_ids = [module] if module else await self.modules()
        found = await store.list_runs(
            module_ids, agent=agent, statuses=statuses, before=before, limit=limit
        )
        next_cursor = found[-1].submitted_at if len(found) == limit and found else None
        return AgentRunsPage(tuple(found), next_cursor)

    async def run(
        self, module_id: str, run_id: str
    ) -> tuple[AgentRun, list[AgentEvent], str | None]:
        store = self._ready(self._runs)
        found = await store.get_run(module_id, run_id)
        events = await store.events(module_id, run_id)
        trace_url = (
            f"{self._trace_ui_url}/trace/{found.trace_id}"
            if self._trace_ui_url and found.trace_id
            else None
        )
        return found, events, trace_url

    async def cancel(self, actor_id: str, module_id: str, run_id: str) -> None:
        found = await self._ready(self._runs).get_run(module_id, run_id)
        if found.status not in CANCELLABLE:
            raise AgentRunNotCancellable(run_id, found.status)
        control = self._ready(self._control)
        action = AdminAction(actor_id, "agents", "cancel", found.key)
        await run_audited(self._audit, action, lambda: control.cancel(found))
