"""Ports of the platform's directory of accounts (Platform Settings > Users).

An entry is a Nexus account (a ``users`` row) or someone invited who has none yet
(their pending invitations, by email). What decides and keeps access is IAM's;
what makes a person exist and sign in is their identity provider's; Nexus keeps
the rows, the sessions and the invitations.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal

AccountKind = Literal["account", "invitation"]
# Signed in at least once, or invited and not yet.
AccountStatus = Literal["signed_in", "invited"]
PrincipalStatus = Literal["active", "suspended", "deleted"]
# The id of someone invited who has no account yet.
INVITED_PREFIX = "invited:"


def invited_id(email: str) -> str:
    return f"{INVITED_PREFIX}{email.lower().strip()}"


def invited_email(account_id: str) -> str | None:
    """The email an ``invited:`` id names; None for an account's id."""
    if not account_id.startswith(INVITED_PREFIX):
        return None
    return account_id.removeprefix(INVITED_PREFIX).lower().strip() or None


# =============================================================================
# Records
# =============================================================================


@dataclass(frozen=True)
class NexusUser:
    """A Nexus ``users`` row. ``idp_*`` are set once the person signed in through
    an identity provider (a row of the old login, or one the configuration seeds,
    has none until then)."""

    id: str
    email: str
    name: str
    created_at: datetime
    avatar: str | None = None
    principal_id: str | None = None
    idp_provider: str | None = None
    idp_subject: str | None = None

    @property
    def signed_in(self) -> bool:
        return self.idp_subject is not None


@dataclass(frozen=True)
class OrganizationRole:
    id: str
    name: str
    role: str


@dataclass(frozen=True)
class Principal:
    """The IAM user of an account, as IAM holds it."""

    id: str
    status: PrincipalStatus


@dataclass(frozen=True)
class PendingInvitation:
    id: str
    email: str
    provider: str
    created_at: datetime | None


@dataclass(frozen=True)
class Provider:
    name: str
    display_name: str
    managed_in_provider: bool
    # ABI's own provider (``provisioning: builtin``): every account there is ABI's.
    own: bool = False


@dataclass(frozen=True)
class ProviderAccount:
    """The person at their identity provider."""

    provider: str
    subject: str
    name: str | None = None
    disabled: bool = False


@dataclass(frozen=True)
class Account:
    """One entry of the directory."""

    id: str
    kind: AccountKind
    email: str
    name: str
    status: AccountStatus
    created_at: datetime | None
    avatar: str | None = None
    principal_id: str | None = None
    deactivated: bool = False
    is_superadmin: bool = False
    organizations: tuple[OrganizationRole, ...] = ()
    provider: str | None = None
    # What the identity provider could not follow, after a change.
    warning: str | None = None


@dataclass(frozen=True)
class Holdings:
    """What IAM holds for a principal, for the deletion's summary."""

    attachments: int = 0
    groups: int = 0
    api_keys: int = 0
    # ``(scope, role)`` of each built-in role: the memberships.
    roles: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True)
class Membership:
    scope: str
    label: str
    role: str


@dataclass(frozen=True)
class DeletionPlan:
    """What deleting an account takes away, and what stays."""

    account: Account
    # What deleting leaves behind that the admin should know (a provider that keeps
    # the person's account, so the address cannot sign in again).
    warning: str | None
    # Why it cannot be deleted (yourself, the last platform admin, an organization's
    # only owner).
    blocked: str | None
    provider_account: Provider | None
    iam_user: str | None
    attachments: int
    memberships: tuple[Membership, ...]
    groups: int
    sessions: int
    api_keys: int
    invitations: int
    # Where what they wrote stays: ``(id, name)`` of their workspaces.
    workspaces: tuple[tuple[str, str], ...] = field(default=())


@dataclass(frozen=True)
class Invited:
    account: Account
    user_created: bool
    sign_in_email_sent: bool
    provisioning_skipped: bool
    renewed: bool
    warning: str | None


# =============================================================================
# Errors
# =============================================================================


class AccountNotFoundError(LookupError):
    pass


class AccountChangeRefused(ValueError):
    """A change the rules refuse, whoever asks: on yourself, the last platform
    admin, the only owner of an organization."""


class AccountExistsError(ValueError):
    """An invitation to an address an account already holds."""


class AccessRefused(PermissionError):
    """IAM (or the identity provider, asked as the caller) refused."""


class ProviderManaged(Exception):
    """The provider manages its people itself (``provisioning: none``)."""


class ProviderUnreachable(Exception):
    """The identity provider could not be reached or refused the call."""


# =============================================================================
# Ports
# =============================================================================


class AccountStorePort(ABC):
    """Nexus's rows: users, their browser sessions, their organization profiles."""

    @abstractmethod
    async def list_users(self) -> list[NexusUser]:
        """Every account that is not deleted."""

    @abstractmethod
    async def get_user(self, user_id: str) -> NexusUser | None: ...

    @abstractmethod
    async def user_by_email(self, email: str) -> NexusUser | None: ...

    @abstractmethod
    async def retired_identity(self, provider: str, subject: str) -> bool:
        """Whether a deleted account is bound to this identity at a provider."""

    @abstractmethod
    async def made_by_abi(self, provider: str, subject: str) -> bool:
        """Whether an invitation made this account at ``provider``
        (``provisioned_identities``): only such an account, or one at ABI's own
        provider, is changed or deleted there with the person's Nexus account."""

    @abstractmethod
    async def rename(self, user_id: str, name: str, *, now: datetime) -> None: ...

    @abstractmethod
    async def set_superadmin_flag(self, user_id: str, on: bool, *, now: datetime) -> None:
        """The stored flag only bootstraps (IAM decides): kept in step."""

    @abstractmethod
    async def count_sessions(self, user_id: str, *, now: datetime) -> int:
        """Browser sessions still open."""

    @abstractmethod
    async def end_sessions(self, user_id: str, *, now: datetime) -> int: ...

    @abstractmethod
    async def retire(self, user_id: str, *, now: datetime) -> None:
        """A deleted account: its sessions and organization profiles go, the row stays
        as the author of what the person wrote, with its email released."""

    @abstractmethod
    async def organizations(self) -> dict[str, list[OrganizationRole]]:
        """Each user's organizations and role there, by Nexus user id."""

    @abstractmethod
    async def workspace_names(self, ids: Sequence[str]) -> dict[str, str]: ...

    @abstractmethod
    async def organization_names(self, ids: Sequence[str]) -> dict[str, str]: ...

    @abstractmethod
    async def commit(self) -> None: ...

    @abstractmethod
    async def rollback(self) -> None: ...


class AccessGateway(ABC):
    """IAM. Reads are Nexus's own; changes are made as the caller (``by``), so IAM
    decides them (``iam:SuspendPrincipal``, ``ResumePrincipal``, ``DeletePrincipal``,
    the attachment of ``builtin.platform_admin``): ``AccessRefused`` when it refuses."""

    @abstractmethod
    async def principals(self, user_ids: Sequence[str]) -> dict[str, Principal]:
        """The IAM user of each Nexus user that has one."""

    @abstractmethod
    async def principal(self, user_id: str) -> Principal:
        """The IAM user of a Nexus user, made on first sight (an account of the old
        login, or one the configuration seeded, has none until it is needed)."""

    @abstractmethod
    async def platform_admins(self) -> set[str]:
        """The Nexus ids of the users holding ``builtin.platform_admin``."""

    @abstractmethod
    async def set_platform_admin(self, user_id: str, on: bool, *, by: str) -> None: ...

    @abstractmethod
    async def suspend(self, principal_id: str, *, by: str) -> None: ...

    @abstractmethod
    async def resume(self, principal_id: str, *, by: str) -> None: ...

    @abstractmethod
    async def holdings(self, principal_id: str, *, by: str) -> Holdings:
        """What the principal holds, as the caller may list it."""

    @abstractmethod
    async def delete(self, principal_id: str, *, by: str) -> None:
        """Every token issued for the principal stops working and its keys are
        revoked, then IAM deletes it: its attachments and group memberships go,
        its id stays for the audit."""

    @abstractmethod
    async def sole_owner_of(self, principal_id: str) -> list[str]:
        """The organizations where they are the only owner."""


class IdentityGateway(ABC):
    """The identity providers, as the engine's identity service reaches them, as
    ``api`` on behalf of the caller (``by``): IAM checks ``identity:*`` for them.
    ``ProviderManaged`` for a provider that manages its people itself,
    ``AccessRefused`` when the caller may not, ``ProviderUnreachable`` otherwise."""

    @abstractmethod
    async def providers(self) -> list[Provider]: ...

    @abstractmethod
    async def find(self, provider: str, email: str, *, by: str) -> ProviderAccount | None: ...

    @abstractmethod
    async def update(
        self,
        provider: str,
        subject: str,
        *,
        name: str | None = None,
        disabled: bool | None = None,
        by: str,
    ) -> ProviderAccount | None: ...

    @abstractmethod
    async def delete(self, provider: str, subject: str, *, by: str) -> bool: ...


class InvitationsGateway(ABC):
    """Nexus's invitations (``services/invites``): the one way someone is invited."""

    @abstractmethod
    async def pending(self) -> list[PendingInvitation]: ...

    @abstractmethod
    async def invite(
        self,
        *,
        email: str,
        name: str | None,
        provider: str | None,
        by: str,
        inviter_name: str | None,
    ) -> Mapping[str, object]:
        """The outcome: ``provider``, ``user_created``, ``sign_in_email_sent``,
        ``provisioning_skipped``, ``renewed``, ``warning``."""

    @abstractmethod
    async def revoke(self, invitation_id: str) -> None: ...
