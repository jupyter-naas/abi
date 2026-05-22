#!/usr/bin/env python3
"""
Generator for the analytics JSON data sources.
Run with `python src/app/analytics/scripts/generate_analytics_data.py` from the web/ app root
whenever the seed data or user/workspace lists change.
The generated events.json is the single source of truth consumed by API routes,
which apply date/user/workspace filters and aggregate at request time.
"""

import json
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data"

USERS = [
    {
        "id": "u_001",
        "email": "admin@example.com",
        "name": "Local Admin",
        "workspace_ids": ["ws_001"],
    },
    {
        "id": "u_002",
        "email": "jeremy@naas.ai",
        "name": "Jeremy Ravenel",
        "workspace_ids": ["ws_001"],
    },
    {
        "id": "u_003",
        "email": "maxime@naas.ai",
        "name": "Maxime Jublou",
        "workspace_ids": ["ws_001"],
    },
    {
        "id": "u_004",
        "email": "florent@naas.ai",
        "name": "Florent Ravenel",
        "workspace_ids": ["ws_001", "ws_002"],
    },
]

WORKSPACES = [
    {"id": "ws_001", "name": "Primary"},
    {"id": "ws_002", "name": "Secondary"},
]

PAGES = [
    {"path": "/chat", "title": "Chat"},
    {"path": "/files", "title": "Files"},
    {"path": "/graph", "title": "Knowledge Graph"},
    {"path": "/ontology", "title": "Ontology"},
    {"path": "/marketplace", "title": "Marketplace"},
    {"path": "/apps", "title": "Apps"},
    {"path": "/settings/agents", "title": "Agents"},
    {"path": "/settings/models", "title": "Models"},
    {"path": "/settings/members", "title": "Members"},
    {"path": "/lab", "title": "Lab"},
    {"path": "/search", "title": "Search"},
    {"path": "/organization", "title": "Organization"},
]

DEVICES = ["Mac", "Windows", "iPhone", "Linux"]
BROWSERS = ["Chrome", "Safari", "Firefox", "Edge"]
COUNTRIES = ["US", "FR", "UK", "DE", "JP", "CA", "IN", "BR"]
REFERRERS = ["direct", "google.com", "linkedin.com", "twitter.com", "github.com"]

EVENT_WEIGHTS = [
    ("page_viewed", 50),
    # ("button_clicked", 20),
    # ("search_performed", 8),
    # ("workspace_opened", 6),
    # ("file_uploaded", 4),
    # ("export_clicked", 3),
    # ("invite_sent", 2),
    # ("workspace_updated", 2),
    # ("workspace_created", 1),
    # ("error_seen", 2),
    ("login", 1),
    ("logout", 1),
]

EVENT_NAMES = [name for name, _ in EVENT_WEIGHTS]
EVENT_WEIGHT_VALUES = [w for _, w in EVENT_WEIGHTS]

# Fixed anchor keeps regenerated files stable across runs.
ANCHOR_NOW = datetime(2026, 5, 22, 12, 0, 0, tzinfo=timezone.utc)
# 90 days covers all preset ranges (7d / 30d / 90d) plus custom ranges.
WINDOW_DAYS = 90


def uid(rng: random.Random, prefix: str) -> str:
    return f"{prefix}_{rng.randint(0, 0xFFFFFFFF):08x}"


def generate_events(rng: random.Random) -> list[dict]:
    events = []

    for day_offset in range(WINDOW_DAYS, -1, -1):
        day_start = ANCHOR_NOW - timedelta(days=day_offset)
        # Python weekday(): Monday=0 … Friday=4, Saturday=5, Sunday=6
        weekend_factor = 0.4 if day_start.weekday() >= 5 else 1.0
        growth_factor = 0.5 + (WINDOW_DAYS - day_offset) / WINDOW_DAYS
        sessions_today = int((6 + rng.random() * 14) * weekend_factor * growth_factor)

        for _ in range(sessions_today):
            user = rng.choice(USERS)
            workspace = rng.choice(WORKSPACES)
            device = rng.choice(DEVICES)
            browser = rng.choice(BROWSERS)
            country = rng.choice(COUNTRIES)
            referrer = rng.choice(REFERRERS)
            session_id = uid(rng, "sess")
            session_start = day_start + timedelta(seconds=rng.random() * 22 * 3600)
            session_duration_min = 2 + rng.random() * 45

            def make_event(event_name: str, timestamp: datetime) -> dict:
                return {
                    "event_id": uid(rng, "evt"),
                    "timestamp": timestamp.strftime("%Y-%m-%dT%H:%M:%S.")
                    + f"{timestamp.microsecond // 1000:03d}Z",
                    "user_id": user["id"],
                    "user_email": user["email"],
                    "workspace_id": workspace["id"],
                    "workspace_name": workspace["name"],
                    "session_id": session_id,
                    "event_name": event_name,
                    "device": device,
                    "browser": browser,
                    "country": country,
                    "referrer": referrer,
                }

            events.append(make_event("session_started", session_start))

            event_count = 4 + int(rng.random() * 22)
            for i in range(event_count):
                event_name = rng.choices(EVENT_NAMES, weights=EVENT_WEIGHT_VALUES, k=1)[
                    0
                ]
                t = session_start + timedelta(
                    minutes=(i + 1) / (event_count + 1) * session_duration_min
                )
                e = make_event(event_name, t)
                if event_name == "page_viewed":
                    page = rng.choice(PAGES)
                    e["page_path"] = page["path"]
                    e["page_title"] = page["title"]
                elif event_name == "button_clicked":
                    e["properties"] = {
                        "label": rng.choice(
                            ["Save", "Run", "Export", "Open", "Cancel", "Submit"]
                        )
                    }
                elif event_name == "search_performed":
                    e["properties"] = {
                        "query": rng.choice(
                            ["revenue", "pipeline", "agents", "ontology", "graph"]
                        )
                    }
                events.append(e)

            events.append(
                make_event(
                    "session_ended",
                    session_start + timedelta(minutes=session_duration_min),
                )
            )

    events.sort(key=lambda e: e["timestamp"])
    return events


def write_json(file_path: Path, data: object) -> None:
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(json.dumps(data, indent=2) + "\n")
    print(f"wrote {file_path}")


def main() -> None:
    rng = random.Random(42)
    events = generate_events(rng)

    write_json(
        DATA_DIR / "ref-users.json",
        [
            {
                "user_id": u["id"],
                "user_email": u["email"],
                "workspace_ids": u["workspace_ids"],
            }
            for u in USERS
        ],
    )
    write_json(
        DATA_DIR / "ref-workspaces.json",
        [{"workspace_id": w["id"], "workspace_name": w["name"]} for w in WORKSPACES],
    )
    write_json(DATA_DIR / "events.json", {"events": events})


if __name__ == "__main__":
    main()
