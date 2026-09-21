"""Unauthenticated transcribe requests must 401 before audio handling."""

from __future__ import annotations

from collections.abc import AsyncIterator

from fastapi import FastAPI
from fastapi.testclient import TestClient
from naas_abi.apps.nexus.apps.api.app.api.endpoints.transcribe import router
from naas_abi.apps.nexus.apps.api.app.core.database import get_db


async def _no_db() -> AsyncIterator[None]:
    yield None


def test_unauthenticated_post_transcribe_returns_401() -> None:
    app = FastAPI()
    app.include_router(router, prefix="/api/transcribe")
    app.dependency_overrides[get_db] = _no_db
    response = TestClient(app).post("/api/transcribe", json={})
    assert response.status_code == 401
    assert "Authorization" not in response.request.headers
