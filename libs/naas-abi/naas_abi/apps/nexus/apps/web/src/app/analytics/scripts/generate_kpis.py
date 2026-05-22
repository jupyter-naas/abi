#!/usr/bin/env python3
"""
Compute KPI snapshots from events.json and write kpis.json.

Each row in kpis.json has these keys:
  workspace_id  — "all" or a specific workspace ID
  user_id       — "all" or a specific user ID
  scenario      — time-window label, e.g. "last_7d"
  date          — snapshot date (ISO date of the anchor)
  title         — grouping category shown in the UI
  label         — KPI name shown on the card
  meta          — secondary hint text (may be empty string)
  value         — raw numeric value (always a number)
  value_d       — display string formatted for humans

Run from repo root or from the web/ app directory:
  python src/app/analytics/scripts/generate_kpis.py
"""

import json
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data"

ANCHOR_NOW = datetime(2026, 5, 22, 12, 0, 0, tzinfo=timezone.utc)

SCENARIOS: list[tuple[str, int]] = [
    ("last_7d", 7),
]


# ---------------------------------------------------------------------------
# Formatting helpers (mirrors format.ts)
# ---------------------------------------------------------------------------

def fmt_number(n: float) -> str:
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n / 1_000:.1f}k"
    return str(int(n))


def fmt_duration(seconds: int) -> str:
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


# ---------------------------------------------------------------------------
# Core aggregations
# ---------------------------------------------------------------------------

def build_sessions(events: list[dict]) -> list[dict]:
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


def session_duration_sec(s: dict) -> int:
    def parse(ts: str) -> datetime:
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))

    return max(0, int((parse(s["ended_at"]) - parse(s["started_at"])).total_seconds()))


def compute_kpi_rows(
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

    sessions = build_sessions(events)
    page_views = [e for e in events if e.get("event_name") == "page_viewed"]
    active_users = {e["user_email"] for e in events if e.get("user_email")}
    workspaces = {e["workspace_id"] for e in events if e.get("workspace_id")}

    sessions_by_user: dict[str, list] = defaultdict(list)
    for s in sessions:
        if s.get("user_email"):
            sessions_by_user[s["user_email"]].append(s)

    total_duration = sum(session_duration_sec(s) for s in sessions)
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
        row(t, "Active users",           "",                    len(active_users),  fmt_number(len(active_users))),
        row(t, "Sessions",               "",                    len(sessions),      fmt_number(len(sessions))),
        row(t, "Avg. sessions / user",   "",                    avg_per_user,       f"{avg_per_user:.1f}"),
        row(t, "Page views",             "",                    len(page_views),    fmt_number(len(page_views))),
        row(t, "Workspaces used",        "",                    len(workspaces),    fmt_number(len(workspaces))),
        row(t, "Avg. session duration",  "",                    avg_duration,       fmt_duration(avg_duration)),
        row(t, "Returning users",        "",                    returning,          fmt_number(returning)),
        row(
            t,
            "Most active workspace",
            f"{fmt_number(top_ws['events'])} events" if top_ws else "",
            top_ws["events"] if top_ws else 0,
            top_ws["name"] if top_ws else "—",
        ),
    ]


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    raw = json.loads((DATA_DIR / "events.json").read_text())
    all_events: list[dict] = raw["events"]

    user_ids = sorted({e["user_id"] for e in all_events if e.get("user_id")})
    workspace_ids = sorted({e["workspace_id"] for e in all_events if e.get("workspace_id")})

    all_rows: list[dict] = []

    for scenario, days in SCENARIOS:
        end = ANCHOR_NOW
        start = end - timedelta(days=days)
        start_s = start.strftime("%Y-%m-%dT%H:%M:%S")
        end_s = end.strftime("%Y-%m-%dT%H:%M:%S")
        snapshot_date = ANCHOR_NOW.strftime("%Y-%m-%d")

        def slice_events(uid: str | None, wid: str | None) -> list[dict]:
            return [
                e
                for e in all_events
                if start_s <= e["timestamp"] <= end_s
                and (not uid or uid == "all" or e.get("user_id") == uid)
                and (not wid or wid == "all" or e.get("workspace_id") == wid)
            ]

        # Global snapshot
        all_rows.extend(compute_kpi_rows(slice_events(None, None), "all", "all", scenario, snapshot_date))

        # Per-workspace (all users)
        for wid in workspace_ids:
            all_rows.extend(compute_kpi_rows(slice_events(None, wid), wid, "all", scenario, snapshot_date))

        # Per-user (all workspaces)
        for uid in user_ids:
            all_rows.extend(compute_kpi_rows(slice_events(uid, None), "all", uid, scenario, snapshot_date))

        # Per-user × per-workspace
        for uid in user_ids:
            for wid in workspace_ids:
                evts = slice_events(uid, wid)
                if evts:
                    all_rows.extend(compute_kpi_rows(evts, wid, uid, scenario, snapshot_date))

    out = DATA_DIR / "kpis.json"
    out.write_text(json.dumps({"kpis": all_rows}, indent=2) + "\n")
    print(f"wrote {out}  ({len(all_rows)} rows)")


if __name__ == "__main__":
    main()
