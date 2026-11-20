"""Pending invitations become invited people (epic #1566, #1570).

Before the people directory (``services/people``), an invitation was three things:
an ``invitations`` row, IAM pending grants, and usually an account at the identity
provider. The person became a ``users`` row only at their first sign-in. Now a
person is a row from the moment they are invited, so the upgrade moves each
pending invitation into one, with the same access:

1. **The person.** An email that has a row already is that person (never a
   duplicate). Otherwise the provider is asked for the account the invitation made
   (``find_provisioned_user``). An account the provider proves at every sign-in
   (``builtin``: a code mailed to the address) or one Nexus made itself
   (``provisioned_identities``) is bound now: IAM's user of that identity
   (``ensure_user``) is the row's id. Any other case (``provisioning: none``, an
   account the person made themselves, no account) is an **unbound** row naming the
   invitation's provider, which their first sign-in through it, email verified,
   binds (``services/oidc``): the trust of the pending grant it replaces, no more.
   The row is ``invited`` until that sign-in.
2. **The access.** The invitation's pending grants were authorized when it was made
   (on the inviting person's behalf, IAM checked they held what they gave), so they
   are attached as ``api`` for nobody: a role through ``MEMBERSHIPS`` (never lower
   than one the person holds there already), a customer policy as is.
3. **The withdrawal.** The pending grants are revoked, the organization profile the
   invitation carried is written, and the invitation is marked ``migrated``.

The invitations of one person through one provider share their grants (IAM keeps
one per role and scope), so they move together. Every step is idempotent: a run
that stopped half-way is finished by the next one, and a second run changes
nothing. A provider that does not answer keeps its invitations pending (they still
work as before) for the next run. Revoked and accepted invitations are left alone.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from uuid import uuid4

from naas_abi.apps.nexus.apps.api.app.services.invites.port import (
    PROFILE_FIELDS,
    Invitation,
    InvitationPersistencePort,
)
from naas_abi.apps.nexus.apps.api.app.services.people.port import (
    EmailTakenError,
    NewUser,
    PeopleStorePort,
    PlatformUser,
)
from naas_abi.apps.nexus.apps.api.app.services.people.service import UNBOUND_PREFIX
from naas_abi_core import logger

Clock = Callable[[], datetime]
# Recorded in ``iam_migrations`` once a run left nothing to retry.
MIGRATION_NAME = "invitations_to_people_v1"


@dataclass(frozen=True)
class MigrationProvider:
    name: str
    issuer: str
    provisioning: str


class ProviderUnavailable(Exception):  # noqa: N818 - a signal: try again later
    """The provider did not answer: its invitations stay pending for the next run."""


class MigrationGateway(ABC):
    """The engine's identity service and IAM, as Nexus itself (``api`` for nobody)."""

    @abstractmethod
    async def providers(self) -> Mapping[str, MigrationProvider]: ...

    @abstractmethod
    async def find(self, provider: MigrationProvider, email: str) -> str | None:
        """The subject of the provider's account for ``email``; None when it has
        none or makes none (``provisioning: none``). ``ProviderUnavailable`` when it
        does not answer."""

    @abstractmethod
    async def ensure_principal(
        self, provider: MigrationProvider, subject: str, *, email: str
    ) -> str | None:
        """IAM's user of ``(issuer, subject)``, made when there is none; None when
        it is not active (a deleted account's identity)."""

    @abstractmethod
    async def pending(self, grant_ids: Sequence[str]) -> dict[str, tuple[str, str | None]]:
        """``{grant id: (policy id, scope)}`` of those that still exist."""

    @abstractmethod
    async def give(self, user_id: str, policy_id: str, scope: str | None) -> None:
        """Attach what a pending grant held to the user, as ``api`` for nobody: a
        role never lowers one held at the scope."""

    @abstractmethod
    async def withdraw(self, grant_ids: Sequence[str]) -> None: ...


@dataclass
class MigrationReport:
    # Invitations marked ``migrated``.
    migrated: int = 0
    # People: a new row bound to the provider's identity, a new unbound row, or a
    # row that existed (by email, or the identity's).
    bound: int = 0
    unbound: int = 0
    linked: int = 0
    # Left pending: the provider did not answer (retried), or it cannot be moved
    # (the provider is gone, the identity belongs to a deleted account), or failed.
    deferred: int = 0
    skipped: list[str] = field(default_factory=list)
    failed: list[str] = field(default_factory=list)

    @property
    def finished(self) -> bool:
        """Nothing a later run would do differently."""
        return not self.deferred and not self.failed


class _Skip(Exception):  # noqa: N818 - a signal, not an error
    pass


class InvitationMigration:
    def __init__(
        self,
        invitations: InvitationPersistencePort,
        people: PeopleStorePort,
        engine: MigrationGateway,
        *,
        clock: Clock,
    ) -> None:
        self.invitations = invitations
        self.people = people
        self.engine = engine
        self._clock = clock

    async def pending(self) -> list[Invitation]:
        return await self.invitations.list(status="pending")

    async def run(self) -> MigrationReport:
        report = MigrationReport()
        groups: dict[tuple[str, str], list[Invitation]] = {}
        for invitation in sorted(await self.pending(), key=_created):
            key = (invitation.email.strip().lower(), invitation.provider)
            groups.setdefault(key, []).append(invitation)
        if not groups:
            return report
        try:
            providers = await self.engine.providers()
        except ProviderUnavailable as exc:
            report.deferred = sum(len(group) for group in groups.values())
            logger.info(f"Pending invitations stay pending until the engine answers: {exc}")
            return report
        for (email, provider_name), invitations in groups.items():
            provider = providers.get(provider_name)
            try:
                if provider is None:
                    raise _Skip(f"{email}: {provider_name!r} is not an identity provider any more")
                await self._move(email, provider, invitations, report)
            except ProviderUnavailable as exc:
                report.deferred += len(invitations)
                logger.info(
                    f"Invitations of {email} stay pending until {provider_name} answers: {exc}"
                )
            except _Skip as skip:
                report.skipped.append(str(skip))
                logger.warning(f"Invitation not moved to the people directory: {skip}")
            except Exception as exc:  # noqa: BLE001 - one person never stops the others
                await self._rollback()
                report.failed.append(f"{email}: {exc}")
                logger.opt(exception=exc).error(
                    f"The invitations of {email} were not moved to the people directory"
                )
        return report

    async def _move(
        self,
        email: str,
        provider: MigrationProvider,
        invitations: list[Invitation],
        report: MigrationReport,
    ) -> None:
        user, how = await self._person(email, provider)
        grant_ids = list(dict.fromkeys(g for i in invitations for g in i.grant_ids))
        held = await self.engine.pending(grant_ids)
        # Policies first, then roles, as an invitation's claim attached them.
        for policy_id, scope in sorted(held.values(), key=lambda g: _is_role(g[0])):
            await self.engine.give(user.id, policy_id, scope)
        await self.engine.withdraw(list(held))
        for invitation in invitations:
            profile = {k: v for k, v in invitation.profile.items() if k in PROFILE_FIELDS and v}
            if invitation.organization_id and profile:
                await self.people.write_profile(invitation.organization_id, user.id, profile)
        await self.people.commit()
        now = self._clock()
        moved = 0
        for invitation in invitations:
            if await self.invitations.mark_migrated(invitation.id, user_id=user.id, now=now):
                moved += 1
        await self.invitations.commit()
        report.migrated += moved
        if how == "bound":
            report.bound += 1
        elif how == "unbound":
            report.unbound += 1
        else:
            report.linked += 1
        logger.info(
            f"{moved} pending invitation(s) of {email} are the invited person {user.id} "
            f"({how}): {len(held)} grant(s) attached"
        )

    async def _person(self, email: str, provider: MigrationProvider) -> tuple[PlatformUser, str]:
        """The row the invitations become, and how: ``linked``, ``bound``, ``unbound``."""
        existing = await self.people.by_email(email)
        if existing is not None:
            return existing, "linked"
        subject = await self.engine.find(provider, email)
        principal_id: str | None = None
        if subject and await self._proven(provider, subject):
            principal_id = await self.engine.ensure_principal(provider, subject, email=email)
            if principal_id is None:
                raise _Skip(f"{email}: the account at {provider.name} belongs to a deleted user")
            known = await self.people.get(principal_id)
            if known is not None:
                # They signed in before with another (or no verified) email.
                return known, "linked"
        try:
            user = await self.people.add(
                NewUser(
                    id=principal_id or f"{UNBOUND_PREFIX}{uuid4().hex}",
                    email=email,
                    name=email.split("@", 1)[0],
                    provider=provider.name,
                    principal_id=principal_id,
                    issuer=provider.issuer if principal_id else None,
                    subject=subject if principal_id else None,
                ),
                now=self._clock(),
            )
        except EmailTakenError:
            # A sign-in made it meanwhile: that person is linked.
            await self.people.rollback()
            found = await self.people.by_email(email)
            if found is None and principal_id is not None:
                found = await self.people.get(principal_id)
            if found is None:
                raise
            return found, "linked"
        await self.people.commit()
        return user, ("bound" if principal_id else "unbound")

    async def _proven(self, provider: MigrationProvider, subject: str) -> bool:
        """Whether the account is the address's owner's without a sign-in proving it:
        the built-in provider mails every sign-in a code, and an account Nexus made
        has an address only its owner verifies. Another one (made at the provider by
        whoever typed the address) waits for a verified sign-in, as the pending
        grant did."""
        if provider.provisioning == "builtin":
            return True
        return await self.invitations.provisioned_by_nexus(provider.name, subject)

    async def _rollback(self) -> None:
        try:
            await self.invitations.rollback()
        except Exception as exc:  # noqa: BLE001 - logged
            logger.warning(f"Rolling back a failed invitation move failed: {exc}")


ROLE_POLICIES = frozenset(f"builtin.{r}" for r in ("owner", "admin", "member", "viewer"))


def _is_role(policy_id: str) -> bool:
    return policy_id in ROLE_POLICIES


def _created(invitation: Invitation) -> datetime:
    return invitation.created_at or datetime.min
