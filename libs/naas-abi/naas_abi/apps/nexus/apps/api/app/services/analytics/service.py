"""Analytics domain service.

Write path:

1. ``ingest_event`` persists one event as a pickle via the storage port and
   updates the ref-users / ref-workspaces directories.
2. A debounced background rebuild reads every per-event pickle, then for
   **each scenario** (Last 7/30/90 days) it computes the full set of
   aggregates against that scenario's time window. Every aggregate JSON is
   written as a ``{scenario_id: <payload>}`` map so the read endpoints can
   serve any scenario with a single dict lookup.

Read path:

The ``get_*`` methods take a ``scenario_id`` and return the matching slice
of the prebuilt JSON. No aggregation or filtering happens at request time.
Line-graph timeseries always cover every day in the scenario window
(missing days are filled with ``0``).
"""

from __future__ import annotations

import re
import threading
import time
import urllib.parse
from collections import defaultdict
from datetime import UTC, date, datetime, timedelta
from typing import Any

from naas_abi.apps.nexus.apps.api.app.services.analytics.port import (
    AnalyticsEvent,
    AnalyticsStoragePort,
    EventsResponse,
    FileStats,
    Metadata,
    OverviewResponse,
    PagesResponse,
    ScenariosResponse,
    SessionsResponse,
    UserDetail,
    UserDetailNotFound,
    UsersResponse,
    WorkspacesResponse,
)
from naas_abi_core import logger

# ---------------------------------------------------------------------------
# Aggregate file names
# ---------------------------------------------------------------------------

EVENTS_FILE = "events.json"
RECENT_EVENTS_FILE = "recent_events.json"
OVERVIEW_FILE = "overview.json"
USERS_FILE = "users.json"
USER_DETAILS_FILE = "user_details.json"
SESSIONS_FILE = "sessions.json"
PAGES_FILE = "pages.json"
WORKSPACES_FILE = "workspaces.json"
METADATA_FILE = "metadata.json"
SCENARIO_FILE = "ref-scenario.json"
REF_USERS_FILE = "ref-users.json"
REF_WORKSPACES_FILE = "ref-workspaces.json"

RECENT_EVENTS_LIMIT = 100

_REBUILD_DEBOUNCE_SECONDS = 60

_CHAT_CONV_PATH_RE = re.compile(r"/chat/(conv-[^/?#]+)")

# Scenario catalog: (name, scenario_id, lookback in days).
_SCENARIOS: list[tuple[str, str, int]] = [
    ("Last 7 days", "last_7_days", 7),
    ("Last 30 days", "last_30_days", 30),
    ("Last 90 days", "last_90_days", 90),
]
DEFAULT_SCENARIO_ID = "last_7_days"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _iso_z(dt: datetime) -> str:
    """ISO-8601 with the trailing ``Z`` (matches event timestamps)."""
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def _enumerate_days(date_start: str, date_end: str) -> list[str]:
    """Every YYYY-MM-DD between two ISO timestamps, inclusive."""
    start_d = date.fromisoformat(date_start[:10])
    end_d = date.fromisoformat(date_end[:10])
    days: list[str] = []
    cursor = start_d
    while cursor <= end_d:
        days.append(cursor.isoformat())
        cursor += timedelta(days=1)
    return days


def _build_scenarios(now: datetime) -> list[dict]:
    """Anchor each scenario window at ``now`` and return JSON-ready dicts."""
    end_s = _iso_z(now)
    out: list[dict] = []
    for name, sid, days in _SCENARIOS:
        start = now - timedelta(days=days)
        out.append(
            {
                "scenario": name,
                "scenario_id": sid,
                "date_start": _iso_z(start),
                "date_end": end_s,
            }
        )
    return out


def _decorate_page_title(title: str, path: str) -> str:
    # Chat conversation pages share the title "Chat" — re-derive the conv
    # suffix from the path so each conversation surfaces as its own row even
    # when stored events predate write-time decoration.
    m = _CHAT_CONV_PATH_RE.search(path or "")
    if not m:
        return title
    conv = m.group(1)
    return title if conv in title else f"{title} - {conv}"


def _session_duration_sec(started_at: str, ended_at: str) -> int:
    def parse(ts: str) -> datetime:
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))

    return max(0, int((parse(ended_at) - parse(started_at)).total_seconds()))


def _filter_events_to_window(events: list[dict], date_start: str, date_end: str) -> list[dict]:
    return [e for e in events if date_start <= e.get("timestamp", "") <= date_end]


# ---------------------------------------------------------------------------
# Pure aggregation helpers (operate on plain dicts for hot-path simplicity)
# ---------------------------------------------------------------------------


def _build_sessions(events: list[dict]) -> list[dict]:
    by_session: dict[str, list[dict]] = defaultdict(list)
    for e in events:
        sid = e.get("session_id")
        if sid:
            by_session[sid].append(e)

    rows: list[dict] = []
    for session_id, evts in by_session.items():
        evts.sort(key=lambda x: x.get("timestamp", ""))
        first, last = evts[0], evts[-1]
        rows.append(
            {
                "session_id": session_id,
                "user_email": first.get("user_email") or "unknown",
                "workspace_name": first.get("workspace_name"),
                "started_at": first["timestamp"],
                "ended_at": last["timestamp"],
                "duration_seconds": _session_duration_sec(first["timestamp"], last["timestamp"]),
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


def _build_page_rows(events: list[dict]) -> list[dict]:
    views = [e for e in events if e.get("event_name") == "page_viewed" and e.get("page_path")]
    by_page: dict[str, list[dict]] = defaultdict(list)
    for e in views:
        by_page[e["page_path"]].append(e)

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
        by_ws[e["workspace_id"]].append(e)

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


def _build_overview(events: list[dict], sessions: list[dict], days: list[str]) -> dict:
    page_views = [e for e in events if e.get("event_name") == "page_viewed"]
    active_users = {e["user_email"] for e in events if e.get("user_email")}
    workspace_set = {e["workspace_id"] for e in events if e.get("workspace_id")}

    sessions_by_user: dict[str, list] = defaultdict(list)
    for s in sessions:
        if s.get("user_email") and s["user_email"] != "unknown":
            sessions_by_user[s["user_email"]].append(s)

    total_duration = sum(s["duration_seconds"] for s in sessions)
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

    # Every day in the scenario window is represented — missing days carry 0.
    sessions_by_day: dict[str, set] = {d: set() for d in days}
    for s in sessions:
        k = s["started_at"][:10]
        if k in sessions_by_day:
            sessions_by_day[k].add(s["session_id"])
    sessions_over_time = [{"date": d, "value": len(sessions_by_day[d])} for d in days]

    users_by_day: dict[str, set] = {d: set() for d in days}
    for e in events:
        if e.get("user_email"):
            k = e["timestamp"][:10]
            if k in users_by_day:
                users_by_day[k].add(e["user_email"])
    active_users_over_time = [{"date": d, "value": len(users_by_day[d])} for d in days]

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


def _build_user_detail_map(events: list[dict]) -> dict[str, dict]:
    by_email: dict[str, list[dict]] = defaultdict(list)
    for e in events:
        email = e.get("user_email")
        if email:
            by_email[email].append(e)

    out: dict[str, dict] = {}
    for email, user_events in by_email.items():
        sorted_events = sorted(user_events, key=lambda e: e.get("timestamp", ""))
        first = sorted_events[0]
        last = sorted_events[-1]

        session_ids = {e["session_id"] for e in sorted_events if e.get("session_id")}
        page_views_list = [e for e in sorted_events if e.get("event_name") == "page_viewed"]
        pages = _build_page_rows(user_events)
        sessions = _build_sessions(user_events)

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

        out[email] = {
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
    return out


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------


class AnalyticsService:
    def __init__(self, storage: AnalyticsStoragePort) -> None:
        self._storage = storage

        # Debounced rebuild bookkeeping.
        self._rebuild_lock = threading.Lock()
        self._rebuild_timer: threading.Timer | None = None
        self._rebuild_running = False
        self._rebuild_pending = False

    # --- ingest -------------------------------------------------------------

    def ingest_event(self, event: AnalyticsEvent) -> str:
        payload = event.model_dump(exclude_none=True)
        stored_at = self._storage.save_event(payload)
        self._upsert_refs(event)
        self._schedule_rebuild()
        return stored_at

    def _upsert_refs(self, event: AnalyticsEvent) -> None:
        if event.workspace_id:
            workspaces: list[dict[str, Any]] = self._storage.load_json(
                REF_WORKSPACES_FILE, fallback=[]
            )
            if not isinstance(workspaces, list):
                workspaces = []
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
                self._storage.save_json(REF_WORKSPACES_FILE, workspaces)

        if event.user_id and event.user_email:
            users: list[dict[str, Any]] = self._storage.load_json(REF_USERS_FILE, fallback=[])
            if not isinstance(users, list):
                users = []
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
                self._storage.save_json(REF_USERS_FILE, users)

    # --- rebuild ------------------------------------------------------------

    def rebuild(self) -> Metadata:
        overall_start = time.monotonic()

        events_start = time.monotonic()
        events = self._storage.list_events()
        events.sort(key=lambda e: e.get("timestamp", ""))
        self._storage.save_json(EVENTS_FILE, {"events": events})
        events_ms = int((time.monotonic() - events_start) * 1000)

        # Anchor every scenario at the same "now" so a single rebuild produces
        # a consistent snapshot across windows.
        now = datetime.now(UTC)
        scenarios = _build_scenarios(now)

        ref_users = self._storage.load_json(REF_USERS_FILE, fallback=[])
        ref_workspaces = self._storage.load_json(REF_WORKSPACES_FILE, fallback=[])
        if not isinstance(ref_users, list):
            ref_users = []
        if not isinstance(ref_workspaces, list):
            ref_workspaces = []

        overview_by_scenario: dict[str, dict] = {}
        users_by_scenario: dict[str, dict] = {}
        sessions_by_scenario: dict[str, dict] = {}
        pages_by_scenario: dict[str, dict] = {}
        workspaces_by_scenario: dict[str, dict] = {}
        user_details_by_scenario: dict[str, dict] = {}
        recent_events_by_scenario: dict[str, dict] = {}

        for scenario in scenarios:
            sid = scenario["scenario_id"]
            ds = scenario["date_start"]
            de = scenario["date_end"]
            window_events = _filter_events_to_window(events, ds, de)
            days = _enumerate_days(ds, de)

            session_rows = _build_sessions(window_events)
            user_rows = _build_user_rows(window_events)
            page_rows = _build_page_rows(window_events)
            workspace_rows = _build_workspace_rows(window_events)

            # _build_overview already returns a fully zeroed overview when
            # given empty inputs; no special-case branch needed.
            overview_by_scenario[sid] = _build_overview(window_events, session_rows, days)
            users_by_scenario[sid] = {"users": user_rows, "directory": ref_users}
            sessions_by_scenario[sid] = {"sessions": session_rows}
            pages_by_scenario[sid] = {"pages": page_rows}
            workspaces_by_scenario[sid] = {
                "workspaces": workspace_rows,
                "directory": ref_workspaces,
            }
            user_details_by_scenario[sid] = _build_user_detail_map(window_events)
            recent_events_by_scenario[sid] = {
                "events": list(reversed(window_events))[:RECENT_EVENTS_LIMIT]
            }

        aggregate_stats: list[FileStats] = []

        def _write(file_name: str, payload: Any, count: int) -> None:
            t0 = time.monotonic()
            self._storage.save_json(file_name, payload)
            aggregate_stats.append(
                FileStats(
                    file=file_name,
                    count=count,
                    duration_ms=int((time.monotonic() - t0) * 1000),
                )
            )

        _write(SCENARIO_FILE, {"scenarios": scenarios}, count=len(scenarios))
        _write(OVERVIEW_FILE, overview_by_scenario, count=len(scenarios))
        _write(USERS_FILE, users_by_scenario, count=len(scenarios))
        _write(SESSIONS_FILE, sessions_by_scenario, count=len(scenarios))
        _write(PAGES_FILE, pages_by_scenario, count=len(scenarios))
        _write(WORKSPACES_FILE, workspaces_by_scenario, count=len(scenarios))
        _write(USER_DETAILS_FILE, user_details_by_scenario, count=len(scenarios))
        _write(RECENT_EVENTS_FILE, recent_events_by_scenario, count=len(scenarios))

        metadata = Metadata(
            updated_at=datetime.now(UTC).isoformat(),
            duration_ms=int((time.monotonic() - overall_start) * 1000),
            events=FileStats(file=EVENTS_FILE, count=len(events), duration_ms=events_ms),
            aggregates=aggregate_stats,
        )
        self._storage.save_json(METADATA_FILE, metadata.model_dump())
        return metadata

    def _schedule_rebuild(self) -> None:
        with self._rebuild_lock:
            if self._rebuild_timer is not None:
                self._rebuild_timer.cancel()
            self._rebuild_timer = threading.Timer(_REBUILD_DEBOUNCE_SECONDS, self._run_rebuild)
            self._rebuild_timer.daemon = True
            self._rebuild_timer.start()

    def _run_rebuild(self) -> None:
        with self._rebuild_lock:
            if self._rebuild_running:
                self._rebuild_pending = True
                return
            self._rebuild_running = True
        try:
            meta = self.rebuild()
            logger.debug(
                f"[analytics] rebuilt: {meta.events.count} events, "
                f"{len(meta.aggregates)} aggregates"
            )
        except Exception as exc:
            logger.warning(f"[analytics] rebuild failed: {exc}")
        finally:
            with self._rebuild_lock:
                self._rebuild_running = False
                rerun = self._rebuild_pending
                self._rebuild_pending = False
            if rerun:
                self._run_rebuild()

    # --- read endpoints -----------------------------------------------------

    def get_metadata(self) -> Metadata | None:
        raw = self._storage.load_json(METADATA_FILE, fallback=None)
        if raw is None:
            return None
        try:
            return Metadata.model_validate(raw)
        except Exception as exc:
            logger.warning(f"[analytics] invalid metadata.json in storage: {exc}")
            return None

    def get_scenarios(self) -> ScenariosResponse:
        raw = self._storage.load_json(SCENARIO_FILE, fallback={"scenarios": []})
        return ScenariosResponse.model_validate(raw)

    def _load_scenario_slice(self, file_name: str, scenario_id: str, fallback: Any) -> Any:
        raw = self._storage.load_json(file_name, fallback={})
        if not isinstance(raw, dict):
            return fallback
        return raw.get(scenario_id, fallback)

    def get_overview(self, scenario_id: str = DEFAULT_SCENARIO_ID) -> OverviewResponse:
        raw = self._storage.load_json(OVERVIEW_FILE, fallback={})
        if isinstance(raw, dict) and scenario_id in raw:
            return OverviewResponse.model_validate(raw[scenario_id])
        # Fallback: never-rebuilt or unknown scenario — synthesize a fully
        # zeroed overview spanning the scenario's day grid.
        days = self._days_for_scenario(scenario_id)
        return OverviewResponse.model_validate(_build_overview([], [], days))

    def get_users(self, scenario_id: str = DEFAULT_SCENARIO_ID) -> UsersResponse:
        slice_data = self._load_scenario_slice(
            USERS_FILE, scenario_id, fallback={"users": [], "directory": []}
        )
        return UsersResponse.model_validate(slice_data)

    def get_user_detail(self, email: str, scenario_id: str = DEFAULT_SCENARIO_ID) -> UserDetail:
        decoded = urllib.parse.unquote(email)
        scenario_data = self._load_scenario_slice(USER_DETAILS_FILE, scenario_id, fallback={})
        if not isinstance(scenario_data, dict) or decoded not in scenario_data:
            raise UserDetailNotFound(decoded)
        return UserDetail.model_validate(scenario_data[decoded])

    def get_sessions(self, scenario_id: str = DEFAULT_SCENARIO_ID) -> SessionsResponse:
        slice_data = self._load_scenario_slice(
            SESSIONS_FILE, scenario_id, fallback={"sessions": []}
        )
        return SessionsResponse.model_validate(slice_data)

    def get_pages(self, scenario_id: str = DEFAULT_SCENARIO_ID) -> PagesResponse:
        slice_data = self._load_scenario_slice(PAGES_FILE, scenario_id, fallback={"pages": []})
        return PagesResponse.model_validate(slice_data)

    def get_workspaces(self, scenario_id: str = DEFAULT_SCENARIO_ID) -> WorkspacesResponse:
        slice_data = self._load_scenario_slice(
            WORKSPACES_FILE, scenario_id, fallback={"workspaces": [], "directory": []}
        )
        return WorkspacesResponse.model_validate(slice_data)

    def get_events(
        self, scenario_id: str = DEFAULT_SCENARIO_ID, limit: int = 200
    ) -> EventsResponse:
        slice_data = self._load_scenario_slice(
            RECENT_EVENTS_FILE, scenario_id, fallback={"events": []}
        )
        events = slice_data.get("events", []) if isinstance(slice_data, dict) else []
        return EventsResponse.model_validate({"events": events[:limit]})

    # --- helpers -----------------------------------------------------------

    def _days_for_scenario(self, scenario_id: str) -> list[str]:
        scenarios = self.get_scenarios().scenarios
        for s in scenarios:
            if s.scenario_id == scenario_id:
                return _enumerate_days(s.date_start, s.date_end)
        return []
