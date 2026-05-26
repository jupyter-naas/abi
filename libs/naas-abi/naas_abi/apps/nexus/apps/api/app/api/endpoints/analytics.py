"""Analytics ingestion, rollup, and query endpoints.

Write path:

1. Each event POSTed by the frontend is persisted as an individual pickle
   in object storage, keyed by content hash:

       naas_abi/nexus/analytics/events/<sha256>.pkl

2. A debounced background thread rebuilds the aggregated artifacts stored
   in object storage:

       events.json — all per-event pickles, sorted by timestamp
       kpis.json   — windowed KPI snapshots (global, per-workspace,
                     per-user, per-user × per-workspace)

   A manual ``POST /api/analytics/rebuild`` is also exposed for ad-hoc
   refresh.

Read path:

The GET endpoints (overview, users, sessions, pages, workspaces, events)
read events.json from object storage, apply filters, and aggregate on the
fly. The Next.js dashboard proxies these endpoints instead of reading local
JSON mirrors.
"""

from __future__ import annotations

import hashlib
import json
import os
import pickle
import re
import threading
import time
import urllib.parse
from collections import defaultdict
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from naas_abi_core import logger
from naas_abi_core.services.object_storage.ObjectStoragePort import Exceptions
from naas_abi_core.services.object_storage.ObjectStorageService import (
    ObjectStorageService,
)
from naas_abi_core.services.triple_store.TripleStoreService import TripleStoreService
from naas_abi_core.utils.StorageUtils import StorageUtils
from pydantic import BaseModel, Field
from rdflib import Graph as RDFGraph
from rdflib import URIRef
from rdflib.query import ResultRow

router = APIRouter()

NEXUS_GRAPH_URI = URIRef("http://ontology.naas.ai/graph/nexus-logs")

OUTPUT_DIR = "naas_abi/nexus/analytics"
EVENTS_PREFIX = f"{OUTPUT_DIR}/events"
REF_USERS_FILE = "ref-users.json"
REF_WORKSPACES_FILE = "ref-workspaces.json"
EVENTS_FILE = "events.json"
KPIS_FILE = "kpis.json"
METADATA_FILE = "metadata.json"

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


def get_triple_store(request: Request) -> TripleStoreService | None:
    """Return the configured triple store, or None if unavailable.

    Analytics ingestion to the knowledge graph is best-effort: the per-event
    pickle is the source of truth, the graph is a derived projection. If the
    engine isn't loaded yet, skip silently rather than failing the request.
    """
    store = getattr(request.app.state, "triple_store", None)
    if store is not None:
        return store
    try:
        from naas_abi import ABIModule

        module = ABIModule.get_instance()
        store = module.engine.services.triple_store
        request.app.state.triple_store = store
        return store
    except Exception as exc:
        logger.debug(f"[analytics] triple store unavailable: {exc}")
        return None


# ---------------------------------------------------------------------------
# Storage helpers
# ---------------------------------------------------------------------------


def _read_json(storage: ObjectStorageService, file_name: str, fallback: Any) -> Any:
    try:
        raw = storage.get_object(OUTPUT_DIR, file_name)
        if raw is None:
            return fallback
        return json.loads(raw.decode("utf-8"))
    except Exception as exc:
        logger.debug(f"[analytics] {file_name} not present in storage: {exc}")
        return fallback


def _publish_json(
    storage_utils: StorageUtils, file_name: str, data: Any, copy: bool = False
) -> None:
    """Write a JSON aggregate to object storage."""
    storage_utils.save_json(
        data=data,
        dir_path=OUTPUT_DIR,
        file_name=file_name,
        copy=copy,
    )


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
            if event.workspace_id and event.workspace_id not in existing.get("workspace_ids", []):
                existing.setdefault("workspace_ids", []).append(event.workspace_id)
                changed = True
        if changed:
            _save_refs(REF_USERS_FILE, users, storage)


# ---------------------------------------------------------------------------
# Knowledge graph ingestion (write-path projection of analytics events)
# ---------------------------------------------------------------------------


def _find_uri_by_label(
    triple_store: TripleStoreService,
    class_uri: str,
    label: str,
) -> str | None:
    """Return the URI of the first instance of ``class_uri`` whose
    ``rdfs:label`` equals ``label`` in the Nexus graph, or None."""
    escaped = label.replace("\\", "\\\\").replace('"', '\\"')
    rows = triple_store.query(
        f"""
        PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        SELECT ?uri WHERE {{
            GRAPH <{str(NEXUS_GRAPH_URI)}> {{
                ?uri rdf:type <{class_uri}> ;
                     rdfs:label "{escaped}" .
            }}
        }} LIMIT 1
        """
    )
    for row in rows:
        assert isinstance(row, ResultRow)
        return str(row[0])
    return None


def _find_visit_session_by_session_id(
    triple_store: TripleStoreService,
    session_id: str,
) -> tuple[str | None, str | None]:
    """Return ``(session_uri, interval_uri)`` for an existing VisitSession
    whose ``nexus:session_id`` matches *session_id*, or ``(None, None)``."""
    escaped = session_id.replace("\\", "\\\\").replace('"', '\\"')
    rows = triple_store.query(
        f"""
        PREFIX nexus: <http://ontology.naas.ai/nexus/>
        SELECT ?session_uri ?interval_uri WHERE {{
            GRAPH <{str(NEXUS_GRAPH_URI)}> {{
                ?session_uri nexus:session_id "{escaped}" .
                OPTIONAL {{ ?session_uri nexus:hasSessionInterval ?interval_uri . }}
            }}
        }} LIMIT 1
        """
    )
    for row in rows:
        assert isinstance(row, ResultRow)
        s = str(row[0]) if row[0] else None
        i = str(row[1]) if row[1] else None
        return s, i
    return None, None


def _ingest_page_view_event(event: AnalyticsEvent, triple_store: TripleStoreService) -> None:
    """Project a ``page_viewed`` analytics event into the Nexus knowledge graph.

    Strategy:
    1. Resolve each related continuant (User, Workspace, Page, VisitSession,
       UserSite, TemporalInstant) by ``rdfs:label`` — reuse the existing URI
       when present, otherwise build a new instance.
    2. Stage all instance triples first (without inter-entity relations).
    3. Build the PageView process node and attach the relations to the
       resolved URIs.
    4. Insert everything in one batch into ``http://ontology.naas.ai/graph/nexus``.
    """
    # Imported lazily so importing this module doesn't force loading the
    # full ontology module (~5k lines) when the API runs without the engine.
    from naas_abi.ontologies.modules.NexusPlatformOntology import (
        Page,
        PageView,
        TemporalInstant,
        User,
        UserSite,
        VisitSession,
        Workspace,
    )

    inserted = RDFGraph()

    def _resolve_or_create(cls, label: str, **kwargs):
        """Return URIRef for an entity, reusing existing or creating new."""
        existing = _find_uri_by_label(triple_store, cls._class_uri, label)
        if existing is not None:
            return URIRef(existing)
        instance = cls(label=label, **kwargs)
        inserted.__iadd__(instance.rdf())
        return URIRef(instance._uri)

    # --- Step 1: resolve / create all related instances ---------------------

    user_uri: URIRef | None = None
    if event.user_email:
        user_uri = _resolve_or_create(
            User, event.user_email, user_id=event.user_id, email=event.user_email
        )

    workspace_uri: URIRef | None = None
    if event.workspace_id:
        ws_label = event.workspace_name or event.workspace_id
        workspace_uri = _resolve_or_create(
            Workspace,
            ws_label,
            workspace_id=event.workspace_id,
            workspace_name=event.workspace_name,
        )

    page_uri: URIRef | None = None
    if event.page_path:
        page_uri = _resolve_or_create(
            Page,
            event.page_path,
            page_path=event.page_path,
            page_title=event.page_title,
        )

    # Reuse the VisitSession URI already persisted by _ingest_visit_session_event
    # (which always runs before this function for page_viewed events).
    session_uri: URIRef | None = None
    if event.session_id:
        existing_session, _ = _find_visit_session_by_session_id(triple_store, event.session_id)
        if existing_session:
            session_uri = URIRef(existing_session)
        else:
            session_uri = _resolve_or_create(
                VisitSession, event.session_id, session_id=event.session_id
            )

    site_uri: URIRef | None = None
    site_label_parts = [p for p in (event.country, event.device, event.browser) if p]
    if site_label_parts:
        site_label = " / ".join(site_label_parts)
        site_uri = _resolve_or_create(
            UserSite,
            site_label,
            country=event.country,
            device=event.device,
            browser=event.browser,
        )

    instant_uri = URIRef(_resolve_or_create(TemporalInstant, event.timestamp))

    # --- Step 2: build the PageView process and attach relations ------------

    page_view = PageView(label=event.event_id, event_id=event.event_id)
    if event.referrer:
        page_view.referrer = event.referrer
    if user_uri is not None:
        page_view.viewed_by = [user_uri]
    if workspace_uri is not None:
        page_view.occurs_in_workspace = [workspace_uri]
    if page_uri is not None:
        page_view.has_visited_page = [page_uri]
    if session_uri is not None:
        page_view.occurs_during_session = [session_uri]
    if site_uri is not None:
        page_view.occurs_in = [site_uri]
    page_view.viewed_at = [instant_uri]

    inserted += page_view.rdf()

    # --- Step 3: insert into the Nexus graph --------------------------------

    if len(inserted) > 0:
        triple_store.insert(inserted, graph_name=NEXUS_GRAPH_URI)


def _ingest_visit_session_event(event: AnalyticsEvent, triple_store: TripleStoreService) -> None:
    """Create or update the VisitSession process node for the session carried by *event*.

    - **First occurrence** of a ``session_id``: create a new ``VisitSession``
      with a ``VisitSessionInterval`` whose ``startedAt`` and ``endedAt`` are
      both set to ``event.timestamp``.
    - **Subsequent occurrences**: advance ``endedAt`` on the existing
      ``VisitSessionInterval`` to ``event.timestamp`` so that the interval
      always reflects the true end of the session seen so far.
    """
    from naas_abi.ontologies.modules.NexusPlatformOntology import (
        TemporalInstant,
        User,
        UserSite,
        VisitSession,
        VisitSessionInterval,
        Workspace,
    )

    session_uri, interval_uri = _find_visit_session_by_session_id(triple_store, event.session_id)

    new_end_instant = TemporalInstant(label=event.timestamp)
    new_end_uri = URIRef(new_end_instant._uri)

    if session_uri is not None and interval_uri is not None:
        # --- Update path: advance endedAt on the existing interval ----------

        # Collect existing endedAt object URIs so we can retract them.
        old_rows = triple_store.query(
            f"""
            PREFIX nexus: <http://ontology.naas.ai/nexus/>
            SELECT ?ended_at WHERE {{
                GRAPH <{str(NEXUS_GRAPH_URI)}> {{
                    <{interval_uri}> nexus:endedAt ?ended_at .
                }}
            }}
            """
        )
        remove_graph = RDFGraph()
        for old_row in old_rows:
            assert isinstance(old_row, ResultRow)
            if old_row[0]:
                remove_graph.add(
                    (
                        URIRef(interval_uri),
                        URIRef("http://ontology.naas.ai/nexus/endedAt"),
                        URIRef(str(old_row[0])),
                    )
                )
        if len(remove_graph) > 0:
            triple_store.remove(remove_graph, NEXUS_GRAPH_URI)

        # Insert new end instant + updated endedAt triple.
        inserted = RDFGraph()
        inserted += new_end_instant.rdf()
        inserted.add(
            (
                URIRef(interval_uri),
                URIRef("http://ontology.naas.ai/nexus/endedAt"),
                new_end_uri,
            )
        )
        triple_store.insert(inserted, NEXUS_GRAPH_URI)

    else:
        # --- Create path: first time we see this session --------------------

        inserted = RDFGraph()

        # Reuse already-persisted continuant URIs when available (best-effort).
        def _resolve_existing(cls, label: str) -> URIRef | None:
            existing = _find_uri_by_label(triple_store, cls._class_uri, label)
            return URIRef(existing) if existing else None

        user_uri: URIRef | None = None
        if event.user_email:
            user_uri = _resolve_existing(User, event.user_email)

        workspace_uri: URIRef | None = None
        if event.workspace_id:
            ws_label = event.workspace_name or event.workspace_id
            workspace_uri = _resolve_existing(Workspace, ws_label)

        site_uri: URIRef | None = None
        site_label_parts = [p for p in (event.country, event.device, event.browser) if p]
        if site_label_parts:
            site_label = " / ".join(site_label_parts)
            site_uri = _resolve_existing(UserSite, site_label)

        # startedAt and endedAt are both the current event timestamp on creation.
        start_instant = TemporalInstant(label=event.timestamp)
        inserted += start_instant.rdf()
        inserted += new_end_instant.rdf()

        interval = VisitSessionInterval(
            label=event.session_id,
            start_at=[URIRef(start_instant._uri)],
            ended_at=[new_end_uri],
        )
        inserted += interval.rdf()

        visit_session = VisitSession(
            label=event.session_id,
            session_id=event.session_id,
            has_session_interval=[URIRef(interval._uri)],
        )
        if user_uri is not None:
            visit_session.started_by = [user_uri]
        if workspace_uri is not None:
            visit_session.occurs_in_workspace = [workspace_uri]
        if site_uri is not None:
            visit_session.occurs_in = [site_uri]

        inserted += visit_session.rdf()

        if len(inserted) > 0:
            triple_store.insert(inserted, NEXUS_GRAPH_URI)


def _ingest_event_to_graph(event: AnalyticsEvent, triple_store: TripleStoreService | None) -> None:
    """Dispatch an event to the matching knowledge-graph projection.

    Best-effort: failures are logged but never propagated — the per-event
    pickle has already been persisted by the caller and remains the source
    of truth.
    """
    if triple_store is None:
        return
    try:
        if event.event_name == "page_viewed":
            # Visit session must be created/updated before the page-view node
            # so that _ingest_page_view_event can reference the persisted URI.
            if event.session_id:
                _ingest_visit_session_event(event, triple_store)
            _ingest_page_view_event(event, triple_store)
    except Exception as exc:
        logger.warning(
            f"[analytics] failed to project event {event.event_id} "
            f"({event.event_name}) to nexus graph: {exc}"
        )


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
                "all",
                "all",
                scenario,
                snapshot_date,
            )
        )

        for wid in workspace_ids:
            rows.extend(
                _compute_kpi_rows(
                    _slice_events(events, start_s, end_s, None, wid),
                    wid,
                    "all",
                    scenario,
                    snapshot_date,
                )
            )

        for uid in user_ids:
            rows.extend(
                _compute_kpi_rows(
                    _slice_events(events, start_s, end_s, uid, None),
                    "all",
                    uid,
                    scenario,
                    snapshot_date,
                )
            )

        for uid in user_ids:
            for wid in workspace_ids:
                evts = _slice_events(events, start_s, end_s, uid, wid)
                if evts:
                    rows.extend(_compute_kpi_rows(evts, wid, uid, scenario, snapshot_date))

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
        logger.debug(f"[analytics] rebuilt: {meta.events.count} events, {meta.kpis.count} kpi rows")
    except Exception as exc:
        logger.warning(f"[analytics] rebuild failed: {exc}")
    finally:
        with _rebuild_lock:
            _rebuild_running = False
            rerun = _rebuild_pending
            _rebuild_pending = False
        if rerun:
            _run_rebuild(storage_utils, storage)


def _schedule_rebuild(storage_utils: StorageUtils, storage: ObjectStorageService) -> None:
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
# Read-path helpers (query, filter, aggregate)
# ---------------------------------------------------------------------------


def _read_events_from_storage(storage: ObjectStorageService) -> list[dict]:
    data = _read_json(storage, EVENTS_FILE, {"events": []})
    if not isinstance(data, dict):
        return []
    events = data.get("events", [])
    return events if isinstance(events, list) else []


def _filter_events(
    events: list[dict],
    start_date: str | None,
    end_date: str | None,
    user_email: str | None,
    workspace_id: str | None,
) -> list[dict]:
    return [
        e
        for e in events
        if (not start_date or e.get("timestamp", "") >= start_date)
        and (not end_date or e.get("timestamp", "") <= end_date)
        and (not user_email or user_email == "all" or e.get("user_email") == user_email)
        and (not workspace_id or workspace_id == "all" or e.get("workspace_id") == workspace_id)
    ]


def _build_full_session_rows(events: list[dict]) -> list[dict]:
    by_session: dict[str, list[dict]] = defaultdict(list)
    for e in events:
        sid = e.get("session_id")
        if sid:
            by_session[sid].append(e)

    rows: list[dict] = []
    for session_id, evts in by_session.items():
        evts.sort(key=lambda x: x.get("timestamp", ""))
        first, last = evts[0], evts[-1]
        dur = _session_duration_sec(
            {"started_at": first["timestamp"], "ended_at": last["timestamp"]}
        )
        rows.append(
            {
                "session_id": session_id,
                "user_email": first.get("user_email") or "unknown",
                "workspace_name": first.get("workspace_name"),
                "started_at": first["timestamp"],
                "ended_at": last["timestamp"],
                "duration_seconds": dur,
                "page_views": sum(1 for e in evts if e.get("event_name") == "page_viewed"),
                "events": len(evts),
                "device": first.get("device"),
                "browser": first.get("browser"),
            }
        )
    rows.sort(key=lambda x: x["started_at"], reverse=True)
    return rows


def _build_user_rows(events: list[dict]) -> list[dict]:
    by_user: dict[str, list[dict]] = defaultdict(list)
    for e in events:
        if e.get("user_email"):
            by_user[e["user_email"]].append(e)

    rows: list[dict] = []
    for email, evts in by_user.items():
        sessions = {e["session_id"] for e in evts if e.get("session_id")}
        workspaces = {e["workspace_id"] for e in evts if e.get("workspace_id")}
        page_views = sum(1 for e in evts if e.get("event_name") == "page_viewed")
        last = max(evts, key=lambda e: e.get("timestamp", ""))
        rows.append(
            {
                "user_id": last.get("user_id") or "",
                "user_email": email,
                "sessions": len(sessions),
                "page_views": page_views,
                "workspaces": len(workspaces),
                "last_seen": last.get("timestamp") or "",
                "total_events": len(evts),
            }
        )
    rows.sort(key=lambda x: x["total_events"], reverse=True)
    return rows


_CHAT_CONV_PATH_RE = re.compile(r"/chat/(conv-[^/?#]+)")


def _decorate_page_title(title: str, path: str) -> str:
    # Chat conversation pages share the title "Chat" — re-derive the conv
    # suffix from the path so each conversation appears as its own row even
    # for events stored before write-time decoration was added.
    m = _CHAT_CONV_PATH_RE.search(path or "")
    if not m:
        return title
    conv = m.group(1)
    return title if conv in title else f"{title} - {conv}"


def _build_page_rows(events: list[dict]) -> list[dict]:
    views = [e for e in events if e.get("event_name") == "page_viewed" and e.get("page_path")]
    by_page: dict[str, list[dict]] = defaultdict(list)
    for e in views:
        by_page[e["page_path"]].append(e)  # type: ignore[index]

    rows: list[dict] = []
    for page_path, evts in by_page.items():
        unique_users = {e.get("user_email") for e in evts if e.get("user_email")}
        base_title = evts[0].get("page_title") or page_path
        rows.append(
            {
                "page_path": page_path,
                "page_title": _decorate_page_title(base_title, page_path),
                "views": len(evts),
                "unique_users": len(unique_users),
            }
        )
    rows.sort(key=lambda x: x["views"], reverse=True)
    return rows


def _build_workspace_rows(events: list[dict]) -> list[dict]:
    with_ws = [e for e in events if e.get("workspace_id")]
    by_ws: dict[str, list[dict]] = defaultdict(list)
    for e in with_ws:
        by_ws[e["workspace_id"]].append(e)  # type: ignore[index]

    rows: list[dict] = []
    for ws_id, evts in by_ws.items():
        sessions = {e["session_id"] for e in evts if e.get("session_id")}
        users = {e.get("user_email") for e in evts if e.get("user_email")}
        rows.append(
            {
                "workspace_id": ws_id,
                "workspace_name": evts[0].get("workspace_name") or ws_id,
                "active_users": len(users),
                "sessions": len(sessions),
                "events": len(evts),
            }
        )
    rows.sort(key=lambda x: x["events"], reverse=True)
    return rows


def _range_days(start_date: str | None, end_date: str | None) -> list[str]:
    now = datetime.now(UTC)
    end = datetime.fromisoformat(end_date.replace("Z", "+00:00")).date() if end_date else now.date()
    start = (
        datetime.fromisoformat(start_date.replace("Z", "+00:00")).date()
        if start_date
        else (now - timedelta(days=30)).date()
    )
    days: list[str] = []
    cursor = start
    while cursor <= end:
        days.append(cursor.isoformat())
        cursor += timedelta(days=1)
    return days


def _build_overview(events: list[dict], start_date: str | None, end_date: str | None) -> dict:
    days = _range_days(start_date, end_date)
    sessions = _build_sessions(events)
    page_views = [e for e in events if e.get("event_name") == "page_viewed"]
    active_users: set[str] = {e["user_email"] for e in events if e.get("user_email")}
    workspace_set: set[str] = {e["workspace_id"] for e in events if e.get("workspace_id")}

    sessions_by_user: dict[str, list] = defaultdict(list)
    for s in sessions:
        if s.get("user_email"):
            sessions_by_user[s["user_email"]].append(s)

    total_duration = sum(_session_duration_sec(s) for s in sessions)
    avg_session_duration = int(total_duration / len(sessions)) if sessions else 0
    returning_users = sum(1 for arr in sessions_by_user.values() if len(arr) > 1)
    avg_sessions_per_user = round(len(sessions) / len(active_users), 1) if active_users else 0.0

    ws_event_counts: dict[str, dict] = {}
    for e in events:
        if e.get("workspace_id"):
            wid = e["workspace_id"]
            if wid not in ws_event_counts:
                ws_event_counts[wid] = {
                    "id": wid,
                    "name": e.get("workspace_name") or wid,
                    "events": 0,
                }
            ws_event_counts[wid]["events"] += 1
    most_active_workspace = (
        max(ws_event_counts.values(), key=lambda x: x["events"]) if ws_event_counts else None
    )

    kpi = {
        "active_users": len(active_users),
        "total_sessions": len(sessions),
        "avg_sessions_per_user": avg_sessions_per_user,
        "total_page_views": len(page_views),
        "workspaces_used": len(workspace_set),
        "avg_session_duration_seconds": avg_session_duration,
        "returning_users": returning_users,
        "most_active_workspace": most_active_workspace,
    }

    sessions_by_day: dict[str, set] = {}
    for s in sessions:
        k = s["started_at"][:10]
        sessions_by_day.setdefault(k, set()).add(s["session_id"])
    sessions_over_time = [{"date": d, "value": len(sessions_by_day.get(d, set()))} for d in days]

    users_by_day: dict[str, set] = {}
    for e in events:
        if e.get("user_email"):
            k = e["timestamp"][:10]
            users_by_day.setdefault(k, set()).add(e["user_email"])
    active_users_over_time = [{"date": d, "value": len(users_by_day.get(d, set()))} for d in days]

    user_rows = _build_user_rows(events)
    page_rows = _build_page_rows(events)
    workspace_rows = _build_workspace_rows(events)
    recent_activity = sorted(events, key=lambda e: e.get("timestamp", ""), reverse=True)[:25]

    return {
        "kpi": kpi,
        "sessions_over_time": sessions_over_time,
        "active_users_over_time": active_users_over_time,
        "top_users": user_rows[:10],
        "top_pages": page_rows[:10],
        "workspace_activity": workspace_rows,
        "recent_activity": recent_activity,
    }


def _build_user_detail(events: list[dict], email: str) -> dict | None:
    user_events = [e for e in events if e.get("user_email") == email]
    if not user_events:
        return None

    sorted_events = sorted(user_events, key=lambda e: e.get("timestamp", ""))
    first = sorted_events[0]
    last = sorted_events[-1]

    session_ids = {e["session_id"] for e in sorted_events if e.get("session_id")}
    page_views_list = [e for e in sorted_events if e.get("event_name") == "page_viewed"]
    pages = _build_page_rows(user_events)
    sessions = _build_full_session_rows(user_events)

    workspace_map: dict[str, str] = {}
    for e in user_events:
        if e.get("workspace_id"):
            workspace_map[e["workspace_id"]] = e.get("workspace_name") or e["workspace_id"]

    most_visited = (
        {
            "path": pages[0]["page_path"],
            "title": pages[0]["page_title"],
            "views": pages[0]["views"],
        }
        if pages
        else None
    )

    return {
        "user_email": email,
        "user_id": first.get("user_id") or "",
        "first_seen": first.get("timestamp") or "",
        "last_seen": last.get("timestamp") or "",
        "total_sessions": len(session_ids),
        "total_page_views": len(page_views_list),
        "workspaces_used": [{"id": k, "name": v} for k, v in workspace_map.items()],
        "most_visited_page": most_visited,
        "sessions": sessions,
        "pages": pages,
        "events": list(reversed(sorted_events)),
    }


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.post("/events", response_model=IngestResponse)
async def ingest_event(
    event: AnalyticsEvent,
    storage: ObjectStorageService = Depends(get_object_storage),
    storage_utils: StorageUtils = Depends(get_storage_utils),
    triple_store: TripleStoreService | None = Depends(get_triple_store),
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
    # _ingest_event_to_graph(event, triple_store)
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


@router.get("/overview")
async def get_overview(
    start_date: str | None = Query(None),
    end_date: str | None = Query(None),
    user_email: str | None = Query(None),
    workspace_id: str | None = Query(None),
    storage: ObjectStorageService = Depends(get_object_storage),
) -> dict:
    """Return overview KPIs, timeseries, and top-N aggregates."""
    all_events = _read_events_from_storage(storage)
    events = _filter_events(all_events, start_date, end_date, user_email, workspace_id)
    return _build_overview(events, start_date, end_date)


@router.get("/users")
async def get_users(
    start_date: str | None = Query(None),
    end_date: str | None = Query(None),
    user_email: str | None = Query(None),
    workspace_id: str | None = Query(None),
    storage: ObjectStorageService = Depends(get_object_storage),
) -> dict:
    """Return per-user stats and the ref-users directory."""
    all_events = _read_events_from_storage(storage)
    events = _filter_events(all_events, start_date, end_date, user_email, workspace_id)
    ref_users = _read_json(storage, REF_USERS_FILE, [])
    return {
        "users": _build_user_rows(events),
        "directory": ref_users if isinstance(ref_users, list) else [],
    }


@router.get("/users/{email:path}")
async def get_user_detail(
    email: str,
    start_date: str | None = Query(None),
    end_date: str | None = Query(None),
    workspace_id: str | None = Query(None),
    storage: ObjectStorageService = Depends(get_object_storage),
) -> dict:
    """Return drill-down data for a single user."""
    decoded_email = urllib.parse.unquote(email)
    all_events = _read_events_from_storage(storage)
    events = _filter_events(all_events, start_date, end_date, decoded_email, workspace_id)
    detail = _build_user_detail(events, decoded_email)
    if detail is None:
        raise HTTPException(status_code=404, detail="No data for user in selected range")
    return detail


@router.get("/sessions")
async def get_sessions(
    start_date: str | None = Query(None),
    end_date: str | None = Query(None),
    user_email: str | None = Query(None),
    workspace_id: str | None = Query(None),
    storage: ObjectStorageService = Depends(get_object_storage),
) -> dict:
    """Return session rows."""
    all_events = _read_events_from_storage(storage)
    events = _filter_events(all_events, start_date, end_date, user_email, workspace_id)
    return {"sessions": _build_full_session_rows(events)}


@router.get("/pages")
async def get_pages(
    start_date: str | None = Query(None),
    end_date: str | None = Query(None),
    user_email: str | None = Query(None),
    workspace_id: str | None = Query(None),
    storage: ObjectStorageService = Depends(get_object_storage),
) -> dict:
    """Return page-view aggregates."""
    all_events = _read_events_from_storage(storage)
    events = _filter_events(all_events, start_date, end_date, user_email, workspace_id)
    return {"pages": _build_page_rows(events)}


@router.get("/workspaces")
async def get_workspaces(
    start_date: str | None = Query(None),
    end_date: str | None = Query(None),
    user_email: str | None = Query(None),
    workspace_id: str | None = Query(None),
    storage: ObjectStorageService = Depends(get_object_storage),
) -> dict:
    """Return per-workspace stats and the ref-workspaces directory."""
    all_events = _read_events_from_storage(storage)
    events = _filter_events(all_events, start_date, end_date, user_email, workspace_id)
    ref_workspaces = _read_json(storage, REF_WORKSPACES_FILE, [])
    return {
        "workspaces": _build_workspace_rows(events),
        "directory": ref_workspaces if isinstance(ref_workspaces, list) else [],
    }


@router.get("/events")
async def get_events(
    start_date: str | None = Query(None),
    end_date: str | None = Query(None),
    user_email: str | None = Query(None),
    workspace_id: str | None = Query(None),
    limit: int = Query(200, ge=1, le=1000),
    storage: ObjectStorageService = Depends(get_object_storage),
) -> dict:
    """Return raw events (most recent first, capped by limit)."""
    all_events = _read_events_from_storage(storage)
    events = _filter_events(all_events, start_date, end_date, user_email, workspace_id)
    return {"events": list(reversed(events[-limit:]))}
