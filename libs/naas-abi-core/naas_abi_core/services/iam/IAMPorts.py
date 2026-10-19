"""IAM ports, records and errors.

* ``IAMStore``: the secondary port holding principals, groups, policies,
  attachments, placements, scopes and catalogs (SQLite, PostgreSQL, memory).
* ``IAuthorizer``: the decision port, shaped like OpenFGA's API (``check``,
  ``filter``, ``explain``), with a ``policy`` and an ``allow_all`` adapter.
* ``PolicySource``: what the policy authorizer reads, implemented by
  ``IAMService`` over its cached store.
* ``IAMSecrets``: where IAM keeps what must not sit in its own store: the
  token signing keys and the engine's own service key (the secret service,
  under ``iam/``, sealed to ``engine``).

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


class KeyRefusedError(IAMError):
    """A key that cannot be exchanged or connect: unknown, wrong, revoked,
    expired, of another kind, or of an inactive principal. One message for
    every cause: a caller learns nothing about which. Wire code
    ``UNAUTHENTICATED``."""

    def __init__(self, *_: object) -> None:
        super().__init__("invalid key")


class ResourceNotFoundError(IAMNotFoundError):
    """The generic not-found of §5.4, for a service with no not-found of its own."""

    def __init__(self, resource: str = "", *, message: str | None = None) -> None:
        self.resource = resource
        super().__init__(message or f"{resource} not found")


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


KeyKind = Literal["service", "personal"]


@dataclass(frozen=True)
class KeyRecord:
    """A key (RFC §8.1): only ``sha256(secret)`` is stored; the key is shown once.

    ``kind``: ``service`` (``abi_sk_``, a service account's) or ``personal``
    (``abi_pk_``, a user's, from #62).
    """

    key_id: str
    principal_id: str
    secret_hash: str
    kind: KeyKind = "service"
    description: str = ""
    created_at: datetime | None = None
    expires_at: datetime | None = None
    last_used_at: datetime | None = None
    revoked_at: datetime | None = None

    def usable(self, now: datetime) -> bool:
        """Neither revoked nor expired at ``now``."""
        if self.revoked_at is not None:
            return False
        return self.expires_at is None or now < self.expires_at


ManifestStatus = Literal["pending", "approved", "rejected", "superseded"]


@dataclass(frozen=True)
class ManifestRecord:
    """A module's permission manifest, one per submitted version (RFC §8.3).

    ``document`` is the submitted policy document (JSON form), variables
    unsubstituted. An approved version is also the managed policy
    ``module.<project>.<module_id>``, possibly narrowed by the admin: that
    policy, not this record, is what grants.
    """

    principal_id: str
    sha256: str
    module_id: str
    project: str
    document: dict[str, Any]
    status: ManifestStatus = "pending"
    submitted_at: datetime | None = None
    decided_at: datetime | None = None
    decided_by: str | None = None
    reason: str = ""


@dataclass(frozen=True)
class CreatedKey:
    """A new key: ``value`` is shown once and never stored."""

    record: KeyRecord
    value: str = field(repr=False)


@dataclass(frozen=True)
class ManifestSubmission:
    """What a module learns when it submits its manifest.

    ``approved_now``: this submission changed the account's approved policy
    (auto-approval), so a connection opened before it carries older broker
    permissions and should reconnect.
    """

    manifest: ManifestRecord
    approved_now: bool = False
    # An approved version (this one or an earlier one) grants now.
    in_force: bool = False


@dataclass(frozen=True)
class SigningKeyRecord:
    """The public half and the schedule of a token signing key (RFC §9.1).

    It is published from ``created_at``, signs from ``activates_at``, and
    stays published until ``retires_at`` (set when a newer key takes over).
    The private half lives in ``IAMSecrets``, never in the store.
    """

    kid: str
    public_jwk: dict[str, Any]
    created_at: datetime
    activates_at: datetime
    retires_at: datetime | None = None


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

    # -- keys -----------------------------------------------------------------

    @abstractmethod
    def create_key(self, record: KeyRecord) -> KeyRecord:
        """``IAMConflictError`` for a taken key id; ``IAMNotFoundError`` when
        the principal does not exist."""

    @abstractmethod
    def get_key(self, key_id: str) -> KeyRecord: ...

    @abstractmethod
    def list_keys(self, principal_id: str | None = None) -> list[KeyRecord]:
        """By creation time, then key id."""

    @abstractmethod
    def revoke_key(self, key_id: str, at: datetime) -> KeyRecord:
        """Set ``revoked_at`` once; revoking again keeps the first time."""

    @abstractmethod
    def touch_key(self, key_id: str, at: datetime) -> None:
        """Record ``last_used_at``. Bookkeeping, not a grant: the revision stays."""

    # -- manifests --------------------------------------------------------------

    @abstractmethod
    def put_manifest(self, record: ManifestRecord) -> ManifestRecord:
        """Create or replace the manifest ``(principal_id, sha256)``."""

    @abstractmethod
    def get_manifest(self, principal_id: str, sha256: str) -> ManifestRecord: ...

    @abstractmethod
    def list_manifests(
        self, principal_id: str | None = None, status: ManifestStatus | None = None
    ) -> list[ManifestRecord]:
        """By submission time."""

    # -- signing keys -------------------------------------------------------------

    @abstractmethod
    def add_signing_key(self, record: SigningKeyRecord) -> None:
        """``IAMConflictError`` for a taken kid."""

    @abstractmethod
    def list_signing_keys(self) -> list[SigningKeyRecord]:
        """By creation time."""

    @abstractmethod
    def retire_signing_key(self, kid: str, retires_at: datetime) -> None:
        """Set ``retires_at`` unless it is already set."""

    # -- store ----------------------------------------------------------------

    @abstractmethod
    def revision(self) -> int:
        """Goes up on every write. Caches compare it to drop stale entries."""

    @abstractmethod
    def install_id(self) -> str:
        """Generated on first use and kept: the engine issuer's install id (§9.1)."""

    @abstractmethod
    def close(self) -> None: ...


class IAMSecrets(ABC):
    """IAM's secrets outside its store: names under ``iam/`` in the secret
    service, which seals them to ``engine`` (RFC §11.3)."""

    @abstractmethod
    def get(self, name: str) -> str | None: ...

    @abstractmethod
    def put(self, name: str, value: str) -> None: ...

    @abstractmethod
    def delete(self, name: str) -> None:
        """Idempotent."""


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
    """A resource pattern only ``owner`` (a service-account name) may ever reach.

    ``module_id``: the module account of that id (``module/<project>/<id>``) owns
    it too. The built-in IdP runs as a module, so its seals name module ``idp``
    beside the built-in account of that name. Module ids are the admin's to hand
    out: nothing else makes an account of that name.
    """

    pattern: str
    owner: str
    module_id: str | None = None


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

    def allows_every(
        self, ctx: CallContext, action: str, service: str, resource_type: str
    ) -> bool:
        """Whether ``ctx`` may perform ``action`` on every resource of the type,
        whatever its id and placement. A shortcut for whole-store reads: False
        whenever unsure, so a caller falls back to ``check`` and ``filter``."""
        return False


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

    def allows_every(self, action: str, service: str, resource_type: str) -> bool:
        """Whether the caller may perform ``action`` on every resource of
        ``service``'s ``resource_type``; False whenever unsure."""
        return False

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
    def placement_of(self, service: str, canonical_id: str) -> Placement | None:
        """The placement covering a resource (exact key, else the longest
        prefix), or None when none does: a new top-level name or container.

        Read by the service owning the resource, in process, to apply RFC §4.4;
        it is not an authorization decision and needs no action.
        """

    def resolve_placement(self, service: str, canonical_id: str) -> tuple[str, str]:
        """``(org, workspace)`` of a resource; the platform when nothing covers it."""
        placement = self.placement_of(service, canonical_id)
        return (placement.org, placement.workspace) if placement else ("-", "-")

    @abstractmethod
    def put_scope(self, org: str, workspace: str = "-") -> ScopeRecord: ...

    @abstractmethod
    def workspace_org(self, workspace: str) -> str | None:
        """The org a workspace was registered in (``iam:PutScope``), or None."""

    @abstractmethod
    def delete_scope(self, org: str, workspace: str = "-") -> bool: ...

    @abstractmethod
    def register_catalog(self, catalog: Any) -> bool: ...

    # -- service accounts, keys and manifests (RFC §8) ----------------------------------

    @abstractmethod
    def find_service_account(self, name: str) -> PrincipalRecord: ...

    @abstractmethod
    def create_key(
        self,
        principal_id: str,
        *,
        description: str = "",
        expires_at: datetime | None = None,
    ) -> CreatedKey: ...

    @abstractmethod
    def list_keys(self, principal_id: str) -> list[KeyRecord]: ...

    @abstractmethod
    def revoke_key(self, principal_id: str, key_id: str) -> KeyRecord: ...

    def rotate_key(
        self, principal_id: str, key_id: str, *, description: str | None = None
    ) -> CreatedKey:
        """A new key, then the old one revoked: deploy the new value at once.

        The new key has the default life of a new key, not what was left of
        the old one's (a key rotated late, or already expired, still gets a
        full one). An account at its limit of active keys revokes the old key
        first: the rotation would otherwise be refused exactly when the
        account has no key to spare.
        """
        old = next(
            (k for k in self.list_keys(principal_id) if k.key_id == key_id), None
        )
        if old is None:
            raise IAMNotFoundError(f"Key {key_id} not found")
        description = old.description if description is None else description
        try:
            created = self.create_key(principal_id, description=description)
        except IAMConflictError:
            self.revoke_key(principal_id, key_id)
            return self.create_key(principal_id, description=description)
        self.revoke_key(principal_id, key_id)
        return created

    @abstractmethod
    def submit_manifest(
        self, module_id: str, project: str, document: Any
    ) -> ManifestSubmission: ...

    @abstractmethod
    def get_manifest(
        self, principal_id: str, sha256: str | None = None
    ) -> ManifestRecord: ...

    @abstractmethod
    def list_manifests(
        self, *, principal_id: str | None = None, status: ManifestStatus | None = None
    ) -> list[ManifestRecord]: ...

    @abstractmethod
    def approve_manifest(
        self, principal_id: str, sha256: str | None = None, *, document: Any = None
    ) -> ManifestRecord: ...

    @abstractmethod
    def reject_manifest(
        self, principal_id: str, sha256: str | None = None, *, reason: str = ""
    ) -> ManifestRecord: ...

    @abstractmethod
    def jwks(self) -> dict[str, Any]:
        """The engine's public signing keys and issuer. Public."""

    @abstractmethod
    def close(self) -> None: ...
