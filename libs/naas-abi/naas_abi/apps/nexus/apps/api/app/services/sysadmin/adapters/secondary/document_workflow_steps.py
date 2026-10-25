"""A workflow run's step summaries from the Document Service, as SDK hosts journal them.

One collection per project (``steps_collection(project)``) in each module's
namespace, one document per (run, step key), read through the platform document
root (``document_admin``). Results live in another collection and are never read.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from datetime import datetime
from typing import Any

from naas_abi.apps.nexus.apps.api.app.services.sysadmin.jobs import (
    ChildRun,
    RunStep,
    WorkflowDetail,
)
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.port import SourceUnavailable
from naas_abi_core import logger
from naas_abi_core.services.document.DocumentPort import CollectionNotFound

# One page: a run with more steps shows the first of them and says so.
MAX_STEPS = 1000


def _text(value: Any) -> str | None:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


def step(data: dict[str, Any]) -> RunStep:
    child = data.get("child")
    link = (
        ChildRun(
            str(child.get("module_id") or ""),
            str(child.get("workflow") or ""),
            str(child.get("run_id") or ""),
        )
        if isinstance(child, dict) and child.get("module_id") and child.get("run_id")
        else None
    )
    duration = data.get("duration_ms")
    size = data.get("result_bytes")
    return RunStep(
        key=str(data.get("key") or ""),
        kind=str(data.get("kind") or "step"),
        status=str(data.get("status") or "RUNNING"),
        attempt=int(data.get("attempt") or 1),
        started_at=_text(data.get("started_at")),
        finished_at=_text(data.get("finished_at")),
        duration_ms=int(duration)
        if isinstance(duration, (int, float)) and _text(data.get("finished_at"))
        else None,
        error=str(data.get("error") or ""),
        child=link,
        result_bytes=int(size) if isinstance(size, (int, float)) else None,
    )


class DocumentWorkflowSteps:
    def __init__(self, documents: Callable[[], Any], project: str) -> None:
        from naas_abi_sdk.workflows import steps_collection

        self._documents = documents
        self.collection = steps_collection(project)

    def _read(self, module_id: str, run_id: str, fired_at: str | None) -> WorkflowDetail:
        try:
            view = self._documents().for_namespace(module_id)
            page = view.find(self.collection, where=[("run_id", "eq", run_id)], limit=MAX_STEPS)
        except CollectionNotFound:
            return WorkflowDetail()
        except Exception as exc:  # noqa: BLE001 - backend errors make the source unavailable
            raise SourceUnavailable("steps", f"{type(exc).__name__}: {exc}") from exc
        data = [
            doc.data
            for doc in page.items
            # A recreated jobs stream reuses run ids: another trigger's steps are not this run's.
            if not fired_at or not doc.data.get("fired_at") or doc.data.get("fired_at") == fired_at
        ]
        steps = []
        for d in data:
            try:
                steps.append(step(d))
            except (ValueError, TypeError, OverflowError, AttributeError):
                # One document a host wrote badly must not hide the run's other steps.
                logger.warning(f"workflow step skipped: unreadable summary {d.get('key')!r}")
        steps.sort(key=lambda s: (s.started_at or "", s.key))
        return WorkflowDetail(tuple(steps), truncated=page.cursor is not None)

    async def journal(
        self, module_id: str, run_id: str, fired_at: str | None = None
    ) -> WorkflowDetail:
        return await asyncio.to_thread(self._read, module_id, run_id, fired_at)
