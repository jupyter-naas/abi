from __future__ import annotations

from datetime import datetime
from unittest.mock import AsyncMock

from fastapi import FastAPI
from fastapi.testclient import TestClient
from naas_abi.apps.nexus.apps.api.app.services.auth.adapters.primary import (
    auth__primary_adapter__FastAPI as auth_api,
)
from naas_abi.apps.nexus.apps.api.app.services.auth.adapters.primary.auth__primary_adapter__dependencies import (
    get_auth_service,
    get_current_user_required,
)
from naas_abi.apps.nexus.apps.api.app.services.auth.adapters.primary.auth__primary_adapter__schemas import (
    User,
)
from naas_abi.apps.nexus.apps.api.app.services.auth.avatar_store_test import MemoryStorage
from naas_abi.apps.nexus.apps.api.app.services.auth.port import AuthUserRecord

NOW = datetime(2026, 1, 1)


def _client(storage) -> tuple[TestClient, AsyncMock]:
    record = AuthUserRecord(
        id="user-1",
        email="alice@example.com",
        name="Alice",
        hashed_password="secret-hash",
        created_at=NOW,
        organization="Forvis Mazars",
        job_title="Partner",
    )
    auth_service = AsyncMock()
    auth_service.update_profile.return_value = record
    auth_service.with_account_fallbacks = AsyncMock(side_effect=lambda user: user)
    app = FastAPI()
    app.include_router(auth_api.router, prefix="/api/auth")
    app.dependency_overrides[get_current_user_required] = lambda: User(
        id="user-1", email="alice@example.com", name="Alice", created_at=NOW
    )
    app.dependency_overrides[get_auth_service] = lambda: auth_service
    app.dependency_overrides[auth_api._get_object_storage] = lambda: storage
    app.dependency_overrides[auth_api.get_db] = lambda: None
    return TestClient(app), auth_service


def test_saving_the_profile_syncs_the_drive_profile(monkeypatch) -> None:
    calls: list[str] = []

    async def fake_sync(db, storage, user_id, now) -> None:
        calls.append(user_id)

    monkeypatch.setattr(auth_api.user_drive_profile, "sync_user_drive_profile_safely", fake_sync)
    client, auth_service = _client(MemoryStorage())

    resp = client.patch(
        "/api/auth/me", json={"organization": "Forvis Mazars", "job_title": "Partner"}
    )

    assert resp.status_code == 200
    assert resp.json()["organization"] == "Forvis Mazars"
    assert resp.json()["job_title"] == "Partner"
    kwargs = auth_service.update_profile.await_args.kwargs
    assert (kwargs["organization"], kwargs["job_title"]) == ("Forvis Mazars", "Partner")
    assert calls == ["user-1"]


def test_a_drive_failure_does_not_fail_the_save() -> None:
    # No database session in this test: the drive sync fails and is only logged.
    client, _ = _client(MemoryStorage())

    assert client.patch("/api/auth/me", json={"name": "Alice"}).status_code == 200
