"""SysAdmin HTTP views, mounted at /api/admin/system. Platform super admins only."""

from __future__ import annotations

import asyncio
import json
import time
from collections.abc import AsyncIterator
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from naas_abi.apps.nexus.apps.api.app.services.auth.adapters.primary.auth__primary_adapter__dependencies import (
    require_superadmin,
)
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.adapters.primary.sysadmin__primary_adapter__jobs import (
    jobs_router,
)
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.adapters.primary.sysadmin__primary_adapter__resources import (
    resources_router,
)
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.adapters.primary.sysadmin__primary_adapter__schemas import (
    to_json,
)
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.adapters.primary.sysadmin__primary_adapter__traces import (
    traces_router,
)
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.factory import (
    get_sysadmin_service,
    get_traffic_hub,
)
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.port import SourceUnavailable
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.service import SysAdminService
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.traffic import TrafficHub, event_json

router = APIRouter(dependencies=[Depends(require_superadmin)])
router.include_router(resources_router, prefix="/resources")
router.include_router(jobs_router, prefix="/jobs")
router.include_router(traces_router, prefix="/traces")

KEEPALIVE_SECONDS = 15.0
BATCH_SIZE = 200


async def _or_503(call: Any) -> Any:
    try:
        return to_json(await call)
    except SourceUnavailable as exc:
        raise HTTPException(
            status_code=503, detail={"source": exc.source, "reason": exc.reason}
        ) from exc


@router.get("/overview")
async def overview(service: SysAdminService = Depends(get_sysadmin_service)) -> Any:
    return to_json(await service.overview())


@router.get("/services")
async def kernel_services(service: SysAdminService = Depends(get_sysadmin_service)) -> Any:
    return to_json(await service.kernel_services())


@router.get("/modules")
async def modules(service: SysAdminService = Depends(get_sysadmin_service)) -> Any:
    return to_json(await service.modules())


@router.get("/telemetry")
async def telemetry(service: SysAdminService = Depends(get_sysadmin_service)) -> Any:
    """Tracing configuration; ``ui_url`` + ``/trace/<trace_id>`` opens a trace."""
    return to_json(service.telemetry)


@router.get("/nats/server")
async def nats_server(service: SysAdminService = Depends(get_sysadmin_service)) -> Any:
    return await _or_503(service.nats_server())


@router.get("/nats/connections")
async def nats_connections(
    limit: int = Query(256, ge=1, le=1024),
    service: SysAdminService = Depends(get_sysadmin_service),
) -> Any:
    return await _or_503(service.nats_connections(limit=limit))


@router.get("/nats/jetstream")
async def jetstream(service: SysAdminService = Depends(get_sysadmin_service)) -> Any:
    return await _or_503(service.jetstream())


def _frame(body: dict[str, Any]) -> str:
    return f"data: {json.dumps(body)}\n\n"


@router.get("/traffic/stream")
async def traffic_stream(
    request: Request,
    max_seconds: float = Query(900, gt=0, le=3600),
    hub: TrafficHub = Depends(get_traffic_hub),
) -> StreamingResponse:
    """Live NATS traffic (metadata only) as server-sent events, while the client reads.

    Frames: ``{"type": "status", "state": "live" | "unavailable" | "ended"}`` and
    ``{"type": "traffic", "events": [...], "dropped": n}`` (n: events this viewer lost
    for being slow). The tap runs only while at least one stream is open.
    """

    async def frames() -> AsyncIterator[str]:
        try:
            async with hub.subscribe() as viewer:
                yield _frame(
                    {
                        "type": "status",
                        "state": "live",
                        "source": hub.source,
                        "skipped": hub.skipped,
                    }
                )
                deadline = time.monotonic() + max_seconds
                last_frame = time.monotonic()
                while time.monotonic() < deadline:
                    if await request.is_disconnected():
                        return
                    try:
                        first = await asyncio.wait_for(viewer.get(), timeout=1.0)
                    except TimeoutError:
                        if time.monotonic() - last_frame >= KEEPALIVE_SECONDS:
                            last_frame = time.monotonic()
                            yield ": keepalive\n\n"
                        continue
                    batch = [first, *viewer.drain(BATCH_SIZE - 1)]
                    last_frame = time.monotonic()
                    yield _frame(
                        {
                            "type": "traffic",
                            "events": [event_json(e) for e in batch],
                            "dropped": viewer.dropped,
                        }
                    )
                yield _frame({"type": "status", "state": "ended", "reason": "stream time limit"})
        except SourceUnavailable as exc:
            yield _frame(
                {
                    "type": "status",
                    "state": "unavailable",
                    "source": exc.source,
                    "reason": exc.reason,
                }
            )

    return StreamingResponse(
        frames(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
