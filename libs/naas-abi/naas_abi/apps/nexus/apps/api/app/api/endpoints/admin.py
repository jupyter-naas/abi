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


@router.get("/events/types")
async def admin_events_types(
    _: User = Depends(require_superadmin),
) -> list[dict[str, str]]:
    """List every known LogProcess event type (URI + short label).

    Backs the admin events filter dropdown so the user can filter by any
    registered event type — not just the ones that happen to be in the most
    recent page. Types come from the in-process LogProcess subclass registry
    (the same one EventCodec uses to deserialize), so it reflects every event
    class loaded by the engine.
    """
    try:
        from naas_abi_core.services.event.EventService import _build_subclass_index
        from naas_abi_core.services.event.ontologies.modules.EventOntology import (
            LogProcess,
        )
    except Exception:
        logger.exception("admin events types: import failed")
        return []

    index = _build_subclass_index()
    out: list[dict[str, str]] = []
    for uri, cls in index.items():
        if cls is LogProcess:
            # The abstract base never appears as a stored event type.
            continue
        label = getattr(cls, "_name", None) or uri.rstrip("/").rsplit("/", 1)[-1].rsplit("#", 1)[-1]
        out.append({"uri": uri, "label": str(label)})
    out.sort(key=lambda t: t["label"].lower())
    return out


@router.get("/events/recent")
async def admin_events_recent(
    limit: int = Query(100, ge=1, le=1000),
    event_class: str | None = Query(
        None,
        description="Event type URI to filter by. Applied server-side so the "
        "limit returns the last N events of THIS type.",
    ),
    q: str | None = Query(
        None,
        description="Case-insensitive substring searched server-side across the "
        "entire event payload (whole log, not just the loaded page).",
    ),
    before_seq: int | None = Query(
        None,
        ge=1,
        description="Return only events older than this seq, for 'load older' paging.",
    ),
    _: User = Depends(require_superadmin),
) -> list[dict[str, Any]]:
    """Return the most recent ``limit`` LogProcess events matching the filters.

    The ``limit`` is applied AFTER ``event_class`` / ``q`` filtering, so a rare
    type yields its last N occurrences rather than being lost in a window of
    recent all-type activity. Events come back oldest-first; the frontend
    reverses them for display.
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

    # Resolve the requested type URI to its LogProcess subclass. An unknown
    # URI means "no such type" → empty result (not a 500).
    resolved_class = None
    if event_class:
        try:
            from naas_abi_core.services.event.EventService import (
                _build_subclass_index,
            )

            resolved_class = _build_subclass_index().get(event_class)
        except Exception:
            logger.exception("admin events recent: type resolution failed")
            resolved_class = None
        if resolved_class is None:
            return []

    # `seq <= until_seq`, so to page strictly older than `before_seq` we cap at
    # before_seq - 1.
    until_seq = (before_seq - 1) if before_seq else None

    try:
        # newest_first=True + limit → the last N matching events; reversed below
        # to the oldest-first contract the frontend expects.
        events = event_service.query(
            event_class=resolved_class,
            until_seq=until_seq,
            search=q,
            newest_first=True,
            limit=limit,
        )
    except Exception:
        logger.exception("admin events recent: query failed")
        return []

    out: list[dict[str, Any]] = []
    for ev in reversed(events):
        try:
            payload = EventCodec.to_event_dict(ev)
            payload["_seq"] = getattr(ev, "_seq", None)
            payload["_stored_at"] = getattr(ev, "_stored_at", None) or None
            # JSON round-trip drops anything non-JSON-safe.
            out.append(json.loads(json.dumps(payload, default=str)))
        except Exception:
            logger.exception("admin events recent: serialize failed")
    return out
