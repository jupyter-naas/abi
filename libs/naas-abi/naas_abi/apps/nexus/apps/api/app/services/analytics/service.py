"""Analytics domain service.

Pure Python aggregation on top of :class:`AnalyticsPort`. No infra
imports — the only dependency is the abstract port.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from naas_abi.apps.nexus.apps.api.app.services.analytics.port import (
    AnalyticsFilters,
    AnalyticsPort,
    LogRecord,
)


@dataclass
class _SessionAgg:
    session_id: str
    user_id: str | None
    user_email: str | None
    workspace_id: str | None
    workspace_name: str | None
    started_at: str
    ended_at: str
    page_views: int
    events: int
    device: str | None
    browser: str | None


class AnalyticsService:
    """Aggregation/use-case layer for the analytics domain."""

    def __init__(self, adapter: AnalyticsPort) -> None:
        self.adapter = adapter

    # ----- single source-of-truth + filter ------------------------------- #

    def flat_events(self) -> list[dict[str, Any]]:
        rows = [e.as_dict() for e in self.adapter.query_flat_events()]
        rows.sort(key=lambda e: e["timestamp"])
        return rows

    def _filtered(self, filters: AnalyticsFilters) -> list[dict[str, Any]]:
        return [e for e in self.flat_events() if _matches(e, filters)]

    # ----- endpoint responses -------------------------------------------- #

    def overview(self, filters: AnalyticsFilters) -> dict[str, Any]:
        events = self._filtered(filters)
        sessions = _build_sessions(events)
        page_views = [e for e in events if e["event_name"] == "page_viewed"]

        active_users = {e["user_email"] for e in events if e["user_email"]}
        workspaces = {e["workspace_id"] for e in events if e["workspace_id"]}

        total_duration = sum(_duration(s) for s in sessions)
        avg_session_duration = total_duration // len(sessions) if sessions else 0

        sessions_by_user: dict[str, list[_SessionAgg]] = defaultdict(list)
        for s in sessions:
            sessions_by_user[s.user_email or "unknown"].append(s)
        returning_users = sum(1 for arr in sessions_by_user.values() if len(arr) > 1)

        ws_counts: dict[str, dict[str, Any]] = {}
        for e in events:
            wsid = e["workspace_id"]
            if not wsid:
                continue
            cur = ws_counts.get(wsid)
            if cur:
                cur["events"] += 1
            else:
                ws_counts[wsid] = {"id": wsid, "name": e["workspace_name"] or wsid, "events": 1}
        most_active = max(ws_counts.values(), key=lambda x: x["events"], default=None)

        days = _range_days(filters)
        sessions_by_day: dict[str, set[str]] = defaultdict(set)
        for s in sessions:
            sessions_by_day[s.started_at[:10]].add(s.session_id)
        users_by_day: dict[str, set[str]] = defaultdict(set)
        for e in events:
            if e["user_email"]:
                users_by_day[e["timestamp"][:10]].add(e["user_email"])

        return {
            "kpi": {
                "active_users": len(active_users),
                "total_sessions": len(sessions),
                "avg_sessions_per_user": (
                    round(len(sessions) / len(active_users), 1) if active_users else 0
                ),
                "total_page_views": len(page_views),
                "workspaces_used": len(workspaces),
                "avg_session_duration_seconds": avg_session_duration,
                "returning_users": returning_users,
                "most_active_workspace": most_active,
            },
            "sessions_over_time": [
                {"date": d, "value": len(sessions_by_day.get(d, ()))} for d in days
            ],
            "active_users_over_time": [
                {"date": d, "value": len(users_by_day.get(d, ()))} for d in days
            ],
            "top_users": self._user_rows(events)[:10],
            "top_pages": self._page_rows(events)[:10],
            "workspace_activity": self._workspace_rows(events),
            "recent_activity": list(reversed(events))[:25],
        }

    def users(self, filters: AnalyticsFilters) -> dict[str, Any]:
        all_events = self.flat_events()
        directory = sorted(
            {(e["user_email"], e["user_id"] or "") for e in all_events if e["user_email"]},
            key=lambda x: x[0],
        )
        return {
            "users": self._user_rows(self._filtered(filters)),
            "directory": [{"user_email": e, "user_id": u} for (e, u) in directory],
        }

    def user_detail(self, email: str, filters: AnalyticsFilters) -> dict[str, Any] | None:
        scoped = AnalyticsFilters(
            start_date=filters.start_date,
            end_date=filters.end_date,
            user_email=None,
            workspace_id=filters.workspace_id,
        )
        user_events = [e for e in self._filtered(scoped) if e["user_email"] == email]
        if not user_events:
            return None
        user_events.sort(key=lambda e: e["timestamp"])
        first, last = user_events[0], user_events[-1]
        session_ids = {e["session_id"] for e in user_events}
        page_views = [e for e in user_events if e["event_name"] == "page_viewed"]
        pages = self._page_rows(user_events)
        sessions = self._session_rows(user_events)
        workspaces: dict[str, str] = {}
        for e in user_events:
            if e["workspace_id"]:
                workspaces[e["workspace_id"]] = e["workspace_name"] or e["workspace_id"]
        return {
            "user_email": email,
            "user_id": first["user_id"] or "",
            "first_seen": first["timestamp"],
            "last_seen": last["timestamp"],
            "total_sessions": len(session_ids),
            "total_page_views": len(page_views),
            "workspaces_used": [{"id": i, "name": n} for i, n in workspaces.items()],
            "most_visited_page": (
                {"path": pages[0]["page_path"], "title": pages[0]["page_title"], "views": pages[0]["views"]}
                if pages
                else None
            ),
            "sessions": sessions,
            "pages": pages,
            "events": list(reversed(user_events)),
        }

    def sessions(self, filters: AnalyticsFilters) -> dict[str, Any]:
        return {"sessions": self._session_rows(self._filtered(filters))}

    def pages(self, filters: AnalyticsFilters) -> dict[str, Any]:
        return {"pages": self._page_rows(self._filtered(filters))}

    def workspaces(self, filters: AnalyticsFilters) -> dict[str, Any]:
        all_events = self.flat_events()
        directory = sorted(
            {
                (e["workspace_id"], e["workspace_name"] or e["workspace_id"])
                for e in all_events
                if e["workspace_id"]
            },
            key=lambda x: x[1],
        )
        return {
            "workspaces": self._workspace_rows(self._filtered(filters)),
            "directory": [{"workspace_id": i, "workspace_name": n} for (i, n) in directory],
        }

    def events(self, filters: AnalyticsFilters, limit: int = 200) -> dict[str, Any]:
        evts = self._filtered(filters)
        evts.sort(key=lambda e: e["timestamp"], reverse=True)
        return {"events": evts[: max(1, int(limit))]}

    # ----- internal row builders ---------------------------------------- #

    @staticmethod
    def _user_rows(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
        by_user: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for e in events:
            if e["user_email"]:
                by_user[e["user_email"]].append(e)
        rows: list[dict[str, Any]] = []
        for email, evts in by_user.items():
            sessions = {e["session_id"] for e in evts}
            workspaces = {e["workspace_id"] for e in evts if e["workspace_id"]}
            page_views = [e for e in evts if e["event_name"] == "page_viewed"]
            last = max(evts, key=lambda e: e["timestamp"])
            rows.append(
                {
                    "user_id": last["user_id"] or "",
                    "user_email": email,
                    "sessions": len(sessions),
                    "page_views": len(page_views),
                    "workspaces": len(workspaces),
                    "last_seen": last["timestamp"],
                    "total_events": len(evts),
                }
            )
        rows.sort(key=lambda r: r["total_events"], reverse=True)
        return rows

    @staticmethod
    def _page_rows(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
        views = [e for e in events if e["event_name"] == "page_viewed" and e["page_path"]]
        by_page: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for e in views:
            by_page[e["page_path"]].append(e)
        rows = [
            {
                "page_path": path,
                "page_title": evts[0]["page_title"] or path,
                "views": len(evts),
                "unique_users": len({e["user_email"] for e in evts if e["user_email"]}),
            }
            for path, evts in by_page.items()
        ]
        rows.sort(key=lambda r: r["views"], reverse=True)
        return rows

    @staticmethod
    def _workspace_rows(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
        with_ws = [e for e in events if e["workspace_id"]]
        by_ws: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for e in with_ws:
            by_ws[e["workspace_id"]].append(e)
        rows = [
            {
                "workspace_id": ws_id,
                "workspace_name": evts[0]["workspace_name"] or ws_id,
                "active_users": len({e["user_email"] for e in evts if e["user_email"]}),
                "sessions": len({e["session_id"] for e in evts}),
                "events": len(evts),
            }
            for ws_id, evts in by_ws.items()
        ]
        rows.sort(key=lambda r: r["events"], reverse=True)
        return rows

    @staticmethod
    def _session_rows(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
        rows = []
        for s in _build_sessions(events):
            rows.append(
                {
                    "session_id": s.session_id,
                    "user_email": s.user_email or "unknown",
                    "workspace_name": s.workspace_name,
                    "started_at": s.started_at,
                    "ended_at": s.ended_at,
                    "duration_seconds": _duration(s),
                    "page_views": s.page_views,
                    "events": s.events,
                    "device": s.device,
                    "browser": s.browser,
                }
            )
        return rows


# ---------------------------------------------------------------------- #
# helpers (mirror apps/web/src/app/analytics/lib/aggregate.ts)            #
# ---------------------------------------------------------------------- #

def _matches(event: dict[str, Any], filters: AnalyticsFilters) -> bool:
    ts = event.get("timestamp", "")
    if filters.start_date and ts < filters.start_date:
        return False
    if filters.end_date and ts > filters.end_date:
        return False
    if filters.user_email and event.get("user_email") != filters.user_email:
        return False
    if filters.workspace_id and event.get("workspace_id") != filters.workspace_id:
        return False
    return True


def _build_sessions(events: list[dict[str, Any]]) -> list[_SessionAgg]:
    by_sid: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for e in events:
        by_sid[e["session_id"]].append(e)
    out: list[_SessionAgg] = []
    for sid, evts in by_sid.items():
        evts.sort(key=lambda e: e["timestamp"])
        first, last = evts[0], evts[-1]
        out.append(
            _SessionAgg(
                session_id=sid,
                user_id=first["user_id"],
                user_email=first["user_email"],
                workspace_id=first["workspace_id"],
                workspace_name=first["workspace_name"],
                started_at=first["timestamp"],
                ended_at=last["timestamp"],
                page_views=sum(1 for e in evts if e["event_name"] == "page_viewed"),
                events=len(evts),
                device=first["device"],
                browser=first["browser"],
            )
        )
    out.sort(key=lambda s: s.started_at, reverse=True)
    return out


def _duration(s: _SessionAgg) -> int:
    try:
        start = datetime.fromisoformat(s.started_at.replace("Z", "+00:00"))
        end = datetime.fromisoformat(s.ended_at.replace("Z", "+00:00"))
    except ValueError:
        return 0
    return max(0, int((end - start).total_seconds()))


def _range_days(filters: AnalyticsFilters) -> list[str]:
    end = (
        datetime.fromisoformat(filters.end_date.replace("Z", "+00:00"))
        if filters.end_date
        else datetime.now(timezone.utc)
    )
    start = (
        datetime.fromisoformat(filters.start_date.replace("Z", "+00:00"))
        if filters.start_date
        else end - timedelta(days=30)
    )
    days: list[str] = []
    cursor = start.replace(hour=0, minute=0, second=0, microsecond=0)
    end_day = end.replace(hour=0, minute=0, second=0, microsecond=0)
    while cursor <= end_day:
        days.append(cursor.date().isoformat())
        cursor += timedelta(days=1)
    return days
