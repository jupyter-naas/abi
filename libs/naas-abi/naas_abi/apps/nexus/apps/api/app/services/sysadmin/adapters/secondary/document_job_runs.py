"""Job run records from the Document Service, as job hosts write them.

One collection per project (``runs_collection(project)``) in each module's
namespace; read through the platform document root (``document_admin``).
Filtering by trigger kind happens here (the kind is nested in the record), so
those queries over-fetch to still fill a page.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Sequence
from datetime import datetime
from typing import Any

from naas_abi.apps.nexus.apps.api.app.services.sysadmin.jobs import (
    ACTIVE_STATUSES,
    JobRun,
    RunNotFound,
    RunTrigger,
)
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.port import SourceUnavailable
from naas_abi_core.services.document.DocumentPort import CollectionNotFound, DocumentNotFound

ORDER = ("started_at", "desc")
MAX_FETCH = 1000
TRIGGER_FILTER_FACTOR = 4


def _text(value: Any) -> str | None:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


def record(module_id: str, run_id: str, data: dict[str, Any]) -> JobRun:
    trigger = data.get("trigger") or {}
    if not isinstance(trigger, dict):
        trigger = {"kind": str(trigger)}
    return JobRun(
        module_id=str(data.get("module_id") or module_id),
        job=str(data.get("job") or run_id.rsplit(":", 1)[0]),
        run_id=run_id,
        status=str(data.get("status") or "QUEUED"),
        attempt=int(data.get("attempt") or 1),
        max_attempts=int(data.get("max_attempts") or 1),
        trigger=RunTrigger(
            str(trigger.get("kind") or "manual"), str(trigger.get("scheduler") or "")
        ),
        fired_at=_text(data.get("fired_at")),
        started_at=_text(data.get("started_at")),
        finished_at=_text(data.get("finished_at")),
        instance=str(data.get("instance") or ""),
        error=str(data.get("error") or ""),
        trace_id=str(data.get("trace_id") or ""),
        payload=data.get("payload"),
        result=data.get("result"),
        logs=tuple(str(line) for line in data.get("logs") or ()),
        skip_reason=str(data.get("skip_reason") or ""),
    )


class DocumentJobRunStore:
    def __init__(self, documents: Callable[[], Any], project: str) -> None:
        from naas_abi_sdk.jobs import runs_collection

        self._documents = documents
        self.collection = runs_collection(project)

    def _find(self, module_id: str, where: list[tuple[str, str, Any]], limit: int) -> list[JobRun]:
        try:
            view = self._documents().for_namespace(module_id)
            page = view.find(self.collection, where=where, order_by=ORDER, limit=limit)
        except CollectionNotFound:
            return []
        except Exception as exc:  # noqa: BLE001 - backend errors make the source unavailable
            raise SourceUnavailable("runs", f"{type(exc).__name__}: {exc}") from exc
        return [record(module_id, doc.id, doc.data) for doc in page.items]

    def _list(
        self,
        module_ids: Sequence[str],
        job: str | None,
        statuses: Sequence[str] | None,
        trigger_kind: str | None,
        before: str | None,
        limit: int,
    ) -> list[JobRun]:
        where: list[tuple[str, str, Any]] = []
        if job:
            where.append(("job", "eq", job))
        if statuses:
            where.append(("status", "in", list(statuses)))
        if before:
            where.append(("started_at", "lt", before))
        fetch = min(MAX_FETCH, limit * TRIGGER_FILTER_FACTOR) if trigger_kind else limit
        found: list[JobRun] = []
        for module_id in module_ids:
            found.extend(self._find(module_id, where, fetch))
        if trigger_kind:
            found = [r for r in found if r.trigger.kind == trigger_kind]
        found.sort(key=lambda r: r.started_at or "", reverse=True)
        return found[:limit]

    def _get(self, module_id: str, run_id: str) -> JobRun:
        try:
            doc = self._documents().for_namespace(module_id).get(self.collection, run_id)
        except (CollectionNotFound, DocumentNotFound):
            raise RunNotFound(module_id, run_id) from None
        except Exception as exc:  # noqa: BLE001
            raise SourceUnavailable("runs", f"{type(exc).__name__}: {exc}") from exc
        return record(module_id, doc.id, doc.data)

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
        return await asyncio.to_thread(
            self._list, list(module_ids), job, statuses, trigger_kind, before, limit
        )

    async def recent(self, module_id: str, job: str, limit: int = 20) -> list[JobRun]:
        return await self.list_runs([module_id], job=job, limit=limit)

    async def running(self, module_id: str) -> list[JobRun]:
        return await self.list_runs([module_id], statuses=list(ACTIVE_STATUSES), limit=MAX_FETCH)

    async def get_run(self, module_id: str, run_id: str) -> JobRun:
        return await asyncio.to_thread(self._get, module_id, run_id)
