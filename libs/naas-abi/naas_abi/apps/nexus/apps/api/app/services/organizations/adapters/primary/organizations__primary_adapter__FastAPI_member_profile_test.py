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
from naas_abi.apps.nexus.apps.api.app.services.auth.adapters.primary.auth__primary_adapter__dependencies import (
    get_auth_service,
)
from naas_abi.apps.nexus.apps.api.app.services.organizations.adapters.primary import (
    organizations__primary_adapter__FastAPI as org_api,
)
from naas_abi.apps.nexus.apps.api.app.services.organizations.port import (
    OrganizationMemberRecord,
)
from naas_abi.apps.nexus.apps.api.app.services.organizations.service import (
    OrganizationService,
)

MEMBER = OrganizationMemberRecord(
    id="orgmem-1",
    organization_id="org-1",
    user_id="user-2",
    role="member",
    email="member@example.com",
    name="Member",
    created_at=datetime(2026, 7, 31),
    company=None,
    job_title=None,
    bio=None,
)

OWNER = OrganizationMemberRecord(
    id="orgmem-owner",
    organization_id="org-1",
    user_id="user-owner",
    role="owner",
    email="owner@example.com",
    name="Owner",
    created_at=datetime(2026, 7, 31),
)


def _client(
    *,
    viewer_role: str,
    viewer_id: str = "user-1",
    member: OrganizationMemberRecord = MEMBER,
) -> tuple[TestClient, AsyncMock, SimpleNamespace]:
    updated = OrganizationMemberRecord(
        **{
            **member.__dict__,
            "name": "Prepared",
            "company": "Acme",
            "job_title": "Partner",
            "bio": "Works on audit.",
        }
    )
    adapter = SimpleNamespace(
        get_organization_role=AsyncMock(return_value=viewer_role),
        get_organization_member=AsyncMock(return_value=member),
        update_organization_member_role=AsyncMock(
            return_value=OrganizationMemberRecord(**{**member.__dict__, "role": "admin"})
        ),
    )
    auth_service = AsyncMock()
    auth_service.update_profile.return_value = SimpleNamespace(id=member.user_id)
    auth_service.update_avatar.return_value = SimpleNamespace(id=member.user_id)

    # After a profile write, return the prepared row.
    async def _get_member(**_kwargs):
        if auth_service.update_profile.await_count:
            return updated
        return member

    adapter.get_organization_member = AsyncMock(side_effect=_get_member)

    app = FastAPI()
    app.include_router(org_api.router, prefix="/organizations")
    app.dependency_overrides[get_current_user_required] = lambda: User.model_construct(
        id=viewer_id, email="viewer@example.com", name="Viewer"
    )
    app.dependency_overrides[org_api.get_organization_service] = lambda: OrganizationService(
        adapter=adapter
    )
    app.dependency_overrides[get_auth_service] = lambda: auth_service
    return TestClient(app), auth_service, adapter


def test_member_cannot_patch_profile() -> None:
    client, auth_service, _ = _client(viewer_role="member")
    resp = client.patch(
        "/organizations/org-1/members/user-2",
        json={"name": "Prepared", "bio": "Works on audit."},
    )
    assert resp.status_code == 403
    auth_service.update_profile.assert_not_awaited()


def test_admin_can_prep_profile_without_touching_email() -> None:
    client, auth_service, _ = _client(viewer_role="admin")
    resp = client.patch(
        "/organizations/org-1/members/user-2",
        json={
            "name": "Prepared",
            "company": "Acme",
            "job_title": "Partner",
            "bio": "Works on audit.",
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["name"] == "Prepared"
    assert body["company"] == "Acme"
    assert body["job_title"] == "Partner"
    assert body["bio"] == "Works on audit."
    assert body["email"] == "member@example.com"
    auth_service.update_profile.assert_awaited_once()
    kwargs = auth_service.update_profile.await_args.kwargs
    assert kwargs["email"] is None
    assert kwargs["role"] == "Partner"


def test_admin_cannot_change_own_org_role() -> None:
    client, _, adapter = _client(viewer_role="admin", viewer_id="user-2")
    resp = client.patch(
        "/organizations/org-1/members/user-2",
        json={"role": "admin"},
    )
    assert resp.status_code == 400
    adapter.update_organization_member_role.assert_not_awaited()


def test_admin_cannot_change_owner_org_role() -> None:
    client, _, adapter = _client(viewer_role="admin", member=OWNER)
    resp = client.patch(
        "/organizations/org-1/members/user-owner",
        json={"role": "admin"},
    )
    assert resp.status_code == 400
    adapter.update_organization_member_role.assert_not_awaited()


def test_cannot_assign_owner_via_patch() -> None:
    client, _, adapter = _client(viewer_role="admin")
    resp = client.patch(
        "/organizations/org-1/members/user-2",
        json={"role": "owner"},
    )
    assert resp.status_code == 422
    adapter.update_organization_member_role.assert_not_awaited()
