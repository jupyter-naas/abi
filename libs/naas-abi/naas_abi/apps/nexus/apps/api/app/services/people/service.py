"""The platform's people: one ``users`` row per person from the moment they are
invited, created or linked by whoever adds them somewhere.

``create_or_link`` makes a person who has no row, in this order:

1. **Authorize** before anything exists: the roles and policies are written as
   IAM pending grants for the email, on behalf of the inviting person, so IAM
   checks that they may attach each one there and hold what it grants (and only
   an owner names an owner). That accepted invitation is the warrant to make the
   account (ADR ``20261118_invitation_provisions_the_account.md``).
2. **Provision** the account at the identity provider, as Nexus.
3. **The IAM user** of the provider's identity ``(issuer, subject)``, as Nexus.
4. **The row**, ``invited``, whose id is that principal id.
5. **Attach** the roles and policies to them, on behalf of the inviting person,
   and withdraw the pending grants: the attachments are the memberships.
6. **Mail** the invitation (never failing the call).

A failure after step 1 takes everything back: the attachments, the row, the
principal, and the provider's account only if this call made it.

A provider whose people are managed there (``provisioning: none``), or a platform
invitation whose inviter may not create accounts at the provider, makes no
account: the row is ``invited`` and **unbound** (a stable id of its own, no
identity), its roles are attached to IAM's user of that id, and the first sign-in
through the provider the row names, with the email verified, binds the row to that
identity (``services/oidc``), which keeps the roles.

An email that already has a row is **linked**: nothing is made, the grants are
attached to that person. The answer never says which of the two happened.
"""

from __future__ import annotations

from collections.abc import Callable, Collection, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from uuid import uuid4

from naas_abi.apps.nexus.apps.api.app.services.iam.names import (
    is_org_container,
    is_workspace_container,
    org_of,
    workspace_of,
)
from naas_abi.apps.nexus.apps.api.app.services.organizations.domain_proof import (
    is_public_mail_domain,
)
from naas_abi.apps.nexus.apps.api.app.services.people.port import (
    MAX_SEARCH,
    MIN_QUERY,
    PROFILE_FIELDS,
    ROLES,
    AccessGateway,
    Actor,
    AlreadyActiveError,
    AlreadyMemberError,
    CreateOrLinkResult,
    EmailTakenError,
    Grant,
    IdentityGateway,
    InvalidPolicyError,
    NewUser,
    NoProviderError,
    OwnerGrantRefusedError,
    PeopleMailer,
    PeopleStorePort,
    Placement,
    PlatformUser,
    ProviderInfo,
    Provisioned,
    ProvisioningRefused,
    UnknownUserError,
    UserStatus,
    Warrant,
)
from naas_abi_core import logger

Clock = Callable[[], datetime]
# The id of a person no provider made yet (``provisioning: none``): IAM's user of
# that id is made on first sight (as for the rows of the old built-in login), and
# the first sign-in links the provider's identity to it.
UNBOUND_PREFIX = "user-"


class _Existing(Exception):  # noqa: N818 - a signal, not an error
    """The person a creation was for has a row already: link it instead."""

    def __init__(self, user: PlatformUser) -> None:
        super().__init__(user.id)
        self.user = user


@dataclass(frozen=True)
class _Step:
    """One attachment a grant asks for: a role, or a customer policy, at a scope."""

    scope: str
    grant: Grant
    role: str | None = None
    policy_id: str | None = None

    @property
    def policy(self) -> str:
        return f"builtin.{self.role}" if self.role is not None else str(self.policy_id)


class PeopleService:
    def __init__(
        self,
        store: PeopleStorePort,
        identity: IdentityGateway,
        access: AccessGateway,
        mailer: PeopleMailer,
        *,
        clock: Clock,
    ) -> None:
        self.store = store
        self.identity = identity
        self.access = access
        self.mailer = mailer
        self._clock = clock

    # =========================================================================
    # Reads
    # =========================================================================

    async def get(self, user_id: str) -> PlatformUser | None:
        return await self.store.get(user_id)

    async def by_email(self, email: str) -> PlatformUser | None:
        return await self.store.by_email(_email(email))

    async def search(
        self, *, q: str, among: Collection[str], limit: int = 10
    ) -> list[PlatformUser]:
        """The people of ``among`` (the ids the caller may see) whose name or email
        contains ``q``. Fewer than ``MIN_QUERY`` characters find nobody, and at most
        ``MAX_SEARCH`` are returned."""
        q = " ".join(q.split())
        if len(q) < MIN_QUERY or not among or limit < 1:
            return []
        return await self.store.search(q, among, min(limit, MAX_SEARCH))

    # =========================================================================
    # Creating or linking
    # =========================================================================

    async def create_or_link(
        self,
        *,
        email: str,
        name: str | None,
        provider: str | None,
        grants: Sequence[Grant],
        by: Actor,
        may_grant_owner: bool = False,
        profile: Mapping[str, str] | None = None,
        organization_id: str | None = None,
    ) -> CreateOrLinkResult:
        """Make the person (``invited``) or link the account the email has, and give
        them ``grants`` on behalf of ``by``. ``organization_id``: the organization
        the profile is written in and the mail names."""
        email = _email(email)
        name = " ".join((name or "").split()) or None
        steps = await self._plan(grants, may_grant_owner)
        kept_profile = _profile(profile)
        existing = await self.store.by_email(email)
        if existing is not None:
            return await self._link(
                existing, steps, by, profile=kept_profile, organization_id=organization_id
            )
        choice = await self._choose(email, provider, organization_id)
        # 1. Authorized before anything exists: IAM accepts the grants on the
        # inviting person's behalf, or nothing is made.
        warrant = (
            await self.access.warrant(
                choice.name, email, [(s.policy, s.scope) for s in steps], by=by.id
            )
            if steps
            else Warrant()
        )
        try:
            provisioned, skipped = await self._provision(
                choice, email, name, by.id, warranted=bool(steps)
            )
        except Exception:
            await self._withdraw(warrant.made)
            raise
        try:
            user = await self._make(
                choice,
                email,
                name,
                provisioned,
                steps,
                by,
                profile=kept_profile,
                organization_id=organization_id,
            )
        except _Existing as taken:
            # The person has a row already: made meanwhile (a sign-in, another
            # invitation), or theirs from before under another email (the
            # provider's identity was known: its principal has a row). Linked as
            # any existing one; an account this call made at the provider is
            # ABI's, whoever's row it is bound to.
            await self._withdraw(warrant.made)
            if provisioned is not None and provisioned.created and provisioned.subject:
                await self.store.record_provisioned(
                    choice.name, provisioned.subject, email, now=self._clock()
                )
                await self.store.commit()
            return await self._link(
                taken.user, steps, by, profile=kept_profile, organization_id=organization_id
            )
        except Exception:
            await self._withdraw(warrant.made)
            raise
        # The roles are attached: the pending grants have done their part.
        await self._withdraw(warrant.made)
        sent = await self._invitation_mail(
            user,
            choice,
            by,
            steps,
            organization_id=organization_id,
            account_made=not skipped,
        )
        return CreateOrLinkResult(
            user=user,
            created=True,
            provisioned=bool(provisioned and provisioned.created),
            sign_in_email_sent=sent,
            warning=provisioned.warning if provisioned else None,
            provisioning_skipped=skipped,
        )

    async def _make(
        self,
        choice: ProviderInfo,
        email: str,
        name: str | None,
        provisioned: Provisioned | None,
        steps: Sequence[_Step],
        by: Actor,
        *,
        profile: Mapping[str, str],
        organization_id: str | None,
    ) -> PlatformUser:
        """Steps 3 to 5, taken back whole when one fails."""
        subject = provisioned.subject if provisioned is not None else None
        made_account = bool(provisioned and provisioned.created and subject)
        principal_id: str | None = None
        user: PlatformUser | None = None
        added: list[_Step] = []
        try:
            if subject:
                principal_id = await self.access.ensure_principal(
                    choice.issuer, subject, provider=choice.name, email=email, name=name
                )
                known = await self.store.get(principal_id)
                if known is not None:
                    # They signed in before with another (or no verified) email.
                    raise _Existing(known)
            user_id = principal_id or f"{UNBOUND_PREFIX}{uuid4().hex}"
            now = self._clock()
            if made_account and subject:
                # Only an account ABI made is changed or deleted at the provider
                # with the person's Nexus account (services/accounts).
                await self.store.record_provisioned(choice.name, subject, email, now=now)
            user = await self.store.add(
                NewUser(
                    id=user_id,
                    email=email,
                    name=name or email.split("@", 1)[0],
                    provider=choice.name,
                    principal_id=principal_id,
                    issuer=choice.issuer if subject else None,
                    subject=subject,
                ),
                now=now,
            )
            if organization_id and profile:
                await self.store.write_profile(organization_id, user.id, profile)
            # Committed before IAM attaches: a row IAM vouches for by asking Nexus.
            await self.store.commit()
            await self._apply(user.id, steps, by, added=added)
        except _Existing:
            raise
        except EmailTakenError as exc:
            await self.store.rollback()
            found = await self.store.by_email(email)
            if found is None and principal_id is not None:
                found = await self.store.get(principal_id)
            if found is None:
                raise
            raise _Existing(found) from exc
        except Exception:
            await self._undo(
                user,
                added,
                principal_id=principal_id,
                provider=choice.name,
                subject=subject if made_account else None,
            )
            raise
        return user

    async def _undo(
        self,
        user: PlatformUser | None,
        added: Sequence[_Step],
        *,
        principal_id: str | None,
        provider: str,
        subject: str | None,
    ) -> None:
        """Take back what a failed creation made: the attachments, the provider's
        account (only one this call made: ``subject``), the principal, the row."""
        if user is not None:
            await self._take_back(user.id, added)
        try:
            await self.store.rollback()
        except Exception as exc:  # noqa: BLE001 - the rest is still taken back
            logger.warning(f"Rolling back a failed invitation failed: {exc}")
        if subject is not None:
            try:
                await self.identity.delete(provider, subject)
                await self.store.forget_provisioned(provider, subject)
            except Exception as exc:  # noqa: BLE001 - logged, the rest goes on
                logger.warning(f"The account {subject} at {provider} was not deleted: {exc}")
        if principal_id is not None and subject is not None:
            # A principal of an identity that existed before stays: it is the
            # person's, and their next sign-in finds it.
            await self.access.discard_principal(principal_id)
        if user is not None:
            try:
                await self.store.remove(user.id)
                await self.store.commit()
            except Exception as exc:  # noqa: BLE001 - logged
                logger.warning(f"The row of a failed invitation ({user.id}) stays: {exc}")

    async def _provision(
        self,
        choice: ProviderInfo,
        email: str,
        name: str | None,
        by: str,
        *,
        warranted: bool,
    ) -> tuple[Provisioned | None, bool]:
        """``(what the provider made, whether provisioning was withheld)``. With a
        warrant (grants IAM accepted for the inviting person) the account is made as
        Nexus; without one (a platform invitation, no role) only on behalf of the
        inviting person, whose own right IAM decides: refused, nothing is made."""
        if choice.managed_in_provider:
            return None, False
        if warranted:
            return await self.identity.provision(choice, email, name), False
        try:
            return await self.identity.provision(choice, email, name, by=by), False
        except ProvisioningRefused:
            return None, True

    async def _link(
        self,
        user: PlatformUser,
        steps: Sequence[_Step],
        by: Actor,
        *,
        profile: Mapping[str, str],
        organization_id: str | None,
    ) -> CreateOrLinkResult:
        await self._apply(user.id, steps, by)
        # The profile is the inviting organization's: written only with a grant
        # IAM accepted there, never about someone the call gave nothing.
        if organization_id and profile and steps:
            await self.store.write_profile(organization_id, user.id, profile)
            await self.store.commit()
        sent = await self._notify(user, by, steps, organization_id=organization_id)
        return CreateOrLinkResult(
            user=user, created=False, provisioned=False, sign_in_email_sent=sent, warning=None
        )

    # =========================================================================
    # Adding someone who exists
    # =========================================================================

    async def add_existing(
        self,
        *,
        user_id: str,
        grants: Sequence[Grant],
        by: Actor,
        may_grant_owner: bool = False,
    ) -> PlatformUser:
        """Give an existing person ``grants`` on behalf of ``by`` and tell them."""
        user = await self.store.get(user_id)
        if user is None:
            raise UnknownUserError(user_id)
        steps = await self._plan(grants, may_grant_owner)
        await self._apply(user.id, steps, by)
        await self._notify(user, by, steps, organization_id=None)
        return user

    async def _plan(self, grants: Sequence[Grant], may_grant_owner: bool) -> list[_Step]:
        """The attachments the grants ask for, checked before anything is asked of
        IAM: known roles, customer policies only, and ``owner`` only from an owner."""
        steps: list[_Step] = []
        for grant in grants:
            if grant.scope not in ("organization", "workspace") or not grant.scope_id:
                raise ValueError("A grant names an organization or a workspace")
            if grant.role is not None and grant.role not in ROLES:
                raise ValueError(f"Unknown role {grant.role!r}")
            if grant.role is None and not grant.policy_ids:
                raise ValueError("A grant names a role or policies")
            if grant.role == "owner" and not may_grant_owner:
                raise OwnerGrantRefusedError("Only an owner can make an owner")
            policies = _policies(grant.policy_ids)
            try:
                scope = await self.access.scope(grant)
            except LookupError as exc:
                raise ValueError(f"Unknown {grant.scope} {grant.scope_id}") from exc
            steps += [_Step(scope, grant, policy_id=p) for p in policies]
            if grant.role is not None:
                steps.append(_Step(scope, grant, role=grant.role))
        return steps

    async def _apply(
        self, user_id: str, steps: Sequence[_Step], by: Actor, *, added: list[_Step] | None = None
    ) -> None:
        """Attach the steps on behalf of ``by``: the policies first, then the roles,
        so a refused one leaves no membership behind. All or nothing."""
        if not steps:
            return
        held = await self.access.roles_of(user_id)
        for step in steps:
            if step.role is not None and step.scope in held:
                raise AlreadyMemberError(user_id, step.scope)
        made: list[_Step] = [] if added is None else added
        try:
            for step in sorted(steps, key=lambda s: s.role is not None):
                if step.role is not None:
                    await self.access.grant_role(user_id, step.role, step.scope, by=by.id)
                    made.append(step)
                elif await self.access.attach(user_id, step.policy, step.scope, by=by.id):
                    made.append(step)
        except Exception:
            if added is None:  # the caller takes back what ``added`` lists
                await self._take_back(user_id, made)
            raise

    async def _take_back(self, user_id: str, made: Sequence[_Step]) -> None:
        for step in reversed(made):
            try:
                if step.role is not None:
                    await self.access.revoke_role(user_id, step.scope)
                else:
                    await self.access.detach(user_id, step.policy, step.scope)
            except Exception as exc:  # noqa: BLE001 - logged, the rest goes on
                logger.warning(f"Could not take back {step.policy} at {step.scope}: {exc}")

    async def _withdraw(self, grant_ids: Sequence[str]) -> None:
        if not grant_ids:
            return
        try:
            await self.access.withdraw(grant_ids)
        except Exception as exc:  # noqa: BLE001 - a grant already gone is gone
            logger.warning(f"Could not withdraw pending grants {list(grant_ids)}: {exc}")

    # =========================================================================
    # Mail, resending, activation
    # =========================================================================

    async def resend(self, *, user_id: str, by: Actor) -> bool:
        """Mail the invitation again to someone who has not signed in yet
        (``AlreadyActiveError`` for someone who has). True when it was sent."""
        user = await self.store.get(user_id)
        if user is None:
            raise UnknownUserError(user_id)
        if user.status != UserStatus.INVITED:
            raise AlreadyActiveError(user_id)
        choice = await self._provider_of(user)
        roles = await self.access.roles_of(user.id)
        placement = await self._placement_of_roles(roles)
        return await self._send_invitation(
            user, choice, by, placement, account_made=_has_account(user)
        )

    async def activate(self, user_id: str) -> None:
        """The person signed in for the first time: ``invited`` → ``active``."""
        if await self.store.activate(user_id, now=self._clock()):
            await self.store.commit()

    async def _notify(
        self,
        user: PlatformUser,
        by: Actor,
        steps: Sequence[_Step],
        *,
        organization_id: str | None,
    ) -> bool:
        """Someone active hears where they were added; someone still invited gets
        the invitation again (they have not signed in)."""
        if user.status == UserStatus.INVITED:
            try:
                choice = await self._provider_of(user)
            except NoProviderError:
                return False
            return await self._invitation_mail(
                user,
                choice,
                by,
                steps,
                organization_id=organization_id,
                account_made=_has_account(user),
            )
        placement = await self._placement(steps, organization_id)
        try:
            return await self.mailer.added(
                to_email=user.email, inviter_name=_name(by), placement=placement
            )
        except Exception as exc:  # noqa: BLE001 - the membership stands
            logger.warning(f"The notice to {user.email} failed: {exc}")
            return False

    async def _invitation_mail(
        self,
        user: PlatformUser,
        choice: ProviderInfo,
        by: Actor,
        steps: Sequence[_Step],
        *,
        organization_id: str | None,
        account_made: bool,
    ) -> bool:
        placement = await self._placement(steps, organization_id)
        return await self._send_invitation(user, choice, by, placement, account_made=account_made)

    async def _send_invitation(
        self,
        user: PlatformUser,
        choice: ProviderInfo,
        by: Actor,
        placement: Placement,
        *,
        account_made: bool,
    ) -> bool:
        try:
            return await self.mailer.invitation(
                to_email=user.email,
                provider=choice,
                inviter_name=_name(by),
                placement=placement,
                account_made=account_made,
            )
        except Exception as exc:  # noqa: BLE001 - the person exists; the admin may resend
            logger.warning(f"Invitation email to {user.email} failed: {exc}")
            return False

    async def _placement(self, steps: Sequence[_Step], organization_id: str | None) -> Placement:
        org = next((s.grant for s in steps if s.grant.scope == "organization"), None)
        ws = next((s.grant for s in steps if s.grant.scope == "workspace"), None)
        org_id = org.scope_id if org is not None else organization_id
        org_name, ws_name = await self.store.names(org_id, ws.scope_id if ws else None)
        return Placement(
            organization_name=org_name,
            organization_role=_role_of(steps, org),
            workspace_name=ws_name,
            workspace_role=_role_of(steps, ws),
        )

    async def _placement_of_roles(self, roles: Mapping[str, str]) -> Placement:
        org = next(((s, r) for s, r in roles.items() if is_org_container(s)), None)
        ws = next(((s, r) for s, r in roles.items() if is_workspace_container(s)), None)
        org_name, ws_name = await self.store.names(
            org_of(org[0]) if org else (org_of(ws[0]) if ws else None),
            workspace_of(ws[0]) if ws else None,
        )
        return Placement(
            organization_name=org_name,
            organization_role=org[1] if org else None,
            workspace_name=ws_name,
            workspace_role=ws[1] if ws else None,
        )

    # =========================================================================
    # Providers
    # =========================================================================

    async def _choose(
        self, email: str, requested: str | None, organization_id: str | None
    ) -> ProviderInfo:
        """The one asked for, else the one the organization's verified domain of the
        email routes to, else the default, else the only one."""
        known, default = await self.identity.providers()
        by_name = {p.name: p for p in known}
        if requested:
            found = by_name.get(requested)
            if found is None:
                raise NoProviderError(f"{requested!r} is not an identity provider")
            return found
        domain = email.rsplit("@", 1)[-1]
        routed = (
            None
            if is_public_mail_domain(domain)
            else await self.store.provider_for_domain(domain, organization_id)
        )
        for name in (routed, default):
            if name and name in by_name:
                return by_name[name]
        if len(known) == 1:
            return known[0]
        raise NoProviderError(
            "Name the identity provider to invite through"
            if known
            else "No identity provider is configured"
        )

    async def _provider_of(self, user: PlatformUser) -> ProviderInfo:
        known, default = await self.identity.providers()
        name = user.provider or default
        found = next((p for p in known if p.name == name), None)
        if found is None:
            raise NoProviderError(f"{name!r} is not an identity provider")
        return found


def _email(email: str) -> str:
    email = email.strip().lower()
    local, _, domain = email.partition("@")
    if not local or not domain or "@" in domain:
        raise ValueError("Enter a valid email address")
    return email


def _has_account(user: PlatformUser) -> bool:
    """Whether the provider has an account for someone invited: one the invitation
    made or found (the row is bound). An unbound row has none, unless the provider
    manages its people (the mail then says so on its own)."""
    return not user.id.startswith(UNBOUND_PREFIX)


def _name(by: Actor) -> str | None:
    return getattr(by, "name", None) or None


def _profile(profile: Mapping[str, str] | None) -> dict[str, str]:
    return {
        key: value
        for key, value in (profile or {}).items()
        if key in PROFILE_FIELDS and value is not None
    }


def _policies(policy_ids: Sequence[str]) -> list[str]:
    """Customer policies (``pol_…``), once each: a role is chosen as the role."""
    found = list(dict.fromkeys(str(p).strip() for p in policy_ids if str(p).strip()))
    managed = [p for p in found if not p.startswith("pol_")]
    if managed:
        raise InvalidPolicyError(
            f"Only customer policies (pol_…) are attached this way, not {', '.join(managed)}: "
            "the role is chosen as the role"
        )
    return found


def _role_of(steps: Sequence[_Step], grant: Grant | None) -> str | None:
    if grant is None:
        return None
    return next((s.role for s in steps if s.grant == grant and s.role is not None), None)
