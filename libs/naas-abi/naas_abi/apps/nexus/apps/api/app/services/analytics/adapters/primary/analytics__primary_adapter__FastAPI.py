"""FastAPI primary adapter for the tracker's ingest: ``POST /api/analytics/events``.

Open to every signed-in user: the identity comes from the token, a
``workspace_id`` stays only for a member of the workspace, and the server stamps
its ``organization_id``. The event is client data: its ``timestamp`` must be ISO-8601
within [now - 45 days, now + 1 day] (422 otherwise: the raw events' retention, and a
client clock a day ahead at most) and control characters (NUL included) are removed
from every string. The event is appended to the EventService log, whose consumer
feeds the rollups (``analytics/jobs.py``); a deploy with no log applies it to the
rollups at once.

The analytics are read in Organization and Workspace settings
(``analytics__primary_adapter__scoped``).
"""

from __future__ import annotations

import logging
import time
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from naas_abi.apps.nexus.apps.api.app.core.database import get_db
from naas_abi.apps.nexus.apps.api.app.services.analytics.adapters.secondary import (
    AnalyticsSecondaryAdapterEventLog,
)
from naas_abi.apps.nexus.apps.api.app.services.analytics.adapters.secondary.analytics__secondary_adapter__postgres import (  # noqa: E501
    AnalyticsSecondaryAdapterPostgresEvents,
)
from naas_abi.apps.nexus.apps.api.app.services.analytics.port import (
    AnalyticsEvent,
    AnalyticsEventLogPort,
    IngestResponse,
)
from naas_abi.apps.nexus.apps.api.app.services.analytics.rollups import (
    FUTURE_TOLERANCE,
    RETENTION_DAYS,
    AnalyticsRollups,
    event_time_accepted,
    parse_timestamp,
    recorded_from_event,
    strip_control,
)
from naas_abi.apps.nexus.apps.api.app.services.auth.adapters.primary.auth__primary_adapter__dependencies import (
    get_current_user_required,
)
from naas_abi.apps.nexus.apps.api.app.services.iam import authz as authz_module
from naas_abi.apps.nexus.apps.api.app.services.iam.names import org_of
from naas_abi_core.engine.call_context import as_service_account
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

logger = logging.getLogger(__name__)
router = APIRouter(dependencies=[Depends(get_current_user_required)])


def _get_event_service() -> Any | None:
    """The engine's event log, or None when this deploy runs without one."""
    try:
        from naas_abi import ABIModule

        engine = ABIModule.get_instance().engine
        if not engine.services.events_available():
            return None
        return engine.services.events
    except Exception as exc:
        logger.debug(f"[analytics] event service unavailable: {exc}")
        return None


def get_event_log() -> AnalyticsEventLogPort | None:
    """Where an ingest is recorded: the engine's event log, None without one."""
    events = _get_event_service()
    return AnalyticsSecondaryAdapterEventLog(events=events) if events is not None else None


def get_direct_rollups(
    log: AnalyticsEventLogPort | None = Depends(get_event_log),
    db: AsyncSession | None = Depends(get_db),
) -> AnalyticsRollups | None:
    """Where an ingest is applied to the rollups at once: only on a deploy with no
    event log (otherwise the log's consumer applies it, ``analytics/jobs.py``)."""
    if log is not None or db is None:
        return None
    return AnalyticsRollups(AnalyticsSecondaryAdapterPostgresEvents(db))


# A tracker event is a few hundred bytes; its ``properties`` stay small.
MAX_EVENT_BYTES = 16 * 1024

# (user, workspace) -> (member, organization, until): the tracker sends an event per
# page view, the membership is asked of IAM once a minute per workspace.
_MEMBERSHIP_SECONDS = 60.0
_memberships: dict[tuple[str, str], tuple[bool, str | None, float]] = {}


async def _membership(user: Any, workspace_id: str) -> tuple[bool, str | None]:
    """Whether the user is a member of the workspace (any role there, or an org-wide
    one), and the workspace's organization."""
    user_id = authz_module.Authz.user_id(user) or ""
    key = (user_id, workspace_id)
    now = time.monotonic()
    found = _memberships.get(key)
    if found is not None and found[2] > now:
        return found[0], found[1]
    member = await authz_module.AUTHZ.allowed("GetWorkspace", user=user, workspace=workspace_id)
    container = await authz_module.AUTHZ.container_of(workspace_id) if member else None
    organization = org_of(container) if container else None
    if len(_memberships) > 10_000:
        _memberships.clear()
    _memberships[key] = (member, organization, now + _MEMBERSHIP_SECONDS)
    return member, organization


async def stamp_event(event: AnalyticsEvent, user: Any) -> AnalyticsEvent:
    """The event as the server records it: the token's user (the payload's
    ``user_id``/``user_email`` are ignored, and no email is kept), the workspace
    only for one of its members, and that workspace's organization."""
    workspace_id = event.workspace_id or None
    organization_id: str | None = None
    if workspace_id is not None:
        member, organization_id = await _membership(user, workspace_id)
        if not member:
            workspace_id, organization_id = None, None
    data = strip_control(event.model_dump())
    data.update(
        user_id=authz_module.Authz.user_id(user),
        user_email=None,
        workspace_id=workspace_id,
        workspace_name=event.workspace_name if workspace_id else None,
        organization_id=organization_id,
    )
    return AnalyticsEvent.model_validate(data)


@router.post("/events", response_model=IngestResponse)
async def ingest_event(
    event: AnalyticsEvent,
    user=Depends(get_current_user_required),
    log: AnalyticsEventLogPort | None = Depends(get_event_log),
    rollups: AnalyticsRollups | None = Depends(get_direct_rollups),
) -> IngestResponse:
    if len(event.model_dump_json()) > MAX_EVENT_BYTES:
        # Any signed-in user may post: what one event may hold is bounded (it is kept
        # in the log, in the raw table and served back to admins).
        raise HTTPException(status_code=413, detail="Analytics event too large")
    if not event_time_accepted(parse_timestamp(event.timestamp), datetime.now(UTC)):
        raise HTTPException(
            status_code=422,
            detail=(
                "timestamp must be an ISO-8601 date within the last "
                f"{RETENTION_DAYS} days and at most {FUTURE_TOLERANCE.days} day ahead"
            ),
        )
    stamped = await stamp_event(event, user)

    if log is not None:

        def record() -> str:
            # The caller is authorized above (signed in, workspace checked): the log
            # is written as ``api``, which a member's own rights never reach.
            with as_service_account("api"):
                return log.save_event(stamped.model_dump(exclude_none=True))

        # Publishing is synchronous (an RPC to the log): off the event loop, so a
        # slow broker never freezes every request of the engine (/health included).
        return IngestResponse(stored_at=await run_in_threadpool(record))
    if rollups is not None:
        recorded = recorded_from_event(stamped)
        if recorded is not None:
            await rollups.apply_recorded([recorded])
        return IngestResponse(stored_at="analytics_events")
    raise HTTPException(status_code=503, detail="Analytics storage unavailable")
