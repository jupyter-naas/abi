"""The platform's directory of accounts and their lifecycle (Platform Settings > Users).

* **list**: every Nexus account, and everyone invited who has none yet (their
  pending invitations, by email), with their IAM id, whether they signed in, whether
  they are deactivated, whether they are a platform admin and their organizations;
* **invite** through Nexus's invitations (``services/invites``), the one way
  someone is invited: the identity provider makes the person exist;
* **rename**, and make a platform admin or not;
* **deactivate** and **reactivate**: IAM suspends the user (no sign-in, no API
  call, no key) and the provider disables the account; data and memberships stay;
* **delete**: the account at the provider, the IAM user (its attachments and
  memberships), its sessions and keys go; the row stays as the author of what the
  person wrote, its email released.

The route decided the caller may (the ``nexus`` action on the account); each change
is then IAM's own, asked as the caller (suspending, deleting, attaching the platform
admin's role), and the provider's (``identity:*``, asked as ``api`` on their behalf).
The rules are the service's, whoever asks: nothing on yourself, never the last active
platform admin, never the only owner of an organization (on deleting). Every change
is audited first (``run_audited``): no record, no change.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Iterable, Sequence
from dataclasses import replace
from datetime import datetime
from typing import Literal, TypeVar

from naas_abi.apps.nexus.apps.api.app.services.accounts.port import (
    AccessGateway,
    AccessRefused,
    Account,
    AccountChangeRefused,
    AccountExistsError,
    AccountNotFoundError,
    AccountStorePort,
    DeletionPlan,
    IdentityGateway,
    InvitationsGateway,
    Invited,
    Membership,
    NexusUser,
    OrganizationRole,
    PendingInvitation,
    Principal,
    Provider,
    ProviderAccount,
    ProviderManaged,
    ProviderUnreachable,
    invited_email,
    invited_id,
)
from naas_abi.apps.nexus.apps.api.app.services.iam.names import (
    is_org_container,
    is_workspace_container,
    org_of,
    workspace_of,
)
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.resources import (
    AdminAction,
    AdminAuditLog,
)
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.resources_service import run_audited
from naas_abi_core import logger

T = TypeVar("T")
Clock = Callable[[], datetime]

# The audit is IAM's (Roles & permissions > Audit): these are changes of who may do what.
AUDIT_SERVICE = "iam"
MAX_NAME = 200

YOURSELF = "You cannot do this to your own account: use your account page"
LAST_ADMIN = "The platform needs at least one active platform admin"
NOT_SIGNED_IN = "They have no account yet: they become a platform admin once they sign in"


class DeletionBlocked(AccountChangeRefused):
    """The account cannot be deleted now (the plan says why)."""


class ConfirmationMismatch(AccountChangeRefused):
    pass


class IdentityRetired(AccountChangeRefused):
    """The address's identity at its provider is bound to a deleted account."""


class AccountService:
    def __init__(
        self,
        store: AccountStorePort,
        access: AccessGateway,
        identity: IdentityGateway,
        invitations: InvitationsGateway,
        audit: AdminAuditLog,
        *,
        clock: Clock,
    ) -> None:
        self.store = store
        self.access = access
        self.identity = identity
        self.invitations = invitations
        self.audit = audit
        self._clock = clock

    # =========================================================================
    # The directory
    # =========================================================================

    async def list(self, *, actor: str) -> list[Account]:
        # Nexus's reads share the request's database session, which takes one
        # operation at a time: they are awaited in turn. IAM's and the providers'
        # calls (worker threads, NATS) run together.
        users = await self.store.list_users()
        organizations = await self.store.organizations()
        pending = await self.invitations.pending()
        principals, admins = await asyncio.gather(
            self.access.principals([u.id for u in users]),
            self.access.platform_admins(),
        )
        accounts = [
            self._account(user, principals.get(user.id), admins, organizations) for user in users
        ]
        held = {user.email.lower() for user in users}
        invited = _by_email(i for i in pending if i.email.lower() not in held)
        accounts += await asyncio.gather(
            *(self._invited(email, rows, actor=actor) for email, rows in invited.items())
        )
        return sorted(accounts, key=lambda a: (a.name.lower(), a.email.lower()))

    async def get(self, account_id: str, *, actor: str) -> Account:
        user, invitations = await self._target(account_id)
        if user is None:
            return await self._invited(invitations[0].email, invitations, actor=actor)
        return await self._account_of(user)

    async def _account_of(self, user: NexusUser, *, warning: str | None = None) -> Account:
        organizations = await self.store.organizations()  # the session: on its own
        principals, admins = await asyncio.gather(
            self.access.principals([user.id]),
            self.access.platform_admins(),
        )
        account = self._account(user, principals.get(user.id), admins, organizations)
        return replace(account, warning=warning)

    @staticmethod
    def _account(
        user: NexusUser,
        principal: Principal | None,
        admins: set[str],
        organizations: dict[str, list[OrganizationRole]],
    ) -> Account:
        return Account(
            id=user.id,
            kind="account",
            email=user.email,
            name=user.name,
            avatar=user.avatar,
            status="signed_in" if user.signed_in else "invited",
            created_at=user.created_at,
            principal_id=principal.id if principal is not None else user.principal_id,
            deactivated=principal is not None and principal.status == "suspended",
            is_superadmin=user.id in admins,
            organizations=tuple(organizations.get(user.id, ())),
            provider=user.idp_provider,
        )

    async def _invited(
        self,
        email: str,
        invitations: Sequence[PendingInvitation],
        *,
        actor: str,
        warning: str | None = None,
    ) -> Account:
        """Someone invited who has no account yet. Their name, and whether they are
        deactivated, are their provider's (asked, never failing the list)."""
        found = await self._at_providers(
            email, sorted({i.provider for i in invitations}), actor=actor, quiet=True
        )
        first = found[0] if found else None
        return Account(
            id=invited_id(email),
            kind="invitation",
            email=email,
            name=(first.name if first and first.name else email.split("@", 1)[0]),
            status="invited",
            created_at=min(
                (i.created_at for i in invitations if i.created_at is not None), default=None
            ),
            deactivated=bool(found) and all(a.disabled for a in found),
            provider=first.provider if first else invitations[0].provider,
            warning=warning,
        )

    async def _target(self, account_id: str) -> tuple[NexusUser | None, list[PendingInvitation]]:
        """The account an id names, or the pending invitations of someone with none."""
        email = invited_email(account_id)
        if email is None:
            user = await self.store.get_user(account_id)
            if user is None:
                raise AccountNotFoundError(account_id)
            return user, []
        if await self.store.user_by_email(email) is not None:
            raise AccountNotFoundError(account_id)  # they signed in since: an account now
        invitations = [i for i in await self.invitations.pending() if i.email.lower() == email]
        if not invitations:
            raise AccountNotFoundError(account_id)
        return None, invitations

    # =========================================================================
    # Inviting
    # =========================================================================

    async def invite(
        self,
        *,
        actor: str,
        actor_name: str | None,
        email: str,
        name: str | None,
        provider: str | None,
    ) -> Invited:
        email = email.lower().strip()
        if await self.store.user_by_email(email) is not None:
            raise AccountExistsError(f"{email} already has an account")
        await self._not_a_retired_identity(email, provider, actor=actor)
        outcome = await self._audited(
            actor,
            "invite_user",
            invited_id(email),
            f"invited {email}",
            lambda: self.invitations.invite(
                email=email, name=name, provider=provider, by=actor, inviter_name=actor_name
            ),
        )
        rows = [i for i in await self.invitations.pending() if i.email.lower() == email]
        warning = _text(outcome.get("warning"))
        account = (
            await self._invited(email, rows, actor=actor, warning=warning)
            if rows
            else Account(
                id=invited_id(email),
                kind="invitation",
                email=email,
                name=name or email.split("@", 1)[0],
                status="invited",
                created_at=self._clock(),
                provider=_text(outcome.get("provider")),
                warning=warning,
            )
        )
        if name and account.name != name:
            account = replace(account, name=name)
        return Invited(
            account=account,
            user_created=bool(outcome.get("user_created")),
            sign_in_email_sent=bool(outcome.get("sign_in_email_sent")),
            provisioning_skipped=bool(outcome.get("provisioning_skipped")),
            renewed=bool(outcome.get("renewed")),
            warning=warning,
        )

    # =========================================================================
    # Changes
    # =========================================================================

    async def update(
        self,
        account_id: str,
        *,
        name: str | None = None,
        is_superadmin: bool | None = None,
        actor: str,
    ) -> Account:
        """Rename and/or change superadmin. Every rule of both is checked before
        either is made; the superadmin change (IAM's) goes first, so its refusal
        leaves the name as it was."""
        user, _ = await self._target(account_id)
        self._not_yourself(user, actor)
        if name is not None:
            _valid_name(name)
        if is_superadmin is not None:
            if user is None:
                raise AccountChangeRefused(NOT_SIGNED_IN)
            admins = await self.access.platform_admins()
            if not is_superadmin and user.id in admins:
                await self._admins_remain(user.id, admins)
        account = None
        if is_superadmin is not None:
            account = await self.set_superadmin(account_id, is_superadmin, actor=actor)
        if name is not None:
            try:
                account = await self.rename(account_id, name, actor=actor)
            except Exception as exc:
                if account is None:
                    raise
                # The superadmin change is made: answered as it now is, with why the
                # name is not, never as if nothing had changed.
                logger.warning(f"Renaming {account_id} failed after its superadmin change: {exc}")
                return replace(
                    account,
                    warning=f"The superadmin change is made; the name is not changed: {exc}",
                )
        assert account is not None, "nothing to change"
        return account

    async def rename(self, account_id: str, name: str, *, actor: str) -> Account:
        name = _valid_name(name)
        user, invitations = await self._target(account_id)
        self._not_yourself(user, actor)
        email = user.email if user is not None else invitations[0].email

        async def change() -> str | None:
            problems: list[str] = []
            found = await self._provider_accounts(user, invitations, actor=actor, problems=problems)
            ours, theirs = await self._split(found)
            if user is not None:
                await self.store.rename(user.id, name, now=self._clock())
                await self.store.commit()
            elif not ours:
                raise AccountChangeRefused(
                    _theirs_refused(theirs, "rename")
                    if theirs
                    else "Their identity provider has no account for them yet: nothing to rename"
                )
            # Sign-in refreshes the name from the provider: it is changed there too, on
            # an account ABI made; one that is the person's own keeps its name there.
            problems.append(
                await self._at_each(
                    ours, lambda a: self.identity.update(a.provider, a.subject, name=name, by=actor)
                )
                or ""
            )
            problems += [
                f"Their account at {a.provider} is theirs, not ABI's: its name stays, and their "
                "next sign-in brings it back here"
                for a in theirs
            ]
            return _joined(problems)

        warning = await self._audited(actor, "rename_user", account_id, f"{email} → {name}", change)
        if user is None:
            return await self._invited(email, invitations, actor=actor, warning=warning)
        return await self._account_of(replace(user, name=name), warning=warning)

    async def set_superadmin(self, account_id: str, on: bool, *, actor: str) -> Account:
        user, _ = await self._target(account_id)
        if user is None:
            raise AccountChangeRefused(NOT_SIGNED_IN)
        self._not_yourself(user, actor)
        admins = await self.access.platform_admins()
        if (user.id in admins) == on:
            return await self._account_of(user)
        if not on:
            await self._admins_remain(user.id, admins)

        async def change() -> None:
            await self.access.set_platform_admin(user.id, on, by=actor)
            await self.store.set_superadmin_flag(user.id, on, now=self._clock())
            await self.store.commit()

        await self._audited(
            actor,
            "grant_platform_admin" if on else "revoke_platform_admin",
            user.id,
            user.email,
            change,
        )
        return await self._account_of(user)

    async def deactivate(self, account_id: str, *, actor: str) -> Account:
        return await self._set_active(account_id, False, actor=actor)

    async def reactivate(self, account_id: str, *, actor: str) -> Account:
        return await self._set_active(account_id, True, actor=actor)

    async def _set_active(self, account_id: str, active: bool, *, actor: str) -> Account:
        user, invitations = await self._target(account_id)
        self._not_yourself(user, actor)
        if user is not None and not active:
            await self._admins_remain(user.id)
        email = user.email if user is not None else invitations[0].email

        async def change() -> str | None:
            if user is None:
                # No IAM user yet: their provider's account is all there is to stop,
                # and only one ABI made.
                found = await self._provider_accounts(None, invitations, actor=actor, strict=True)
                ours, theirs = await self._split(found)
                if not ours:
                    raise AccountChangeRefused(
                        _theirs_refused(theirs, "deactivate")
                        if theirs
                        else "Their identity provider has no account for them yet: "
                        "delete the invitation instead"
                    )
                for account in ours:
                    await self.identity.update(
                        account.provider, account.subject, disabled=not active, by=actor
                    )
                return None
            principal = await self.access.principal(user.id)
            if active:
                await self.access.resume(principal.id, by=actor)
            else:
                await self.access.suspend(principal.id, by=actor)
                await self.store.end_sessions(user.id, now=self._clock())
                await self.store.commit()
            problems: list[str] = []
            found = await self._provider_accounts(user, [], actor=actor, problems=problems)
            ours, theirs = await self._split(found)
            problems.append(
                await self._at_each(
                    ours,
                    lambda a: self.identity.update(
                        a.provider, a.subject, disabled=not active, by=actor
                    ),
                )
                or ""
            )
            # The person's own account at a realm ABI shares: their access to ABI is
            # what changes (IAM, sessions), never their account there.
            problems += [_theirs_stays(a.provider) for a in theirs]
            return _joined(problems)

        warning = await self._audited(
            actor, "resume_user" if active else "suspend_user", account_id, email, change
        )
        if user is None:
            return await self._invited(email, invitations, actor=actor, warning=warning)
        return await self._account_of(user, warning=warning)

    # =========================================================================
    # Deleting
    # =========================================================================

    async def deletion(self, account_id: str, *, actor: str) -> DeletionPlan:
        """What deleting the account takes away and what stays, and whether it may."""
        user, invitations = await self._target(account_id)
        providers = {p.name: p for p in await self.identity.providers()}
        if user is None:
            account = await self._invited(invitations[0].email, invitations, actor=actor)
            found = await self._at_providers(
                account.email, sorted({i.provider for i in invitations}), actor=actor, quiet=True
            )
            ours, theirs = await self._split(found)
            return DeletionPlan(
                account=account,
                # An account ABI did not make is the person's: it stays.
                warning=_joined([_theirs_stays(a.provider) for a in theirs]),
                blocked=None,
                provider_account=_provider(ours, None, providers) if ours else None,
                iam_user=None,
                attachments=0,
                memberships=(),
                groups=0,
                sessions=0,
                api_keys=0,
                invitations=len(invitations),
            )
        account = await self._account_of(user)
        blocked = None
        if user.id == actor:
            blocked = YOURSELF
        else:
            try:
                await self._admins_remain(user.id)
            except AccountChangeRefused as exc:
                blocked = str(exc)
        principal = (await self.access.principals([user.id])).get(user.id)
        holdings = None
        if principal is not None:
            holdings = await self.access.holdings(principal.id, by=actor)
            if blocked is None:
                alone = await self.access.sole_owner_of(principal.id)
                if alone:
                    labels = await self._labels(alone)
                    blocked = (
                        f"They are the only owner of {', '.join(labels)}: "
                        "make someone else an owner there first"
                    )
        found = await self._provider_accounts(user, [], actor=actor, quiet=True)
        ours, theirs = await self._split(found)
        pending = [i for i in await self.invitations.pending() if i.email == user.email.lower()]
        roles = holdings.roles if holdings is not None else ()
        labels = await self._labels([scope for scope, _ in roles])
        workspace_ids = [
            ws
            for scope, _ in roles
            if is_workspace_container(scope) and (ws := workspace_of(scope)) is not None
        ]
        names = await self.store.workspace_names(workspace_ids)
        # Only an account ABI made goes with them; theirs stays (``_split``).
        provider_account = (
            _provider(ours, None, providers)
            if ours
            else None
            if theirs
            else _provider(found, user.idp_provider, providers)
        )
        warning = None
        if user.signed_in and provider_account is not None and provider_account.managed_in_provider:
            warning = _kept_identity(provider_account.display_name)
        if theirs:
            warning = _joined(
                [warning or "", *(_theirs_stays(a.provider, bound=user.signed_in) for a in theirs)]
            )
        return DeletionPlan(
            account=account,
            blocked=blocked,
            warning=warning,
            provider_account=provider_account,
            iam_user=principal.id if principal is not None else None,
            attachments=holdings.attachments if holdings is not None else 0,
            memberships=tuple(
                Membership(scope, label, role)
                for (scope, role), label in zip(roles, labels, strict=True)
            ),
            groups=holdings.groups if holdings is not None else 0,
            sessions=await self.store.count_sessions(user.id, now=self._clock()),
            api_keys=holdings.api_keys if holdings is not None else 0,
            invitations=len(pending),
            workspaces=tuple((ws, names.get(ws, ws)) for ws in dict.fromkeys(workspace_ids)),
        )

    async def delete(self, account_id: str, *, confirm: str, actor: str) -> str | None:
        """Delete the account once its email is typed back. Returns what the provider
        could not follow."""
        plan = await self.deletion(account_id, actor=actor)
        if plan.blocked:
            raise DeletionBlocked(plan.blocked)
        if confirm.strip().lower() != plan.account.email.lower():
            raise ConfirmationMismatch("Type their email to confirm the deletion")
        user, invitations = await self._target(account_id)
        email = plan.account.email

        async def change() -> str | None:
            if user is None:
                # The provider first: refused there, the invitations are kept. A
                # provider that manages its people has nothing for ABI to delete:
                # the invitations go, which is what is asked.
                found = await self._provider_accounts(
                    None, invitations, actor=actor, strict=True, managed="skip"
                )
                ours, theirs = await self._split(found)
                for account in ours:
                    await self.identity.delete(account.provider, account.subject, by=actor)
                await self._revoke(invitations)
                return _joined([_theirs_stays(a.provider) for a in theirs])
            lookups: list[str] = []
            found = await self._provider_accounts(user, [], actor=actor, problems=lookups)
            found, theirs = await self._split(found)
            principal = await self.access.principal(user.id)
            # IAM decides first: refused, nothing else goes. A principal a failed
            # attempt already deleted is done: the rest goes on, so a retry finishes.
            if principal.status != "deleted":
                await self.access.delete(principal.id, by=actor)
            await self.store.retire(user.id, now=self._clock())
            await self.store.commit()
            await self._revoke(
                [i for i in await self.invitations.pending() if i.email == email.lower()]
            )
            problems = await self._at_each(
                found, lambda a: self.identity.delete(a.provider, a.subject, by=actor)
            )
            kept = plan.warning or (
                _kept_identity("Their identity provider") if problems and user.signed_in else None
            )
            if theirs and not plan.warning:
                kept = _joined(
                    [kept or "", *(_theirs_stays(a.provider, bound=user.signed_in) for a in theirs)]
                )
            return _joined([*lookups, problems or "", kept or ""])

        return await self._audited(actor, "delete_user", account_id, email, change)

    async def _not_a_retired_identity(
        self, email: str, provider: str | None, *, actor: str
    ) -> None:
        """Refuse inviting an address whose account at a provider a deleted account is
        still bound to (the provider's delete failed): IAM keeps that identity on the
        deleted user, so the person could never sign in with it."""
        names = (
            [provider]
            if provider
            else [p.name for p in await self.identity.providers() if not p.managed_in_provider]
        )
        for account in await self._at_providers(email, names, actor=actor, quiet=True):
            if await self.store.retired_identity(account.provider, account.subject):
                raise IdentityRetired(
                    f"{email} belonged to a deleted account, and {account.provider} still holds "
                    "that account: delete it at the provider first, or they cannot sign in"
                )

    async def _revoke(self, invitations: Iterable[PendingInvitation]) -> None:
        for invitation in invitations:
            try:
                await self.invitations.revoke(invitation.id)
            except Exception as exc:  # noqa: BLE001 - one left is logged, the rest go
                logger.warning(f"Could not revoke invitation {invitation.id}: {exc}")

    # =========================================================================
    # Rules
    # =========================================================================

    @staticmethod
    def _not_yourself(user: NexusUser | None, actor: str) -> None:
        if user is not None and user.id == actor:
            raise AccountChangeRefused(YOURSELF)

    async def _admins_remain(self, user_id: str, admins: set[str] | None = None) -> None:
        """Refuse taking away the last active platform admin."""
        admins = admins if admins is not None else await self.access.platform_admins()
        if user_id not in admins:
            return
        others = [a for a in admins if a != user_id]
        principals = await self.access.principals(others)
        if not any(
            principals.get(a) is not None and principals[a].status == "active" for a in others
        ):
            raise AccountChangeRefused(LAST_ADMIN)

    # =========================================================================
    # Identity providers
    # =========================================================================

    async def _provider_accounts(
        self,
        user: NexusUser | None,
        invitations: Sequence[PendingInvitation],
        *,
        actor: str,
        strict: bool = False,
        quiet: bool = False,
        managed: Literal["refuse", "skip"] = "refuse",
        problems: list[str] | None = None,
    ) -> list[ProviderAccount]:
        """The person's accounts at their providers: the one they signed in with, else
        the one each provider holds for their email. ``problems`` collects a lookup
        that failed (not ``strict``), for the change's answer."""
        if user is not None and user.idp_provider and user.idp_subject:
            return [ProviderAccount(user.idp_provider, user.idp_subject)]
        email = user.email if user is not None else invitations[0].email
        names = sorted({i.provider for i in invitations}) or [
            p.name for p in await self.identity.providers() if not p.managed_in_provider
        ]
        return await self._at_providers(
            email,
            names,
            actor=actor,
            strict=strict,
            quiet=quiet,
            managed=managed,
            problems=problems,
        )

    async def _at_providers(
        self,
        email: str,
        providers: Sequence[str],
        *,
        actor: str,
        strict: bool = False,
        quiet: bool = False,
        managed: Literal["refuse", "skip"] = "refuse",
        problems: list[str] | None = None,
    ) -> list[ProviderAccount]:
        """``strict``: a refusal or an unreachable provider stops the change, and so
        does a provider that manages its people, unless ``managed="skip"``. Else a
        lookup that failed is logged (unless ``quiet``) and said in ``problems``: the
        account there, if any, was not changed."""
        found: list[ProviderAccount] = []
        for name in providers:
            try:
                account = await self.identity.find(name, email, by=actor)
            except ProviderManaged:
                if strict and managed == "refuse":
                    raise AccountChangeRefused(
                        f"{name} manages its people itself: do it there, or delete the invitation"
                    ) from None
                continue
            except (AccessRefused, ProviderUnreachable) as exc:
                if strict:
                    raise
                if not quiet:
                    logger.warning(f"Could not look {email} up at {name}: {exc}")
                if problems is not None:
                    problems.append(
                        f"{name} could not be asked for their account ({exc}): "
                        "do the same there if they have one"
                    )
                continue
            if account is not None:
                found.append(account)
        return found

    async def _split(
        self, accounts: Sequence[ProviderAccount]
    ) -> tuple[list[ProviderAccount], list[ProviderAccount]]:
        """``(ABI's, theirs)``: an account at ABI's own provider, or one an invitation
        made (``provisioned_identities``), is ABI's to change and delete; any other
        (one that already existed in a shared realm when they were invited) is the
        person's, used by other applications, and stays as it is."""
        own = {p.name for p in await self.identity.providers() if p.own}
        ours: list[ProviderAccount] = []
        theirs: list[ProviderAccount] = []
        for account in accounts:
            made = account.provider in own or await self.store.made_by_abi(
                account.provider, account.subject
            )
            (ours if made else theirs).append(account)
        return ours, theirs

    @staticmethod
    async def _at_each(
        accounts: Sequence[ProviderAccount], call: Callable[[ProviderAccount], Awaitable[object]]
    ) -> str | None:
        """Make the change at each provider; what one could not do is a warning (the
        IAM side already holds)."""
        problems: list[str] = []
        for account in accounts:
            try:
                await call(account)
            except ProviderManaged:
                problems.append(f"{account.provider} manages its people: do the same there")
            except AccessRefused as exc:
                problems.append(f"{account.provider} refused it: {exc}")
            except ProviderUnreachable as exc:
                problems.append(f"{account.provider} could not be reached: {exc}")
        return "; ".join(problems) or None

    # =========================================================================
    # Helpers
    # =========================================================================

    async def _labels(self, scopes: Sequence[str]) -> list[str]:
        """How a container reads: "Organization Acme", "Workspace W"."""
        orgs = [o for s in scopes if is_org_container(s) and (o := org_of(s)) is not None]
        workspaces = [
            w for s in scopes if is_workspace_container(s) and (w := workspace_of(s)) is not None
        ]
        org_names = await self.store.organization_names(orgs)
        ws_names = await self.store.workspace_names(workspaces)
        labels = []
        for scope in scopes:
            if is_workspace_container(scope) and (ws := workspace_of(scope)) is not None:
                labels.append(f"Workspace {ws_names.get(ws, ws)}")
            elif is_org_container(scope) and (org := org_of(scope)) is not None:
                labels.append(f"Organization {org_names.get(org, org)}")
            else:
                labels.append("the platform" if scope in ("", "abi:") else scope)
        return labels

    async def _audited(
        self,
        actor: str,
        operation: str,
        resource_id: str,
        detail: str,
        call: Callable[[], Awaitable[T]],
    ) -> T:
        action = AdminAction(actor, AUDIT_SERVICE, operation, resource_id, detail[:200])
        return await run_audited(self.audit, action, call)


def _by_email(invitations: Iterable[PendingInvitation]) -> dict[str, list[PendingInvitation]]:
    found: dict[str, list[PendingInvitation]] = {}
    for invitation in invitations:
        found.setdefault(invitation.email.lower(), []).append(invitation)
    return found


def _provider(
    found: Sequence[ProviderAccount], fallback: str | None, providers: dict[str, Provider]
) -> Provider | None:
    name = found[0].provider if found else fallback
    if name is None:
        return None
    return providers.get(name) or Provider(name, name, managed_in_provider=False)


def _text(value: object) -> str | None:
    return str(value) if value else None


def _valid_name(name: str) -> str:
    name = name.strip()
    if not name or len(name) > MAX_NAME:
        raise AccountChangeRefused(f"A name is 1 to {MAX_NAME} characters")
    return name


def _joined(parts: Iterable[str]) -> str | None:
    return "; ".join(p for p in parts if p) or None


def _theirs_stays(provider: str, *, bound: bool = False) -> str:
    """What happens to an account ABI did not make at a shared provider. ``bound``: a
    deleted account they signed in with keeps that identity, so it cannot sign in to
    ABI again (``_not_a_retired_identity``)."""
    said = (
        f"Their account at {provider} is theirs, not ABI's (it existed when they were "
        "invited): it stays as it is, and only their access to ABI changes"
    )
    if bound:
        said += (
            "; invited again with this address, they could not sign in with it "
            "(that identity stays with the deleted account)"
        )
    return said


def _theirs_refused(accounts: Sequence[ProviderAccount], verb: str) -> str:
    providers = ", ".join(sorted({a.provider for a in accounts}))
    return (
        f"Their account at {providers} is theirs, not ABI's: ABI does not {verb} it. "
        "Delete the invitation to end what ABI gave them"
    )


def _kept_identity(provider: str) -> str:
    """What deleting an account leaves when its provider keeps the person's account."""
    return (
        f"{provider} keeps their account: invited again with this address, they could not "
        "sign in with it (that identity stays with the deleted account). Delete it at the "
        "provider too"
    )
