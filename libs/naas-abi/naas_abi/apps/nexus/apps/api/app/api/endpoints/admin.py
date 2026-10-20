"""Platform admin endpoints.

Surfaces capabilities scoped to platform superadmins (users with the
``is_superadmin`` flag), independent of workspace membership. The flag is
managed with ``PATCH /api/admin/users/{id}``; config ``users:`` only bootstraps operators.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from datetime import datetime
from typing import Any
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, HTTPException, Query
from naas_abi.apps.nexus.apps.api.app.core.database import get_db
from naas_abi.apps.nexus.apps.api.app.core.platform_tables import (
    UnknownPlatformRowError,
    UnknownPlatformTableError,
    list_platform_tables,
    read_platform_table,
    read_platform_table_row,
    read_platform_table_schema,
)
from naas_abi.apps.nexus.apps.api.app.services.auth.adapters.primary.auth__primary_adapter__dependencies import (
    get_auth_service,
    get_current_user_required,
    require_superadmin,
)
from naas_abi.apps.nexus.apps.api.app.services.auth.adapters.primary.auth__primary_adapter__schemas import (
    User,
)
from naas_abi.apps.nexus.apps.api.app.services.auth.port import AuthUserRecord
from naas_abi.apps.nexus.apps.api.app.services.auth.service import (
    AuthService,
    SuperadminChangeError,
    UserNotFoundError,
)
from naas_abi.apps.nexus.apps.api.app.services.organizations.adapters.secondary.postgres import (
    OrganizationSecondaryAdapterPostgres,
)
from naas_abi.apps.nexus.apps.api.app.services.organizations.port import (
    UserOrganizationMembershipRecord,
)
from naas_abi.apps.nexus.apps.api.app.services.organizations.service import OrganizationService
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

router = APIRouter()


def _runtime_site() -> str:
    """Deploy public host for BFO Site projection (occurs-in).

    Prefer the configured public web host, then API host. Do not invent a Site
    from container/process hostname: that is not a tenant-facing occurrence
    site. Return Unknown when unset so other ABI deploys stay honest.
    """
    for key in ("PUBLIC_WEB_HOST", "PUBLIC_API_HOST"):
        raw = (os.environ.get(key) or "").strip()
        if not raw:
            continue
        if "://" in raw:
            host = urlparse(raw).hostname
            if host:
                return host
            continue
        host = raw.split("/")[0].split(":")[0]
        if host:
            return host
    return "Unknown"


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


class ConfiguredService(BaseModel):
    id: str
    adapters: list[str]


@router.get("/services", response_model=list[ConfiguredService])
async def admin_services(_: User = Depends(require_superadmin)) -> list[ConfiguredService]:
    """Platform services set in ``config.yaml`` with their adapters (Settings > Services).

    Names only: adapter configs hold credentials and are never returned.
    """
    from naas_abi import ABIModule
    from naas_abi.apps.nexus.apps.api.app.utils.configured_services import (
        configured_services,
    )

    services = ABIModule.get_instance().engine.configuration.services
    return [ConfiguredService(**service) for service in configured_services(services)]


class AdminUserOrganization(BaseModel):
    id: str
    name: str
    role: str


class AdminUser(BaseModel):
    id: str
    email: str
    name: str
    avatar: str | None = None
    is_superadmin: bool
    created_at: datetime
    organizations: list[AdminUserOrganization] = Field(default_factory=list)


class AdminUserUpdate(BaseModel):
    is_superadmin: bool


_SUPERADMIN_CHANGE_DETAIL = {
    "cannot_demote_self": "You cannot remove your own superadmin access",
    "last_superadmin": "The platform needs at least one superadmin",
}


def get_organization_service(db: AsyncSession = Depends(get_db)) -> OrganizationService:
    return OrganizationService(adapter=OrganizationSecondaryAdapterPostgres(db=db))


def _admin_user(
    record: AuthUserRecord, memberships: list[UserOrganizationMembershipRecord] | None = None
) -> AdminUser:
    return AdminUser(
        id=record.id,
        email=record.email,
        name=record.name,
        avatar=record.avatar,
        is_superadmin=record.is_superadmin,
        created_at=record.created_at,
        organizations=[
            AdminUserOrganization(id=m.organization_id, name=m.organization_name, role=m.role)
            for m in memberships or []
        ],
    )


async def _memberships_by_user(
    organization_service: OrganizationService,
) -> dict[str, list[UserOrganizationMembershipRecord]]:
    by_user: dict[str, list[UserOrganizationMembershipRecord]] = {}
    for membership in await organization_service.list_all_memberships():
        by_user.setdefault(membership.user_id, []).append(membership)
    return by_user


@router.get("/users", response_model=list[AdminUser])
async def admin_list_users(
    _: User = Depends(require_superadmin),
    auth_service: AuthService = Depends(get_auth_service),
    organization_service: OrganizationService = Depends(get_organization_service),
) -> list[AdminUser]:
    """Every platform account with its organizations."""
    by_user = await _memberships_by_user(organization_service)
    return [
        _admin_user(record, by_user.get(record.id)) for record in await auth_service.list_users()
    ]


@router.patch("/users/{user_id}", response_model=AdminUser)
async def admin_update_user(
    user_id: str,
    body: AdminUserUpdate,
    current_user: User = Depends(require_superadmin),
    auth_service: AuthService = Depends(get_auth_service),
    organization_service: OrganizationService = Depends(get_organization_service),
) -> AdminUser:
    """Promote or demote a platform superadmin."""
    try:
        record = await auth_service.set_superadmin(
            actor_id=current_user.id, user_id=user_id, is_superadmin=body.is_superadmin
        )
    except UserNotFoundError as exc:
        raise HTTPException(status_code=404, detail="User not found") from exc
    except SuperadminChangeError as exc:
        raise HTTPException(
            status_code=400, detail=_SUPERADMIN_CHANGE_DETAIL.get(exc.reason, exc.reason)
        ) from exc
    by_user = await _memberships_by_user(organization_service)
    return _admin_user(record, by_user.get(record.id))


class AdminTableSummary(BaseModel):
    name: str
    description: str
    rows: int | None = None
    columns: int | None = None


class AdminTableColumn(BaseModel):
    name: str
    type: str
    nullable: bool
    default: str | None = None
    primary_key: bool
    references: str | None = None
    redacted: bool


class AdminTableSchema(BaseModel):
    name: str
    description: str
    columns: list[AdminTableColumn]


class AdminTable(BaseModel):
    name: str
    description: str
    columns: list[str]
    rows: list[dict[str, Any]]
    total: int
    truncated: bool
    primary_key: list[str] = Field(default_factory=list)


class AdminTableRow(BaseModel):
    name: str
    description: str
    id: str
    primary_key: list[str]
    columns: list[str]
    row: dict[str, Any]


@router.get("/tables", response_model=list[AdminTableSummary])
async def admin_list_tables(
    _: User = Depends(require_superadmin),
    db: AsyncSession = Depends(get_db),
) -> list[AdminTableSummary]:
    """People & access tables for the Platform Settings dashboard, with row and column counts."""
    return [AdminTableSummary(**s.__dict__) for s in await list_platform_tables(db)]


@router.get("/tables/{name}/schema", response_model=AdminTableSchema)
async def admin_read_table_schema(
    name: str,
    _: User = Depends(require_superadmin),
    db: AsyncSession = Depends(get_db),
) -> AdminTableSchema:
    """Columns of one table: type, nullability, default, keys, masked or not."""
    try:
        schema = await read_platform_table_schema(db, name)
    except UnknownPlatformTableError as exc:
        raise HTTPException(status_code=404, detail="Unknown table") from exc
    return AdminTableSchema(
        name=schema.name,
        description=schema.description,
        columns=[AdminTableColumn(**column.__dict__) for column in schema.columns],
    )


@router.get("/tables/{name}/rows/{row_id}", response_model=AdminTableRow)
async def admin_read_table_row(
    name: str,
    row_id: str,
    _: User = Depends(require_superadmin),
    db: AsyncSession = Depends(get_db),
) -> AdminTableRow:
    """One row by its id: primary key value, or values joined with ``~`` (secrets masked)."""
    try:
        row = await read_platform_table_row(db, name, row_id)
    except UnknownPlatformTableError as exc:
        raise HTTPException(status_code=404, detail="Unknown table") from exc
    except UnknownPlatformRowError as exc:
        raise HTTPException(status_code=404, detail="Row not found") from exc
    return AdminTableRow(**row.__dict__)


@router.get("/tables/{name}", response_model=AdminTable)
async def admin_read_table(
    name: str,
    _: User = Depends(require_superadmin),
    db: AsyncSession = Depends(get_db),
) -> AdminTable:
    """Every column and row of one people & access table (secrets masked)."""
    try:
        table = await read_platform_table(db, name)
    except UnknownPlatformTableError as exc:
        raise HTTPException(status_code=404, detail="Unknown table") from exc
    return AdminTable(**table.__dict__)


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

    site = _runtime_site()
    out: list[dict[str, Any]] = []
    for ev in reversed(events):
        try:
            payload = EventCodec.to_event_dict(ev)
            payload["_seq"] = getattr(ev, "_seq", None)
            payload["_stored_at"] = getattr(ev, "_stored_at", None) or None
            payload["_site"] = site
            # JSON round-trip drops anything non-JSON-safe.
            out.append(json.loads(json.dumps(payload, default=str)))
        except Exception:
            logger.exception("admin events recent: serialize failed")
    await _attach_identities(engine, out)
    return out


async def _attach_identities(engine: Any, events: list[dict[str, Any]]) -> None:
    """Add ``_identity`` (person names, workspace, roles) from graph/nexus-identity.

    Payloads only hold ids. Best effort: without a triple store the events
    are returned as they are.
    """
    try:
        from naas_abi.apps.nexus.apps.api.app.services.identity_graph.resolver import (
            IdentityResolver,
            enrich_events,
        )

        triple_store = engine.services.triple_store
        await asyncio.to_thread(enrich_events, events, IdentityResolver(query=triple_store.query))
    except Exception:
        logger.exception("admin events recent: identity resolution failed")
