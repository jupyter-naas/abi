"""IAM ports, records and errors.

* ``IAMStore``: the secondary port holding principals, groups, policies,
  attachments, placements, scopes and catalogs (SQLite, PostgreSQL, memory).
* ``IAuthorizer``: the decision port, shaped like OpenFGA's API (``check``,
  ``filter``, ``explain``), with a ``policy`` and an ``allow_all`` adapter.
* ``PolicySource``: what the policy authorizer reads, implemented by
  ``IAMService`` over its cached store.

See docs/specs/rfcs/20261013_identity-and-authorization.md, §2, §3, §5 and §11.
"""

from __future__ import annotations

import os
import time
from abc import ABC, abstractmethod
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Literal

from naas_abi_core.engine.call_context import CallContext
from naas_abi_core.services.iam.catalog import ActionCatalog, CatalogRegistry
from naas_abi_core.services.iam.policy import PolicyDocument, Statement

PrincipalKind = Literal["user", "group", "service_account"]
Status = Literal["active", "suspended", "deleted"]
Reason = Literal["allow", "explicit_deny", "implicit_deny", "suspended", "sealed"]

KIND_PREFIXES: dict[PrincipalKind, str] = {
    "user": "usr",
    "group": "grp",
    "service_account": "sa",
}

_CROCKFORD = "0123456789abcdefghjkmnpqrstvwxyz"


def new_ulid() -> str:
    """A lowercase ULID: 48 bits of milliseconds, 80 random bits, 26 characters."""
    value = (int(time.time() * 1000) << 80) | int.from_bytes(os.urandom(10), "big")
    chars = []
    for _ in range(26):
        chars.append(_CROCKFORD[value & 31])
        value >>= 5
    return "".join(reversed(chars))


def new_id(prefix: str) -> str:
    """``<prefix>_<ulid>``: ``usr_``, ``grp_``, ``sa_``, ``pol_``, ``att_``."""
    return f"{prefix}_{new_ulid()}"


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class IAMError(Exception):
    """Base of IAM's own errors."""


class IAMNotFoundError(IAMError, LookupError):
    """An IAM record does not exist (or the caller may not know it does)."""


class IAMConflictError(IAMError):
    """A uniqueness rule refused the write (same user, name or attachment)."""


class RevisionConflictError(IAMError):
    """A policy changed since the revision the update was based on."""


class PermissionDeniedError(IAMError, PermissionError):
    """The caller can see the resource but may not perform this action (RFC §5.4).

    Wire code ``PERMISSION_DENIED``. A caller who cannot see the resource at
    all gets the service's own not-found error instead.
    """

    def __init__(
        self, action: str = "", resource: str = "", *, message: str | None = None
    ) -> None:
        self.action = action
        self.resource = resource
        super().__init__(message or f"{action} is not allowed on {resource}")


class ResourceNotFoundError(IAMNotFoundError):
    """The generic not-found of §5.4, for a service with no not-found of its own."""

    def __init__(self, resource: str) -> None:
        self.resource = resource
        super().__init__(f"{resource} not found")


# ---------------------------------------------------------------------------
# Records
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PrincipalRecord:
    """A user, a group or a service account. Ids never change and are never reused."""

    id: str
    kind: PrincipalKind
    status: Status = "active"
    # Service accounts: their unique name ("engine", "module/acme/people").
    # Groups: their display name. Users: none.
    name: str | None = None
    # Users: the verified IdP identity, unique together.
    issuer: str | None = None
    subject: str | None = None
    # Users, informational: the provider name and the last seen profile.
    provider: str | None = None
    email: str | None = None
    email_verified: bool = False
    display_name: str | None = None
    # Groups: the org they belong to, None for a platform group.
    org: str | None = None
    # Service accounts: the user who created them, for scripts and CI.
    owner_id: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    @property
    def active(self) -> bool:
        return self.status == "active"


@dataclass(frozen=True)
class GroupMapping:
    """An IdP group claim value mapped to an ABI group (RFC §2)."""

    provider: str
    claim_value: str
    group_id: str


@dataclass(frozen=True)
class Policy:
    id: str
    name: str
    document: PolicyDocument
    description: str = ""
    managed: bool = False
    revision: int = 1
    created_at: datetime | None = None
    updated_at: datetime | None = None


@dataclass(frozen=True)
class Attachment:
    """A policy bound to a principal, optionally at a scope (RFC §3.4)."""

    id: str
    policy_id: str
    principal_id: str
    scope: str | None = None
    created_at: datetime | None = None


@dataclass(frozen=True)
class Placement:
    """``(service, id_key) -> (org, workspace)``; ``id_key`` is exact or ends with ``*``."""

    service: str
    id_key: str
    org: str = "-"
    workspace: str = "-"


@dataclass(frozen=True)
class ScopeRecord:
    """An org (``workspace`` is ``-``) or a workspace in an org, from ``iam:PutScope``."""

    org: str
    workspace: str = "-"


@dataclass(frozen=True)
class Page:
    items: list[Any]
    next_after: str | None = None


# ---------------------------------------------------------------------------
# Secondary port: the store
# ---------------------------------------------------------------------------


class IAMStore(ABC):
    """IAM's own SQL store. It is not the Document Service: IAM authorizes that.

    Every write bumps the store's revision in the same transaction. Errors:
    ``IAMNotFoundError``, ``IAMConflictError`` and ``RevisionConflictError``.
    """

    # -- principals ---------------------------------------------------------

    @abstractmethod
    def create_principal(self, record: PrincipalRecord) -> PrincipalRecord:
        """Store a new principal; ``IAMConflictError`` when its id, its
        ``(issuer, subject)`` or its service-account name is taken."""

    @abstractmethod
    def get_principal(self, principal_id: str) -> PrincipalRecord: ...

    @abstractmethod
    def find_user(self, issuer: str, subject: str) -> PrincipalRecord | None: ...

    @abstractmethod
    def find_service_account(self, name: str) -> PrincipalRecord | None: ...

    @abstractmethod
    def list_principals(
        self,
        kind: PrincipalKind | None = None,
        *,
        limit: int = 100,
        after: str | None = None,
    ) -> Page:
        """Principals by ascending id, strictly after ``after``."""

    @abstractmethod
    def update_principal(self, record: PrincipalRecord) -> PrincipalRecord:
        """Replace a principal's mutable fields (everything but id, kind,
        issuer, subject and created_at)."""

    # -- groups -------------------------------------------------------------

    @abstractmethod
    def add_group_member(self, group_id: str, member_id: str) -> None:
        """Idempotent."""

    @abstractmethod
    def remove_group_member(self, group_id: str, member_id: str) -> bool:
        """True when the member was there."""

    @abstractmethod
    def list_group_members(self, group_id: str) -> list[str]: ...

    @abstractmethod
    def groups_of(self, member_id: str) -> list[str]:
        """The static groups ``member_id`` belongs to."""

    @abstractmethod
    def map_idp_group(self, mapping: GroupMapping) -> None:
        """Idempotent."""

    @abstractmethod
    def unmap_idp_group(self, mapping: GroupMapping) -> bool: ...

    @abstractmethod
    def list_idp_group_mappings(
        self, group_id: str | None = None
    ) -> list[GroupMapping]: ...

    @abstractmethod
    def resolve_idp_groups(
        self, provider: str, claim_values: Iterable[str]
    ) -> list[str]:
        """The group ids ``claim_values`` of ``provider`` map to, sorted, unique."""

    # -- policies -----------------------------------------------------------

    @abstractmethod
    def create_policy(self, policy: Policy) -> Policy:
        """Store a new policy at revision 1; ``IAMConflictError`` for a taken id."""

    @abstractmethod
    def get_policy(self, policy_id: str) -> Policy: ...

    @abstractmethod
    def list_policies(self, *, limit: int = 100, after: str | None = None) -> Page: ...

    @abstractmethod
    def update_policy(self, policy: Policy, expected_revision: int) -> Policy:
        """Replace name, description and document; the revision goes up by one.

        ``RevisionConflictError`` when the stored revision is not
        ``expected_revision``.
        """

    @abstractmethod
    def put_managed_policy(self, policy: Policy) -> Policy:
        """Create or replace a managed policy. The revision goes up only when
        its name, description or document changed."""

    @abstractmethod
    def delete_policy(self, policy_id: str) -> None:
        """``IAMConflictError`` while the policy is attached."""

    # -- attachments --------------------------------------------------------

    @abstractmethod
    def attach(self, attachment: Attachment) -> Attachment:
        """``IAMConflictError`` when the same (policy, principal, scope) exists;
        ``IAMNotFoundError`` when the policy or the principal does not."""

    @abstractmethod
    def detach(self, policy_id: str, principal_id: str, scope: str | None) -> bool:
        """True when the attachment was there."""

    @abstractmethod
    def list_attachments(
        self, *, principal_id: str | None = None, policy_id: str | None = None
    ) -> list[Attachment]: ...

    @abstractmethod
    def attachments_for(self, principal_ids: Sequence[str]) -> list[Attachment]:
        """Every attachment of any of ``principal_ids`` (a principal and its groups)."""

    # -- placements and scopes ----------------------------------------------

    @abstractmethod
    def put_placement(self, placement: Placement) -> None:
        """Create or replace the placement of ``(service, id_key)``."""

    @abstractmethod
    def delete_placement(self, service: str, id_key: str) -> bool: ...

    @abstractmethod
    def list_placements(self, service: str | None = None) -> list[Placement]: ...

    @abstractmethod
    def put_scope(self, scope: ScopeRecord) -> None:
        """Idempotent. A workspace keeps its first org: ``IAMConflictError``
        when it is registered under another."""

    @abstractmethod
    def delete_scope(self, org: str, workspace: str = "-") -> bool: ...

    @abstractmethod
    def list_scopes(self, org: str | None = None) -> list[ScopeRecord]: ...

    # -- catalogs -----------------------------------------------------------

    @abstractmethod
    def put_catalog(self, catalog: ActionCatalog) -> None:
        """Create or replace the stored catalog of ``catalog.service``."""

    @abstractmethod
    def list_catalogs(self) -> list[ActionCatalog]: ...

    # -- store ----------------------------------------------------------------

    @abstractmethod
    def revision(self) -> int:
        """Goes up on every write. Caches compare it to drop stale entries."""

    @abstractmethod
    def install_id(self) -> str:
        """Generated on first use and kept: the engine issuer's install id (§9.1)."""

    @abstractmethod
    def close(self) -> None: ...


# ---------------------------------------------------------------------------
# Decisions
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class EffectiveStatement:
    """A statement as it reaches a principal: through which policy and attachment."""

    statement: Statement
    policy_id: str
    statement_index: int
    attachment_id: str | None = None  # None for an implicit attachment (builtin.self)
    scope: str | None = None
    via_group: str | None = None


@dataclass(frozen=True)
class Subject:
    """What the evaluator knows of one principal of a call."""

    principal_id: str  # as the call names it: ${principal.id}
    status: Status
    statements: tuple[EffectiveStatement, ...] = ()


@dataclass(frozen=True)
class DecidingStatement:
    """Which statement decided, and whose it was: the actor's, the user's or the token's."""

    side: Literal["actor", "user", "token"]
    principal_id: str
    effect: str
    policy_id: str | None
    statement_index: int
    sid: str | None = None
    attachment_id: str | None = None
    scope: str | None = None
    via_group: str | None = None


@dataclass(frozen=True)
class Decision:
    """``allowed``; ``visible`` tells a denied caller's "not found" from "denied"."""

    allowed: bool
    visible: bool
    reason: Reason


@dataclass(frozen=True)
class FilterResult:
    """The allowed items, in input order, and the literal prefixes every allowed
    item starts with (RFC §5.5). ``[""]`` means no prefix can narrow the scan."""

    allowed: list[str]
    prefix_hints: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class Explanation:
    allowed: bool
    reason: Reason
    action: str
    resource: str
    statement: DecidingStatement | None = None


@dataclass(frozen=True)
class Seal:
    """A resource pattern only ``owner`` (a service-account name) may ever reach."""

    pattern: str
    owner: str


# ---------------------------------------------------------------------------
# Authorizer port
# ---------------------------------------------------------------------------


class IAuthorizer(ABC):
    """Shaped like OpenFGA's API, so a relationship-based adapter can replace
    the policy one without touching callers (RFC §11.2)."""

    name: str

    @abstractmethod
    def check(self, ctx: CallContext, action: str, resource: str) -> Decision: ...

    @abstractmethod
    def filter(
        self, ctx: CallContext, action: str, resources: Iterable[str]
    ) -> FilterResult: ...

    @abstractmethod
    def explain(self, ctx: CallContext, action: str, resource: str) -> Explanation: ...


class PolicySource(ABC):
    """The policy authorizer's view of IAM's state, cached by ``IAMService``."""

    @abstractmethod
    def subject(
        self, ctx: CallContext, side: Literal["actor", "user"]
    ) -> Subject | None:
        """The actor or the OBO user of ``ctx`` (None when the call has no user)."""

    @abstractmethod
    def seals(self) -> Sequence[Seal]: ...

    @property
    @abstractmethod
    def catalogs(self) -> CatalogRegistry: ...


# ---------------------------------------------------------------------------
# What callers use: the in-process service, or a NATS client of it
# ---------------------------------------------------------------------------


class IIAMService(ABC):
    """IAM as its callers see it, in process (``IAMService``) or over NATS
    (``IAMSecondaryAdapterNATSClient``, for engines in the client role).

    Decisions are about the current ``CallContext``; over NATS, the caller the
    server verifies from the request's credentials.
    """

    # -- decisions ------------------------------------------------------------

    @abstractmethod
    def authorize(self, action: str, resource: str) -> Decision: ...

    def require(
        self,
        action: str,
        resource: str,
        *,
        not_found: Callable[[], BaseException] | None = None,
    ) -> None:
        """Raise unless the caller may perform ``action`` on ``resource`` (§5.4).

        A caller who can see the resource gets ``PermissionDeniedError``; anyone
        else gets ``not_found()`` (the service's own not-found error), exactly as
        if the resource did not exist; ``ResourceNotFoundError`` by default.
        """
        decision = self.authorize(action, resource)
        if decision.allowed:
            return
        if decision.visible:
            raise PermissionDeniedError(action, resource)
        raise not_found() if not_found is not None else ResourceNotFoundError(resource)

    @abstractmethod
    def filter(self, action: str, resources: Iterable[str]) -> FilterResult: ...

    @abstractmethod
    def explain(
        self, action: str, resource: str, *, principal_id: str | None = None
    ) -> Explanation: ...

    # -- principals -------------------------------------------------------------

    @abstractmethod
    def ensure_user(
        self,
        issuer: str,
        subject: str,
        *,
        provider: str | None = None,
        email: str | None = None,
        email_verified: bool = False,
        display_name: str | None = None,
    ) -> PrincipalRecord: ...

    @abstractmethod
    def create_service_account(
        self, name: str, *, owner_id: str | None = None
    ) -> PrincipalRecord: ...

    @abstractmethod
    def get_principal(self, principal_id: str) -> PrincipalRecord: ...

    @abstractmethod
    def list_principals(
        self,
        kind: PrincipalKind | None = None,
        *,
        limit: int = 100,
        after: str | None = None,
    ) -> Page: ...

    @abstractmethod
    def suspend_principal(self, principal_id: str) -> PrincipalRecord: ...

    @abstractmethod
    def resume_principal(self, principal_id: str) -> PrincipalRecord: ...

    @abstractmethod
    def delete_principal(self, principal_id: str) -> PrincipalRecord: ...

    # -- groups -----------------------------------------------------------------

    @abstractmethod
    def create_group(self, name: str, *, org: str | None = None) -> PrincipalRecord: ...

    @abstractmethod
    def get_group(self, group_id: str) -> PrincipalRecord: ...

    @abstractmethod
    def list_groups(self, *, limit: int = 100, after: str | None = None) -> Page: ...

    @abstractmethod
    def delete_group(self, group_id: str) -> PrincipalRecord: ...

    @abstractmethod
    def add_group_member(self, group_id: str, member_id: str) -> None: ...

    @abstractmethod
    def remove_group_member(self, group_id: str, member_id: str) -> bool: ...

    @abstractmethod
    def list_group_members(self, group_id: str) -> list[str]: ...

    @abstractmethod
    def map_idp_group(
        self, provider: str, claim_value: str, group_id: str
    ) -> GroupMapping: ...

    @abstractmethod
    def unmap_idp_group(
        self, provider: str, claim_value: str, group_id: str
    ) -> bool: ...

    @abstractmethod
    def list_idp_group_mappings(self, group_id: str) -> list[GroupMapping]: ...

    # -- policies and attachments -------------------------------------------------

    @abstractmethod
    def create_policy(
        self, name: str, document: Any, *, description: str = ""
    ) -> Policy: ...

    @abstractmethod
    def get_policy(self, policy_id: str) -> Policy: ...

    @abstractmethod
    def list_policies(self, *, limit: int = 100, after: str | None = None) -> Page: ...

    @abstractmethod
    def update_policy(
        self,
        policy_id: str,
        *,
        expected_revision: int,
        document: Any = None,
        name: str | None = None,
        description: str | None = None,
    ) -> Policy: ...

    @abstractmethod
    def delete_policy(self, policy_id: str) -> None: ...

    @abstractmethod
    def attach_policy(
        self, policy_id: str, principal_id: str, scope: str | None = None
    ) -> Attachment: ...

    @abstractmethod
    def detach_policy(
        self, policy_id: str, principal_id: str, scope: str | None = None
    ) -> bool: ...

    @abstractmethod
    def list_attachments(
        self, *, principal_id: str | None = None, policy_id: str | None = None
    ) -> list[Attachment]: ...

    # -- placements, scopes, catalogs ----------------------------------------------

    @abstractmethod
    def put_placement(
        self, service: str, id_key: str, org: str = "-", workspace: str = "-"
    ) -> Placement: ...

    @abstractmethod
    def delete_placement(self, service: str, id_key: str) -> bool: ...

    @abstractmethod
    def list_placements(self, service: str | None = None) -> list[Placement]: ...

    @abstractmethod
    def put_scope(self, org: str, workspace: str = "-") -> ScopeRecord: ...

    @abstractmethod
    def delete_scope(self, org: str, workspace: str = "-") -> bool: ...

    @abstractmethod
    def register_catalog(self, catalog: Any) -> bool: ...

    @abstractmethod
    def close(self) -> None: ...
