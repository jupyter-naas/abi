"""Analytics ingestion + rollup endpoint.

Owns the entire analytics write path:

1. Each event POSTed by the frontend is persisted as an individual pickle
   in object storage, keyed by content hash:

       naas_abi/nexus/analytics/events/<sha256>.pkl

2. A debounced background thread rebuilds the aggregated artifacts that
   the Nexus dashboard reads from local disk:

       events.json — all per-event pickles, sorted by timestamp
       kpis.json   — windowed KPI snapshots (global, per-workspace,
                     per-user, per-user × per-workspace)

   These used to live in two standalone scripts (``generate_events.py``
   and ``generate_kpis.py``) that the endpoint shelled out to. Both are
   now inlined below so no subprocess hop is required and the rebuild
   shares the running API's object-storage handle.

   A manual ``POST /api/analytics/rebuild`` is also exposed for ad-hoc
   refresh.
"""

from __future__ import annotations

import hashlib
import json
import os
import pickle
import threading
import time
from collections import defaultdict
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from naas_abi_core import logger
from naas_abi_core.services.object_storage.ObjectStoragePort import Exceptions
from naas_abi_core.services.object_storage.ObjectStorageService import (
    ObjectStorageService,
)
from naas_abi_core.utils.StorageUtils import StorageUtils
from pydantic import BaseModel, Field

router = APIRouter()

OUTPUT_DIR = "naas_abi/nexus/analytics"
EVENTS_PREFIX = f"{OUTPUT_DIR}/events"
REF_USERS_FILE = "ref-users.json"
REF_WORKSPACES_FILE = "ref-workspaces.json"
EVENTS_FILE = "events.json"
KPIS_FILE = "kpis.json"
METADATA_FILE = "metadata.json"

# Local mirror — the Next.js dashboard and the rebuilt aggregates live on
# disk so the frontend can read them without an object-storage round trip.
# parents resolve as: endpoints → api → app → api → apps (the nexus apps/ dir).
_NEXUS_APPS_DIR = Path(__file__).resolve().parents[4]
_LOCAL_DATA_DIR = _NEXUS_APPS_DIR / "web" / "src" / "app" / "analytics" / "data"

_REBUILD_DEBOUNCE_SECONDS = 1.5

# KPI computation anchors the time windows at a fixed "now" so demo data
# inside the window stays visible regardless of wall clock.
_KPI_ANCHOR_NOW = datetime(2026, 5, 22, 12, 0, 0, tzinfo=UTC)
_KPI_SCENARIOS: list[tuple[str, int]] = [("last_7d", 7)]

# Debounced rebuild bookkeeping.
_rebuild_lock = threading.Lock()
_rebuild_timer: threading.Timer | None = None
_rebuild_running = False
_rebuild_pending = False


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
    stored_at: str = Field(description="object storage path of the per-event pickle")


class FileStats(BaseModel):
    file: str
    count: int
    duration_ms: int


class Metadata(BaseModel):
    updated_at: str
    duration_ms: int
    events: FileStats
    kpis: FileStats


class RebuildResponse(BaseModel):
    ok: bool = True
    metadata: Metadata


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
    """Mirror a JSON file to local disk for the dashboard."""
    try:
        _LOCAL_DATA_DIR.mkdir(parents=True, exist_ok=True)
        path = _LOCAL_DATA_DIR / file_name
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    except Exception as exc:
        logger.warning(f"[analytics] failed to mirror {file_name} locally: {exc}")


def _publish_json(
    storage_utils: StorageUtils, file_name: str, data: Any, copy: bool = False
) -> None:
    """Write a JSON aggregate to both object storage and the local mirror."""
    storage_utils.save_json(
        data=data,
        dir_path=OUTPUT_DIR,
        file_name=file_name,
        copy=copy,
    )
    _mirror_local(file_name, data)


def _save_refs(file_name: str, data: list[dict[str, Any]], storage: ObjectStorageService) -> None:
    _publish_json(StorageUtils(storage_service=storage), file_name, data)


def _upsert_refs(event: AnalyticsEvent, storage: ObjectStorageService) -> None:
    if event.workspace_id:
        workspaces: list[dict[str, Any]] = _read_json(storage, REF_WORKSPACES_FILE, [])
        existing = next(
            (w for w in workspaces if w.get("workspace_id") == event.workspace_id),
            None,
        )
        changed = False
        if existing is None:
            workspaces.append(
                {
                    "workspace_id": event.workspace_id,
                    "workspace_name": event.workspace_name or event.workspace_id,
                }
            )
            changed = True
        elif event.workspace_name and existing.get("workspace_name") != event.workspace_name:
            existing["workspace_name"] = event.workspace_name
            changed = True
        if changed:
            _save_refs(REF_WORKSPACES_FILE, workspaces, storage)

    if event.user_id and event.user_email:
        users: list[dict[str, Any]] = _read_json(storage, REF_USERS_FILE, [])
        existing = next((u for u in users if u.get("user_id") == event.user_id), None)
        changed = False
        if existing is None:
            users.append(
                {
                    "user_id": event.user_id,
                    "user_email": event.user_email,
                    "workspace_ids": [event.workspace_id] if event.workspace_id else [],
                }
            )
            changed = True
        else:
            if existing.get("user_email") != event.user_email:
                existing["user_email"] = event.user_email
                changed = True
            if event.workspace_id and event.workspace_id not in existing.get(
                "workspace_ids", []
            ):
                existing.setdefault("workspace_ids", []).append(event.workspace_id)
                changed = True
        if changed:
            _save_refs(REF_USERS_FILE, users, storage)


# ---------------------------------------------------------------------------
# Rebuild: events.json (from per-event pickles)
# ---------------------------------------------------------------------------


def _rebuild_events(storage_utils: StorageUtils, storage: ObjectStorageService) -> list[dict]:
    """Read every per-event pickle, materialize ``events.json`` in storage and on disk."""

    try:
        keys = storage.list_objects(prefix=EVENTS_PREFIX)
    except Exceptions.ObjectNotFound:
        keys = []

    events: list[dict] = []
    for full_key in keys:
        filename = os.path.basename(full_key)
        if not filename.endswith(".pkl"):
            continue
        event = storage_utils.get_pickle(EVENTS_PREFIX, filename)
        if isinstance(event, dict):
            events.append(event)
        else:
            logger.debug(f"[analytics] skip {filename}: not a dict")

    events.sort(key=lambda e: e.get("timestamp", ""))
    _publish_json(storage_utils, EVENTS_FILE, {"events": events})
    return events


# ---------------------------------------------------------------------------
# Rebuild: kpis.json (from in-memory events)
# ---------------------------------------------------------------------------


def _fmt_number(n: float) -> str:
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n / 1_000:.1f}k"
    return str(int(n))


def _fmt_duration(seconds: int) -> str:
    if seconds <= 0:
        return "—"
    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60
    if h > 0:
        return f"{h}h {m}m"
    if m > 0:
        return f"{m}m {s}s"
    return f"{s}s"


def _build_sessions(events: list[dict]) -> list[dict]:
    by_session: dict[str, list[dict]] = defaultdict(list)
    for e in events:
        by_session[e["session_id"]].append(e)

    sessions = []
    for session_id, evts in by_session.items():
        evts.sort(key=lambda x: x["timestamp"])
        first, last = evts[0], evts[-1]
        sessions.append(
            {
                "session_id": session_id,
                "user_id": first.get("user_id"),
                "user_email": first.get("user_email"),
                "workspace_id": first.get("workspace_id"),
                "workspace_name": first.get("workspace_name"),
                "started_at": first["timestamp"],
                "ended_at": last["timestamp"],
                "page_views": sum(1 for e in evts if e["event_name"] == "page_viewed"),
                "events": len(evts),
            }
        )
    return sessions


def _session_duration_sec(s: dict) -> int:
    def parse(ts: str) -> datetime:
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))

    return max(0, int((parse(s["ended_at"]) - parse(s["started_at"])).total_seconds()))


def _compute_kpi_rows(
    events: list[dict],
    workspace_id: str,
    user_id: str,
    scenario: str,
    date: str,
) -> list[dict]:
    def row(title: str, label: str, meta: str, value: float, value_d: str) -> dict:
        return {
            "workspace_id": workspace_id,
            "user_id": user_id,
            "scenario": scenario,
            "date": date,
            "title": title,
            "label": label,
            "meta": meta,
            "value": value,
            "value_d": value_d,
        }

    sessions = _build_sessions(events)
    page_views = [e for e in events if e.get("event_name") == "page_viewed"]
    active_users = {e["user_email"] for e in events if e.get("user_email")}
    workspaces = {e["workspace_id"] for e in events if e.get("workspace_id")}

    sessions_by_user: dict[str, list] = defaultdict(list)
    for s in sessions:
        if s.get("user_email"):
            sessions_by_user[s["user_email"]].append(s)

    total_duration = sum(_session_duration_sec(s) for s in sessions)
    avg_duration = int(total_duration / len(sessions)) if sessions else 0
    returning = sum(1 for arr in sessions_by_user.values() if len(arr) > 1)
    avg_per_user = round(len(sessions) / len(active_users), 1) if active_users else 0.0

    ws_counts: dict[str, dict] = {}
    for e in events:
        if e.get("workspace_id"):
            wid = e["workspace_id"]
            if wid not in ws_counts:
                ws_counts[wid] = {"name": e.get("workspace_name", wid), "events": 0}
            ws_counts[wid]["events"] += 1
    top_ws = max(ws_counts.values(), key=lambda x: x["events"]) if ws_counts else None

    t = "Engagement"
    return [
        row(t, "Active users", "", len(active_users), _fmt_number(len(active_users))),
        row(t, "Sessions", "", len(sessions), _fmt_number(len(sessions))),
        row(t, "Avg. sessions / user", "", avg_per_user, f"{avg_per_user:.1f}"),
        row(t, "Page views", "", len(page_views), _fmt_number(len(page_views))),
        row(t, "Workspaces used", "", len(workspaces), _fmt_number(len(workspaces))),
        row(t, "Avg. session duration", "", avg_duration, _fmt_duration(avg_duration)),
        row(t, "Returning users", "", returning, _fmt_number(returning)),
        row(
            t,
            "Most active workspace",
            f"{_fmt_number(top_ws['events'])} events" if top_ws else "",
            top_ws["events"] if top_ws else 0,
            top_ws["name"] if top_ws else "—",
        ),
    ]


def _slice_events(
    events: list[dict],
    start_s: str,
    end_s: str,
    uid: str | None,
    wid: str | None,
) -> list[dict]:
    return [
        e
        for e in events
        if start_s <= e["timestamp"] <= end_s
        and (not uid or uid == "all" or e.get("user_id") == uid)
        and (not wid or wid == "all" or e.get("workspace_id") == wid)
    ]


def _rebuild_kpis(storage_utils: StorageUtils, events: list[dict]) -> list[dict]:
    """Compute every KPI row from an in-memory events list, write kpis.json."""

    user_ids = sorted({e["user_id"] for e in events if e.get("user_id")})
    workspace_ids = sorted({e["workspace_id"] for e in events if e.get("workspace_id")})

    rows: list[dict] = []

    for scenario, days in _KPI_SCENARIOS:
        end = _KPI_ANCHOR_NOW
        start = end - timedelta(days=days)
        start_s = start.strftime("%Y-%m-%dT%H:%M:%S")
        end_s = end.strftime("%Y-%m-%dT%H:%M:%S")
        snapshot_date = _KPI_ANCHOR_NOW.strftime("%Y-%m-%d")

        rows.extend(
            _compute_kpi_rows(
                _slice_events(events, start_s, end_s, None, None),
                "all", "all", scenario, snapshot_date,
            )
        )

        for wid in workspace_ids:
            rows.extend(
                _compute_kpi_rows(
                    _slice_events(events, start_s, end_s, None, wid),
                    wid, "all", scenario, snapshot_date,
                )
            )

        for uid in user_ids:
            rows.extend(
                _compute_kpi_rows(
                    _slice_events(events, start_s, end_s, uid, None),
                    "all", uid, scenario, snapshot_date,
                )
            )

        for uid in user_ids:
            for wid in workspace_ids:
                evts = _slice_events(events, start_s, end_s, uid, wid)
                if evts:
                    rows.extend(
                        _compute_kpi_rows(evts, wid, uid, scenario, snapshot_date)
                    )

    _publish_json(storage_utils, KPIS_FILE, {"kpis": rows})
    return rows


# ---------------------------------------------------------------------------
# Rebuild orchestration (debounced)
# ---------------------------------------------------------------------------


def _rebuild_all(storage_utils: StorageUtils, storage: ObjectStorageService) -> Metadata:
    overall_start = time.monotonic()

    events_start = time.monotonic()
    events = _rebuild_events(storage_utils, storage)
    events_ms = int((time.monotonic() - events_start) * 1000)

    kpis_start = time.monotonic()
    rows = _rebuild_kpis(storage_utils, events)
    kpis_ms = int((time.monotonic() - kpis_start) * 1000)

    metadata = Metadata(
        updated_at=datetime.now(UTC).isoformat(),
        duration_ms=int((time.monotonic() - overall_start) * 1000),
        events=FileStats(file=EVENTS_FILE, count=len(events), duration_ms=events_ms),
        kpis=FileStats(file=KPIS_FILE, count=len(rows), duration_ms=kpis_ms),
    )
    _publish_json(storage_utils, METADATA_FILE, metadata.model_dump())
    return metadata


def _run_rebuild(storage_utils: StorageUtils, storage: ObjectStorageService) -> None:
    global _rebuild_running, _rebuild_pending
    with _rebuild_lock:
        if _rebuild_running:
            _rebuild_pending = True
            return
        _rebuild_running = True
    try:
        meta = _rebuild_all(storage_utils, storage)
        logger.debug(
            f"[analytics] rebuilt: {meta.events.count} events, {meta.kpis.count} kpi rows"
        )
    except Exception as exc:
        logger.warning(f"[analytics] rebuild failed: {exc}")
    finally:
        with _rebuild_lock:
            _rebuild_running = False
            rerun = _rebuild_pending
            _rebuild_pending = False
        if rerun:
            _run_rebuild(storage_utils, storage)


def _schedule_rebuild(
    storage_utils: StorageUtils, storage: ObjectStorageService
) -> None:
    global _rebuild_timer
    with _rebuild_lock:
        if _rebuild_timer is not None:
            _rebuild_timer.cancel()
        _rebuild_timer = threading.Timer(
            _REBUILD_DEBOUNCE_SECONDS,
            _run_rebuild,
            args=[storage_utils, storage],
        )
        _rebuild_timer.daemon = True
        _rebuild_timer.start()


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.post("/events", response_model=IngestResponse)
async def ingest_event(
    event: AnalyticsEvent,
    storage: ObjectStorageService = Depends(get_object_storage),
    storage_utils: StorageUtils = Depends(get_storage_utils),
) -> IngestResponse:
    """Persist one analytics event as ``<sha256>.pkl`` in object storage."""

    payload = event.model_dump(exclude_none=True)
    digest = hashlib.sha256(pickle.dumps(payload)).hexdigest()
    key = f"{digest}.pkl"

    storage_utils.save_pickle(
        obj=payload,
        dir_path=EVENTS_PREFIX,
        file_name=key,
        copy=False,  # filename is already content-hashed; no audit copy needed.
    )
    _upsert_refs(event, storage)
    _schedule_rebuild(storage_utils, storage)

    return IngestResponse(stored_at=f"{EVENTS_PREFIX}/{key}")


@router.post("/rebuild", response_model=RebuildResponse)
async def rebuild_now(
    storage: ObjectStorageService = Depends(get_object_storage),
    storage_utils: StorageUtils = Depends(get_storage_utils),
) -> RebuildResponse:
    """Synchronously rebuild ``events.json`` and ``kpis.json`` from storage."""

    metadata = _rebuild_all(storage_utils, storage)
    return RebuildResponse(metadata=metadata)


@router.get("/metadata", response_model=Metadata | None)
async def get_metadata(
    storage: ObjectStorageService = Depends(get_object_storage),
) -> Metadata | None:
    """Return the last rebuild timestamp + per-file stats, or null if never rebuilt."""

    raw = _read_json(storage, METADATA_FILE, None)
    if raw is None:
        return None
    try:
        return Metadata.model_validate(raw)
    except Exception as exc:
        logger.warning(f"[analytics] invalid metadata.json in storage: {exc}")
        return None
