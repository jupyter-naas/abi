"""Ports of the platform's people: one ``users`` row per person, from the moment
they are invited (``invited``) to their first sign-in (``active``).

The domain records and errors are the contract the organization and workspace
routes code against (epic #1566, "API contract"); the ports are what the service
needs from Nexus's tables, the identity providers, IAM and the mail.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Literal, Protocol

from naas_abi.apps.nexus.apps.api.app.services.iam.memberships import UnknownUserError
from naas_abi.apps.nexus.apps.api.app.services.invites.port import (
    InvalidPolicyError,
    NoProviderError,
    OwnerGrantRefusedError,
)

__all__ = [
    "AccessGateway",
    "Actor",
    "AlreadyActiveError",
    "AlreadyMemberError",
    "CreateOrLinkResult",
    "EmailTakenError",
    "Grant",
    "GrantNotHeldError",
    "IdentityGateway",
    "InvalidPolicyError",
    "NewUser",
    "NoProviderError",
    "OwnerGrantRefusedError",
    "PeopleMailer",
    "PeopleStorePort",
    "PlatformUser",
    "ProviderInfo",
    "Placement",
    "Provisioned",
    "ProvisioningFailedError",
    "ProvisioningRefused",
    "RetiredIdentityError",
    "Role",
    "UnknownUserError",
    "UserStatus",
    "Warrant",
]

Role = Literal["owner", "admin", "member", "viewer"]
ROLES: tuple[Role, ...] = ("owner", "admin", "member", "viewer")
# What an organization admin may set about a person in their organization.
PROFILE_FIELDS = ("organization", "job_title", "bio", "service_line", "country", "interest")
# A search needs this many characters, and returns at most ``MAX_SEARCH`` people.
MIN_QUERY = 2
MAX_SEARCH = 20


class UserStatus(StrEnum):
    INVITED = "invited"
    ACTIVE = "active"


@dataclass(frozen=True)
class Grant:
    """One role, and/or customer policies (``pol_…``), to attach at an organization
    or a workspace."""

    scope: Literal["organization", "workspace"]
    scope_id: str
    role: Role | None = None
    policy_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class PlatformUser:
    """A ``users`` row. ``id`` is the IAM principal id of a person whose identity at
    their provider is known (made by the invitation, or signed in); a person no
    provider made yet (``provisioning: none``) keeps a stable id of their own, and
    keeps it once their first sign-in binds them."""

    id: str
    email: str
    name: str | None
    status: UserStatus
    provider: str | None


@dataclass(frozen=True)
class CreateOrLinkResult:
    user: PlatformUser
    # Internal: whether a new row was made. A route never says it (the answer of
    # a creation and a link is the same).
    created: bool
    provisioned: bool
    sign_in_email_sent: bool
    warning: str | None
    # The inviting person may not create accounts at the provider (a platform
    # invitation, which no grant warrants): none was made, the mail says so.
    provisioning_skipped: bool = False


class Actor(Protocol):
    """Who asks: the request's user (``User``), of whom the service reads the id,
    and the name for the mail."""

    @property
    def id(self) -> str: ...

    @property
    def name(self) -> str: ...


# =============================================================================
# Errors (translated to HTTP by the routes)
# =============================================================================


class GrantNotHeldError(PermissionError):
    """IAM refused a role or a policy to the person asking (they may not attach it
    there, or it grants what they do not hold): 403. Nothing was made."""


class AlreadyMemberError(Exception):
    """The person already holds a role where a grant would put one: 409."""

    def __init__(self, user_id: str, scope: str) -> None:
        super().__init__(f"{user_id} already holds a role at {scope}")
        self.user_id = user_id
        self.scope = scope


class AlreadyActiveError(AlreadyMemberError):
    """``resend`` to someone who has signed in already: 409, as already a member."""

    def __init__(self, user_id: str) -> None:
        Exception.__init__(self, f"{user_id} has signed in already")
        self.user_id = user_id
        self.scope = ""


class RetiredIdentityError(ValueError):
    """The provider's identity of this address belongs to a deleted account: 409."""


class ProvisioningFailedError(Exception):
    """The identity provider could not make the person (unreachable, refused): 502.
    Nothing was kept."""


class ProvisioningRefused(Exception):
    """IAM does not let the caller create accounts at the provider."""


# =============================================================================
# Records the ports carry
# =============================================================================


@dataclass(frozen=True)
class ProviderInfo:
    name: str
    display_name: str
    issuer: str
    provisioning: Literal["builtin", "zitadel", "keycloak", "none"]

    @property
    def managed_in_provider(self) -> bool:
        return self.provisioning == "none"


@dataclass(frozen=True)
class Provisioned:
    """What the provider's admin API said about the person."""

    subject: str | None
    created: bool
    warning: str | None = None


@dataclass(frozen=True)
class Warrant:
    """The pending grants IAM accepted on the inviting person's behalf before
    anything was made: the authorization of the invitation. ``made`` are those this
    call created (the others belong to an older invitation)."""

    grant_ids: tuple[str, ...] = ()
    made: tuple[str, ...] = ()


@dataclass(frozen=True)
class NewUser:
    id: str
    email: str
    name: str
    provider: str
    principal_id: str | None
    issuer: str | None
    subject: str | None


# =============================================================================
# Ports
# =============================================================================


class PeopleStorePort(ABC):
    """Nexus's ``users`` rows (and what an invitation writes beside them)."""

    @abstractmethod
    async def get(self, user_id: str) -> PlatformUser | None:
        """A row that is not deleted."""

    @abstractmethod
    async def by_email(self, email: str) -> PlatformUser | None: ...

    @abstractmethod
    async def search(self, q: str, among: Collection[str], limit: int) -> list[PlatformUser]:
        """The rows of ``among`` whose name or email contains ``q`` (any case)."""

    @abstractmethod
    async def add(self, user: NewUser, *, now: datetime) -> PlatformUser:
        """An ``invited`` row. ``EmailTakenError`` when another row holds the email."""

    @abstractmethod
    async def remove(self, user_id: str) -> None:
        """Take back a row ``add`` made (a failed invitation)."""

    @abstractmethod
    async def activate(self, user_id: str, *, now: datetime) -> bool:
        """``invited`` → ``active``, once. True when this call did."""

    @abstractmethod
    async def write_profile(
        self, organization_id: str, user_id: str, profile: Mapping[str, str]
    ) -> None:
        """The member profile an organization admin set (``PROFILE_FIELDS``)."""

    @abstractmethod
    async def record_provisioned(
        self, provider: str, subject: str, email: str, *, now: datetime
    ) -> None:
        """An account the invitation made at the provider (``provisioned_identities``)."""

    @abstractmethod
    async def forget_provisioned(self, provider: str, subject: str) -> None: ...

    @abstractmethod
    async def provider_for_domain(self, domain: str, organization_id: str | None) -> str | None:
        """The provider a verified domain of the organization routes to."""

    @abstractmethod
    async def names(
        self, organization_id: str | None, workspace_id: str | None
    ) -> tuple[str | None, str | None]:
        """``(organization name, workspace name)`` for the mail."""

    @abstractmethod
    async def commit(self) -> None: ...

    @abstractmethod
    async def rollback(self) -> None: ...


class EmailTakenError(Exception):
    """Another row holds the email (a concurrent invitation or sign-in)."""


class IdentityGateway(ABC):
    """The engine's identity service: the providers and their admin APIs."""

    @abstractmethod
    async def providers(self) -> tuple[list[ProviderInfo], str | None]:
        """The configured providers and the default one."""

    @abstractmethod
    async def provision(
        self, provider: ProviderInfo, email: str, name: str | None, *, by: str | None = None
    ) -> Provisioned | None:
        """Make the person exist at the provider; None for ``provisioning: none``.
        ``by``: on that user's behalf (their own right, ``ProvisioningRefused``);
        ``None``: as Nexus, only under a warrant. Provider failures propagate."""

    @abstractmethod
    async def delete(self, provider: str, subject: str) -> None:
        """Delete an account ``provision`` made (a failed invitation), as Nexus."""


class AccessGateway(ABC):
    """IAM. What gives access is written as ``api`` on behalf of ``by`` (IAM checks
    that they may attach it and hold what it grants: ``GrantNotHeldError``); reads,
    principals and take-backs are Nexus's own."""

    @abstractmethod
    async def scope(self, grant: Grant) -> str:
        """The container name of a grant's organization or workspace
        (``UnknownUserError`` is not this: ``LookupError`` for an unknown one)."""

    @abstractmethod
    async def warrant(
        self, provider: str, email: str, grants: Sequence[tuple[str, str]], *, by: str
    ) -> Warrant:
        """Pending grants ``(policy, scope)`` for the email at the provider, on
        behalf of ``by``: the check, before anything is made, that they may give
        them. A refusal takes back what the call made and raises."""

    @abstractmethod
    async def withdraw(self, grant_ids: Sequence[str]) -> None:
        """Revoke pending grants (as Nexus)."""

    @abstractmethod
    async def ensure_principal(
        self, issuer: str, subject: str, *, provider: str, email: str, name: str | None
    ) -> str:
        """The IAM user of ``(issuer, subject)``, made when it has none (as Nexus)."""

    @abstractmethod
    async def discard_principal(self, principal_id: str) -> None:
        """Take back a principal a failed invitation made (best effort)."""

    @abstractmethod
    async def roles_of(self, user_id: str) -> dict[str, str]:
        """``{scope: role}`` the user holds directly."""

    @abstractmethod
    async def grant_role(self, user_id: str, role: str, scope: str, *, by: str) -> None: ...

    @abstractmethod
    async def revoke_role(self, user_id: str, scope: str) -> None:
        """Take back a role ``grant_role`` gave (as Nexus)."""

    @abstractmethod
    async def attach(self, user_id: str, policy_id: str, scope: str, *, by: str) -> bool:
        """True when this call attached it."""

    @abstractmethod
    async def detach(self, user_id: str, policy_id: str, scope: str) -> None: ...


@dataclass(frozen=True)
class Placement:
    """Where a mail says the person was put."""

    organization_name: str | None = None
    organization_role: str | None = None
    workspace_name: str | None = None
    workspace_role: str | None = None


class PeopleMailer(ABC):
    @abstractmethod
    async def invitation(
        self,
        *,
        to_email: str,
        provider: ProviderInfo,
        inviter_name: str | None,
        placement: Placement,
        account_made: bool,
    ) -> bool:
        """The invitation of someone who never signed in. True when sent."""

    @abstractmethod
    async def added(self, *, to_email: str, inviter_name: str | None, placement: Placement) -> bool:
        """The notice to someone active that they were added somewhere."""
