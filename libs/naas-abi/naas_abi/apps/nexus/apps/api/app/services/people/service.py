"""The platform's people: one ``users`` row per person from the moment they are
invited, created or linked by whoever adds them somewhere.

``create_or_link`` makes a person who has no row, in this order:

1. **Authorize** before anything exists: IAM checks, as the inviting person, that
   they may put someone in each group the grant names and give the level (#1589:
   ``Grant`` is a level, the organization's and the workspaces' groups, and
   capability groups). That accepted check is the warrant to make the account
   (ADR ``20261118_invitation_provisions_the_account.md``).
2. **Provision** the account at the identity provider, as Nexus.
3. **The IAM user** of the provider's identity ``(issuer, subject)``, as Nexus.
4. **The row**, ``invited``, whose id is that principal id.
5. **Join** the groups and set the level (``AccessGateway``): the memberships.
6. **Mail** the invitation (never failing the call).

A failure after step 1 takes everything back: the groups joined, the level, the
row, the principal, and the provider's account only if this call made it.

A provider whose people are managed there (``provisioning: none``), or a platform
invitation whose inviter may not create accounts at the provider, makes no
account: the row is ``invited`` and **unbound** (a stable id of its own, no
identity), its groups hold IAM's user of that id, and the first sign-in
through the provider the row names, with the email verified, binds the row to that
identity (``services/oidc``), which keeps the roles.

An email that already has a row is **linked**: nothing is made, the grants are
given to that person. The answer never says which of the two happened.
"""

from __future__ import annotations

from collections.abc import Callable, Collection, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Any
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
    ADMINS,
    CAPABILITY,
    LEVELS,
    MAX_SEARCH,
    MEMBERSHIP,
    MIN_QUERY,
    PROFILE_FIELDS,
    AccessGateway,
    Actor,
    AddedUser,
    AlreadyActiveError,
    AlreadyMemberError,
    CreateOrLinkResult,
    EmailTakenError,
    Grant,
    IdentityGateway,
    Level,
    NewUser,
    NoProviderError,
    PeopleMailer,
    PeopleStorePort,
    Placement,
    PlatformUser,
    ProviderInfo,
    Provisioned,
    ProvisioningRefused,
    Seat,
    UnknownUserError,
    UserStatus,
    WorkspaceAccess,
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
class _Access:
    """What a grant asks for: the seats (groups by container), the level, and where
    the grant puts the person (the containers they work in from now on, for
    ``AlreadyMemberError``), with the organization and workspaces for the mail."""

    grant: Grant
    seats: tuple[Seat, ...]
    places: tuple[str, ...]
    organization: str | None

    def level_after(self, current: Level | None) -> Level | None:
        """The level the person has afterwards: the one asked for; a Member for a
        workspace admin (a workspace admin is a Member); a Member for someone with no
        level who joins a workspace; else theirs."""
        if self.grant.level is not None:
            return self.grant.level
        if any(w.admin for w in self.grant.workspaces) and current != "member":
            return "member"
        if current is None and self.grant.workspaces:
            return "member"
        return current

    @property
    def containers(self) -> list[str]:
        return [s.container for s in self.seats if s.kind != CAPABILITY]


# What a change did, to take it back: ``("join", seat)``, ``("level", level before)``.
_Done = tuple[str, Any]

# The order seats are joined in: where first (the person's tie), then what they
# administer, then capabilities (which need the tie).
_ORDER = {MEMBERSHIP: 0, ADMINS: 1, CAPABILITY: 2}


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
        grant: Grant | None,
        by: Actor,
        profile: Mapping[str, str] | None = None,
        organization_id: str | None = None,
    ) -> CreateOrLinkResult:
        """Make the person (``invited``) or link the account the email has, and give
        them ``grant`` (their level and groups) on behalf of ``by``. None: an
        account with no access (a platform invitation). ``organization_id``: the
        organization the profile is written in and the mail names (the grant's by
        default)."""
        email = _email(email)
        name = " ".join((name or "").split()) or None
        access = await self._plan(grant)
        if organization_id is None and access is not None:
            organization_id = access.organization
        kept_profile = _profile(profile)
        if provider:
            # A provider asked for is checked whether the email has an account or not:
            # an unknown one is refused the same way, so the answer tells nothing.
            known, _default = await self.identity.providers()
            if provider not in {p.name for p in known}:
                raise NoProviderError(f"{provider!r} is not an identity provider")
        existing = await self.store.by_email(email)
        if existing is not None:
            return await self._link(
                existing, access, by, profile=kept_profile, organization_id=organization_id
            )
        choice = await self._choose(email, provider, organization_id)
        # 1. Authorized before anything exists: IAM accepts, as the inviting person,
        # every group and the level, or nothing is made.
        if access is not None:
            await self.access.check(
                None,
                access.seats,
                level=access.level_after(None),
                by=by.id,
                organization_id=access.organization,
            )
        provisioned, skipped = await self._provision(
            choice, email, name, by.id, warranted=access is not None
        )
        try:
            user = await self._make(
                choice,
                email,
                name,
                provisioned,
                access,
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
            if provisioned is not None and provisioned.created and provisioned.subject:
                await self.store.record_provisioned(
                    choice.name, provisioned.subject, email, now=self._clock()
                )
                await self.store.commit()
            return await self._link(
                taken.user, access, by, profile=kept_profile, organization_id=organization_id
            )
        sent = await self._invitation_mail(
            user,
            choice,
            by,
            access,
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
            provider=choice,
        )

    async def _make(
        self,
        choice: ProviderInfo,
        email: str,
        name: str | None,
        provisioned: Provisioned | None,
        access: _Access | None,
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
        done: list[_Done] = []
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
            # As for a link: an organization's profile only with a grant it gave.
            if organization_id and profile and access is not None:
                await self.store.write_profile(organization_id, user.id, profile)
            # Committed before IAM is changed: a row IAM vouches for by asking Nexus.
            await self.store.commit()
            if access is not None:
                await self._apply(user.id, access, by, done=done)
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
                done,
                principal_id=principal_id,
                provider=choice.name,
                subject=subject if made_account else None,
            )
            raise
        return user

    async def _undo(
        self,
        user: PlatformUser | None,
        done: Sequence[_Done],
        *,
        principal_id: str | None,
        provider: str,
        subject: str | None,
    ) -> None:
        """Take back what a failed creation made: the groups and the level, the
        provider's account (only one this call made: ``subject``), the principal,
        the row."""
        if user is not None:
            await self._take_back(user.id, done)
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
        warrant (a grant IAM accepted for the inviting person) the account is made
        as Nexus; without one (a platform invitation, no access) only on behalf of
        the inviting person, whose own right IAM decides: refused, nothing is made."""
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
        access: _Access | None,
        by: Actor,
        *,
        profile: Mapping[str, str],
        organization_id: str | None,
    ) -> CreateOrLinkResult:
        if access is not None:
            await self._apply(user.id, access, by)
        # Someone who exists has a profile of their own in the organization: a link
        # writes it only with an organization grant IAM accepted (who may make an
        # org admin or put someone in the organization's people may edit them),
        # never with workspaces alone (a workspace admin cannot rewrite an org
        # member's profile).
        org_granted = (
            access is not None
            and access.organization == organization_id
            and (access.grant.org_admin or not access.grant.workspaces)
        )
        if organization_id and profile and org_granted:
            await self.store.write_profile(organization_id, user.id, profile)
            await self.store.commit()
        sent = await self._notify(user, by, access, organization_id=organization_id)
        return CreateOrLinkResult(
            user=user,
            created=False,
            provisioned=False,
            sign_in_email_sent=sent,
            warning=None,
            provider=await self._known_provider_of(user),
        )

    # =========================================================================
    # Adding someone who exists, changing a level
    # =========================================================================

    async def add_existing(self, *, user_id: str, grant: Grant, by: Actor) -> AddedUser:
        """Give an existing person ``grant`` on behalf of ``by`` and tell them.
        The answer is the person, and whether the mail telling them was sent."""
        user = await self.store.get(user_id)
        if user is None:
            raise UnknownUserError(user_id)
        access = await self._plan(grant)
        if access is not None:
            await self._apply(user.id, access, by)
        sent = await self._notify(user, by, access, organization_id=None)
        return AddedUser(
            id=user.id,
            email=user.email,
            name=user.name,
            status=user.status,
            provider=user.provider,
            sign_in_email_sent=sent,
        )

    async def set_level(
        self, *, user_id: str, level: str, by: Actor, where: Sequence[str] = ()
    ) -> Level | None:
        """Make ``level`` the person's, in every workspace they work in, on behalf of
        ``by``: the platform admin, an org admin, or an admin of any of the person's
        workspaces may (IAM's level-group rule); audited with who asked. Returns the
        level they had. ``where``: containers the change is asked from."""
        if level not in LEVELS:
            raise ValueError(f"Unknown level {level!r}")
        if await self.store.get(user_id) is None:
            raise UnknownUserError(user_id)
        return await self.access.set_level(user_id, level, by=by.id, where=where)  # type: ignore[arg-type]

    async def set_workspace_admin(
        self, *, user_id: str, workspace_id: str, admin: bool, by: Actor
    ) -> None:
        """Make a person of the workspace its admin ("<W> admins"; a workspace admin
        is a Member, so a Viewer becomes one) or take that back, on behalf of ``by``,
        all or nothing. ``UnknownUserError`` for someone who is not in it."""
        if await self.store.get(user_id) is None:
            raise UnknownUserError(user_id)
        container = await self.access.container("workspace", workspace_id)
        seat, tie = Seat(container, ADMINS), Seat(container, MEMBERSHIP)
        held = await self.access.held(user_id, [seat, tie])
        if tie not in held:
            raise UnknownUserError(user_id)
        if not admin:
            if seat in held:
                await self.access.check_leaving(user_id, [seat], by=by.id)
                await self.access.leave(user_id, seat, by=by.id)
            return
        if seat in held:
            return
        current = await self.access.level_of(user_id)
        target: Level | None = "member" if current != "member" else None
        await self.access.check(
            user_id, [seat], level=target, by=by.id, organization_id=org_of(container)
        )
        done: list[_Done] = []
        try:
            if target is not None:
                done.append(("level", await self.access.set_level(user_id, target, by=by.id)))
            if await self.access.join(user_id, seat, by=by.id, level="member"):
                done.append(("join", seat))
        except Exception:
            await self._take_back(user_id, done)
            raise

    async def change_access(
        self,
        *,
        user_id: str,
        organization_id: str,
        by: Actor,
        level: str | None = None,
        org_admin: bool | None = None,
        workspaces: Sequence[WorkspaceAccess] | None = None,
        among: Sequence[str] = (),
        capabilities: Sequence[str] | None = None,
    ) -> None:
        """Change where a person of the organization works and what they do there,
        on behalf of ``by``, all or nothing: their org admin seat (``org_admin``),
        their workspaces (``workspaces``, the full set wanted of ``among``, the
        organization's workspaces: those left out are left), their capability
        groups (the full set wanted of the organization's) and their level. None
        leaves that part as it is. Someone with no workspace left and no org admin
        seat stays among the organization's people ("<O> people")."""
        if level is not None and level not in LEVELS:
            raise ValueError(f"Unknown level {level!r}")
        if await self.store.get(user_id) is None:
            raise UnknownUserError(user_id)
        org = await self.access.container("organization", organization_id)
        joins: list[Seat] = []
        leaves: list[Seat] = []

        def want(seat: Seat, wanted: bool) -> None:
            (joins if wanted else leaves).append(seat)

        if org_admin is not None:
            if org_admin:
                want(Seat(org, MEMBERSHIP), True)
            want(Seat(org, ADMINS), org_admin)
        if workspaces is not None:
            chosen = {w.id: w for w in workspaces}
            unknown = sorted(set(chosen) - set(among))
            if unknown:
                raise ValueError(f"Not workspaces of this organization: {', '.join(unknown)}")
            for workspace_id in among:
                container = await self.access.container("workspace", workspace_id)
                picked = chosen.get(workspace_id)
                if picked is not None:
                    want(Seat(container, MEMBERSHIP), True)
                    want(Seat(container, ADMINS), picked.admin)
                else:
                    want(Seat(container, ADMINS), False)
                    want(Seat(container, MEMBERSHIP), False)
        if capabilities is not None:
            listed = {gid for gid, _name in await self.access.capability_groups(organization_id)}
            unknown = sorted(set(capabilities) - listed)
            if unknown:
                raise ValueError(f"Not a capability group here: {', '.join(unknown)}")
            for group_id in sorted(listed):
                want(Seat(org, CAPABILITY, group_id), group_id in capabilities)
        held = await self.access.held(user_id, [*joins, *leaves])
        joins = [s for s in joins if s not in held]
        leaves = [s for s in leaves if s in held]
        # Out of every workspace and not an admin: among the organization's people.
        if workspaces is not None and not workspaces:
            if Seat(org, MEMBERSHIP) not in held and Seat(org, MEMBERSHIP) not in joins:
                joins.insert(0, Seat(org, MEMBERSHIP))
        current = await self.access.level_of(user_id)
        if level is None and any(s.kind == ADMINS and s.container != org for s in joins):
            level = "member" if current != "member" else None  # a workspace admin is a Member
        target = level if level is not None and level != current else None
        if joins or target is not None:
            await self.access.check(
                user_id, joins, level=target, by=by.id, organization_id=organization_id
            )  # type: ignore[arg-type]
        if leaves:
            await self.access.check_leaving(user_id, leaves, by=by.id)
        done: list[_Done] = []
        try:
            for seat in sorted(joins, key=lambda s: _ORDER[s.kind]):
                if await self.access.join(user_id, seat, by=by.id, level=target or current):  # type: ignore[arg-type]
                    done.append(("join", seat))
            if target is not None:
                before = await self.access.set_level(user_id, target, by=by.id)  # type: ignore[arg-type]
                done.append(("level", before))
            for seat in sorted(leaves, key=lambda s: -_ORDER[s.kind]):
                await self.access.leave(user_id, seat, by=by.id)
        except Exception:
            await self._take_back(user_id, done)
            raise

    async def _plan(self, grant: Grant | None) -> _Access | None:
        """The seats a grant asks for, checked before anything is asked of IAM: a
        known level, an organization or a workspace, workspaces of the organization,
        and no workspace admin who is a Viewer. None: no grant."""
        if grant is None:
            return None
        if grant.level is not None and grant.level not in LEVELS:
            raise ValueError(f"Unknown level {grant.level!r}")
        if not grant.organization_id and not grant.workspaces:
            raise ValueError("A grant names an organization or a workspace")
        if grant.org_admin and not grant.organization_id:
            raise ValueError("An organization admin needs an organization")
        if grant.level == "viewer" and any(w.admin for w in grant.workspaces):
            raise ValueError("A workspace admin is a Member: a Viewer administers nothing")
        org = (
            await self.access.container("organization", grant.organization_id)
            if grant.organization_id
            else None
        )
        seats: list[Seat] = []
        places: list[str] = []
        for workspace in {w.id: w for w in grant.workspaces}.values():
            try:
                container = await self.access.container("workspace", workspace.id)
            except LookupError as exc:
                raise ValueError(f"Unknown workspace {workspace.id}") from exc
            if org_of(container) != grant.organization_id:
                raise ValueError(f"The workspace {workspace.id} is not one of the organization's")
            seats.append(Seat(container, MEMBERSHIP))
            places.append(container)
            if workspace.admin:
                seats.append(Seat(container, ADMINS))
        if org is not None and (grant.org_admin or not grant.workspaces):
            seats.append(Seat(org, MEMBERSHIP))
            places.append(org)
            if grant.org_admin:
                seats.append(Seat(org, ADMINS))
        given_in = org or places[0]
        seats += [
            Seat(given_in, CAPABILITY, g)
            for g in dict.fromkeys(str(c).strip() for c in grant.capabilities)
            if g
        ]
        return _Access(grant, tuple(seats), tuple(places), grant.organization_id)

    async def _apply(
        self, user_id: str, access: _Access, by: Actor, *, done: list[_Done] | None = None
    ) -> None:
        """Put the person in the seats and at the level, on behalf of ``by``: all
        checked first, then the membership groups (their tie), the level, the admins
        groups and the capability groups. All or nothing: what this call did is
        taken back on a failure (by the caller when it passes ``done``)."""
        held = await self.access.held(user_id, access.seats)
        for seat in access.seats:
            if seat.kind == MEMBERSHIP and seat.container in access.places and seat in held:
                raise AlreadyMemberError(user_id, seat.container)
        current = await self.access.level_of(user_id)
        level = access.level_after(current)
        target = level if level != current else None
        todo = sorted((s for s in access.seats if s not in held), key=lambda s: _ORDER[s.kind])
        await self.access.check(
            user_id, todo, level=target, by=by.id, organization_id=access.organization
        )
        made: list[_Done] = [] if done is None else done
        try:
            for seat in (s for s in todo if s.kind == MEMBERSHIP):
                if await self.access.join(user_id, seat, by=by.id, level=level):
                    made.append(("join", seat))
            if target is not None:
                made.append(("level", await self.access.set_level(user_id, target, by=by.id)))
            for seat in (s for s in todo if s.kind != MEMBERSHIP):
                if await self.access.join(user_id, seat, by=by.id, level=level):
                    made.append(("join", seat))
        except Exception:
            if done is None:  # the caller takes back what ``done`` lists
                await self._take_back(user_id, made)
            raise

    async def _take_back(self, user_id: str, done: Sequence[_Done]) -> None:
        for kind, what in reversed(done):
            try:
                if kind == "join":
                    await self.access.leave(user_id, what, by=None)  # type: ignore[arg-type]
                elif what is None:
                    await self.access.clear_level(user_id)
                else:
                    await self.access.set_level(user_id, what, by=None)  # type: ignore[arg-type]
            except Exception as exc:  # noqa: BLE001 - logged, the rest goes on
                logger.warning(f"Could not take back {kind} {what} of {user_id}: {exc}")

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

    async def provision(self, user_id: str) -> Provisioned | None:
        """Make the person's account at the provider their row names, as Nexus: for
        the people the platform's configuration names (``core/org_seed.py``,
        ``core/users_import.py``), whom the operator's configuration warrants as an
        authorized invitation does. Nothing else: a row no provider binds yet stays
        unbound (the first sign-in through that provider, email verified, binds it:
        ``services/oidc``), and nobody is mailed. An account made here is recorded
        as ABI's. None when the provider makes no account (``provisioning: none``);
        the provider's failures propagate (``ProvisioningFailedError``)."""
        user = await self.store.get(user_id)
        if user is None:
            raise UnknownUserError(user_id)
        choice = await self._provider_of(user)
        provisioned = await self.identity.provision(choice, user.email, user.name)
        if provisioned is not None and provisioned.created and provisioned.subject:
            await self.store.record_provisioned(
                choice.name, provisioned.subject, user.email, now=self._clock()
            )
            await self.store.commit()
        return provisioned

    async def activate(self, user_id: str) -> None:
        """The person signed in for the first time: ``invited`` → ``active``."""
        if await self.store.activate(user_id, now=self._clock()):
            await self.store.commit()

    async def _notify(
        self,
        user: PlatformUser,
        by: Actor,
        access: _Access | None,
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
                access,
                organization_id=organization_id,
                account_made=_has_account(user),
            )
        placement = await self._placement(access, organization_id)
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
        access: _Access | None,
        *,
        organization_id: str | None,
        account_made: bool,
    ) -> bool:
        placement = await self._placement(access, organization_id)
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

    async def _placement(self, access: _Access | None, organization_id: str | None) -> Placement:
        """Where the mail says the person was put: the organization (as its admin, or
        among its people) and the first workspace (as its admin, or at their level)."""
        grant = access.grant if access is not None else None
        org_id = grant.organization_id if grant and grant.organization_id else organization_id
        workspace = grant.workspaces[0] if grant and grant.workspaces else None
        org_name, ws_name = await self.store.names(org_id, workspace.id if workspace else None)
        level = (grant.level if grant else None) or "member"
        org_role = None
        if grant is not None and grant.organization_id:
            org_role = "admin" if grant.org_admin else (None if grant.workspaces else level)
        return Placement(
            organization_name=org_name,
            organization_role=org_role,
            workspace_name=ws_name,
            workspace_role=("admin" if workspace.admin else level) if workspace else None,
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

    async def _known_provider_of(self, user: PlatformUser) -> ProviderInfo | None:
        """The provider the person signs in with, None when it is not configured
        (any more) or the providers cannot be read: an answer, never a failure."""
        try:
            return await self._provider_of(user)
        except Exception as exc:  # noqa: BLE001 - the membership stands
            logger.info(f"The provider of {user.id} is not known: {exc}")
            return None

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
