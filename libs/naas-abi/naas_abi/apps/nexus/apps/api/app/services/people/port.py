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

from naas_abi.apps.nexus.apps.api.app.services.iam.memberships import (
    ADMINS,
    CAPABILITY,
    MEMBERSHIP,
    LastOrgAdminError,
    Seat,
    UnknownUserError,
)
from naas_abi.apps.nexus.apps.api.app.services.invites.port import (
    InvalidPolicyError,
    NoProviderError,
)

__all__ = [
    "ADMINS",
    "CAPABILITY",
    "LEVELS",
    "MEMBERSHIP",
    "AccessGateway",
    "Actor",
    "AddedUser",
    "AlreadyActiveError",
    "AlreadyMemberError",
    "CreateOrLinkResult",
    "EmailTakenError",
    "Grant",
    "GrantNotHeldError",
    "IdentityGateway",
    "InvalidPolicyError",
    "LastOrgAdminError",
    "Level",
    "NewUser",
    "NoProviderError",
    "PeopleMailer",
    "PeopleStorePort",
    "PlatformUser",
    "ProviderInfo",
    "Placement",
    "Provisioned",
    "ProvisioningFailedError",
    "ProvisioningRefused",
    "RetiredIdentityError",
    "Seat",
    "UnknownUserError",
    "UserStatus",
    "WorkspaceAccess",
    "people_status",
    "status_of_row",
]

# A person's level (#1583): one choice, everywhere they work.
Level = Literal["viewer", "member"]
LEVELS: tuple[Level, ...] = ("member", "viewer")
# What an organization admin may set about a person in their organization.
PROFILE_FIELDS = ("organization", "job_title", "bio", "service_line", "country", "interest")
# A search needs this many characters, and returns at most ``MAX_SEARCH`` people.
MIN_QUERY = 2
MAX_SEARCH = 20


class UserStatus(StrEnum):
    INVITED = "invited"
    ACTIVE = "active"


@dataclass(frozen=True)
class WorkspaceAccess:
    """A workspace the person works in, and whether they administer it."""

    id: str
    admin: bool = False


@dataclass(frozen=True)
class Grant:
    """Where a person works and what they do there (#1589; ADR
    ``20261120_access_levels_and_groups.md``), in one organization:

    - ``level``: their level, one choice applying in every workspace they work in
      (None: keep theirs; someone with none who joins a workspace is a Member);
    - ``org_admin``: they administer the organization ("<O> admins");
    - ``workspaces``: the workspaces they join ("<W> workspace"), each with whether
      they administer it ("<W> admins"; a workspace admin is a Member);
    - ``capabilities``: the capability groups (ids) they join beside their level.

    With no workspace and no org admin they join "<O> people", the organization's
    own people (Viewer access at its level). ``organization_id`` None: a workspace in
    no organization. Nothing is attached to the person, and Owner is not assigned."""

    organization_id: str | None = None
    level: Level | None = None
    org_admin: bool = False
    workspaces: tuple[WorkspaceAccess, ...] = ()
    capabilities: tuple[str, ...] = ()


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
class AddedUser(PlatformUser):
    """What ``add_existing`` answers: the person (still a ``PlatformUser``), and
    whether the mail telling them (the "added" notice, or the invitation again for
    someone who never signed in) was sent."""

    sign_in_email_sent: bool = False


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
    # The provider the person signs in with (the one chosen, or the one their row
    # names when linked); None when it is not configured any more.
    provider: ProviderInfo | None = None


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
    """IAM, as the people flows change it (#1589): a person joins and leaves groups
    ("<W> workspace", "<W> admins", "<O> people", "<O> admins", capability groups,
    named by ``Seat``) and has one level. Every change is checked as the caller
    (``by``: IAM's member change on each group, its level-group rule for the level),
    then written as ``api``, and recorded with who asked (the Nexus audit log): IAM's
    own audit names ``api``. Reads, principals and take-backs are Nexus's own. The
    single path of the routes, the CLI (through the routes) and the agent's tools."""

    @abstractmethod
    async def container(self, kind: Literal["organization", "workspace"], id: str) -> str:
        """The container name of an organization or a workspace (``LookupError`` for
        an unknown workspace)."""

    @abstractmethod
    async def check(
        self,
        user_id: str | None,
        seats: Sequence[Seat],
        *,
        level: Level | None,
        by: str,
        organization_id: str | None,
    ) -> None:
        """That ``by`` may put the person (``None``: someone not made yet) in ``seats``
        and at ``level``, changing nothing: ``GrantNotHeldError`` otherwise, and
        ``ValueError`` for a capability group that is not one of the organization's
        (or the platform's). The warrant of an invitation: checked before anything
        exists (ADR ``20261118_invitation_provisions_the_account.md``)."""

    @abstractmethod
    async def held(self, user_id: str, seats: Sequence[Seat]) -> set[Seat]:
        """Which of ``seats`` the person holds now."""

    @abstractmethod
    async def level_of(self, user_id: str) -> Level | None: ...

    @abstractmethod
    async def join(self, user_id: str, seat: Seat, *, by: str | None, level: Level | None) -> bool:
        """Put the person in ``seat`` (checked first), as ``api``; a capability group on
        ``by``'s behalf. ``level``: the person's, for a container recorded before
        #1585 (the role the seat stands for). True when this call did."""

    @abstractmethod
    async def leave(self, user_id: str, seat: Seat, *, by: str | None) -> bool:
        """Take the person out of ``seat``: checked as ``by`` (None: Nexus, a
        take-back), as ``api``. ``LastOrgAdminError`` for an organization's last
        admin. True when this call did."""

    @abstractmethod
    async def check_leaving(self, user_id: str, seats: Sequence[Seat], *, by: str) -> None:
        """That ``by`` may take the person out of each of ``seats`` they hold
        (``GrantNotHeldError``; ``LastOrgAdminError``), changing nothing."""

    @abstractmethod
    async def set_level(
        self, user_id: str, level: Level, *, by: str | None, where: Sequence[str] = ()
    ) -> Level | None:
        """Make ``level`` the person's everywhere. Checked as ``by`` (None: Nexus) by
        IAM's level-group rule: the platform admin, an org admin, or an admin of any
        of the person's containers (or of ``where``). Audited. Returns the level
        they had."""

    @abstractmethod
    async def clear_level(self, user_id: str) -> None:
        """Leave every level group, as Nexus (the take-back for someone who had none)."""

    @abstractmethod
    async def capability_groups(self, organization_id: str | None) -> list[tuple[str, str]]:
        """``(group id, name)`` of the capability groups a person may join in the
        organization: its own, then the platform's."""

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
        """``{container: role}`` the person holds (``admin``, or their level), for
        the mail."""


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


# =============================================================================
# How a status reads
# =============================================================================


def people_status(status: object) -> str:
    """A status as the API spells it (``invited``, ``active``)."""
    return str(getattr(status, "value", status))


def status_of_row(row: object) -> str:
    """A ``users`` row's status (``users.status``); a row read without the column
    is ``active``, as every row from before invitations made rows."""
    status = getattr(row, "status", None)
    return people_status(status) if status else UserStatus.ACTIVE.value
