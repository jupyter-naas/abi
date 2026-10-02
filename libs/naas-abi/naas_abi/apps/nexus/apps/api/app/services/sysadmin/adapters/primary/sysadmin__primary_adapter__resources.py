"""Kernel service data over HTTP: /api/admin/system/resources. Super admins only.

Reads are GETs. Changes and reveals go through ``ResourceAdminService``:
typed confirmation (``confirm`` = the id) to replace or delete, and an audit
record before anything changes. Values travel as raw request/response bodies;
the HTTP activity log skips bodies under this path.
"""

from __future__ import annotations

import json
from collections.abc import Awaitable
from typing import Any, TypeVar

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import Response
from naas_abi.apps.nexus.apps.api.app.core.content_disposition import content_disposition
from naas_abi.apps.nexus.apps.api.app.services.auth.adapters.primary.auth__primary_adapter__dependencies import (
    get_current_user_required,
    require_superadmin,
)
from naas_abi.apps.nexus.apps.api.app.services.auth.adapters.primary.auth__primary_adapter__schemas import (
    User,
)
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.adapters.primary.sysadmin__primary_adapter__schemas import (
    to_json,
)
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.factory import get_resource_admin
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.port import SourceUnavailable
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.resources import (
    AuditUnavailable,
    ConfirmationRequired,
    InvalidResource,
    ResourceNotFound,
    ResourceTooLarge,
    UnknownService,
    UnsupportedOperation,
)
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.resources_service import (
    ResourceAdminService,
)

T = TypeVar("T")

resources_router = APIRouter(dependencies=[Depends(require_superadmin)])


async def _call(call: Awaitable[T]) -> T:
    try:
        return await call
    except (UnknownService, ResourceNotFound) as exc:
        raise HTTPException(404, detail=str(exc)) from exc
    except UnsupportedOperation as exc:
        raise HTTPException(405, detail=str(exc)) from exc
    except InvalidResource as exc:
        raise HTTPException(400, detail=exc.reason) from exc
    except ResourceTooLarge as exc:
        raise HTTPException(413, detail={"size": exc.size, "limit": exc.limit}) from exc
    except ConfirmationRequired as exc:
        raise HTTPException(
            409,
            detail={
                "operation": exc.operation,
                "confirm": exc.resource_id,
                "reason": f"Type {exc.resource_id!r} to confirm the {exc.operation}.",
            },
        ) from exc
    except AuditUnavailable as exc:
        raise HTTPException(
            503, detail={"source": "audit", "reason": f"No change made: {exc.reason}"}
        ) from exc
    except SourceUnavailable as exc:
        raise HTTPException(503, detail={"source": exc.source, "reason": exc.reason}) from exc


async def _body(request: Request, limit: int) -> bytes:
    declared = request.headers.get("content-length")
    if declared and declared.isdigit() and int(declared) > limit:
        raise HTTPException(413, detail={"size": int(declared), "limit": limit})
    data = bytearray()
    async for chunk in request.stream():
        data.extend(chunk)
        if len(data) > limit:
            raise HTTPException(413, detail={"size": len(data), "limit": limit})
    return bytes(data)


@resources_router.get("")
async def list_services(admin: ResourceAdminService = Depends(get_resource_admin)) -> Any:
    return {"services": to_json(admin.services())}


@resources_router.get("/history")
async def all_history(
    service: str | None = None,
    limit: int = Query(50, ge=1, le=500),
    admin: ResourceAdminService = Depends(get_resource_admin),
) -> Any:
    """Recent System app changes and reveals, newest first."""
    return {"entries": to_json(await _call(admin.history(service, limit=limit)))}


@resources_router.get("/{service}/entries")
async def list_entries(
    service: str,
    parent: str = "",
    cursor: str | None = None,
    limit: int = Query(100, ge=1, le=500),
    query: str | None = Query(None, max_length=200),
    admin: ResourceAdminService = Depends(get_resource_admin),
) -> Any:
    page = await _call(admin.list(service, parent, cursor=cursor, limit=limit, query=query))
    return to_json(page)


@resources_router.get("/{service}/history")
async def entry_history(
    service: str,
    id: str = Query(..., min_length=1),
    limit: int = Query(50, ge=1, le=500),
    admin: ResourceAdminService = Depends(get_resource_admin),
) -> Any:
    """Who changed or revealed this entry, newest first."""
    return {"entries": to_json(await _call(admin.history(service, id, limit=limit)))}


@resources_router.get("/{service}/entry")
async def read_entry(
    service: str,
    id: str = Query(..., min_length=1),
    admin: ResourceAdminService = Depends(get_resource_admin),
) -> Any:
    return to_json(await _call(admin.read(service, id)))


@resources_router.post("/{service}/reveal")
async def reveal_entry(
    service: str,
    id: str = Query(..., min_length=1),
    user: User = Depends(get_current_user_required),
    admin: ResourceAdminService = Depends(get_resource_admin),
) -> Response:
    detail = to_json(await _call(admin.reveal(user.id, service, id)))
    # A revealed value is never cached.
    return _no_store(detail)


@resources_router.get("/{service}/download")
async def download_entry(
    service: str,
    id: str = Query(..., min_length=1),
    admin: ResourceAdminService = Depends(get_resource_admin),
) -> Response:
    entry, data = await _call(admin.download(service, id))
    return Response(
        content=data,
        media_type="application/octet-stream",
        headers={
            "Content-Disposition": content_disposition("attachment", entry.name),
            "X-Content-Type-Options": "nosniff",
            "Cache-Control": "no-store",
        },
    )


@resources_router.put("/{service}/entry")
async def write_entry(
    service: str,
    request: Request,
    id: str = Query(..., min_length=1),
    confirm: str | None = None,
    user: User = Depends(get_current_user_required),
    admin: ResourceAdminService = Depends(get_resource_admin),
) -> Any:
    content = await _body(request, admin.upload_limit)
    return to_json(await _call(admin.write(user.id, service, id, content, confirm=confirm)))


@resources_router.delete("/{service}/entry", status_code=204)
async def delete_entry(
    service: str,
    id: str = Query(..., min_length=1),
    confirm: str | None = None,
    user: User = Depends(get_current_user_required),
    admin: ResourceAdminService = Depends(get_resource_admin),
) -> Response:
    await _call(admin.delete(user.id, service, id, confirm=confirm))
    return Response(status_code=204)


def _no_store(body: Any) -> Response:
    return Response(
        content=json.dumps(body),
        media_type="application/json",
        headers={"Cache-Control": "no-store"},
    )
