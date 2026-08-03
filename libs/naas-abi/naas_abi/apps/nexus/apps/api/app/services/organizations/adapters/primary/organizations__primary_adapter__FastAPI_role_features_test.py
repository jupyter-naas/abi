from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from naas_abi.apps.nexus.apps.api.app.api.endpoints.auth import (
    User,
    get_current_user_required,
)
from naas_abi.apps.nexus.apps.api.app.services.organizations.adapters.primary import (
    organizations__primary_adapter__FastAPI as org_api,
)
from naas_abi.apps.nexus.apps.api.app.services.organizations.port import (
    OrganizationRoleFeaturesRecord,
)
from naas_abi.apps.nexus.apps.api.app.services.organizations.service import (
    OrganizationService,
)


def _baseline() -> dict[str, list[str]]:
    return {
        "owner": ["maps", "chat", "files", "settings"],
        "admin": ["maps", "chat", "files", "settings"],
        "member": ["maps", "chat"],
        "viewer": ["maps"],
    }


def _client(*, role: str, store: dict[str, OrganizationRoleFeaturesRecord]) -> TestClient:
    adapter = SimpleNamespace(
        get_organization_role=AsyncMock(return_value=role),
        get_organization_role_features=AsyncMock(
            side_effect=lambda org_id: store.get(org_id)
        ),
        upsert_organization_role_features=AsyncMock(),
    )

    async def _upsert(
        org_id: str,
        role_baseline: dict[str, list[str]],
        updated_by: str | None,
        now: datetime,
    ) -> OrganizationRoleFeaturesRecord:
        record = OrganizationRoleFeaturesRecord(
            organization_id=org_id,
            role_baseline={key: list(value) for key, value in role_baseline.items()},
            updated_by=updated_by,
            created_at=now,
            updated_at=now,
        )
        store[org_id] = record
        return record

    adapter.upsert_organization_role_features = AsyncMock(side_effect=_upsert)
    service = OrganizationService(adapter=adapter)

    app = FastAPI()
    app.include_router(org_api.router, prefix="/organizations")
    app.dependency_overrides[get_current_user_required] = lambda: User.model_construct(
        id="user-1", email="admin@example.com", name="Admin"
    )
    app.dependency_overrides[org_api.get_organization_service] = lambda: service
    return TestClient(app)


def test_get_role_features_forbidden_for_member() -> None:
    client = _client(role="member", store={})
    resp = client.get("/organizations/org-1/roles/features")
    assert resp.status_code == 403


def test_put_role_features_forbidden_for_viewer() -> None:
    client = _client(role="viewer", store={})
    resp = client.put(
        "/organizations/org-1/roles/features",
        json={"role_baseline": _baseline()},
    )
    assert resp.status_code == 403


def test_put_role_features_persists_and_round_trips() -> None:
    store: dict[str, OrganizationRoleFeaturesRecord] = {}
    client = _client(role="admin", store=store)

    before = client.get("/organizations/org-1/roles/features")
    assert before.status_code == 200
    assert before.json()["persistence"] == "deployment"

    payload = _baseline()
    put = client.put(
        "/organizations/org-1/roles/features",
        json={"role_baseline": payload},
    )
    assert put.status_code == 200, put.text
    body = put.json()
    assert body["persistence"] == "database"
    assert body["role_baseline"]["member"] == ["maps", "chat"]
    assert body["updated_by"] == "user-1"
    assert "org-1" in store
    assert store["org-1"].role_baseline["viewer"] == ["maps"]

    again = client.get("/organizations/org-1/roles/features")
    assert again.status_code == 200
    assert again.json()["persistence"] == "database"
    assert again.json()["role_baseline"]["member"] == ["maps", "chat"]


def test_put_role_features_rejects_feature_outside_enabled_catalog() -> None:
    client = _client(role="owner", store={})
    payload = _baseline()
    # "code" is a known FeatureKey but off in the default enabled catalog.
    payload["member"] = ["maps", "code"]
    resp = client.put(
        "/organizations/org-1/roles/features",
        json={"role_baseline": payload},
    )
    assert resp.status_code == 400
    assert "not enabled in deployment catalog" in resp.json()["detail"]


def test_put_role_features_rejects_unknown_feature_at_schema() -> None:
    client = _client(role="owner", store={})
    payload = _baseline()
    payload["member"] = ["maps", "not-a-feature"]
    resp = client.put(
        "/organizations/org-1/roles/features",
        json={"role_baseline": payload},
    )
    assert resp.status_code == 422


def test_put_role_features_requires_all_baseline_roles() -> None:
    client = _client(role="owner", store={})
    resp = client.put(
        "/organizations/org-1/roles/features",
        json={"role_baseline": {"owner": ["maps"], "admin": ["maps"]}},
    )
    assert resp.status_code == 400
    assert "must include all baseline roles" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_service_get_and_upsert_role_features_delegate() -> None:
    record = OrganizationRoleFeaturesRecord(
        organization_id="org-1",
        role_baseline=_baseline(),
        updated_by="user-1",
    )
    adapter = SimpleNamespace(
        get_organization_role_features=AsyncMock(return_value=record),
        upsert_organization_role_features=AsyncMock(return_value=record),
    )
    service = OrganizationService(adapter=adapter)
    now = datetime.utcnow()

    got = await service.get_role_features(org_id="org-1")
    assert got == record
    adapter.get_organization_role_features.assert_awaited_once_with(org_id="org-1")

    saved = await service.upsert_role_features(
        org_id="org-1",
        role_baseline=_baseline(),
        updated_by="user-1",
        now=now,
    )
    assert saved == record
    adapter.upsert_organization_role_features.assert_awaited_once()
