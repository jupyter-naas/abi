"""Invitations: an email is invited to an organization and/or a workspace.

The invited person may not exist yet, so nothing is attached to an account:

1. IAM keeps **pending grants**, the roles as ``builtin.<role>`` policies at the
   org's or workspace's scope, and the policies the invitation carries beside
   them (``policy_ids``: no role brings a feature, so a workspace's "Features of
   member" comes this way) at its workspace, else its org, for that email on that
   provider. They attach to whoever first signs in through the provider with
   that email verified (``IAMService.claim_pending_grants``, run by the engine's
   identity service), and to nobody else.
2. The **provisioning** port makes the person exist at the provider (the
   built-in IdP's admin app, Zitadel, Keycloak), unless the provider's people
   are managed in the provider (``provisioning: none``): then the grants alone
   wait for them there.
3. Nexus keeps the **invitation** (who invited whom, where, as what) to list,
   resend and revoke it, and marks it accepted once the person signs in (``claim``).

The service never decides whether the inviting person may invite: the route
did, before it called, and IAM's checks of the grants it writes run
as ``api`` for nobody (``GrantsGateway``).
"""

from __future__ import annotations

from collections.abc import Callable, Collection, Iterable, Mapping, Sequence
from datetime import datetime
from uuid import uuid4

from naas_abi.apps.nexus.apps.api.app.services.invites.names import (
    org_scope,
    role_policy,
    workspace_scope,
)
from naas_abi.apps.nexus.apps.api.app.services.invites.port import (
    PROFILE_FIELDS,
    Directory,
    DirectoryGateway,
    GrantMade,
    GrantsGateway,
    IdpBindingView,
    InvalidPolicyError,
    Invitation,
    InvitationMail,
    InvitationMailer,
    InvitationNotFoundError,
    InvitationPersistencePort,
    InviteOutcome,
    NoProviderError,
    OrgInvitationExistsError,
    OwnerGrantRefusedError,
    ProviderChoice,
    Provisioned,
    ProvisioningRefused,
)
from naas_abi_core import logger

Clock = Callable[[], datetime]
SignInUrl = Callable[[str, str], str]


class InvitationService:
    def __init__(
        self,
        persistence: InvitationPersistencePort,
        directory: DirectoryGateway,
        grants: GrantsGateway,
        mailer: InvitationMailer,
        *,
        sign_in_url: SignInUrl,
        clock: Clock,
    ) -> None:
        self.persistence = persistence
        self.directory = directory
        self.grants = grants
        self.mailer = mailer
        self._sign_in_url = sign_in_url
        self._clock = clock

    # =========================================================================
    # Providers
    # =========================================================================

    async def providers(self) -> Directory:
        return await self.directory.directory()

    async def choose(
        self, email: str, requested: str | None, organization_id: str | None
    ) -> ProviderChoice:
        """The provider an invitation goes through: the one asked for, else the
        one the organization's verified domain of the email's routes to, else
        the default, else the only one. ``NoProviderError`` when there is none."""
        known = await self.directory.directory()
        if requested:
            found = known.get(requested)
            if found is None:
                raise NoProviderError(f"{requested!r} is not an identity provider")
            return found
        domain = email.rsplit("@", 1)[-1]
        routed = await self.persistence.provider_for_domain(domain, organization_id)
        for name in (routed, known.default):
            found = known.get(name) if name else None
            if found is not None:
                return found
        if len(known.providers) == 1:
            return known.providers[0]
        raise NoProviderError(
            "Name the identity provider to invite through"
            if known.providers
            else "No identity provider is configured"
        )

    # =========================================================================
    # Inviting
    # =========================================================================

    async def invite(
        self,
        *,
        email: str,
        name: str | None,
        provider: str | None,
        organization_id: str | None,
        org_role: str | None,
        workspace_id: str | None,
        workspace_role: str | None,
        invited_by: str | None,
        inviter_name: str | None = None,
        organization_name: str | None = None,
        workspace_name: str | None = None,
        may_grant_owner: bool = False,
        may_renew_org_invitation: bool = False,
        profile: Mapping[str, str] | None = None,
        policy_ids: Sequence[str] = (),
    ) -> InviteOutcome:
        """Invite ``email`` and send the invitation. Inviting again someone
        already invited here renews the invitation (new roles, a new email).

        ``may_grant_owner``: the inviting person is an owner. The grants are
        written as Nexus's own, so IAM's rule that only an owner makes an owner
        cannot see who asked: the route says it, and nobody else gets ``owner``.

        ``may_renew_org_invitation``: the inviting person administers the
        organization. A workspace-only invitation of someone already invited to the
        organization *and* this workspace would rewrite that invitation without its
        organization role: it is refused unless they may, and then the organization
        role is kept.

        ``profile``: what the organization sets about the person (``PROFILE_FIELDS``),
        written as their profile in the organization when they sign in and their
        account exists; with a renewal, it replaces the one kept.

        ``policy_ids``: customer policies (``pol_…``) the person gets beside the
        roles, at the workspace (else the organization), each a pending grant the
        inviting person must be able to attach there and hold. A renewal carries
        the ones it names, and the earlier ones it drops are withdrawn.

        The provider makes the person exist only for an inviting user IAM lets
        create accounts there (``identity:ProvisionUser``), or for an address on a
        domain the organization verified and routed to that provider. Otherwise the
        grants wait for the person's sign-in, as with a provider that manages its people.
        """
        email = email.lower().strip()
        if org_role is None and workspace_role is None:
            raise ValueError("An invitation names a role in an organization or a workspace")
        choice = await self.choose(email, provider, organization_id)
        existing = await self.persistence.find_pending(
            email=email,
            provider=choice.name,
            organization_id=organization_id,
            workspace_id=workspace_id,
        )
        if existing is not None and existing.org_role is not None and org_role is None:
            if not may_renew_org_invitation:
                raise OrgInvitationExistsError(
                    "This person is invited to the organization and this workspace: "
                    "an organization administrator renews that invitation"
                )
            org_role = existing.org_role
        if "owner" in (org_role, workspace_role) and not may_grant_owner:
            raise OwnerGrantRefusedError("Only an owner can invite an owner")
        carried = _policies(policy_ids)
        now = self._clock()
        grants = [
            (role_policy(role), scope)
            for role, scope in _scopes(organization_id, org_role, workspace_id, workspace_role)
        ]
        grants += [
            (policy_id, policy_scope(organization_id, workspace_id)) for policy_id in carried
        ]
        elsewhere = await self._held_elsewhere(
            email, choice.name, existing.id if existing else None
        )
        made = await self._grant(choice.name, email, grants, by=invited_by)
        grant_ids = [g.id for g in made]
        try:
            provisioned, skipped = await self._provision(
                choice, email, name, organization_id, invited_by
            )
            if existing is None:
                invitation = await self.persistence.add(
                    Invitation(
                        id=str(uuid4()),
                        email=email,
                        provider=choice.name,
                        organization_id=organization_id,
                        org_role=org_role,
                        workspace_id=workspace_id,
                        workspace_role=workspace_role,
                        invited_by=invited_by,
                        grant_ids=tuple(grant_ids),
                        policy_ids=carried,
                        profile={
                            key: value
                            for key, value in (profile or {}).items()
                            if key in PROFILE_FIELDS and value is not None
                        },
                    ),
                    now=now,
                )
            else:
                invitation = await self.persistence.update(
                    existing.id,
                    org_role=org_role,
                    workspace_role=workspace_role,
                    grant_ids=grant_ids,
                    policy_ids=carried,
                    invited_by=invited_by,
                    now=now,
                    profile={
                        key: value
                        for key, value in profile.items()
                        if key in PROFILE_FIELDS and value is not None
                    }
                    if profile
                    else None,
                )
            await self.persistence.commit()
        except Exception:
            # Nothing was made for this call: take back the grants it made, and
            # only those (another invitation, or the one renewed, may hold the
            # rest), so IAM never holds a grant no invitation lists.
            await self.persistence.rollback()
            await self._revoke(
                [g.id for g in made if g.created],
                keep={*elsewhere, *(existing.grant_ids if existing else ())},
            )
            raise
        if existing is not None:
            # The roles may have changed: what the old ones granted goes.
            await self._revoke(existing.grant_ids, keep={*grant_ids, *elsewhere})
        sent = await self._mail(
            invitation,
            choice,
            inviter_name=inviter_name,
            organization_name=organization_name,
            workspace_name=workspace_name,
        )
        return InviteOutcome(
            invitation=invitation,
            provider=choice,
            user_created=bool(provisioned and provisioned.created),
            sign_in_email_sent=sent,
            renewed=existing is not None,
            warning=provisioned.warning if provisioned else None,
            provisioning_skipped=skipped,
        )

    async def _provision(
        self,
        choice: ProviderChoice,
        email: str,
        name: str | None,
        organization_id: str | None,
        invited_by: str | None,
    ) -> tuple[Provisioned | None, bool]:
        """``(what the provider made, whether provisioning was withheld)``."""
        if choice.managed_in_provider:
            return None, False
        routed = await self.persistence.provider_for_domain(
            email.rsplit("@", 1)[-1], organization_id
        )
        if routed == choice.name or invited_by is None:
            # An address the organization proved it controls (or the system's own
            # call): Nexus's own, for nobody.
            return await self.directory.provision(choice, email, name), False
        try:
            return await self.directory.provision(choice, email, name, by=invited_by), False
        except ProvisioningRefused:
            return None, True

    async def _held_elsewhere(self, email: str, provider: str, except_id: str | None) -> set[str]:
        """The pending grants other invitations of this person rely on: IAM keeps
        one grant per role and scope, so an invitation to a workspace and one to
        another workspace of the same org share the org-level one."""
        others = await self.persistence.pending_for(email=email, provider=provider)
        return {g for i in others if i.id != except_id for g in i.grant_ids}

    async def _grant(
        self,
        provider: str,
        email: str,
        grants: list[tuple[str, str]],
        *,
        by: str | None = None,
    ) -> list[GrantMade]:
        """``(policy, scope)`` pending grants, as ``by``, the inviting person: IAM
        refuses a role or a policy they may not attach or that grants more than
        they hold (``GrantNotHeldError``)."""
        made: list[GrantMade] = []
        try:
            for policy_id, scope in grants:
                made.append(await self.grants.grant(provider, email, policy_id, scope, by=by))
        except Exception:
            await self._revoke([g.id for g in made if g.created])
            raise
        return made

    async def _revoke(self, ids: Iterable[str], *, keep: Collection[str] = ()) -> None:
        for grant_id in ids:
            if grant_id in keep:
                continue
            try:
                await self.grants.revoke(grant_id)
            except Exception as exc:  # noqa: BLE001 - a grant already gone is gone
                logger.warning(f"Could not revoke pending grant {grant_id}: {exc}")

    async def _mail(
        self,
        invitation: Invitation,
        choice: ProviderChoice,
        *,
        inviter_name: str | None,
        organization_name: str | None,
        workspace_name: str | None,
    ) -> bool:
        try:
            return await self.mailer.send(
                InvitationMail(
                    to_email=invitation.email,
                    provider=choice,
                    inviter_name=inviter_name,
                    organization_name=organization_name,
                    organization_role=invitation.org_role,
                    workspace_name=workspace_name,
                    workspace_role=invitation.workspace_role,
                    sign_in_url=self._sign_in_url(invitation.email, choice.name),
                    managed_in_provider=choice.managed_in_provider,
                )
            )
        except Exception as exc:  # noqa: BLE001 - the invitation stands; the admin may resend
            logger.warning(f"Invitation email to {invitation.email} failed: {exc}")
            return False

    async def attach_policies(
        self,
        *,
        user_id: str,
        organization_id: str | None,
        workspace_id: str | None,
        policy_ids: Sequence[str],
        by: str | None,
    ) -> tuple[str, ...]:
        """For someone who has an account already (added directly, not invited):
        attach the policies an invitation would carry, at the workspace, else the
        organization, as ``by`` (IAM checks the attachment and what it grants).
        Returns the policies attached."""
        carried = _policies(policy_ids)
        scope = policy_scope(organization_id, workspace_id)
        for policy_id in carried:
            await self.grants.attach(user_id, policy_id, scope, by=by)
        return carried

    # =========================================================================
    # Listing, resending, revoking
    # =========================================================================

    async def pending(
        self, *, organization_id: str | None = None, workspace_id: str | None = None
    ) -> list[Invitation]:
        return await self.persistence.list(
            organization_id=organization_id, workspace_id=workspace_id, status="pending"
        )

    async def get(self, invitation_id: str) -> Invitation:
        invitation = await self.persistence.get(invitation_id)
        if invitation is None:
            raise InvitationNotFoundError(invitation_id)
        return invitation

    async def resend(
        self,
        invitation_id: str,
        *,
        inviter_name: str | None = None,
        organization_name: str | None = None,
        workspace_name: str | None = None,
    ) -> bool:
        invitation = await self.get(invitation_id)
        if invitation.status != "pending":
            raise InvitationNotFoundError(invitation_id)
        known = await self.directory.directory()
        choice = known.get(invitation.provider)
        if choice is None:
            raise NoProviderError(f"{invitation.provider!r} is not an identity provider")
        return await self._mail(
            invitation,
            choice,
            inviter_name=inviter_name,
            organization_name=organization_name,
            workspace_name=workspace_name,
        )

    async def revoke(self, invitation_id: str) -> Invitation:
        """Withdraw an invitation and what it granted. A person who already
        signed in keeps their membership: that is removed as any member is."""
        invitation = await self.get(invitation_id)
        if invitation.status != "pending":
            raise InvitationNotFoundError(invitation_id)
        # What another invitation of this person still lists stays.
        elsewhere = await self._held_elsewhere(invitation.email, invitation.provider, invitation.id)
        await self._revoke(invitation.grant_ids, keep=elsewhere)
        await self.persistence.mark_revoked(invitation.id, now=self._clock())
        await self.persistence.commit()
        return invitation

    # =========================================================================
    # The first sign-in
    # =========================================================================

    async def claim(self, *, user_id: str, email: str, provider: str) -> list[Invitation]:
        """Mark the invitations of ``email`` on ``provider`` accepted. The memberships
        are IAM's: the engine claimed the pending grants at the sign-in, and those
        attachments are the roles. The caller vouches that the provider verified the
        address (IAM's grants wait for the same proof)."""
        accepted: list[Invitation] = []
        for invitation in await self.persistence.pending_for(
            email=email.lower().strip(), provider=provider
        ):
            now = self._clock()
            if not await self.persistence.mark_accepted(invitation.id, user_id=user_id, now=now):
                continue  # another sign-in of this person took it
            accepted.append(invitation)
        if accepted:
            await self.persistence.commit()
        return accepted

    # =========================================================================
    # IdP group bindings
    # =========================================================================

    async def bind_group(
        self, *, provider: str, group: str, role: str, scope: str, by: str | None = None
    ) -> None:
        """As ``by``: IAM checks that they may attach the role and hold what it grants."""
        known = await self.directory.directory()
        if known.get(provider) is None:
            raise NoProviderError(f"{provider!r} is not an identity provider")
        await self.grants.bind(provider, group.strip(), role_policy(role), scope, by=by)

    async def unbind_group(self, *, provider: str, group: str, role: str, scope: str) -> bool:
        return await self.grants.unbind(provider, group.strip(), role_policy(role), scope)

    async def bindings(self, scopes: list[str]) -> list[IdpBindingView]:
        return await self.grants.bindings(scopes)

    @staticmethod
    def org_scope(organization_id: str) -> str:
        return org_scope(organization_id)

    @staticmethod
    def workspace_scope(organization_id: str | None, workspace_id: str) -> str:
        return workspace_scope(organization_id, workspace_id)


def policy_scope(organization_id: str | None, workspace_id: str | None) -> str:
    """Where an invitation's policies attach: its workspace, else its organization."""
    if workspace_id is not None:
        return workspace_scope(organization_id, workspace_id)
    if organization_id is None:
        raise ValueError("An invitation's policies need an organization or a workspace")
    return org_scope(organization_id)


def _policies(policy_ids: Sequence[str]) -> tuple[str, ...]:
    """The customer policies an invitation carries, in order, once each."""
    found = tuple(dict.fromkeys(str(p).strip() for p in policy_ids if str(p).strip()))
    managed = [p for p in found if not p.startswith("pol_")]
    if managed:
        raise InvalidPolicyError(
            f"An invitation carries customer policies (pol_…), not {', '.join(managed)}: "
            "the role is chosen as the role"
        )
    return found


def _scopes(
    organization_id: str | None,
    org_role: str | None,
    workspace_id: str | None,
    workspace_role: str | None,
) -> list[tuple[str, str]]:
    found: list[tuple[str, str]] = []
    if org_role is not None:
        if organization_id is None:
            raise ValueError("An organization role needs an organization")
        found.append((org_role, org_scope(organization_id)))
    if workspace_role is not None:
        if workspace_id is None:
            raise ValueError("A workspace role needs a workspace")
        found.append((workspace_role, workspace_scope(organization_id, workspace_id)))
    return found
