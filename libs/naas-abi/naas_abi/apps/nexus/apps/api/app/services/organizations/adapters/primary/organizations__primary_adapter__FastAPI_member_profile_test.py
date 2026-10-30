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
from naas_abi.apps.nexus.apps.api.app.services.auth.avatar_store_test import (
    MemoryStorage as _MemoryStorage,
)
from naas_abi.apps.nexus.apps.api.app.services.organizations.adapters.primary import (
    organizations__primary_adapter__FastAPI as org_api,
)
from naas_abi.apps.nexus.apps.api.app.services.organizations.port import (
    OrganizationMemberProfileRecord,
    UserRecord,
)
from naas_abi.apps.nexus.apps.api.app.services.organizations.service import (
    OrganizationService,
)

PEOPLE = ("owner", "admin", "member", "viewer")


@pytest.fixture(autouse=True)
def _team(team):
    return team


def _adapter(profiles: dict[str, OrganizationMemberProfileRecord] | None = None) -> SimpleNamespace:
    """The organization's rows: every person of the team has an account; ``profiles``
    is what the organization set for them (kept by the fake, as the table would)."""
    kept = dict(profiles or {})

    async def update(org_id, user_id, **fields):
        current = kept.get(user_id, OrganizationMemberProfileRecord())
        changed = {k: v for k, v in fields.items() if v is not None}
        field_of = {"organization": "organization", "name": "name"}
        kept[user_id] = OrganizationMemberProfileRecord(
            **{**current.__dict__, **{field_of.get(k, k): v for k, v in changed.items()}}
        )
        return kept[user_id]

    return SimpleNamespace(
        get_users_by_ids=AsyncMock(
            side_effect=lambda ids: {
                i: UserRecord(id=i, email=f"{i}@example.com", name=i.title(), bio="Account bio")
                for i in ids
                if i in PEOPLE
            }
        ),
        list_organization_member_profiles=AsyncMock(side_effect=lambda org_id: dict(kept)),
        get_organization_member_profile=AsyncMock(side_effect=lambda org_id, uid: kept.get(uid)),
        get_member_account=AsyncMock(
            side_effect=lambda uid: SimpleNamespace(
                user_id=uid,
                email=f"{uid}@example.com",
                name=uid.title(),
                avatar=None,
                organization=None,
                job_title=None,
                bio="Account bio",
                created_at=datetime(2026, 7, 1),
                updated_at=None,
            )
        ),
        list_workspaces_for_org=AsyncMock(
            return_value=[SimpleNamespace(id="ws-1", name="Audit", slug="audit", owner_id="x")]
        ),
        update_organization_member_profile=AsyncMock(side_effect=update),
        set_organization_member_avatar=AsyncMock(return_value="/api/auth/avatar/old.png"),
    )


def _client(
    *, user: str, profiles: dict[str, OrganizationMemberProfileRecord] | None = None
) -> tuple[TestClient, SimpleNamespace]:
    adapter = _adapter(profiles)
    app = FastAPI()
    app.include_router(org_api.router, prefix="/organizations")
    app.dependency_overrides[get_current_user_required] = lambda: User.model_construct(
        id=user, email="viewer@example.com", name="Viewer"
    )
    app.dependency_overrides[org_api.get_organization_service] = lambda: OrganizationService(
        adapter=adapter
    )
    # The drive sync (best effort) gets a storage and no database here.
    app.dependency_overrides[org_api._get_object_storage] = lambda: _MemoryStorage()
    app.dependency_overrides[org_api.get_db] = lambda: _NoDb()
    return TestClient(app), adapter


def test_member_cannot_patch_profile() -> None:
    client, adapter = _client(user="member")
    resp = client.patch(
        "/organizations/org-1/members/viewer",
        json={"bio": "Works on audit."},
    )
    assert resp.status_code == 403
    adapter.update_organization_member_profile.assert_not_awaited()


def test_admin_edits_the_org_profile_not_the_account() -> None:
    client, adapter = _client(user="admin")
    resp = client.patch(
        "/organizations/org-1/members/member",
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
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["name"] == "Member"
    assert body["organization"] == "Acme"
    assert body["job_title"] == "Partner"
    assert body["bio"] == "Works on audit."
    assert body["email"] == "member@example.com"
    adapter.update_organization_member_profile.assert_awaited_once_with(
        org_id="org-1",
        user_id="member",
        name=None,
        organization="Acme",
        job_title="Partner",
        bio="Works on audit.",
        service_line="Audit",
        country="France",
        interest="AI in audit",
    )


def test_a_profile_is_only_kept_for_people_who_hold_a_role_in_the_org() -> None:
    client, adapter = _client(user="admin")

    resp = client.patch("/organizations/org-1/members/stranger", json={"bio": "x"})

    assert resp.status_code == 404
    adapter.update_organization_member_profile.assert_not_awaited()


def test_admin_sets_the_org_avatar_in_the_members_drive() -> None:
    from naas_abi.apps.nexus.apps.api.app.services.auth.avatar_store_test import MemoryStorage

    storage = MemoryStorage()
    client, adapter = _client(user="admin")
    client.app.dependency_overrides[org_api._get_object_storage] = lambda: storage

    resp = client.post(
        "/organizations/org-1/members/member/avatar",
        files={"file": ("me.png", b"png-bytes", "image/png")},
    )

    assert resp.status_code == 200, resp.text
    assert storage.paths() == {"naas_abi/my-drive/member/.settings/avatar/avatar_org_org-1.png"}
    assert adapter.set_organization_member_avatar.await_args.kwargs["avatar"].startswith(
        "/api/auth/avatar/user/member/org/org-1?v="
    )


def test_removing_the_org_avatar_archives_it() -> None:
    from naas_abi.apps.nexus.apps.api.app.services.auth.avatar_store_test import MemoryStorage

    storage = MemoryStorage()
    storage.put_object("naas_abi/my-drive/member/.settings/avatar", "avatar_org_org-1.png", b"org")
    # Another organization's picture of the same person.
    storage.put_object("naas_abi/my-drive/member/.settings/avatar", "avatar_org_org-2.png", b"o2")
    storage.put_object("naas_abi/my-drive/member/.settings/avatar", "avatar.png", b"account")
    client, adapter = _client(user="admin")
    client.app.dependency_overrides[org_api._get_object_storage] = lambda: storage

    resp = client.delete("/organizations/org-1/members/member/avatar")

    assert resp.status_code == 200, resp.text
    adapter.set_organization_member_avatar.assert_awaited_once_with(
        org_id="org-1", user_id="member", avatar=None
    )
    paths = storage.paths()
    assert "naas_abi/my-drive/member/.settings/avatar/avatar_org_org-1.png" not in paths
    assert "naas_abi/my-drive/member/.settings/avatar/avatar_org_org-2.png" in paths
    assert "naas_abi/my-drive/member/.settings/avatar/avatar.png" in paths
    assert any(p.endswith("_avatar_org_org-1.png") and "/archives/" in p for p in paths)


def test_admin_cannot_change_own_org_role() -> None:
    client, _ = _client(user="admin")
    resp = client.patch("/organizations/org-1/members/admin", json={"role": "member"})
    assert resp.status_code == 400


def test_admin_cannot_change_owner_org_role() -> None:
    # IAM: only an owner takes the owner role away.
    client, _ = _client(user="admin")
    resp = client.patch("/organizations/org-1/members/owner", json={"role": "admin"})
    assert resp.status_code == 403


def test_only_an_owner_assigns_the_owner_role() -> None:
    client, _ = _client(user="admin")
    assert (
        client.patch("/organizations/org-1/members/member", json={"role": "owner"}).status_code
        == 403
    )
    client, _ = _client(user="owner")
    assert (
        client.patch("/organizations/org-1/members/member", json={"role": "owner"}).status_code
        == 200
    )


def test_admin_reads_account_and_membership_details(team) -> None:
    team.grant("member", "member", "abi:nexus:organization/org-1/nexus:workspace/ws-1")
    client, _ = _client(
        user="admin", profiles={"member": OrganizationMemberProfileRecord(name="Member (Acme)")}
    )

    resp = client.get("/organizations/org-1/members/member")

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["member"]["role"] == "member"
    assert body["account"]["email"] == "member@example.com"
    assert body["account"]["created_at"].startswith("2026-07-01")
    assert body["organization_profile"]["name"] == "Member (Acme)"
    assert body["organization_profile"]["organization"] is None
    assert body["workspaces"] == [
        {"id": "ws-1", "name": "Audit", "slug": "audit", "role": "member", "source": "workspace"}
    ]


def test_an_org_admin_reaches_every_workspace_of_the_org_and_it_shows(team) -> None:
    team.workspace("org-1", "ws-2")
    client, adapter = _client(user="owner")
    adapter.list_workspaces_for_org.return_value = [
        SimpleNamespace(id="ws-1", name="Audit", slug="audit", owner_id="x"),
        SimpleNamespace(id="ws-2", name="Tax", slug="tax", owner_id="x"),
    ]

    resp = client.get("/organizations/org-1/members/admin")

    assert resp.status_code == 200, resp.text
    # In ws-1 the admin holds the role itself; ws-2 they reach through the org.
    assert resp.json()["workspaces"] == [
        {"id": "ws-1", "name": "Audit", "slug": "audit", "role": "admin", "source": "workspace"},
        {"id": "ws-2", "name": "Tax", "slug": "tax", "role": "admin", "source": "organization"},
    ]


def test_member_details_are_admin_only_and_404_for_non_members() -> None:
    assert _client(user="member")[0].get("/organizations/org-1/members/viewer").status_code == 403
    assert _client(user="admin")[0].get("/organizations/org-1/members/nobody").status_code == 404


class _NoDb:
    """Stands in for the session: flush works, the drive sync then fails and is logged."""

    async def flush(self) -> None:
        return None
