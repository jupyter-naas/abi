"""Ports of Nexus's invitations: who was invited where, the identity
provider that makes the person exist, and the IAM grants that wait for them."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal

InvitationStatus = Literal["pending", "accepted", "revoked"]
# What an organization admin may set about a person when inviting them: their
# profile in that organization, written at their first sign-in.
PROFILE_FIELDS = ("organization", "job_title", "bio", "service_line", "country", "interest")
Provisioning = Literal["builtin", "zitadel", "keycloak", "none"]


@dataclass(frozen=True)
class Invitation:
    """An email invited to an organization and/or a workspace through one
    identity provider. ``grant_ids`` are the IAM pending grants that carry the
    roles and ``policy_ids`` until the person signs in. The policies attach at
    the invitation's workspace, else at its organization (``policy_scope``)."""

    id: str
    email: str
    provider: str
    organization_id: str | None
    org_role: str | None
    workspace_id: str | None
    workspace_role: str | None
    invited_by: str | None
    grant_ids: tuple[str, ...] = ()
    status: InvitationStatus = "pending"
    created_at: datetime | None = None
    accepted_at: datetime | None = None
    accepted_user_id: str | None = None
    # The member profile to write in ``organization_id`` once the person exists.
    profile: dict[str, str] = field(default_factory=dict)
    # The policies carried beside the roles ("Features of member", say).
    policy_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class ProviderChoice:
    name: str
    display_name: str
    provisioning: Provisioning

    @property
    def managed_in_provider(self) -> bool:
        """Its people are made in the provider itself, never from ABI."""
        return self.provisioning == "none"


@dataclass(frozen=True)
class Directory:
    """The providers Nexus can invite through, and the default one."""

    providers: tuple[ProviderChoice, ...] = ()
    default: str | None = None

    def get(self, name: str) -> ProviderChoice | None:
        return next((p for p in self.providers if p.name == name), None)


@dataclass(frozen=True)
class Provisioned:
    """What the provider's admin API said about the invited person."""

    subject: str | None
    created: bool
    # Something the invitation could not do for them (the provider's own mail).
    warning: str | None = None


@dataclass(frozen=True)
class GrantMade:
    """A pending grant of an invitation. ``created`` is False when IAM already
    held the same grant (an earlier invitation of the same person): it is then
    not this call's to take back."""

    id: str
    created: bool


@dataclass(frozen=True)
class IdpBindingView:
    provider: str
    claim_value: str
    role: str
    scope: str | None
    group_id: str


@dataclass(frozen=True)
class InviteOutcome:
    invitation: Invitation
    provider: ProviderChoice
    user_created: bool = False
    sign_in_email_sent: bool = False
    # What the provider could not do for the invitee, for the admin to see.
    warning: str | None = None
    # An invitation to the same person at the same place, made again: the roles
    # may have changed, nothing else was made twice.
    renewed: bool = False
    # The inviting user may not create accounts at the provider (and the address is
    # not one the organization proved): the grants wait for the person's sign-in.
    provisioning_skipped: bool = False


class ProvisioningRefused(Exception):
    """IAM does not let the inviting user create accounts at the provider."""


class OrgInvitationExistsError(Exception):
    """A workspace-only invitation would rewrite the organization invitation that
    already names this workspace."""


class NoProviderError(Exception):
    """No identity provider can take this invitation (none is configured, or
    the one asked for is not)."""


class InvitationNotFoundError(Exception):
    pass


class OwnerGrantRefusedError(Exception):
    """Only an owner makes an owner: an admin's invitation names a lower role."""


class InvalidPolicyError(ValueError):
    """An invitation carries customer policies (``pol_…``): a role is chosen as
    the role, never as one of its policies."""


class InvitationPersistencePort(ABC):
    """Nexus's ``invitations`` table."""

    @abstractmethod
    async def add(self, invitation: Invitation, *, now: datetime) -> Invitation: ...

    @abstractmethod
    async def get(self, invitation_id: str) -> Invitation | None: ...

    @abstractmethod
    async def find_pending(
        self,
        *,
        email: str,
        provider: str,
        organization_id: str | None,
        workspace_id: str | None,
    ) -> Invitation | None: ...

    @abstractmethod
    async def list(
        self,
        *,
        organization_id: str | None = None,
        workspace_id: str | None = None,
        status: InvitationStatus | None = "pending",
    ) -> list[Invitation]: ...

    @abstractmethod
    async def pending_for(self, *, email: str, provider: str) -> list[Invitation]: ...

    @abstractmethod
    async def update(
        self,
        invitation_id: str,
        *,
        org_role: str | None,
        workspace_role: str | None,
        grant_ids: Sequence[str],
        policy_ids: Sequence[str] = (),
        invited_by: str | None,
        now: datetime,
        profile: Mapping[str, str] | None = None,
    ) -> Invitation:
        """``profile``: replaces the stored one when given (``None``: kept)."""

    @abstractmethod
    async def mark_accepted(self, invitation_id: str, *, user_id: str, now: datetime) -> bool:
        """True when this call took it (another sign-in may have)."""

    @abstractmethod
    async def mark_revoked(self, invitation_id: str, *, now: datetime) -> bool: ...

    @abstractmethod
    async def provider_for_domain(self, domain: str, organization_id: str | None) -> str | None:
        """The provider a verified domain of the organization (else any
        organization) routes to."""

    @abstractmethod
    async def organization_of_workspace(self, workspace_id: str) -> str | None: ...

    @abstractmethod
    async def user_id_by_email(self, email: str) -> str | None:
        """The Nexus account that already holds this email."""

    @abstractmethod
    async def commit(self) -> None: ...

    @abstractmethod
    async def rollback(self) -> None: ...


class DirectoryGateway(ABC):
    """The engine's identity service, as Nexus calls it for invitations."""

    @abstractmethod
    async def directory(self) -> Directory: ...

    @abstractmethod
    async def provision(
        self, provider: ProviderChoice, email: str, name: str | None, *, by: str | None = None
    ) -> Provisioned | None:
        """Make the person exist at the provider; None when its people are
        managed there (``provisioning: none``). ``by``: the user asking, whose
        right to create accounts at the provider IAM checks (``ProvisioningRefused``
        when they have none); ``None`` is Nexus's own call, for an address the
        organization proved it controls."""


class GrantsGateway(ABC):
    """IAM's pending grants and IdP group bindings, as Nexus writes them: as
    ``api`` on behalf of the inviting person (``by``), so IAM checks that they may
    attach the role and hold what it grants; for nobody when the system invites."""

    @abstractmethod
    async def grant(
        self,
        provider: str,
        email: str,
        policy_id: str,
        scope: str | None,
        *,
        by: str | None = None,
    ) -> GrantMade:
        """The pending grant, and whether this call made it."""

    @abstractmethod
    async def revoke(self, grant_id: str) -> None: ...

    @abstractmethod
    async def attach(
        self, user_id: str, policy_id: str, scope: str, *, by: str | None = None
    ) -> bool:
        """Attach ``policy_id`` at ``scope`` to a Nexus user who exists already,
        as ``api`` on behalf of ``by``: IAM checks that they may attach it and
        hold what it grants. True when this call attached it (it was not)."""

    @abstractmethod
    async def detach(self, user_id: str, policy_id: str, scope: str) -> None:
        """Take back what ``attach`` made (Nexus's own call, for nobody)."""

    @abstractmethod
    async def bind(
        self,
        provider: str,
        claim_value: str,
        policy_id: str,
        scope: str | None,
        *,
        by: str | None = None,
    ) -> None: ...

    @abstractmethod
    async def unbind(
        self, provider: str, claim_value: str, policy_id: str, scope: str | None
    ) -> bool: ...

    @abstractmethod
    async def bindings(self, scopes: Sequence[str]) -> list[IdpBindingView]:
        """The bindings of ``builtin.*`` roles at these scopes."""


@dataclass(frozen=True)
class InvitationMail:
    """What an invitation email says."""

    to_email: str
    provider: ProviderChoice
    inviter_name: str | None
    organization_name: str | None
    organization_role: str | None
    workspace_name: str | None
    workspace_role: str | None
    sign_in_url: str
    managed_in_provider: bool = False
    extra: dict[str, str] = field(default_factory=dict)


class InvitationMailer(ABC):
    @abstractmethod
    async def send(self, mail: InvitationMail) -> bool:
        """True when the email service took it."""
