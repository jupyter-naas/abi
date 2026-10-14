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
from naas_abi.apps.nexus.apps.api.app.services.auth.avatar_store_test import (
    MemoryStorage as _MemoryStorage,
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
    organization=None,
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
            "organization": "Acme",
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
        update_organization_member_profile=AsyncMock(return_value=updated),
        set_organization_member_avatar=AsyncMock(return_value="/api/auth/avatar/old.png"),
    )
    # The profile is per organization: the account must never be written.
    auth_service = AsyncMock()

    app = FastAPI()
    app.include_router(org_api.router, prefix="/organizations")
    app.dependency_overrides[get_current_user_required] = lambda: User.model_construct(
        id=viewer_id, email="viewer@example.com", name="Viewer"
    )
    app.dependency_overrides[org_api.get_organization_service] = lambda: OrganizationService(
        adapter=adapter
    )
    app.dependency_overrides[get_auth_service] = lambda: auth_service
    # The drive sync (best effort) gets a storage and no database here.
    app.dependency_overrides[org_api._get_object_storage] = lambda: _MemoryStorage()
    app.dependency_overrides[org_api.get_db] = lambda: _NoDb()
    return TestClient(app), auth_service, adapter


def test_member_cannot_patch_profile() -> None:
    client, _, adapter = _client(viewer_role="member")
    resp = client.patch(
        "/organizations/org-1/members/user-2",
        json={"name": "Prepared", "bio": "Works on audit."},
    )
    assert resp.status_code == 403
    adapter.update_organization_member_profile.assert_not_awaited()


def test_admin_edits_the_org_profile_not_the_account() -> None:
    client, auth_service, adapter = _client(viewer_role="admin")
    resp = client.patch(
        "/organizations/org-1/members/user-2",
        json={
            "name": "Ignored: the full name is the account name",
            "organization": "Acme",
            "job_title": "Partner",
            "bio": "Works on audit.",
            "service_line": "Audit",
            "country": "France",
            "interest": "AI in audit",
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["name"] == "Member"
    assert body["organization"] == "Acme"
    assert body["job_title"] == "Partner"
    assert body["bio"] == "Works on audit."
    assert body["email"] == "member@example.com"
    adapter.update_organization_member_profile.assert_awaited_once_with(
        org_id="org-1",
        user_id="user-2",
        name=None,
        organization="Acme",
        job_title="Partner",
        bio="Works on audit.",
        service_line="Audit",
        country="France",
        interest="AI in audit",
    )
    assert auth_service.mock_calls == []


def test_admin_sets_the_org_avatar_in_the_members_drive() -> None:
    from naas_abi.apps.nexus.apps.api.app.services.auth.avatar_store_test import MemoryStorage

    storage = MemoryStorage()
    client, auth_service, adapter = _client(viewer_role="admin")
    client.app.dependency_overrides[org_api._get_object_storage] = lambda: storage

    resp = client.post(
        "/organizations/org-1/members/user-2/avatar",
        files={"file": ("me.png", b"png-bytes", "image/png")},
    )

    assert resp.status_code == 200
    assert storage.paths() == {"naas_abi/my-drive/user-2/.settings/avatar/avatar_org.png"}
    assert adapter.set_organization_member_avatar.await_args.kwargs["avatar"].startswith(
        "/api/auth/avatar/user/user-2/org?v="
    )
    # The account picture and the account itself are never touched.
    assert auth_service.mock_calls == []


def test_removing_the_org_avatar_archives_it() -> None:
    from naas_abi.apps.nexus.apps.api.app.services.auth.avatar_store_test import MemoryStorage

    storage = MemoryStorage()
    storage.put_object("naas_abi/my-drive/user-2/.settings/avatar", "avatar_org.png", b"org")
    storage.put_object("naas_abi/my-drive/user-2/.settings/avatar", "avatar.png", b"account")
    client, auth_service, adapter = _client(viewer_role="admin")
    client.app.dependency_overrides[org_api._get_object_storage] = lambda: storage

    resp = client.delete("/organizations/org-1/members/user-2/avatar")

    assert resp.status_code == 200
    adapter.set_organization_member_avatar.assert_awaited_once_with(
        org_id="org-1", user_id="user-2", avatar=None
    )
    paths = storage.paths()
    assert "naas_abi/my-drive/user-2/.settings/avatar/avatar_org.png" not in paths
    assert "naas_abi/my-drive/user-2/.settings/avatar/avatar.png" in paths
    assert any(p.endswith("_avatar_org.png") and "/archives/" in p for p in paths)
    assert auth_service.mock_calls == []


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


def _details_client(viewer_role: str) -> TestClient:
    from naas_abi.apps.nexus.apps.api.app.services.organizations.port import (
        OrganizationMemberAccountRecord,
        OrganizationMemberDetailsRecord,
        OrganizationMemberProfileRecord,
        OrganizationWorkspaceMembershipRecord,
    )

    details = OrganizationMemberDetailsRecord(
        member=MEMBER,
        account=OrganizationMemberAccountRecord(
            user_id="user-2",
            email="member@example.com",
            name="Member",
            created_at=datetime(2026, 7, 1),
        ),
        organization_profile=OrganizationMemberProfileRecord(name="Member (Acme)"),
    )
    adapter = SimpleNamespace(
        get_organization_role=AsyncMock(return_value=viewer_role),
        get_organization_member_details=AsyncMock(
            side_effect=lambda org_id, user_id: details if user_id == "user-2" else None
        ),
        list_workspaces_for_org=AsyncMock(
            return_value=[SimpleNamespace(id="ws-1", name="Audit", slug="audit", owner_id="x")]
        ),
        list_workspace_memberships_for_org=AsyncMock(
            return_value=[
                OrganizationWorkspaceMembershipRecord(
                    user_id="user-2", workspace_id="ws-1", role="member"
                )
            ]
        ),
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


def test_admin_reads_account_and_membership_details() -> None:
    resp = _details_client("admin").get("/organizations/org-1/members/user-2")

    assert resp.status_code == 200
    body = resp.json()
    assert body["member"]["role"] == "member"
    assert body["account"]["email"] == "member@example.com"
    assert body["account"]["created_at"].startswith("2026-07-01")
    assert body["organization_profile"]["name"] == "Member (Acme)"
    assert body["organization_profile"]["organization"] is None
    assert body["workspaces"] == [
        {"id": "ws-1", "name": "Audit", "slug": "audit", "role": "member", "source": "workspace"}
    ]


def test_member_details_are_admin_only_and_404_for_non_members() -> None:
    assert _details_client("member").get("/organizations/org-1/members/user-2").status_code == 403
    assert _details_client("admin").get("/organizations/org-1/members/nobody").status_code == 404


class _NoDb:
    """Stands in for the session: flush works, the drive sync then fails and is logged."""

    async def flush(self) -> None:
        return None
