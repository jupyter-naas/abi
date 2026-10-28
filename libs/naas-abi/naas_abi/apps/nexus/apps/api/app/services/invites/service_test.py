"""``InvitationService``: choosing a provider, the grants an invitation holds,
renewing, revoking and claiming. Fakes stand for the ports."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import replace
from datetime import datetime

import pytest
from naas_abi.apps.nexus.apps.api.app.services.invites.port import (
    Directory,
    DirectoryGateway,
    GrantMade,
    GrantsGateway,
    IdpBindingView,
    Invitation,
    InvitationMail,
    InvitationMailer,
    InvitationNotFoundError,
    InvitationPersistencePort,
    NoProviderError,
    OrgInvitationExistsError,
    OwnerGrantRefusedError,
    ProviderChoice,
    Provisioned,
    ProvisioningRefused,
)
from naas_abi.apps.nexus.apps.api.app.services.invites.service import InvitationService

NOW = datetime(2026, 10, 19, 12, 0)
BUILTIN = ProviderChoice("builtin", "Built-in", "builtin")
OKTA = ProviderChoice("okta", "Okta", "none")


class Store(InvitationPersistencePort):
    def __init__(self) -> None:
        self.rows: dict[str, Invitation] = {}
        self.domains: dict[str, str] = {}
        self.commits = 0
        self.rollbacks = 0
        self.fail_commit = False

    async def add(self, invitation, *, now):
        self.rows[invitation.id] = replace(invitation, created_at=now)
        return self.rows[invitation.id]

    async def get(self, invitation_id):
        return self.rows.get(invitation_id)

    async def find_pending(self, *, email, provider, organization_id, workspace_id):
        return next(
            (
                i
                for i in self.rows.values()
                if (i.email, i.provider, i.organization_id, i.workspace_id, i.status)
                == (email, provider, organization_id, workspace_id, "pending")
            ),
            None,
        )

    async def list(self, *, organization_id=None, workspace_id=None, status="pending"):
        return [
            i
            for i in self.rows.values()
            if organization_id in (None, i.organization_id)
            and workspace_id in (None, i.workspace_id)
            and status in (None, i.status)
        ]

    async def pending_for(self, *, email, provider):
        return [
            i
            for i in self.rows.values()
            if (i.email, i.provider, i.status) == (email, provider, "pending")
        ]

    async def update(
        self,
        invitation_id,
        *,
        org_role,
        workspace_role,
        grant_ids,
        invited_by,
        now,
        profile=None,
        policy_ids=(),
    ):
        row = replace(
            self.rows[invitation_id],
            org_role=org_role,
            workspace_role=workspace_role,
            grant_ids=tuple(grant_ids),
            policy_ids=tuple(policy_ids),
            invited_by=invited_by,
        )
        if profile is not None:
            row = replace(row, profile=dict(profile))
        self.rows[invitation_id] = row
        return self.rows[invitation_id]

    async def mark_accepted(self, invitation_id, *, user_id, now):
        row = self.rows[invitation_id]
        if row.status != "pending":
            return False
        self.rows[invitation_id] = replace(row, status="accepted", accepted_user_id=user_id)
        return True

    async def mark_revoked(self, invitation_id, *, now):
        row = self.rows[invitation_id]
        if row.status != "pending":
            return False
        self.rows[invitation_id] = replace(row, status="revoked")
        return True

    async def provider_for_domain(self, domain, organization_id):
        return self.domains.get(domain)

    async def organization_of_workspace(self, workspace_id):
        return "org-1"

    async def user_id_by_email(self, email):
        return None

    async def commit(self):
        if self.fail_commit:
            raise RuntimeError("the database is down")
        self.commits += 1

    async def rollback(self):
        self.rollbacks += 1


class Directories(DirectoryGateway):
    def __init__(self, *providers: ProviderChoice, default: str | None = None) -> None:
        self.known = Directory(tuple(providers), default)
        self.provisioned: list[tuple[str, str, str | None]] = []
        self.provisioned_by: list[str | None] = []
        # The users IAM lets create accounts at a provider (``identity:ProvisionUser``).
        self.may = {"usr-alice"}
        self.fail: Exception | None = None

    async def directory(self):
        return self.known

    async def provision(self, provider, email, name, *, by=None):
        if self.fail is not None:
            raise self.fail
        if provider.managed_in_provider:
            return None
        if by is not None and by not in self.may:
            raise ProvisioningRefused(f"{by} may not create accounts at {provider.name}")
        self.provisioned.append((provider.name, email, name))
        self.provisioned_by.append(by)
        return Provisioned(subject="sub-1", created=True)


class Grants(GrantsGateway):
    def __init__(self) -> None:
        self.live: dict[str, tuple] = {}
        self.bound: set[tuple] = set()
        self.fail_on: int | None = None
        self.made = 0
        self.granted_by: list[str | None] = []
        self.bound_by: list[str | None] = []
        self.attached: list[tuple] = []
        self.refuse: set[str] = set()

    async def grant(self, provider, email, policy_id, scope, *, by=None):
        self.granted_by.append(by)
        self.made += 1
        if self.fail_on == self.made:
            raise PermissionError("denied")
        key = (provider, email, policy_id, scope)
        held = next((i for i, v in self.live.items() if v == key), None)
        if held is not None:
            return GrantMade(held, created=False)  # IAM keeps one grant per role and scope
        grant_id = f"g{self.made}"
        self.live[grant_id] = key
        return GrantMade(grant_id, created=True)

    async def revoke(self, grant_id):
        self.live.pop(grant_id, None)

    async def pending(self, grant_ids):
        return {g: (self.live[g][2], self.live[g][3]) for g in grant_ids if g in self.live}

    async def attach(self, user_id, policy_id, scope, *, by=None):
        if policy_id in self.refuse:
            raise PermissionError(f"{by} may not attach {policy_id}")
        self.attached.append((user_id, policy_id, scope, by))
        return True

    async def detach(self, user_id, policy_id, scope):
        self.attached = [a for a in self.attached if a[:3] != (user_id, policy_id, scope)]

    async def bind(self, provider, claim_value, policy_id, scope, *, by=None):
        self.bound_by.append(by)
        self.bound.add((provider, claim_value, policy_id, scope))

    async def unbind(self, provider, claim_value, policy_id, scope):
        key = (provider, claim_value, policy_id, scope)
        found = key in self.bound
        self.bound.discard(key)
        return found

    async def bindings(self, scopes: Sequence[str]):
        return [
            IdpBindingView(p, c, pol.removeprefix("builtin."), s, "grp")
            for p, c, pol, s in sorted(self.bound)
            if s in scopes
        ]


class Mailer(InvitationMailer):
    def __init__(self) -> None:
        self.sent: list[InvitationMail] = []
        self.fail = False

    async def send(self, mail):
        if self.fail:
            raise RuntimeError("mail is down")
        self.sent.append(mail)
        return True


class Harness:
    def __init__(self, *providers: ProviderChoice, default: str | None = None) -> None:
        self.store, self.grants, self.mailer = Store(), Grants(), Mailer()
        self.directory = Directories(*(providers or (BUILTIN,)), default=default)
        self.service = InvitationService(
            self.store,
            self.directory,
            self.grants,
            self.mailer,
            sign_in_url=lambda email, provider: (
                f"https://web/auth/login?email={email}&provider={provider}"
            ),
            clock=lambda: NOW,
        )

    async def invite(self, **overrides):
        fields = {
            "email": "Bob@Example.com",
            "name": None,
            "provider": None,
            "organization_id": "org-1",
            "org_role": "member",
            "workspace_id": "ws-1",
            "workspace_role": "member",
            "invited_by": "usr-alice",
            "inviter_name": "Alice",
            "organization_name": "Acme",
            "workspace_name": "Research",
            **overrides,
        }
        return await self.service.invite(**fields)


@pytest.mark.asyncio
async def test_an_invitation_grants_provisions_records_and_mails():
    h = Harness()
    outcome = await h.invite(name="Bob B")
    assert outcome.user_created and outcome.sign_in_email_sent and not outcome.renewed
    invitation = outcome.invitation
    assert (invitation.email, invitation.provider, invitation.status) == (
        "bob@example.com",
        "builtin",
        "pending",
    )
    assert set(h.grants.live.values()) == {
        ("builtin", "bob@example.com", "builtin.member", "abi:org-1:-"),
        ("builtin", "bob@example.com", "builtin.member", "abi:org-1:ws-1"),
    }
    assert set(invitation.grant_ids) == set(h.grants.live)
    assert h.directory.provisioned == [("builtin", "bob@example.com", "Bob B")]
    (mail,) = h.mailer.sent
    assert (mail.to_email, mail.organization_name, mail.workspace_name) == (
        "bob@example.com",
        "Acme",
        "Research",
    )
    assert mail.sign_in_url == "https://web/auth/login?email=bob@example.com&provider=builtin"
    assert h.store.commits == 1


@pytest.mark.asyncio
async def test_a_workspace_only_invitation_grants_the_workspace_role_only():
    h = Harness()
    await h.invite(org_role=None, workspace_role="viewer")
    assert {(p, s) for _, _, p, s in h.grants.live.values()} == {
        ("builtin.viewer", "abi:org-1:ws-1")
    }


@pytest.mark.asyncio
async def test_a_workspace_without_an_organization_sits_in_the_reserved_org():
    h = Harness()
    await h.invite(organization_id=None, org_role=None, workspace_role="member")
    assert {s for *_, s in h.grants.live.values()} == {"abi:_none:ws-1"}


@pytest.mark.asyncio
async def test_an_invitation_names_a_role_somewhere():
    with pytest.raises(ValueError):
        await Harness().invite(org_role=None, workspace_role=None)
    with pytest.raises(ValueError):
        await Harness().invite(organization_id=None, workspace_id=None)


@pytest.mark.asyncio
async def test_a_provider_whose_people_are_managed_there_gets_grants_only():
    h = Harness(OKTA)
    outcome = await h.invite()
    assert outcome.provider.managed_in_provider and outcome.user_created is False
    assert h.directory.provisioned == []
    assert len(h.grants.live) == 2
    assert h.mailer.sent[0].managed_in_provider is True


@pytest.mark.asyncio
async def test_the_provider_is_the_asked_one_then_the_domains_then_the_default_then_the_only_one():
    h = Harness(BUILTIN, OKTA, default="builtin")
    assert (await h.service.choose("a@x.org", "okta", None)).name == "okta"
    assert (await h.service.choose("a@x.org", None, None)).name == "builtin"
    h.store.domains["acme.com"] = "okta"
    assert (await h.service.choose("a@acme.com", None, "org-1")).name == "okta"
    with pytest.raises(NoProviderError):
        await h.service.choose("a@x.org", "nope", None)
    assert (await Harness(OKTA).service.choose("a@x.org", None, None)).name == "okta"
    with pytest.raises(NoProviderError, match="Name the identity provider"):
        await Harness(BUILTIN, OKTA).service.choose("a@x.org", None, None)
    none = Harness()
    none.directory.known = Directory()
    with pytest.raises(NoProviderError, match="No identity provider"):
        await none.service.choose("a@x.org", None, None)


@pytest.mark.asyncio
async def test_when_no_provider_is_configured_nothing_is_made():
    h = Harness()
    h.directory.known = Directory()
    with pytest.raises(NoProviderError, match="No identity provider"):
        await h.invite()
    assert h.grants.live == {} and h.store.rows == {}


@pytest.mark.asyncio
async def test_a_refused_grant_takes_back_the_ones_already_made():
    h = Harness()
    h.grants.fail_on = 2
    with pytest.raises(PermissionError):
        await h.invite()
    assert h.grants.live == {} and h.store.rows == {} and h.mailer.sent == []
    assert h.directory.provisioned == []


@pytest.mark.asyncio
async def test_a_provider_that_refuses_to_provision_leaves_no_grant_behind():
    h = Harness()
    h.directory.fail = RuntimeError("the provider is down")
    with pytest.raises(RuntimeError):
        await h.invite()
    assert h.grants.live == {} and h.store.rows == {} and h.mailer.sent == []


@pytest.mark.asyncio
async def test_inviting_again_renews_the_invitation_and_replaces_its_grants():
    h = Harness()
    first = (await h.invite()).invitation
    again = await h.invite(workspace_role="admin", invited_by="usr-carol")
    assert again.renewed and again.invitation.id == first.id
    assert again.invitation.workspace_role == "admin" and again.invitation.invited_by == "usr-carol"
    assert {(p, s) for _, _, p, s in h.grants.live.values()} == {
        ("builtin.member", "abi:org-1:-"),
        ("builtin.admin", "abi:org-1:ws-1"),
    }
    assert set(again.invitation.grant_ids) == set(h.grants.live)
    assert len(h.store.rows) == 1 and len(h.mailer.sent) == 2


@pytest.mark.asyncio
async def test_the_profile_set_at_invitation_is_kept_and_a_renewal_replaces_it():
    h = Harness()
    first = (
        await h.invite(profile={"job_title": "CTO", "country": "FR", "unknown": "x"})
    ).invitation
    assert first.profile == {"job_title": "CTO", "country": "FR"}
    kept = (await h.invite()).invitation
    assert kept.profile == first.profile
    replaced = (await h.invite(profile={"bio": "Hi"})).invitation
    assert replaced.profile == {"bio": "Hi"}


@pytest.mark.asyncio
async def test_a_failed_email_does_not_fail_the_invitation():
    h = Harness()
    h.mailer.fail = True
    outcome = await h.invite()
    assert outcome.sign_in_email_sent is False
    assert outcome.invitation.status == "pending" and len(h.grants.live) == 2


@pytest.mark.asyncio
async def test_revoking_withdraws_the_grants_and_only_once():
    h = Harness()
    invitation = (await h.invite()).invitation
    await h.service.revoke(invitation.id)
    assert h.grants.live == {} and h.store.rows[invitation.id].status == "revoked"
    assert await h.service.pending(organization_id="org-1") == []
    with pytest.raises(InvitationNotFoundError):
        await h.service.revoke(invitation.id)
    with pytest.raises(InvitationNotFoundError):
        await h.service.resend(invitation.id)
    with pytest.raises(InvitationNotFoundError):
        await h.service.revoke("unknown")


@pytest.mark.asyncio
async def test_resending_mails_the_same_invitation_again():
    h = Harness()
    invitation = (await h.invite()).invitation
    assert await h.service.resend(invitation.id, inviter_name="Alice") is True
    assert len(h.mailer.sent) == 2 and len(h.grants.live) == 2
    h.directory.known = Directory()
    with pytest.raises(NoProviderError):
        await h.service.resend(invitation.id)


@pytest.mark.asyncio
async def test_a_sign_in_accepts_the_invitations_once_and_per_provider():
    h = Harness(BUILTIN, OKTA, default="builtin")
    await h.invite()
    await h.invite(provider="okta")
    other = await h.service.claim(user_id="u-bob", email="BOB@example.com", provider="builtin")
    assert [i.provider for i in other] == ["builtin"]
    # The memberships are the attachments IAM claimed: the invitation is only marked.
    assert await h.service.claim(user_id="u-bob", email="bob@example.com", provider="builtin") == []
    # The Okta invitation stays for whoever signs in through Okta with that email.
    assert len(await h.service.pending(organization_id="org-1")) == 1
    assert await h.service.claim(user_id="u-x", email="eve@example.com", provider="builtin") == []


@pytest.mark.asyncio
async def test_two_sign_ins_race_for_an_invitation_and_one_wins():
    h = Harness()
    invitation = (await h.invite()).invitation
    original = h.store.mark_accepted

    async def lose(invitation_id, *, user_id, now):
        await original(invitation_id, user_id="someone-else", now=now)
        return False

    h.store.mark_accepted = lose  # type: ignore[method-assign]
    assert await h.service.claim(user_id="u-bob", email="bob@example.com", provider="builtin") == []
    assert h.store.rows[invitation.id].accepted_user_id == "someone-else"


@pytest.mark.asyncio
async def test_group_bindings_go_to_iam_as_builtin_roles_at_their_scope():
    h = Harness()
    await h.service.bind_group(
        provider="builtin", group=" Data readers ", role="viewer", scope="abi:org-1:ws-1"
    )
    assert h.grants.bound == {("builtin", "Data readers", "builtin.viewer", "abi:org-1:ws-1")}
    found = await h.service.bindings(["abi:org-1:ws-1", "abi:org-1:-"])
    assert [(b.provider, b.claim_value, b.role) for b in found] == [
        ("builtin", "Data readers", "viewer")
    ]
    assert await h.service.bindings(["abi:org-1:ws-2"]) == []
    assert await h.service.unbind_group(
        provider="builtin", group="Data readers", role="viewer", scope="abi:org-1:ws-1"
    )
    assert h.grants.bound == set()
    with pytest.raises(NoProviderError):
        await h.service.bind_group(provider="nope", group="g", role="viewer", scope="abi:o:w")


@pytest.mark.asyncio
async def test_only_an_owner_invites_an_owner():
    h = Harness()
    for roles in ({"org_role": "owner"}, {"workspace_role": "owner"}):
        with pytest.raises(OwnerGrantRefusedError):
            await h.invite(**roles)
    # Nothing was granted, provisioned or recorded.
    assert h.grants.live == {} and h.store.rows == {} and h.directory.provisioned == []
    assert (await h.invite(org_role="owner", may_grant_owner=True)).invitation.org_role == "owner"


@pytest.mark.asyncio
async def test_two_invitations_share_the_org_grant_and_one_revoke_keeps_it():
    h = Harness()
    first = (await h.invite(workspace_id="ws-1")).invitation
    second = (await h.invite(workspace_id="ws-2")).invitation
    org_grant = next(i for i, v in h.grants.live.items() if v[3] == "abi:org-1:-")
    assert org_grant in first.grant_ids and org_grant in second.grant_ids
    await h.service.revoke(first.id)
    # The workspace grant of the first goes; the org one the second relies on stays.
    assert {v[3] for v in h.grants.live.values()} == {"abi:org-1:-", "abi:org-1:ws-2"}
    await h.service.revoke(second.id)
    assert h.grants.live == {}


@pytest.mark.asyncio
async def test_a_failed_second_invitation_leaves_the_first_ones_grants():
    h = Harness()
    first = (await h.invite(workspace_id="ws-1")).invitation
    before = dict(h.grants.live)
    h.directory.fail = RuntimeError("the provider is down")
    with pytest.raises(RuntimeError):
        await h.invite(workspace_id="ws-2")
    # Only the workspace grant the failed call made is taken back.
    assert h.grants.live == before
    assert set(h.store.rows[first.id].grant_ids) <= set(h.grants.live)


@pytest.mark.asyncio
async def test_a_database_that_fails_after_the_grants_takes_them_back():
    h = Harness()
    held = (await h.invite(workspace_id="ws-1")).invitation
    before = dict(h.grants.live)
    h.store.fail_commit = True
    with pytest.raises(RuntimeError):
        await h.invite(workspace_id="ws-2")
    assert h.store.rollbacks == 1
    assert h.grants.live == before and h.store.rows[held.id].status == "pending"
    # And a first invitation whose record cannot be kept leaves no grant at all.
    fresh = Harness()
    fresh.store.fail_commit = True
    with pytest.raises(RuntimeError):
        await fresh.invite()
    assert fresh.grants.live == {}


@pytest.mark.asyncio
async def test_renewing_does_not_withdraw_what_another_invitation_holds():
    h = Harness()
    first = (await h.invite(workspace_id="ws-1")).invitation
    await h.invite(workspace_id="ws-2")
    await h.invite(workspace_id="ws-1", workspace_role="admin", org_role="admin")
    # The first invitation now holds an admin org grant; the member one stays for ws-2.
    assert ("builtin", "bob@example.com", "builtin.member", "abi:org-1:-") in h.grants.live.values()
    assert h.store.rows[first.id].org_role == "admin"


# -- who may make accounts at the provider --------------------------------------------------


@pytest.mark.asyncio
async def test_a_user_without_the_right_creates_no_account_at_the_provider():
    """Anyone may own an organization they made: that must not let them create
    accounts in the provider's directory for addresses they control."""
    h = Harness()
    outcome = await h.invite(invited_by="usr-mallory", email="victim@corp.example")
    assert h.directory.provisioned == []
    assert outcome.provisioning_skipped and not outcome.user_created
    # The invitation still stands: grants wait for whoever signs in with that address.
    assert {g[1] for g in h.grants.live.values()} == {"victim@corp.example"}
    assert outcome.invitation.status == "pending" and len(h.mailer.sent) == 1


@pytest.mark.asyncio
async def test_an_address_on_a_domain_the_organization_verified_is_provisioned():
    h = Harness()
    h.store.domains["corp.example"] = "builtin"
    outcome = await h.invite(invited_by="usr-mallory", email="bob@corp.example")
    assert h.directory.provisioned == [("builtin", "bob@corp.example", None)]
    assert h.directory.provisioned_by == [None]  # Nexus's own call: the domain is proven
    assert outcome.user_created and not outcome.provisioning_skipped
    # A domain routed to another provider proves nothing for this one.
    h2 = Harness(BUILTIN, OKTA)
    h2.store.domains["corp.example"] = "okta"
    refused = await h2.invite(
        invited_by="usr-mallory", email="eve@corp.example", provider="builtin"
    )
    assert h2.directory.provisioned == [] and refused.provisioning_skipped


@pytest.mark.asyncio
async def test_a_user_who_holds_the_right_provisions_as_themselves():
    h = Harness()
    h.directory.may.add("usr-ops")
    outcome = await h.invite(invited_by="usr-ops", email="bob@elsewhere.example")
    assert h.directory.provisioned_by == ["usr-ops"] and outcome.user_created


@pytest.mark.asyncio
async def test_a_provider_that_manages_its_people_is_never_asked():
    h = Harness(OKTA, default="okta")
    outcome = await h.invite(invited_by="usr-mallory")
    assert h.directory.provisioned == [] and not outcome.provisioning_skipped


# -- invitations that carry an organization role --------------------------------------------


@pytest.mark.asyncio
async def test_a_workspace_invite_never_rewrites_an_organization_invitation():
    h = Harness()
    first = (await h.invite(org_role="admin", workspace_role="member")).invitation
    grants = dict(h.grants.live)
    with pytest.raises(OrgInvitationExistsError):
        await h.invite(org_role=None, workspace_role="viewer", invited_by="usr-wsadmin")
    kept = h.store.rows[first.id]
    assert (kept.org_role, kept.workspace_role, kept.invited_by) == ("admin", "member", "usr-alice")
    assert h.grants.live == grants and len(h.grants.live) == 2


@pytest.mark.asyncio
async def test_an_organization_admin_renewing_through_the_workspace_keeps_the_org_role():
    h = Harness()
    first = (await h.invite(org_role="admin", workspace_role="member")).invitation
    renewed = await h.invite(
        org_role=None,
        workspace_role="viewer",
        invited_by="usr-alice",
        may_renew_org_invitation=True,
    )
    assert renewed.renewed and renewed.invitation.id == first.id
    assert (renewed.invitation.org_role, renewed.invitation.workspace_role) == ("admin", "viewer")
    assert {(p, s) for _, _, p, s in h.grants.live.values()} == {
        ("builtin.admin", "abi:org-1:-"),
        ("builtin.viewer", "abi:org-1:ws-1"),
    }


@pytest.mark.asyncio
async def test_an_invitation_carries_policies_at_its_workspace():
    h = Harness()
    outcome = await h.invite(policy_ids=["pol_features_member", "pol_features_member"])
    assert outcome.invitation.policy_ids == ("pol_features_member",)
    assert set(h.grants.live.values()) == {
        ("builtin", "bob@example.com", "builtin.member", "abi:org-1:-"),
        ("builtin", "bob@example.com", "builtin.member", "abi:org-1:ws-1"),
        ("builtin", "bob@example.com", "pol_features_member", "abi:org-1:ws-1"),
    }
    # As the inviting person: IAM checks they may attach it and hold it.
    assert set(h.grants.granted_by) == {"usr-alice"}
    # Renewed without it, the policy's grant is withdrawn.
    again = await h.invite()
    assert again.invitation.policy_ids == ()
    assert ("builtin", "bob@example.com", "pol_features_member", "abi:org-1:ws-1") not in set(
        h.grants.live.values()
    )


@pytest.mark.asyncio
async def test_an_organization_invitation_carries_policies_at_the_organization():
    h = Harness()
    await h.invite(workspace_id=None, workspace_role=None, policy_ids=["pol_x"])
    assert ("builtin", "bob@example.com", "pol_x", "abi:org-1:-") in set(h.grants.live.values())


@pytest.mark.asyncio
async def test_an_invitation_carries_no_managed_policy():
    h = Harness()
    with pytest.raises(ValueError, match="customer policies"):
        await h.invite(policy_ids=["builtin.owner"])
    assert h.grants.live == {} and h.store.rows == {}


@pytest.mark.asyncio
async def test_someone_with_an_account_gets_the_policies_attached_as_the_inviter():
    h = Harness()
    attached = await h.service.attach_policies(
        user_id="usr-bob",
        organization_id="org-1",
        workspace_id="ws-1",
        policy_ids=["pol_a"],
        by="usr-alice",
    )
    assert attached == ("pol_a",)
    assert h.grants.attached == [("usr-bob", "pol_a", "abi:org-1:ws-1", "usr-alice")]


@pytest.mark.asyncio
async def test_a_refused_policy_attaches_none_of_the_others():
    h = Harness()
    h.grants.refuse = {"pol_b"}
    with pytest.raises(PermissionError):
        await h.service.attach_policies(
            user_id="usr-bob",
            organization_id="org-1",
            workspace_id="ws-1",
            policy_ids=["pol_a", "pol_b"],
            by="usr-alice",
        )
    assert h.grants.attached == []


@pytest.mark.asyncio
async def test_renewing_keeps_a_carried_policy_at_its_own_scope():
    """The move of the role features carried an organization's "Features of
    owner" org-wide for an invitation pending then: renewing it keeps that grant
    where it is, never moves it to the organization's own scope."""
    from dataclasses import replace

    h = Harness()
    first = (
        await h.invite(
            workspace_id=None, workspace_role=None, org_role="owner", may_grant_owner=True
        )
    ).invitation
    # As the move does: a pending grant at abi:org-1:* listed on the invitation.
    h.grants.live["g-wide"] = ("builtin", "bob@example.com", "pol_org_features", "abi:org-1:*")
    h.store.rows[first.id] = replace(
        first,
        grant_ids=(*first.grant_ids, "g-wide"),
        policy_ids=("pol_org_features",),
    )
    again = await h.invite(
        workspace_id=None,
        workspace_role=None,
        org_role="owner",
        may_grant_owner=True,
        policy_ids=["pol_org_features"],
    )
    assert "g-wide" in again.invitation.grant_ids
    assert h.grants.live["g-wide"][3] == "abi:org-1:*"
    assert not any(
        v[2] == "pol_org_features" and v[3] == "abi:org-1:-" for v in h.grants.live.values()
    )
