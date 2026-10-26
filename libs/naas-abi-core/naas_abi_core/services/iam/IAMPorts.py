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

The specification is ``services/iam/AGENTS.md``.
"""

from __future__ import annotations

import os
import time
from abc import ABC, abstractmethod
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Literal

from naas_abi_core.engine.call_context import CallContext
from naas_abi_core.engine.nats_auth import IssuedToken
from naas_abi_core.services.iam.catalog import ActionCatalog, CatalogRegistry
from naas_abi_core.services.iam.names import PLATFORM_SCOPE
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
    """The caller can see the resource but may not perform this action.

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
    # Groups: the org of their owner scope, None for a platform group. A group
    # made before owner scopes may name an org while platform-owned.
    org: str | None = None
    # Service accounts: the user who created them, for scripts and CI.
    owner_id: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    # Groups: the platform (``abi:-:-``), an org (``abi:<org>:-``) or a
    # workspace (``abi:<org>:<ws>``) that owns them and names them. Users and
    # service accounts are the platform's.
    owner_scope: str = PLATFORM_SCOPE

    @property
    def active(self) -> bool:
        return self.status == "active"


@dataclass(frozen=True)
class GroupMapping:
    """An IdP group claim value mapped to an ABI group."""

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
    # The platform (``abi:-:-``), an org (``abi:<org>:-``) or a workspace
    # (``abi:<org>:<ws>``): it names the policy and bounds where it is attached.
    # Managed policies are the platform's.
    owner_scope: str = PLATFORM_SCOPE


@dataclass(frozen=True)
class Attachment:
    """A policy bound to a principal, optionally at a scope."""

    id: str
    policy_id: str
    principal_id: str
    scope: str | None = None
    created_at: datetime | None = None


@dataclass(frozen=True)
class PendingGrant:
    """A policy attached at a scope to someone who has not signed in yet: the
    person an invitation names, by email, on one identity provider.

    It becomes an ``Attachment`` of the user's principal when that user first
    signs in through ``provider`` with this email verified; on no other
    provider and never on an unverified email."""

    id: str
    provider: str
    email: str  # lower case
    policy_id: str
    scope: str | None = None
    created_by: str | None = None  # the principal that granted it
    created_at: datetime | None = None


@dataclass(frozen=True)
class IdpBinding:
    """An IdP group bound to a policy at a scope: the members of the provider's
    group ``claim_value`` hold the policy there. ``group_id`` is the ABI group
    that carries the attachment."""

    provider: str
    claim_value: str
    group_id: str
    policy_id: str
    scope: str | None = None
    attachment_id: str | None = None


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


KeyKind = Literal["service", "personal", "grant"]

# RFC 8693 token exchange: the kinds of subject token.
GRANT_TYPE_TOKEN_EXCHANGE = "urn:ietf:params:oauth:grant-type:token-exchange"
TOKEN_TYPE_JWT = "urn:ietf:params:oauth:token-type:jwt"  # an engine token
TOKEN_TYPE_ID_TOKEN = "urn:ietf:params:oauth:token-type:id_token"  # an IdP's
TOKEN_TYPE_ACCESS_TOKEN = "urn:ietf:params:oauth:token-type:access_token"  # an IdP's
TOKEN_TYPE_API_KEY = "urn:abi:params:oauth:token-type:api_key"  # abi_pk_, abi_gk_
# A signed-in user of a first-party service (Nexus), who that service verified:
# the subject token is the user's principal id.
TOKEN_TYPE_SESSION = "urn:abi:params:oauth:token-type:session"
SUBJECT_TOKEN_TYPES = (
    TOKEN_TYPE_JWT,
    TOKEN_TYPE_ID_TOKEN,
    TOKEN_TYPE_ACCESS_TOKEN,
    TOKEN_TYPE_API_KEY,
    TOKEN_TYPE_SESSION,
)


@dataclass(frozen=True)
class TokenExchange:
    """A token exchange request.

    ``resource``: the discovery resource a token for ``abi:delegated:agent`` is
    for (a module, one of its agents, apps or models); IAM reads the acting
    module off it. ``scope``: the token's ``abi_scope``, a list of Allow
    statements; an exchange only narrows. ``groups`` and ``session_id`` are
    taken from a ``session`` subject only: they are what the first-party
    service verified at sign-in.
    """

    subject_token: str
    subject_token_type: str
    audience: str
    resource: str | None = None
    scope: Sequence[Mapping[str, Any]] | None = None
    groups: Sequence[str] = ()
    session_id: str | None = None
    ttl_seconds: int | None = None


class IdentityAuthenticator(ABC):
    """What IAM asks to read an identity provider's token (``services/identity``
    implements it): who the token is, as an IAM principal id, and the ids of the
    IAM groups the provider's groups claim maps to."""

    @abstractmethod
    def authenticate_token(
        self, token: str, token_type: str
    ) -> tuple[str, tuple[str, ...]]:
        """``(principal id, group ids)``; ``InvalidServiceTokenError`` for a
        token no provider vouches for."""


@dataclass(frozen=True)
class KeyRecord:
    """A key: only ``sha256(secret)`` is stored; the key is shown once.

    ``kind``: ``service`` (``abi_sk_``, a service account's), ``personal``
    (``abi_pk_``, a user's) or ``grant`` (``abi_gk_``, the link of an app or a
    preview, a user's too). A personal or grant key is exchanged for a token of
    its ``audience`` only (``abi:delegated:api-key`` by default for a personal
    key), bound to ``resource`` when it names one, and narrowed by ``scope``
    (a list of Allow statements, the token's ``abi_scope``; ``None`` is no
    narrowing, ``()`` allows nothing).
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
    audience: str | None = None
    resource: str | None = None
    scope: tuple[Mapping[str, Any], ...] | None = None

    def usable(self, now: datetime) -> bool:
        """Neither revoked nor expired at ``now``."""
        if self.revoked_at is not None:
            return False
        return self.expires_at is None or now < self.expires_at


ManifestStatus = Literal["pending", "approved", "rejected", "superseded"]


@dataclass(frozen=True)
class ManifestRecord:
    """A module's permission manifest, one per submitted version.

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
    """The public half and the schedule of a token signing key.

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
    def find_user(self, issuer: str, subject: str) -> PrincipalRecord | None:
        """The user of an identity: the one it was linked to (``link_identity``),
        else the one holding it as its own."""

    @abstractmethod
    def link_identity(self, issuer: str, subject: str, principal_id: str) -> None:
        """Give an existing user one more identity. ``find_user`` then answers
        ``principal_id`` for it, whoever else holds it. Idempotent for the same
        user; ``IAMConflictError`` when the identity is linked to another one or
        the principal is not a user, ``IAMNotFoundError`` for an unknown id."""

    @abstractmethod
    def linked_identities(self, principal_id: str) -> list[tuple[str, str]]:
        """The ``(issuer, subject)`` pairs linked to a user, sorted."""

    @abstractmethod
    def find_service_account(self, name: str) -> PrincipalRecord | None: ...

    @abstractmethod
    def list_principals(
        self,
        kind: PrincipalKind | None = None,
        *,
        limit: int = 100,
        after: str | None = None,
        owner_scopes: Sequence[str] | None = None,
    ) -> Page:
        """Principals by ascending id, strictly after ``after``; with
        ``owner_scopes``, only those owned by one of them."""

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
    def list_policies(
        self,
        *,
        limit: int = 100,
        after: str | None = None,
        owner_scopes: Sequence[str] | None = None,
    ) -> Page:
        """Policies by ascending id, strictly after ``after``; with
        ``owner_scopes``, only those owned by one of them."""

    @abstractmethod
    def update_policy(self, policy: Policy, expected_revision: int) -> Policy:
        """Replace name, description and document (never the owner scope);
        the revision goes up by one.

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

    # -- pending grants -------------------------------------------------------

    @abstractmethod
    def add_pending_grant(self, grant: PendingGrant) -> PendingGrant:
        """``IAMConflictError`` when the same (provider, email, policy, scope)
        exists; ``IAMNotFoundError`` when the policy does not."""

    @abstractmethod
    def list_pending_grants(
        self,
        *,
        provider: str | None = None,
        email: str | None = None,
        policy_id: str | None = None,
    ) -> list[PendingGrant]: ...

    @abstractmethod
    def get_pending_grant(self, grant_id: str) -> PendingGrant | None: ...

    @abstractmethod
    def remove_pending_grant(self, grant_id: str) -> bool:
        """True when the grant was there."""

    @abstractmethod
    def claim_pending_grant(
        self, grant_id: str, principal_id: str, attachment_id: str
    ) -> Attachment | None:
        """Atomically delete the grant and attach its policy to ``principal_id``
        (an attachment that exists is kept). None when another claim, or a
        removal, took the grant first: exactly one caller wins."""

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

    @abstractmethod
    def delete_keys(self, key_ids: Sequence[str]) -> int:
        """Forget keys that can no longer be used (expired or revoked), with
        their narrowing; the number deleted. Housekeeping, not a grant: the
        revision stays. Unknown ids are skipped."""

    # -- token floors ---------------------------------------------------------

    @abstractmethod
    def set_token_floor(self, principal_id: str, not_before: datetime) -> None:
        """Every token of ``principal_id`` issued at or before ``not_before`` is
        revoked. A floor never moves back. ``IAMNotFoundError`` for an unknown
        principal."""

    @abstractmethod
    def token_floors(self) -> dict[str, datetime]:
        """Every principal's floor, by principal id."""

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
    service, which seals them to ``engine``."""

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
    item starts with. ``[""]`` means no prefix can narrow the scan."""

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
    the policy one without touching callers."""

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

    def identity_at(self, principal_id: str, issuer: str) -> str | None:
        """The subject by which an identity provider (``issuer``) names the user,
        its own or a linked one; None when it has none there. In process only."""
        raise NotImplementedError("identity_at runs in the engine that holds IAM")

    def link_user(
        self,
        principal_id: str,
        issuer: str,
        subject: str,
        *,
        provider: str | None = None,
        email: str | None = None,
        email_verified: bool = False,
        display_name: str | None = None,
    ) -> PrincipalRecord:
        """Make ``(issuer, subject)`` one more identity of the user of the
        built-in login ``principal_id`` (``iam:LinkUser``), so that its roles,
        groups and keys follow it to the identity provider. The user the
        identity may already have made (a first sign-in) is merged into it.
        In process only."""
        raise NotImplementedError("link_user runs in the engine that holds IAM")

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
    def create_group(
        self, name: str, *, org: str | None = None, scope: str | None = None
    ) -> PrincipalRecord:
        """A group owned by ``scope`` (``abi:<org>:-`` when only ``org`` is
        given, else the platform)."""

    @abstractmethod
    def get_group(self, group_id: str) -> PrincipalRecord: ...

    @abstractmethod
    def list_groups(
        self, *, limit: int = 100, after: str | None = None, scope: str | None = None
    ) -> Page:
        """The groups the caller may list; with ``scope``, those it owns, plus
        its org's groups at a workspace for whoever lists that workspace's
        attachments."""

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
        self,
        name: str,
        document: Any,
        *,
        description: str = "",
        scope: str | None = None,
    ) -> Policy:
        """A customer policy owned by ``scope`` (the platform when None)."""

    @abstractmethod
    def get_policy(self, policy_id: str) -> Policy: ...

    @abstractmethod
    def list_policies(
        self, *, limit: int = 100, after: str | None = None, scope: str | None = None
    ) -> Page:
        """The policies the caller may list; with ``scope``, those it owns, plus
        those of the levels above that the caller may attach there."""

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

    # -- invitations and IdP group bindings --------------------------

    @abstractmethod
    def create_pending_grant(
        self, provider: str, email: str, policy_id: str, scope: str | None = None
    ) -> PendingGrant:
        """Attach ``policy_id`` at ``scope`` to whoever first signs in through
        ``provider`` with ``email`` verified. Needs the right to attach that
        policy there, like ``attach_policy``. Idempotent."""

    @abstractmethod
    def list_pending_grants(
        self,
        *,
        provider: str | None = None,
        email: str | None = None,
        policy_id: str | None = None,
    ) -> list[PendingGrant]:
        """The grants the caller may list (``iam:ListAttachments`` at their scope)."""

    @abstractmethod
    def revoke_pending_grant(self, grant_id: str) -> bool:
        """Needs the right to detach that policy there."""

    @abstractmethod
    def claim_pending_grants(self, principal_id: str) -> list[Attachment]:
        """Attach what invitations granted to this user: the grants of the
        user's provider and verified email, once. The identity service calls it
        at sign-in (``iam:ClaimPendingGrants``)."""

    @abstractmethod
    def bind_idp_group(
        self, provider: str, claim_value: str, policy_id: str, scope: str | None = None
    ) -> IdpBinding:
        """Give the members of ``provider``'s group ``claim_value`` the policy
        at the scope: an ABI group is mapped to the claim and carries the
        attachment. Needs the right to attach that policy there. Idempotent."""

    @abstractmethod
    def unbind_idp_group(
        self, provider: str, claim_value: str, policy_id: str, scope: str | None = None
    ) -> bool: ...

    @abstractmethod
    def list_idp_bindings(
        self, *, provider: str | None = None, policy_id: str | None = None
    ) -> list[IdpBinding]:
        """The bindings the caller may list (``iam:ListAttachments`` at their scope)."""

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

        Read by the service owning the resource, in process, to apply the placement rules (``AGENTS.md``, "Placements");
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

    def set_platform_grants(self, grants: Sequence[Any]) -> None:
        """The deployment's platform-level resources workspace roles reach (the
        serving engine's IAM only)."""
        raise NotImplementedError("Platform grants are set on the serving engine")

    def put_feature_policies(self, grants: Mapping[str, Sequence[str]]) -> None:
        """Replace the feature policies (``UseFeature`` grants). The
        serving engine's IAM only: Nexus runs there."""
        raise NotImplementedError("Feature policies are set on the serving engine")

    # -- service accounts, keys and manifests ----------------------------------

    @abstractmethod
    def find_service_account(self, name: str) -> PrincipalRecord: ...

    @abstractmethod
    def create_key(
        self,
        principal_id: str,
        *,
        description: str = "",
        expires_at: datetime | None = None,
        kind: KeyKind | None = None,
        audience: str | None = None,
        resource: str | None = None,
        scope: Sequence[Mapping[str, Any]] | None = None,
    ) -> CreatedKey:
        """A new key; its value is in the result only.

        A service account's key is ``service``. A user's is ``personal`` (an
        API key, or a coding environment's with ``audience`` coding and its
        ``resource``) or ``grant`` (the link of an app or a preview, at most 8
        hours). ``scope`` narrows every token the key buys.
        """

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
        # A personal key keeps what it is for: its audience, environment and scope.
        narrowing: dict[str, Any] = {}
        if old.kind != "service":
            narrowing = {
                "kind": old.kind,
                "audience": old.audience,
                "resource": old.resource,
                "scope": old.scope,
            }
        try:
            created = self.create_key(
                principal_id, description=description, **narrowing
            )
        except IAMConflictError:
            self.revoke_key(principal_id, key_id)
            return self.create_key(principal_id, description=description, **narrowing)
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
    def exchange_token(self, request: TokenExchange) -> IssuedToken:
        """A narrow, engine-signed token for an identity that was already
        verified (RFC 8693, §9.4). The requester is the current caller, and
        needs ``iam:ExchangeToken`` on the audience (its own user, when it acts
        for one, does not decide)."""

    @abstractmethod
    def revoke_tokens(self, principal_id: str, *, include_keys: bool = False) -> None:
        """Cut off every token issued so far to or for ``principal_id``
        (delegated ones included), and end its links and coding keys.
        ``include_keys``: its personal API keys too."""

    @abstractmethod
    def jwks(self) -> dict[str, Any]:
        """The engine's public signing keys and issuer. Public."""

    @abstractmethod
    def close(self) -> None: ...
