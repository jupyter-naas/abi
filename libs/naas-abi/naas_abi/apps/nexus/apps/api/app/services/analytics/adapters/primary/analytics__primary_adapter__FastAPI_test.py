"""Unauthenticated analytics routes must 401 before any storage work."""

from __future__ import annotations

from collections.abc import AsyncIterator

from fastapi import FastAPI
from fastapi.testclient import TestClient
from naas_abi.apps.nexus.apps.api.app.core.database import get_db
from naas_abi.apps.nexus.apps.api.app.services.analytics.adapters.primary import (
    analytics__primary_adapter__FastAPI as analytics,
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
