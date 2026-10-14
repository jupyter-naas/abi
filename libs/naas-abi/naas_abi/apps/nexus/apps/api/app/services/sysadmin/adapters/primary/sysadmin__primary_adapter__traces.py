"""The trace viewer over HTTP: /api/admin/system/traces. Super admins only.

Services and their operations for the search form, a trace search (newest
first), and one whole trace laid out for a waterfall. Times are ISO 8601 UTC,
durations and offsets float milliseconds. Errors carry ``{"source": "tracing",
"reason": ...}``: 400 for a malformed search or trace id, 404 for an unknown
trace, 503 when tracing is not configured or its backend cannot answer.
"""

from __future__ import annotations

from collections.abc import Awaitable
from typing import Any, TypeVar

from fastapi import APIRouter, Depends, HTTPException
from naas_abi.apps.nexus.apps.api.app.services.auth.adapters.primary.auth__primary_adapter__dependencies import (
    require_superadmin,
)
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.adapters.primary.sysadmin__primary_adapter__schemas import (
    to_json,
)
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.factory import (
    get_trace_store,
    get_trace_ui_url,
)
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.port import SourceUnavailable
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.traces import (
    DEFAULT_LOOKBACK,
    InvalidTraceQuery,
    TraceNotFound,
    TraceQuery,
    TraceStore,
)
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.traces_service import TraceService

T = TypeVar("T")
SOURCE = "tracing"

traces_router = APIRouter(dependencies=[Depends(require_superadmin)])


def get_trace_service(
    store: TraceStore | SourceUnavailable = Depends(get_trace_store),
    ui_url: str | None = Depends(get_trace_ui_url),
) -> TraceService:
    return TraceService(store, ui_url=ui_url)


def _error(status: int, source: str, reason: str) -> HTTPException:
    return HTTPException(status, detail={"source": source, "reason": reason})


async def _call(call: Awaitable[T]) -> T:
    try:
        return await call
    except InvalidTraceQuery as exc:
        raise _error(400, SOURCE, str(exc)) from exc
    except TraceNotFound as exc:
        raise _error(404, SOURCE, str(exc)) from exc
    except SourceUnavailable as exc:
        raise _error(503, exc.source, exc.reason) from exc


@traces_router.get("/services")
async def services(traces: TraceService = Depends(get_trace_service)) -> Any:
    return {"services": await _call(traces.services()), "ui_url": traces.ui_url}


@traces_router.get("/operations")
async def operations(service: str = "", traces: TraceService = Depends(get_trace_service)) -> Any:
    found = await _call(traces.operations(service.strip()))
    return {"operations": [{"name": name, "kind": kind} for name, kind in found]}


@traces_router.get("")
async def search(
    service: str | None = None,
    operation: str | None = None,
    lookback: str = DEFAULT_LOOKBACK,
    min_duration_ms: float | None = None,
    max_duration_ms: float | None = None,
    errors: bool = False,
    limit: int = 20,
    traces: TraceService = Depends(get_trace_service),
) -> Any:
    query = TraceQuery(
        service=(service or "").strip() or None,
        operation=(operation or "").strip() or None,
        lookback=lookback,
        min_duration_ms=min_duration_ms,
        max_duration_ms=max_duration_ms,
        errors=errors,
        limit=limit,
    )
    return {"traces": to_json(await _call(traces.search(query)))}


@traces_router.get("/{trace_id}")
async def trace(trace_id: str, traces: TraceService = Depends(get_trace_service)) -> Any:
    return to_json(await _call(traces.get(trace_id)))
