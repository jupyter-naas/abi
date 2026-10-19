from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from naas_abi.apps.nexus.apps.api.app.api.endpoints.auth import get_current_user_required
from naas_abi.apps.nexus.apps.api.app.services.organizations.adapters.primary import (
    organizations__primary_adapter__FastAPI as org_api,
)
from naas_abi.apps.nexus.apps.api.app.services.organizations.port import OrganizationRecord
from naas_abi.apps.nexus.apps.api.app.services.organizations.service import (
    OrganizationService,
)

ORG = OrganizationRecord(id="org-1", name="Acme", slug="acme", owner_id="owner")


@pytest.fixture
def client_for(team):
    """A client signed in as one of the team's users, whose roles are IAM's."""

    def make(user: str) -> TestClient:
        adapter = SimpleNamespace(
            get_organization_by_id=AsyncMock(return_value=ORG),
            get_users_by_ids=AsyncMock(
                side_effect=lambda ids: {
                    i: SimpleNamespace(id=i, email=f"{i}@example.com", name=i.title())
                    for i in ids
                }
            ),
        )
        app = FastAPI()
        app.include_router(org_api.router, prefix="/organizations")
        app.dependency_overrides[get_current_user_required] = lambda: SimpleNamespace(id=user)
        app.dependency_overrides[org_api.get_organization_service] = lambda: OrganizationService(
            adapter=adapter
        )
        return TestClient(app)

    return make


def test_member_cannot_list_organization_members(client_for) -> None:
    resp = client_for("member").get("/organizations/org-1/members")
    assert resp.status_code == 403


def test_admin_can_list_organization_members(client_for) -> None:
    resp = client_for("admin").get("/organizations/org-1/members")
    assert resp.status_code == 200
    assert {m["email"]: m["role"] for m in resp.json()} == {
        "owner@example.com": "owner",
        "admin@example.com": "admin",
        "member@example.com": "member",
        "viewer@example.com": "viewer",
    }


def test_get_organization_includes_current_user_role(client_for) -> None:
    resp = client_for("member").get("/organizations/org-1")
    assert resp.status_code == 200
    assert resp.json()["current_user_role"] == "member"


def test_member_cannot_list_domains(client_for) -> None:
    assert client_for("member").get("/organizations/org-1/domains").status_code == 403


def test_member_cannot_read_billing(client_for) -> None:
    assert client_for("member").get("/organizations/org-1/billing").status_code == 403
