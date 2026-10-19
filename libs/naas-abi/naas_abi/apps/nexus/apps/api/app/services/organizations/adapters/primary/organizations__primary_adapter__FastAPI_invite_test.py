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
from naas_abi.apps.nexus.apps.api.app.services.auth.adapters.primary.auth__primary_adapter__dependencies import (
    get_auth_service,
)
from naas_abi.apps.nexus.apps.api.app.services.invites import runtime as invites_runtime
from naas_abi.apps.nexus.apps.api.app.services.organizations.adapters.primary import (
    organizations__primary_adapter__FastAPI as org_api,
)
from naas_abi.apps.nexus.apps.api.app.services.organizations.port import (
    OrganizationMemberRecord,
)
from naas_abi.apps.nexus.apps.api.app.services.organizations.service import (
    OrganizationMemberAlreadyExistsError,
    OrganizationService,
)

EXISTING = OrganizationMemberRecord(
    id="orgmem-1",
    organization_id="org-1",
    user_id="viewer",
    role="viewer",
    email="invitee@example.com",
    name="Invitee",
    created_at=datetime(2026, 7, 31),
)


@pytest.fixture(autouse=True)
def _team(team):
    return team


def _client(members: list[OrganizationMemberRecord]) -> TestClient:
    """The invitee (``viewer`` of the team) is a member of org-1 when ``members``
    holds them, else they hold no role there."""
    adapter = SimpleNamespace(
        get_user_by_email=AsyncMock(
            return_value=SimpleNamespace(id="viewer", email="invitee@example.com", name="Invitee")
        ),
        get_users_by_ids=AsyncMock(
            side_effect=lambda ids: {
                i: SimpleNamespace(id=i, email="invitee@example.com", name="Invitee") for i in ids
            }
        ),
    )
    service = OrganizationService(adapter=adapter)

    auth_service = AsyncMock()
    auth_service.ensure_user_for_invite.return_value = (SimpleNamespace(id="viewer"), False)

    app = FastAPI()
    app.include_router(org_api.router, prefix="/organizations")
    app.dependency_overrides[get_current_user_required] = lambda: User.model_construct(
        id="admin", email="admin@example.com", name="Admin"
    )
    app.dependency_overrides[org_api.get_organization_service] = lambda: service
    app.dependency_overrides[org_api.get_workspace_service_for_org_invite] = lambda: AsyncMock()
    app.dependency_overrides[get_auth_service] = lambda: auth_service
    app.dependency_overrides[org_api._get_email_service] = lambda: None
    # The invitee already has an account: the invitation service has nothing to do.
    app.dependency_overrides[invites_runtime.get_invitation_service] = lambda: SimpleNamespace(
        persistence=SimpleNamespace(user_id_by_email=AsyncMock(return_value="user-2"))
    )
    return TestClient(app)


@pytest.fixture(autouse=True)
def _no_rate_limit(monkeypatch) -> None:
    monkeypatch.setattr(org_api, "check_rate_limit", AsyncMock())


def test_reinviting_an_existing_member_resends_instead_of_400(monkeypatch, team) -> None:
    """Re-inviting is the admin's only resend path, so it must not be rejected."""
    send = AsyncMock(return_value=True)
    monkeypatch.setattr(org_api, "issue_and_send_invite_sign_in", send)

    client = _client([EXISTING])
    resp = client.post(
        "/organizations/org-1/members/invite",
        json={"email": "Invitee@Example.com", "role": "member"},
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["user_id"] == "viewer"
    assert body["sign_in_email_sent"] is True
    send.assert_awaited_once()


def test_inviting_someone_without_a_role_grants_it_and_sends_the_sign_in(
    monkeypatch, nexus_iam
) -> None:
    send = AsyncMock(return_value=True)
    monkeypatch.setattr(org_api, "issue_and_send_invite_sign_in", send)
    nexus_iam.user("newcomer")
    client = _client([])
    service = client.app.dependency_overrides[org_api.get_organization_service]()
    service.adapter.get_user_by_email = AsyncMock(
        return_value=SimpleNamespace(id="newcomer", email="new@example.com", name="New")
    )
    service.adapter.get_users_by_ids = AsyncMock(return_value={})
    client.app.dependency_overrides[get_auth_service] = lambda: SimpleNamespace(
        ensure_user_for_invite=AsyncMock(return_value=(SimpleNamespace(id="newcomer"), True))
    )

    resp = client.post(
        "/organizations/org-1/members/invite", json={"email": "new@example.com", "role": "member"}
    )

    assert resp.status_code == 200, resp.text
    assert resp.json()["role"] == "member"
    assert resp.json()["user_id"] == "newcomer"
    send.assert_awaited_once()


def test_send_failure_propagates_so_the_challenge_is_not_left_live(monkeypatch) -> None:
    """The route delegates delivery, so the helper's invalidate-then-raise wins."""
    send = AsyncMock(side_effect=RuntimeError("smtp down"))
    monkeypatch.setattr(org_api, "issue_and_send_invite_sign_in", send)

    client = _client([EXISTING])
    with pytest.raises(RuntimeError):
        client.post(
            "/organizations/org-1/members/invite",
            json={"email": "invitee@example.com", "role": "member"},
        )

    send.assert_awaited_once()


def test_already_exists_error_carries_the_user_id() -> None:
    """_find_org_member relies on this to locate the row it should resend to."""
    exc = OrganizationMemberAlreadyExistsError(org_id="org-1", user_id="user-2")
    assert exc.user_id == "user-2"
