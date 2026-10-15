from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

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
    OrganizationMemberRecord,
    OrganizationRecord,
)
from naas_abi.apps.nexus.apps.api.app.services.organizations.service import (
    OrganizationService,
)

ORG = OrganizationRecord(id="org-1", name="Acme", slug="acme", owner_id="user-owner")
MEMBER = OrganizationMemberRecord(
    id="orgmem-1",
    organization_id="org-1",
    user_id="user-2",
    role="member",
    email="member@example.com",
    name="Member",
    created_at=datetime(2026, 7, 31),
)


def _client(role: str) -> TestClient:
    adapter = SimpleNamespace(
        get_organization_role=AsyncMock(return_value=role),
        get_organization_by_id=AsyncMock(return_value=ORG),
        list_organization_members=AsyncMock(return_value=[MEMBER]),
    )
    app = FastAPI()
    app.include_router(org_api.router, prefix="/organizations")
    app.dependency_overrides[get_current_user_required] = lambda: User.model_construct(
        id="user-1", email="viewer@example.com", name="Viewer"
    )
    app.dependency_overrides[org_api.get_organization_service] = lambda: OrganizationService(
        adapter=adapter
    )
    return TestClient(app)


def test_member_cannot_list_organization_members() -> None:
    resp = _client("member").get("/organizations/org-1/members")
    assert resp.status_code == 403


def test_admin_can_list_organization_members() -> None:
    resp = _client("admin").get("/organizations/org-1/members")
    assert resp.status_code == 200
    assert resp.json()[0]["email"] == "member@example.com"


def test_get_organization_includes_current_user_role() -> None:
    resp = _client("member").get("/organizations/org-1")
    assert resp.status_code == 200
    assert resp.json()["current_user_role"] == "member"


def test_member_cannot_list_domains() -> None:
    assert _client("member").get("/organizations/org-1/domains").status_code == 403


def test_member_cannot_read_billing() -> None:
    assert _client("member").get("/organizations/org-1/billing").status_code == 403
