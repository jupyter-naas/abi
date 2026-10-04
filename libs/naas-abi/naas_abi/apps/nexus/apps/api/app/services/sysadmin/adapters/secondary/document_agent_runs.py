"""Agent run records from the Document Service, as SDK agent hosts write them.

Each module's namespace holds ``agent_runs_collection(project)`` (one record per
invocation, id ``sha256(agent, invocation_id)``) and
``agent_events_collection(project)`` (``<run>:<sequence>`` manifests naming the
event and its part count, ``<run>:<sequence>:<part>`` text fragments). Read
through the platform document root (``document_admin``).
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Sequence
from typing import Any

from naas_abi.apps.nexus.apps.api.app.services.sysadmin.agents import (
    EVENT_PREVIEW,
    MAX_EVENTS,
    AgentEvent,
    AgentRun,
    AgentRunNotFound,
)
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.port import SourceUnavailable
from naas_abi_core.services.document.DocumentPort import CollectionNotFound, DocumentNotFound

ORDER = ("submitted_at", "desc")
SOURCE = "agent_runs"


def _text(value: Any) -> str | None:
    return str(value) if value not in (None, "") else None


def record(module_id: str, run_id: str, data: dict[str, Any]) -> AgentRun:
    return AgentRun(
        module_id=module_id,
        run_id=run_id,
        agent=str(data.get("agent_name") or ""),
        invocation_id=str(data.get("invocation_id") or ""),
        status=str(data.get("status") or "ACCEPTED"),
        thread_id=str(data.get("thread_id") or ""),
        caller=str(data.get("caller") or ""),
        owner=str(data.get("owner") or ""),
        submitted_at=_text(data.get("submitted_at")),
        finished_at=_text(data.get("finished_at")),
        error_code=str(data.get("error_code") or ""),
        error_message=str(data.get("error_message") or ""),
        trace_id=str(data.get("trace_id") or ""),
        events=int(data.get("last_sequence") or len(data.get("events") or ())),
    )


def _fragment_text(data: Any) -> str:
    if isinstance(data, (bytes, bytearray, memoryview)):
        return bytes(data).decode("utf-8", errors="replace")
    return str(data)


class DocumentAgentRunStore:
    def __init__(self, documents: Callable[[], Any], project: str) -> None:
        from naas_abi_sdk.agent_host import agent_events_collection, agent_runs_collection

        self._documents = documents
        self.runs_collection = agent_runs_collection(project)
        self.events_collection = agent_events_collection(project)

    def _view(self, module_id: str) -> Any:
        try:
            return self._documents().for_namespace(module_id)
        except Exception as exc:  # noqa: BLE001 - backend errors make the source unavailable
            raise SourceUnavailable(SOURCE, f"{type(exc).__name__}: {exc}") from exc

    def _list(
        self,
        module_ids: Sequence[str],
        agent: str | None,
        statuses: Sequence[str] | None,
        before: str | None,
        limit: int,
    ) -> list[AgentRun]:
        where: list[tuple[str, str, Any]] = []
        if agent:
            where.append(("agent_name", "eq", agent))
        if statuses:
            where.append(("status", "in", list(statuses)))
        if before:
            where.append(("submitted_at", "lt", before))
        found: list[AgentRun] = []
        for module_id in module_ids:
            view = self._view(module_id)
            try:
                page = view.find(self.runs_collection, where=where, order_by=ORDER, limit=limit)
            except CollectionNotFound:
                continue
            except Exception as exc:  # noqa: BLE001
                raise SourceUnavailable(SOURCE, f"{type(exc).__name__}: {exc}") from exc
            found.extend(record(module_id, doc.id, doc.data) for doc in page.items)
        found.sort(key=lambda r: r.submitted_at or "", reverse=True)
        return found[:limit]

    def _get(self, module_id: str, run_id: str) -> AgentRun:
        view = self._view(module_id)
        try:
            doc = view.get(self.runs_collection, run_id)
        except (CollectionNotFound, DocumentNotFound):
            raise AgentRunNotFound(module_id, run_id) from None
        except Exception as exc:  # noqa: BLE001
            raise SourceUnavailable(SOURCE, f"{type(exc).__name__}: {exc}") from exc
        return record(module_id, doc.id, doc.data)

    def _events(self, module_id: str, run_id: str, limit: int) -> list[AgentEvent]:
        run = self._get(module_id, run_id)
        view = self._view(module_id)
        events: list[AgentEvent] = []
        try:
            for sequence in range(1, min(run.events, limit) + 1):
                manifest = view.get(self.events_collection, f"{run_id}:{sequence}").data
                text = ""
                if int(manifest.get("parts") or 0):
                    first = view.get(self.events_collection, f"{run_id}:{sequence}:0").data
                    text = _fragment_text(first.get("data", ""))
                more = len(text) > EVENT_PREVIEW or int(manifest.get("parts") or 0) > 1
                events.append(
                    AgentEvent(
                        sequence, str(manifest.get("event") or ""), text[:EVENT_PREVIEW], more
                    )
                )
        except (CollectionNotFound, DocumentNotFound):
            return events  # an event not committed yet ends the list
        except Exception as exc:  # noqa: BLE001
            raise SourceUnavailable(SOURCE, f"{type(exc).__name__}: {exc}") from exc
        return events

    async def list_runs(
        self,
        module_ids: Sequence[str],
        *,
        agent: str | None = None,
        statuses: Sequence[str] | None = None,
        before: str | None = None,
        limit: int = 50,
    ) -> list[AgentRun]:
        return await asyncio.to_thread(self._list, list(module_ids), agent, statuses, before, limit)

    async def get_run(self, module_id: str, run_id: str) -> AgentRun:
        return await asyncio.to_thread(self._get, module_id, run_id)

    async def events(
        self, module_id: str, run_id: str, *, limit: int = MAX_EVENTS
    ) -> list[AgentEvent]:
        return await asyncio.to_thread(self._events, module_id, run_id, limit)
