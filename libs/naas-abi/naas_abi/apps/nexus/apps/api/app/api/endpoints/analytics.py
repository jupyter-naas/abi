"""Analytics ingestion endpoint.

Persists frontend analytics events through ABI's object storage service.
Source of truth lives at ``naas_abi/nexus/analytics/`` in object storage;
a local mirror is also written so the existing Next.js dashboard routes
(`/api/analytics/overview`, `/users`, ...) and ``generate_kpis.py`` keep
working without changes.
"""

from __future__ import annotations

import json
import subprocess
import threading
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from naas_abi_core import logger
from naas_abi_core.services.object_storage.ObjectStorageService import (
    ObjectStorageService,
)
from naas_abi_core.utils.StorageUtils import StorageUtils
from pydantic import BaseModel, Field

router = APIRouter()

OUTPUT_DIR = "naas_abi/nexus/analytics"
EVENTS_FILE = "events.json"
REF_USERS_FILE = "ref-users.json"
REF_WORKSPACES_FILE = "ref-workspaces.json"

# Local mirror — kept in sync with object storage so the existing Next.js
# dashboard reads and ``generate_kpis.py`` keep working unchanged.
# parents resolve as: endpoints → api → app → api → apps (the nexus apps/ dir).
_NEXUS_APPS_DIR = Path(__file__).resolve().parents[4]
_LOCAL_DATA_DIR = _NEXUS_APPS_DIR / "web" / "src" / "app" / "analytics" / "data"
_KPI_SCRIPT = _NEXUS_APPS_DIR / "web" / "src" / "app" / "analytics" / "scripts" / "generate_kpis.py"

_KPI_DEBOUNCE_SECONDS = 1.5

# In-process serialization so concurrent POSTs do not race the
# read-modify-write of events.json.
_write_lock = threading.Lock()
_kpi_lock = threading.Lock()
_kpi_timer: threading.Timer | None = None


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


class AnalyticsEvent(BaseModel):
    """Minimal contract; matches the shape emitted by analytics-tracking.ts."""

    model_config = {"extra": "allow"}

    event_id: str
    event_name: str
    timestamp: str
    session_id: str
    user_id: str | None = None
    user_email: str | None = None
    workspace_id: str | None = None
    workspace_name: str | None = None
    page_path: str | None = None
    page_title: str | None = None
    properties: dict[str, Any] | None = None
    device: str | None = None
    browser: str | None = None
    country: str | None = None
    referrer: str | None = None


class IngestResponse(BaseModel):
    ok: bool = True
    stored_at: str = Field(description="object storage path of the live events file")


# ---------------------------------------------------------------------------
# Dependencies
# ---------------------------------------------------------------------------


def get_object_storage(request: Request) -> ObjectStorageService:
    storage = getattr(request.app.state, "object_storage", None)
    if storage is not None:
        return storage
    try:
        from naas_abi import ABIModule

        module = ABIModule.get_instance()
        storage = module.engine.services.object_storage
        request.app.state.object_storage = storage
        return storage
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail="Object storage is not initialized. Load API through naas_abi.ABIModule.",
        ) from exc


def get_storage_utils(
    storage: ObjectStorageService = Depends(get_object_storage),
) -> StorageUtils:
    return StorageUtils(storage_service=storage)


# ---------------------------------------------------------------------------
# Storage helpers
# ---------------------------------------------------------------------------


def _read_json(
    storage: ObjectStorageService, file_name: str, fallback: Any
) -> Any:
    try:
        raw = storage.get_object(OUTPUT_DIR, file_name)
        if raw is None:
            return fallback
        return json.loads(raw.decode("utf-8"))
    except Exception as exc:
        logger.debug(f"[analytics] {file_name} not present in storage: {exc}")
        return fallback


def _mirror_local(file_name: str, data: Any) -> None:
    """Mirror the canonical JSON to disk for the dashboard + KPI script."""
    try:
        _LOCAL_DATA_DIR.mkdir(parents=True, exist_ok=True)
        path = _LOCAL_DATA_DIR / file_name
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    except Exception as exc:
        logger.warning(f"[analytics] failed to mirror {file_name} locally: {exc}")


def _upsert_refs(event: AnalyticsEvent, storage: ObjectStorageService) -> tuple[bool, bool]:
    """Append the event's user/workspace to the ref files if new.

    Returns ``(users_changed, workspaces_changed)``.
    """
    users_changed = False
    workspaces_changed = False

    if event.workspace_id:
        workspaces: list[dict[str, Any]] = _read_json(storage, REF_WORKSPACES_FILE, [])
        existing = next(
            (w for w in workspaces if w.get("workspace_id") == event.workspace_id),
            None,
        )
        if existing is None:
            workspaces.append(
                {
                    "workspace_id": event.workspace_id,
                    "workspace_name": event.workspace_name or event.workspace_id,
                }
            )
            workspaces_changed = True
        elif event.workspace_name and existing.get("workspace_name") != event.workspace_name:
            existing["workspace_name"] = event.workspace_name
            workspaces_changed = True

        if workspaces_changed:
            _save_refs(REF_WORKSPACES_FILE, workspaces, storage)

    if event.user_id and event.user_email:
        users: list[dict[str, Any]] = _read_json(storage, REF_USERS_FILE, [])
        existing = next(
            (u for u in users if u.get("user_id") == event.user_id),
            None,
        )
        if existing is None:
            users.append(
                {
                    "user_id": event.user_id,
                    "user_email": event.user_email,
                    "workspace_ids": [event.workspace_id] if event.workspace_id else [],
                }
            )
            users_changed = True
        else:
            if existing.get("user_email") != event.user_email:
                existing["user_email"] = event.user_email
                users_changed = True
            if event.workspace_id and event.workspace_id not in existing.get(
                "workspace_ids", []
            ):
                existing.setdefault("workspace_ids", []).append(event.workspace_id)
                users_changed = True

        if users_changed:
            _save_refs(REF_USERS_FILE, users, storage)

    return users_changed, workspaces_changed


def _save_refs(file_name: str, data: list[dict[str, Any]], storage: ObjectStorageService) -> None:
    StorageUtils(storage_service=storage).save_json(
        data=data,
        dir_path=OUTPUT_DIR,
        file_name=file_name,
        copy=False,  # Ref files churn rarely; no audit trail needed.
    )
    _mirror_local(file_name, data)


# ---------------------------------------------------------------------------
# KPI regeneration (debounced)
# ---------------------------------------------------------------------------


def _run_kpi_script() -> None:
    try:
        subprocess.Popen(
            ["python3", str(_KPI_SCRIPT)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except Exception as exc:
        logger.warning(f"[analytics] failed to spawn generate_kpis.py: {exc}")


def _schedule_kpi_regen() -> None:
    global _kpi_timer
    with _kpi_lock:
        if _kpi_timer is not None:
            _kpi_timer.cancel()
        _kpi_timer = threading.Timer(_KPI_DEBOUNCE_SECONDS, _run_kpi_script)
        _kpi_timer.daemon = True
        _kpi_timer.start()


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.post("/events", response_model=IngestResponse)
async def ingest_event(
    event: AnalyticsEvent,
    storage_utils: StorageUtils = Depends(get_storage_utils),
    storage: ObjectStorageService = Depends(get_object_storage),
) -> IngestResponse:
    """Append an analytics event to ``events.json`` in object storage."""

    payload = event.model_dump(exclude_none=True)

    with _write_lock:
        current = _read_json(storage, EVENTS_FILE, {"events": []})
        events = current.get("events") if isinstance(current, dict) else current
        if not isinstance(events, list):
            events = []
        events.append(payload)
        data = {"events": events}

        storage_utils.save_json(
            data=data,
            dir_path=OUTPUT_DIR,
            file_name=EVENTS_FILE,
            copy=True,
        )
        _mirror_local(EVENTS_FILE, data)

        _upsert_refs(event, storage)

    _schedule_kpi_regen()

    return IngestResponse(stored_at=f"{OUTPUT_DIR}/{EVENTS_FILE}")
