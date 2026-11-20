"""Latency of the scoped analytics reads over seeded rollups (epic #1533 target:
p95 under 300 ms on 1M events across 100 workspaces).

    python -m naas_abi.apps.nexus.apps.api.app.services.analytics.benchmark \\
        postgresql+asyncpg://user:pass@host:5432/db [events] [runs]

The database (its name must contain ``bench``: every Nexus table is dropped)
is emptied and seeded (``events`` 0 measures what is there): 10 organizations of 10 workspaces, 20 members
per workspace, ``events`` (1,000,000 by default) over the current month, in sessions
of about 20 events. Each figure of the organization and the workspace scope is then
read ``runs`` times per period; p50 and p95 are printed per figure.
"""

from __future__ import annotations

import asyncio
import random
import statistics
import sys
import time
from datetime import UTC, datetime, timedelta
from functools import partial
from typing import Any

from naas_abi.apps.nexus.apps.api.app.core.database import Base
from naas_abi.apps.nexus.apps.api.app.models import (
    OrganizationModel,
    UserModel,
    WorkspaceModel,
)
from naas_abi.apps.nexus.apps.api.app.services.analytics.adapters.primary.analytics__primary_adapter__scoped import (  # noqa: E501
    scoped_analytics_over,
)
from naas_abi.apps.nexus.apps.api.app.services.analytics.adapters.secondary.analytics__secondary_adapter__postgres import (  # noqa: E501
    AnalyticsSecondaryAdapterPostgresEvents,
)
from naas_abi.apps.nexus.apps.api.app.services.analytics.port import AnalyticsScope, RecordedEvent
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

ORGS = 10
WORKSPACES_PER_ORG = 10
MEMBERS_PER_WORKSPACE = 20
EVENTS_PER_SESSION = 20
PAGES = [f"/workspace/{{ws}}/{name}" for name in ("home", "files", "chat", "graph", "search")]


def _workspace(org: int, index: int) -> str:
    return f"ws-{org:02d}-{index:02d}"


def _user(org: int, ws: int, index: int) -> str:
    return f"user-{org:02d}-{ws:02d}-{index:02d}"


async def seed(engine, events: int, now: datetime) -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    async with AsyncSession(engine) as db:
        db.add(UserModel(id="owner", email="owner@example.com", name="Owner"))
        for org in range(ORGS):
            db.add(
                OrganizationModel(
                    id=f"org-{org:02d}", name=f"Org {org}", slug=f"org-{org:02d}", owner_id="owner"
                )
            )
            for ws in range(WORKSPACES_PER_ORG):
                db.add(
                    WorkspaceModel(
                        id=_workspace(org, ws),
                        name=f"Space {org}/{ws}",
                        slug=_workspace(org, ws),
                        owner_id="owner",
                        organization_id=f"org-{org:02d}",
                    )
                )
                for member in range(MEMBERS_PER_WORKSPACE):
                    uid = _user(org, ws, member)
                    db.add(UserModel(id=uid, email=f"{uid}@example.com", name=uid))
        await db.commit()

    rng = random.Random(1533)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    span = (now - month_start).total_seconds()
    sessions = events // EVENTS_PER_SESSION
    batch: list[RecordedEvent] = []
    started = time.monotonic()
    applied = 0
    async with AsyncSession(engine) as db:
        port = AnalyticsSecondaryAdapterPostgresEvents(db)
        for session in range(sessions):
            org = rng.randrange(ORGS)
            ws = rng.randrange(WORKSPACES_PER_ORG)
            uid = _user(org, ws, rng.randrange(MEMBERS_PER_WORKSPACE))
            begin = month_start + timedelta(seconds=rng.random() * max(span - 3600, 1))
            for step in range(EVENTS_PER_SESSION):
                at = (begin + timedelta(seconds=step * 30)).replace(tzinfo=None)
                path = rng.choice(PAGES).format(ws=_workspace(org, ws))
                name = "page_viewed" if step % 3 else "button_clicked"
                eid = f"e-{session}-{step}"
                batch.append(
                    RecordedEvent(
                        event_id=eid,
                        timestamp=at,
                        session_id=f"s-{session}",
                        event_name=name,
                        user_id=uid,
                        workspace_id=_workspace(org, ws),
                        organization_id=f"org-{org:02d}",
                        page_path=path,
                        page_title="Page",
                        payload={
                            "event_id": eid,
                            "timestamp": at.isoformat() + "Z",
                            "session_id": f"s-{session}",
                            "event_name": name,
                            "user_id": uid,
                            "workspace_id": _workspace(org, ws),
                            "page_path": path,
                        },
                    )
                )
            if len(batch) >= 10_000:
                applied += await port.apply_events(batch, not_before=datetime(2000, 1, 1))
                await db.commit()
                batch = []
        applied += await port.apply_events(batch, not_before=datetime(2000, 1, 1))
        await db.commit()
    print(f"seeded {applied} events in {time.monotonic() - started:.0f}s")
    if engine.dialect.name == "postgresql":
        # Fresh tables have no statistics until autovacuum's analyze runs.
        async with engine.connect() as conn:
            await conn.execute(text("ANALYZE"))


def _scope(kind: str, org: int) -> AnalyticsScope:
    org_id = f"org-{org:02d}"
    if kind == "organization":
        workspaces = tuple(_workspace(org, ws) for ws in range(WORKSPACES_PER_ORG))
        members = tuple(
            _user(org, ws, m)
            for ws in range(WORKSPACES_PER_ORG)
            for m in range(MEMBERS_PER_WORKSPACE)
        )
        return AnalyticsScope("organization", org_id, workspaces, members, "Europe/Paris")
    members = tuple(_user(org, 0, m) for m in range(MEMBERS_PER_WORKSPACE))
    return AnalyticsScope("workspace", org_id, (_workspace(org, 0),), members, "Europe/Paris")


async def measure(engine, runs: int, now: datetime) -> None:
    rows = []
    for kind in ("organization", "workspace"):
        for period in ("today", "this_week", "this_month"):
            timings: dict[str, list[float]] = {}
            for run in range(runs):
                scope = _scope(kind, run % ORGS)
                async with AsyncSession(engine) as db:
                    # As the API builds it: the overview's reads run at the same time.
                    service = scoped_analytics_over(db, now=lambda: now)
                    window = service.window(scope, period)
                    figures: dict[str, Any] = {
                        "overview": service.overview,
                        "users": service.users,
                        "sessions": service.sessions,
                        "pages": service.pages,
                        "events": partial(service.events, limit=200),
                        "chat-analytics": service.chat_analytics,
                    }
                    for name, read in figures.items():
                        started = time.perf_counter()
                        await read(scope, window)
                        timings.setdefault(name, []).append((time.perf_counter() - started) * 1000)
            for name, values in timings.items():
                values.sort()
                p95 = values[max(0, int(len(values) * 0.95) - 1)]
                rows.append((kind, period, name, statistics.median(values), p95))
    print(f"{'scope':<13}{'period':<12}{'figure':<16}{'p50 ms':>8}{'p95 ms':>8}")
    for kind, period, name, p50, p95 in rows:
        print(f"{kind:<13}{period:<12}{name:<16}{p50:>8.1f}{p95:>8.1f}")


async def main(dsn: str, events: int, runs: int) -> None:
    engine = create_async_engine(dsn)
    if events and "bench" not in (engine.url.database or ""):
        # Seeding drops every Nexus table of the database.
        raise SystemExit("Seeding empties the database: give one whose name contains 'bench'.")
    now = datetime.now(UTC)
    if events:
        await seed(engine, events, now)
    await measure(engine, 1, now)  # warm-up: the first reads load the indexes
    await measure(engine, runs, now)
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(
        main(
            sys.argv[1],
            int(sys.argv[2]) if len(sys.argv) > 2 else 1_000_000,
            int(sys.argv[3]) if len(sys.argv) > 3 else 20,
        )
    )
