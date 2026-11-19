"""The tracker's ingest: every signed-in user's (identity from the token), 401 before
any storage work otherwise. The platform-wide reads of the removed analytics app are
gone (#1536); the analytics are read in Organization and Workspace settings."""

from __future__ import annotations

import asyncio
import threading
from collections.abc import AsyncIterator
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from naas_abi.apps.nexus.apps.api.app.core.database import get_db
from naas_abi.apps.nexus.apps.api.app.services.analytics.adapters.primary import (
    analytics__primary_adapter__FastAPI as analytics,
)
from naas_abi.apps.nexus.apps.api.app.services.auth.adapters.primary.auth__primary_adapter__dependencies import (  # noqa: E501
    get_current_user_required,
)


async def _no_db() -> AsyncIterator[None]:
    yield None


def _client() -> TestClient:
    app = FastAPI()
    app.include_router(analytics.router, prefix="/api/analytics")
    app.dependency_overrides[get_db] = _no_db
    return TestClient(app)


def test_unauthenticated_post_events_returns_401() -> None:
    assert _client().post("/api/analytics/events", json={}).status_code == 401


OLD_READS = (
    "/api/analytics/metadata",
    "/api/analytics/scenarios",
    "/api/analytics/overview",
    "/api/analytics/users",
    "/api/analytics/users/someone@example.com",
    "/api/analytics/sessions",
    "/api/analytics/pages",
    "/api/analytics/workspaces",
    "/api/analytics/chats",
    "/api/analytics/chat-analytics",
    "/api/analytics/chats/c-1",
    "/api/analytics/chats/c-1/export",
)


def test_the_platform_wide_reads_are_gone(team) -> None:
    team.platform_admin("root")
    app = FastAPI()
    app.include_router(analytics.router, prefix="/api/analytics")
    app.dependency_overrides[get_db] = _no_db
    app.dependency_overrides[get_current_user_required] = lambda: SimpleNamespace(id="root")
    client = TestClient(app)
    for path in OLD_READS:
        assert client.get(path).status_code == 404, path
    # ``/events`` is the ingest's: a GET is not allowed.
    assert client.get("/api/analytics/events").status_code == 405
    assert client.post("/api/analytics/rebuild").status_code == 404
    assert (
        client.patch(
            "/api/analytics/chats/c-1/messages/m-1/feedback", json={"feedback": "like"}
        ).status_code
        == 404
    )


class _BlockingIngest:
    """An event log whose publish blocks its thread until released, as a publish
    over NATS does while the broker is slow."""

    def __init__(self) -> None:
        self.entered = threading.Event()
        self.release = threading.Event()
        self.released_while_waiting: bool | None = None

    def save_event(self, event: dict) -> str:
        self.entered.set()
        self.released_while_waiting = self.release.wait(timeout=3)
        return "event-log#seq=1"


@pytest.mark.asyncio
async def test_a_slow_ingestion_does_not_hold_the_event_loop(team) -> None:
    """``POST /events`` publishes synchronously (NATS RPC). Run on the event loop,
    a slow broker froze every request of the engine, /health included."""
    import httpx

    app = FastAPI()
    app.include_router(analytics.router, prefix="/api/analytics")
    app.dependency_overrides[get_db] = _no_db
    app.dependency_overrides[get_current_user_required] = lambda: SimpleNamespace(id="member")
    slow = _BlockingIngest()
    app.dependency_overrides[analytics.get_event_log] = lambda: slow

    event = {
        "event_id": "e-1",
        "timestamp": "2026-11-18T10:28:00Z",
        "session_id": "s-1",
        "event_name": "page_view",
    }
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        posting = asyncio.create_task(client.post("/api/analytics/events", json=event))
        # The loop must keep running while the ingestion waits: this coroutine
        # sees it enter, then releases it.
        for _ in range(300):
            if slow.entered.is_set():
                break
            await asyncio.sleep(0.01)
        assert slow.entered.is_set()
        assert not posting.done()
        slow.release.set()
        response = await asyncio.wait_for(posting, timeout=5)

    assert response.status_code == 200
    assert response.json()["stored_at"] == "event-log#seq=1"
    assert slow.released_while_waiting is True


class _Recording:
    """The event log, keeping what the route hands it (as a stamped event)."""

    def __init__(self) -> None:
        self.events: list = []

    def save_event(self, event: dict) -> str:
        from naas_abi.apps.nexus.apps.api.app.services.analytics.port import AnalyticsEvent
        from naas_abi_core.engine.call_context import current_call_context

        self.events.append((AnalyticsEvent.model_validate(event), current_call_context()))
        return "event-log#seq=7"


def _ingest_as(user: str) -> tuple[TestClient, _Recording]:
    app = FastAPI()
    app.include_router(analytics.router, prefix="/api/analytics")
    app.dependency_overrides[get_db] = _no_db
    app.dependency_overrides[get_current_user_required] = lambda: SimpleNamespace(
        id=user, email=f"{user}@example.com"
    )
    recording = _Recording()
    app.dependency_overrides[analytics.get_event_log] = lambda: recording
    analytics._memberships.clear()
    return TestClient(app), recording


TRACKED = {
    "event_id": "e-1",
    "timestamp": "2026-11-18T10:28:00Z",
    "session_id": "s-1",
    "event_name": "page_viewed",
    "page_path": "/workspace/ws-1/home",
}


@pytest.mark.parametrize("user", ["member", "viewer"])
def test_a_regular_member_s_event_is_recorded_as_the_token_says(team, user: str) -> None:
    client, recording = _ingest_as(user)
    response = client.post(
        "/api/analytics/events",
        json={
            **TRACKED,
            "workspace_id": "ws-1",
            "user_id": "someone-else",
            "user_email": "forged@example.com",
            "organization_id": "org-forged",
        },
    )
    assert response.status_code == 200
    assert response.json()["stored_at"] == "event-log#seq=7"
    (event, context) = recording.events[0]
    # No email is kept: it is read from the users table when the analytics are read.
    assert (event.user_id, event.user_email) == (user, None)
    assert (event.workspace_id, event.organization_id) == ("ws-1", "org-1")
    # Written as ``api``: a member's own rights never reach the log.
    assert context.principal.id.endswith("api") and context.on_behalf_of is None


def test_a_workspace_the_user_is_not_a_member_of_is_dropped(team) -> None:
    client, recording = _ingest_as("stranger")
    response = client.post(
        "/api/analytics/events", json={**TRACKED, "workspace_id": "ws-1", "workspace_name": "W"}
    )
    assert response.status_code == 200
    (event, _context) = recording.events[0]
    assert (event.user_id, event.workspace_id, event.workspace_name, event.organization_id) == (
        "stranger",
        None,
        None,
        None,
    )


def test_an_event_with_no_workspace_has_no_organization(team) -> None:
    client, recording = _ingest_as("member")
    assert client.post("/api/analytics/events", json=TRACKED).status_code == 200
    (event, _context) = recording.events[0]
    assert (event.workspace_id, event.organization_id) == (None, None)


@pytest.mark.asyncio
async def test_with_no_event_log_the_ingest_feeds_the_rollups_at_once(
    team, nexus_db, monkeypatch
) -> None:
    import httpx
    from naas_abi.apps.nexus.apps.api.app.models import AnalyticsEventModel, AnalyticsHourlyModel
    from sqlalchemy import select

    monkeypatch.setattr(analytics, "_get_event_service", lambda: None)
    app = FastAPI()
    app.include_router(analytics.router, prefix="/api/analytics")

    async def db():
        async with nexus_db() as session:
            yield session
            await session.commit()

    app.dependency_overrides[get_db] = db
    app.dependency_overrides[get_current_user_required] = lambda: SimpleNamespace(
        id="member", email="member@example.com"
    )
    analytics._memberships.clear()
    from datetime import UTC, datetime

    # Within the 45 days kept, whenever the test runs.
    now = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        for _ in range(2):  # a retried POST is counted once
            response = await client.post(
                "/api/analytics/events",
                json={**TRACKED, "timestamp": now, "workspace_id": "ws-1"},
            )
            assert response.status_code == 200

    async with nexus_db() as session:
        rows = (await session.execute(select(AnalyticsEventModel))).scalars().all()
        hourly = (await session.execute(select(AnalyticsHourlyModel))).scalars().all()
    assert [(r.user_id, r.workspace_id, r.organization_id) for r in rows] == [
        ("member", "ws-1", "org-1")
    ]
    assert "member@example.com" not in rows[0].payload
    assert [h.count for h in hourly] == [1]


def test_an_oversized_event_is_refused(team) -> None:
    client, recording = _ingest_as("member")
    big = {**TRACKED, "properties": {"blob": "x" * (1024 * 1024)}}
    assert client.post("/api/analytics/events", json=big).status_code == 413
    assert recording.events == []


def test_with_neither_log_nor_database_the_ingest_is_unavailable(team, monkeypatch) -> None:
    monkeypatch.setattr(analytics, "_get_event_service", lambda: None)
    app = FastAPI()
    app.include_router(analytics.router, prefix="/api/analytics")
    app.dependency_overrides[get_db] = _no_db
    app.dependency_overrides[get_current_user_required] = lambda: SimpleNamespace(id="member")
    assert TestClient(app).post("/api/analytics/events", json=TRACKED).status_code == 503
