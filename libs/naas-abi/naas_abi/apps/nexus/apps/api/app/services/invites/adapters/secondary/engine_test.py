"""Invitations and IdP group bindings over the engine's real IAM: written on behalf
of the inviting person, so IAM refuses a role that grants more than they hold."""

from __future__ import annotations

import pytest
from naas_abi.apps.nexus.apps.api.app.services.iam.names import workspace_scope
from naas_abi.apps.nexus.apps.api.app.services.invites.adapters.secondary.engine import (
    EngineGrantsGateway,
)
from naas_abi.apps.nexus.apps.api.app.services.invites.service import InvitationService
from naas_abi.apps.nexus.apps.api.app.services.invites.service_test import (
    BUILTIN,
    NOW,
    Directories,
    Mailer,
    Store,
)
from naas_abi_core.engine.call_context import as_service_account, use_call_context
from naas_abi_core.services.iam.IAMPorts import GrantNotHeldError, IAMNotFoundError
from naas_abi_core.services.iam.IAMService import LEGACY_NEXUS_ISSUER

WS1 = workspace_scope("org-1", "ws-1")


@pytest.fixture
def invites(team):
    store = Store()
    service = InvitationService(
        store,
        Directories(BUILTIN),
        EngineGrantsGateway(lambda: team.iam),
        Mailer(),
        sign_in_url=lambda email, provider: f"https://web/login?email={email}",
        clock=lambda: NOW,
    )
    # May attach member and viewer at ws-1, and holds a viewer's reach there.
    with as_service_account("engine"):
        inviter = team.iam.ensure_user(LEGACY_NEXUS_ISSUER, "inviter", provider="nexus")
        policy = team.iam.create_policy(
            "inviter",
            {
                "version": "2026-10-13",
                "statements": [
                    {
                        "effect": "Allow",
                        "actions": ["iam:AttachPolicy", "iam:DetachPolicy"],
                        "resources": [
                            "${scope}:iam:attachment/builtin.member/*",
                            "${scope}:iam:attachment/builtin.viewer/*",
                        ],
                    }
                ],
            },
        )
        team.iam.attach_policy(policy.id, inviter.id, WS1)
        team.iam.attach_policy("builtin.viewer", inviter.id, WS1)
    return service


async def _invite(invites, role: str, by: str):
    return await invites.invite(
        email="bob@example.com",
        name=None,
        provider=None,
        organization_id="org-1",
        org_role=None,
        workspace_id="ws-1",
        workspace_role=role,
        invited_by=by,
    )


def _grants(team) -> list[tuple[str, str | None]]:
    with as_service_account("engine"):
        return [(g.policy_id, g.scope) for g in team.iam.list_pending_grants()]


@pytest.mark.asyncio
async def test_an_invitation_to_a_role_the_inviter_lacks_is_refused(team, invites):
    with pytest.raises(GrantNotHeldError) as refused:
        await _invite(invites, "member", "inviter")
    assert "builtin.member" in str(refused.value)
    assert _grants(team) == []
    assert invites.persistence.rows == {}
    # A role it holds, it gives.
    await _invite(invites, "viewer", "inviter")
    assert _grants(team) == [("builtin.viewer", WS1)]


@pytest.mark.asyncio
async def test_an_admin_invites_to_the_roles_below_it(team, invites):
    await _invite(invites, "admin", "admin")
    assert _grants(team) == [("builtin.admin", WS1)]


@pytest.mark.asyncio
async def test_an_idp_binding_grants_no_more_than_the_one_binding(team, invites):
    with pytest.raises(GrantNotHeldError):
        await invites.bind_group(
            provider="builtin", group="Sales", role="member", scope=WS1, by="inviter"
        )
    assert await invites.bindings([WS1]) == []
    await invites.bind_group(
        provider="builtin", group="Sales", role="member", scope=WS1, by="admin"
    )
    assert [(b.claim_value, b.role) for b in await invites.bindings([WS1])] == [("Sales", "member")]


@pytest.mark.asyncio
async def test_an_invitation_carrying_features_of_member_gives_them_at_sign_in(team, invites):
    """No role brings a feature: the workspace's "Features of member" travels with
    the invitation, checked as the inviting person, and attaches at the sign-in."""
    from naas_abi.apps.nexus.apps.api.app.services.iam import role_features

    with as_service_account("engine"):
        features = team.iam.create_policy(
            "Features of member", role_features.policy_document(["chat", "files"]), scope=WS1
        )
    # The inviter may attach the role, not this policy: IAM refuses it (as a policy
    # they cannot see) and nothing is made.
    with pytest.raises((GrantNotHeldError, IAMNotFoundError)):
        await invites.invite(
            email="bob@example.com",
            name=None,
            provider=None,
            organization_id="org-1",
            org_role=None,
            workspace_id="ws-1",
            workspace_role="viewer",
            invited_by="inviter",
            policy_ids=[features.id],
        )
    assert _grants(team) == []
    await invites.invite(
        email="bob@example.com",
        name=None,
        provider=None,
        organization_id="org-1",
        org_role=None,
        workspace_id="ws-1",
        workspace_role="member",
        invited_by="admin",
        policy_ids=[features.id],
    )
    assert sorted(_grants(team)) == sorted([("builtin.member", WS1), (features.id, WS1)])
    with as_service_account("engine"):
        bob = team.iam.ensure_user(
            "https://idp.example",
            "bob",
            provider="builtin",
            email="bob@example.com",
            email_verified=True,
        )
        team.iam.claim_pending_grants(bob.id)
    with use_call_context(team.context(bob.id)):
        for key, allowed in (("chat", True), ("files", True), ("graph", False)):
            name = f"abi:org-1:ws-1:nexus:feature/{key}"
            assert team.iam.authorize("nexus:UseFeature", name).allowed is allowed, key
