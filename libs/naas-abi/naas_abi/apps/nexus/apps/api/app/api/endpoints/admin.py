"""Platform admin endpoints.

Surfaces capabilities scoped to platform superadmins (users with the
``is_superadmin`` flag set in ``config.yaml``), independent of workspace
membership.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from fastapi import APIRouter, Depends, Query
from naas_abi.apps.nexus.apps.api.app.services.auth.adapters.primary.auth__primary_adapter__dependencies import (
    get_current_user_required,
    require_superadmin,
)
from naas_abi.apps.nexus.apps.api.app.services.auth.adapters.primary.auth__primary_adapter__schemas import (
    User,
)
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter()


class AdminMeResponse(BaseModel):
    is_superadmin: bool


@router.get("/me", response_model=AdminMeResponse)
async def admin_me(
    current_user: User = Depends(get_current_user_required),
) -> AdminMeResponse:
    """Lightweight check the frontend can call to decide whether to show
    platform-admin surfaces (event stream, etc.). Does not 403 — returns
    a boolean so non-admin clients can simply hide the UI."""
    return AdminMeResponse(is_superadmin=bool(current_user.is_superadmin))


@router.get("/ping")
async def admin_ping(_: User = Depends(require_superadmin)) -> dict[str, bool]:
    """403s for non-superadmins. Used by the admin page to gate access."""
    return {"ok": True}


@router.get("/events/recent")
async def admin_events_recent(
    limit: int = Query(100, ge=1, le=1000),
    _: User = Depends(require_superadmin),
) -> list[dict[str, Any]]:
    """Return the most recent ``limit`` LogProcess events from the durable log.

    Used by the admin events page to hydrate its live stream on first mount
    so the user immediately sees recent activity instead of an empty list.
    Events come back oldest-first; the frontend reverses them for display.
    """
    try:
        from naas_abi import ABIModule
        from naas_abi_core.services.event import EventCodec

        engine = ABIModule.get_instance().engine
    except Exception:
        logger.exception("admin events recent: engine unavailable")
        return []

    if not engine.services.events_available():
        return []

    event_service = engine.services.events

    try:
        adapter = event_service._adapter  # type: ignore[attr-defined]
        max_seq = adapter.max_seq()
        since_seq = max(0, max_seq - limit)
        # event_class=None → query across every event type; rows are
        # reconstructed via the stored ``_class_uri`` so subclass-specific
        # fields survive.
        events = event_service.query(
            event_class=None,
            since_seq=since_seq,
            limit=limit,
        )
    except Exception:
        logger.exception("admin events recent: query failed")
        return []

    out: list[dict[str, Any]] = []
    for ev in events:
        try:
            payload = EventCodec.to_event_dict(ev)
            payload["_seq"] = getattr(ev, "_seq", None)
            payload["_stored_at"] = getattr(ev, "_stored_at", None) or None
            # JSON round-trip drops anything non-JSON-safe.
            out.append(json.loads(json.dumps(payload, default=str)))
        except Exception:
            logger.exception("admin events recent: serialize failed")
    return out
