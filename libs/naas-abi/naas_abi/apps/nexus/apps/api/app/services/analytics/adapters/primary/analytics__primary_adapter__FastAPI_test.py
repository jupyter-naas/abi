"""Unauthenticated analytics routes must 401 before any storage work, and the
analytics are the platform's: only a platform admin reads or writes them."""

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


def test_unauthenticated_get_users_returns_401() -> None:
    response = _client().get("/api/analytics/users")
    assert response.status_code == 401
    assert "Authorization" not in response.request.headers


def test_unauthenticated_get_events_sessions_overview_return_401() -> None:
    client = _client()
    for path in (
        "/api/analytics/events",
        "/api/analytics/sessions",
        "/api/analytics/overview",
    ):
        assert client.get(path).status_code == 401


def test_unauthenticated_post_rebuild_returns_401() -> None:
    assert _client().post("/api/analytics/rebuild").status_code == 401


def test_unauthenticated_post_events_returns_401() -> None:
    assert _client().post("/api/analytics/events", json={}).status_code == 401


READS = (
    "/api/analytics/metadata",
    "/api/analytics/scenarios",
    "/api/analytics/overview",
    "/api/analytics/users",
    "/api/analytics/users/someone@example.com",
    "/api/analytics/sessions",
    "/api/analytics/pages",
    "/api/analytics/workspaces",
    "/api/analytics/events",
    "/api/analytics/chats",
    "/api/analytics/chat-analytics",
    "/api/analytics/chats/c-1",
    "/api/analytics/chats/c-1/export",
)
WRITES = (
    ("POST", "/api/analytics/events", {"json": {}}),
    ("POST", "/api/analytics/rebuild", {}),
    (
        "PATCH",
        "/api/analytics/chats/c-1/messages/m-1/feedback",
        {"json": {"feedback": "like"}},
    ),
)


def _as(user: str, tmp_path) -> TestClient:
    from naas_abi_core.services.object_storage.adapters.secondary.ObjectStorageSecondaryAdapterFS import (  # noqa: E501
        ObjectStorageSecondaryAdapterFS,
    )
    from naas_abi_core.services.object_storage.ObjectStorageService import ObjectStorageService

    app = FastAPI()
    app.include_router(analytics.router, prefix="/api/analytics")
    app.dependency_overrides[get_db] = _no_db
    app.dependency_overrides[get_current_user_required] = lambda: SimpleNamespace(id=user)
    storage = ObjectStorageService(ObjectStorageSecondaryAdapterFS(str(tmp_path)))
    app.dependency_overrides[analytics._get_object_storage] = lambda: storage
    return TestClient(app)


@pytest.mark.parametrize("user", ["owner", "admin", "member", "viewer", "stranger"])
def test_no_workspace_role_reads_or_writes_the_analytics(team, tmp_path, user: str) -> None:
    client = _as(user, tmp_path)
    for path in READS:
        assert client.get(path).status_code == 403, path
    for method, path, kwargs in WRITES:
        assert client.request(method, path, **kwargs).status_code == 403, (method, path)


def test_a_platform_admin_reads_and_rebuilds_the_analytics(team, tmp_path) -> None:
    team.platform_admin("root")
    client = _as("root", tmp_path)

    assert client.get("/api/analytics/metadata").status_code == 200
    assert client.get("/api/analytics/scenarios").status_code == 200
    assert client.post("/api/analytics/rebuild").status_code == 200


class _BlockingIngest:
    """An analytics service whose ingestion blocks its thread until released, as
    a publish over NATS does while the broker is slow."""

    def __init__(self) -> None:
        self.entered = threading.Event()
        self.release = threading.Event()
        self.released_while_waiting: bool | None = None

    def ingest_event(self, event) -> str:  # noqa: ANN001 - the service's signature
        self.entered.set()
        self.released_while_waiting = self.release.wait(timeout=3)
        return "event-log#seq=1"


@pytest.mark.asyncio
async def test_a_slow_ingestion_does_not_hold_the_event_loop(team) -> None:
    """``POST /events`` publishes synchronously (NATS RPC). Run on the event loop,
    a slow broker froze every request of the engine, /health included."""
    import httpx

    team.platform_admin("root")
    app = FastAPI()
    app.include_router(analytics.router, prefix="/api/analytics")
    app.dependency_overrides[get_db] = _no_db
    app.dependency_overrides[get_current_user_required] = lambda: SimpleNamespace(id="root")
    slow = _BlockingIngest()
    app.dependency_overrides[analytics.get_analytics_service] = lambda: slow

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
