"""The organization invite on the people service: the account is created or
linked (never both), the org role and the profile go through ``create_or_link``,
and its refusals are HTTP answers. The end-to-end flows are in
``workspaces/adapters/primary/workspaces__people_routes_test.py``."""

from __future__ import annotations

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
from naas_abi.apps.nexus.apps.api.app.services.organizations.port import UserRecord
from naas_abi.apps.nexus.apps.api.app.services.organizations.service import (
    OrganizationService,
)
from naas_abi.apps.nexus.apps.api.app.services.workspaces.people_port import get_people_service
from naas_abi.apps.nexus.apps.api.app.services.workspaces.people_testing import (
    FakePeopleService,
)


@pytest.fixture(autouse=True)
def _team(team):
    return team


@pytest.fixture(autouse=True)
def _no_rate_limit(monkeypatch) -> None:
    monkeypatch.setattr(org_api, "check_rate_limit", AsyncMock())
    monkeypatch.setattr(org_api, "check_invitation_mail_quota", AsyncMock())


class _NoDb:
    """Stands in for the session: flush works, the drive sync then fails and is logged."""

    async def flush(self) -> None:
        return None


def _client(people: FakePeopleService) -> TestClient:
    adapter = SimpleNamespace(
        get_users_by_ids=AsyncMock(
            side_effect=lambda ids: {
                i: UserRecord(id=i, email=f"{i}@example.com", name=i.title()) for i in ids
            }
        ),
        get_organization_by_id=AsyncMock(return_value=SimpleNamespace(id="org-1", name="Acme")),
        list_organization_member_profiles=AsyncMock(return_value={}),
        list_workspaces_for_org=AsyncMock(return_value=[SimpleNamespace(id="ws-1")]),
    )
    app = FastAPI()
    app.include_router(org_api.router, prefix="/organizations")
    app.dependency_overrides[get_current_user_required] = lambda: User.model_construct(
        id="admin", email="admin@example.com", name="Admin"
    )
    app.dependency_overrides[org_api.get_organization_service] = lambda: OrganizationService(
        adapter=adapter
    )
    app.dependency_overrides[get_people_service] = lambda: people
    # The drive sync (best effort) gets a storage and no database here.
    app.dependency_overrides[org_api._get_object_storage] = lambda: _MemoryStorage()
    app.dependency_overrides[org_api.get_db] = lambda: _NoDb()
    return TestClient(app)


def test_inviting_an_existing_account_links_it_and_gives_the_org_role(nexus_iam) -> None:
    nexus_iam.user("newcomer")
    people = FakePeopleService.of(("newcomer", "new@example.com", "New"))

    resp = _client(people).post(
        "/organizations/org-1/members/invite",
        json={"email": " New@Example.com ", "role": "member", "country": "France"},
    )

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "added"
    assert body["user"]["id"] == "newcomer"
    assert (body["member"]["role"], body["member"]["source"]) == ("member", "organization")
    assert "user_created" not in body
    (asked,) = people.named("create_or_link")
    assert asked["email"] == "new@example.com"
    assert asked["profile"] == {"country": "France"}
    assert asked["organization_id"] == "org-1"
    assert asked["by"] == "admin"


def test_reinviting_a_member_is_a_conflict_resend_is_its_own_route() -> None:
    people = FakePeopleService.of(("viewer", "invitee@example.com", "Invitee"))

    resp = _client(people).post(
        "/organizations/org-1/members/invite",
        json={"email": "invitee@example.com", "role": "member"},
    )

    assert resp.status_code == 409


def test_someone_with_no_account_needs_an_identity_provider() -> None:
    """Nexus has no login of its own: with no provider to sign in at, an invitation
    of a person it does not know is refused, never answered with a local account."""
    from naas_abi.apps.nexus.apps.api.app.services.invites.port import NoProviderError

    people = FakePeopleService()

    async def no_provider(**_kwargs):
        raise NoProviderError("No identity provider is configured")

    people.create_or_link = no_provider  # type: ignore[method-assign]

    resp = _client(people).post(
        "/organizations/org-1/members/invite",
        json={"email": "stranger@example.com", "role": "member"},
    )

    assert resp.status_code == 422
    assert "No identity provider is configured" in resp.json()["detail"]


def test_without_the_people_service_inviting_is_unavailable() -> None:
    client = _client(FakePeopleService())
    client.app.dependency_overrides.pop(get_people_service)
    client.app.dependency_overrides[org_api.get_db] = lambda: _NoDb()

    resp = client.post(
        "/organizations/org-1/members/invite", json={"email": "a@example.com", "role": "member"}
    )

    assert resp.status_code == 503
