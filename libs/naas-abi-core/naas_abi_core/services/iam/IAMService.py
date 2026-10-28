"""The IAM domain service: who may do what, for every kernel service.

Domain services call ``require`` and ``filter``; both read the caller from the
current ``CallContext`` (never from a request field). IAM authorizes its own
operations with its own ``iam:*`` catalog, like any other service.

Effective policies are cached per principal for at most ``cache_ttl_seconds``
(60 by default) and dropped on every change made through this
service. Change listeners (the NATS primary) hear each new store revision.
"""

from __future__ import annotations

import re
import threading
import time
from collections import OrderedDict
from collections.abc import Callable, Iterable, Iterator, Mapping, Sequence
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from functools import partial
from typing import Any, Literal, NoReturn, TypeVar

from naas_abi_core import logger
from naas_abi_core.engine.call_context import (
    FIRST_PARTY_ACCOUNTS,
    CallContext,
    as_service_account,
    current_call_context,
)
from naas_abi_core.engine.call_context import (
    Principal as CallPrincipal,
)
from naas_abi_core.engine.nats_auth import (
    API_KEY_AUDIENCE,
    APP_AUDIENCE,
    CODING_AUDIENCE,
    DELEGATED_AUDIENCES,
    KERNEL_AUDIENCES,
    NATS_AUDIENCE,
    PREVIEW_AUDIENCE,
    SESSION_AUDIENCE,
    IssuedToken,
    JWKSVerifier,
    TokenClaims,
    host_audience,
    issuable_audience,
)
from naas_abi_core.services.iam import (
    broker,
    grants,
    keys,
    module_scopes,
    modules,
    roles,
    sets,
)
from naas_abi_core.services.iam.adapters.secondary.authorizer__policy import (
    PolicyAuthorizer,
)
from naas_abi_core.services.iam.catalog import (
    ActionCatalog,
    CatalogRegistry,
    removed_actions,
)
from naas_abi_core.services.iam.evaluator import token_statements
from naas_abi_core.services.iam.exchange import TokenExchanger
from naas_abi_core.services.iam.iam_catalog import CATALOG, SEALS
from naas_abi_core.services.iam.IAMPorts import (
    KIND_PREFIXES,
    Attachment,
    Bound,
    CreatedKey,
    Decision,
    EffectiveStatement,
    Explanation,
    FilterResult,
    GrantableCatalog,
    GrantNotHeldError,
    GroupMapping,
    IAMConflictError,
    IAMNotFoundError,
    IAMSecrets,
    IAMStore,
    IAuthorizer,
    IdentityAuthenticator,
    IdpBinding,
    IIAMService,
    KeyKind,
    KeyRecord,
    KeyRefusedError,
    ManifestRecord,
    ManifestStatus,
    ManifestSubmission,
    Page,
    PendingGrant,
    PermissionDeniedError,
    Placement,
    Policy,
    PolicySource,
    PrincipalKind,
    PrincipalRecord,
    ScopeRecord,
    ScopeSet,
    Seal,
    Subject,
    TokenExchange,
    new_id,
)
from naas_abi_core.services.iam.names import (
    ALL_ORGS,
    ALL_WORKSPACES,
    NONE,
    PLATFORM_SCOPE,
    owner_ancestors,
    resource_name,
    scope_fields,
    scope_name,
    validate_owner_scope,
    validate_scope,
    within_owner,
)
from naas_abi_core.services.iam.policy import (
    MAX_DEPTH,
    SCOPE_PREFIX,
    PolicyDocument,
    PolicyValidationError,
    Statement,
    bind_variables,
    check_owned_document,
    parse_policy_document,
    within_scope,
)
from naas_abi_core.services.iam.sets import (
    SetValidationError,
    intersect,
    normalize,
    outside,
    read_resource,
    write_resource,
)
from naas_abi_core.services.iam.tokens import TokenIssuer, normalize_scope

# The legacy issuer of the accounts of the old Nexus login, kept while they
# link to an identity provider: such a user is named on a call by its Nexus
# user id. IAM records it as a user of this issuer, subject = that id.
LEGACY_NEXUS_ISSUER = "urn:abi:nexus"

_PRINCIPAL_ID = re.compile(r"^(usr|grp|sa)_[0-9a-z]{26}$")
_FEATURE_NAME = re.compile(r"^[a-z][a-z0-9_]{0,63}$")
_T = TypeVar("_T")

AuthorizerFactory = Callable[[PolicySource], IAuthorizer]


def principal_resource(principal_id: str) -> str:
    return resource_name("iam", "principal", principal_id)


def _owned_resource(type_name: str, item_id: str, owner_scope: str) -> str:
    """A policy or a group, named at the org or workspace that owns it,
    ``abi:<org>:<ws>:iam:<type>/<id>``. The platform's are ``abi:%2A:%2A:…``
    (``ALL_ORGS``), like unscoped attachments: no ``${scope}`` expands to it,
    the platform scope ``abi:-:-`` included, so a role attached anywhere never
    reaches a platform policy, which may be attached unscoped."""
    org, workspace = scope_fields(owner_scope)
    if owner_scope == PLATFORM_SCOPE:
        org, workspace = ALL_ORGS, ALL_WORKSPACES
    return resource_name("iam", type_name, item_id, org=org, workspace=workspace)


def group_resource(group_id: str, owner_scope: str = PLATFORM_SCOPE) -> str:
    return _owned_resource("group", group_id, owner_scope)


def policy_resource(policy_id: str, owner_scope: str = PLATFORM_SCOPE) -> str:
    return _owned_resource("policy", policy_id, owner_scope)


def attachment_resource(policy_id: str, principal_id: str, scope: str | None) -> str:
    """Named at the attachment's scope (§6.4), so no ``${scope}`` grant reaches
    past its scope.

    * An org-wide one (``abi:<org>:*``) is in workspace ``%2A``
      (``ALL_WORKSPACES``): an ``abi:<org>:*`` grant reaches it, an org-level
      ``abi:<org>:-`` one does not, so an org admin cannot widen itself to every
      workspace.
    * An unscoped one is ``abi:%2A:%2A:…`` (``ALL_ORGS``): no ``${scope}``
      expands to it, the platform scope ``abi:-:-`` included, so only grants
      written for every org (the platform admin's) attach or detach policies
      that apply everywhere.
    """
    if scope is None:
        org, workspace = ALL_ORGS, ALL_WORKSPACES
    else:
        org, workspace = scope_fields(scope)
        if workspace == "*":
            workspace = ALL_WORKSPACES
    return resource_name(
        "iam",
        "attachment",
        [policy_id, principal_id],
        kind="path",
        org=org,
        workspace=workspace,
    )


_PROVIDER_NAME = re.compile(r"^[a-z0-9-]{1,32}$")


def _grantee(provider: str, value: str, *, email: bool = True) -> tuple[str, str]:
    """A provider name, and an email (lower case) or a groups claim value."""
    if not _PROVIDER_NAME.match(provider or ""):
        raise ValueError(f"{provider!r} is not a provider name")
    value = (value or "").strip()
    if email:
        value = value.lower()
        if "@" not in value[1:-1] or any(c.isspace() for c in value):
            raise ValueError(f"{value!r} is not an email address")
    elif not value:
        raise ValueError("A binding names a groups claim value")
    return provider, value


def _invitee(provider: str, email: str) -> str:
    """The principal part of a pending grant's resource: who is not here yet."""
    return f"pending:{provider}:{email}"


def _bound_group(provider: str, claim_value: str) -> str:
    """The name of the ABI group an IdP group's binding is carried by."""
    return f"idp:{provider}:{claim_value}"


def _grant_resource(grant: PendingGrant) -> str:
    return attachment_resource(
        grant.policy_id, _invitee(grant.provider, grant.email), grant.scope
    )


def key_resource(principal_id: str, key_id: str) -> str:
    return resource_name("iam", "key", [principal_id, key_id], kind="path")


def manifest_resource(principal_id: str) -> str:
    return resource_name("iam", "manifest", principal_id)


def placement_resource(service: str, id_key: str) -> str:
    return resource_name("iam", "placement", [service, id_key], kind="path")


def scope_resource(org: str, workspace: str = NONE) -> str:
    parts = [org] if workspace == NONE else [org, workspace]
    return resource_name("iam", "scope", parts, kind="path")


def catalog_resource(service: str) -> str:
    return resource_name("iam", "catalog", service)


# The engine's own service key, for its client-role engines: they
# exchange it like any other key. Sealed to engine, like every iam/ secret.
ENGINE_KEY_SECRET = "iam/service-keys/engine"
# The key the engine seals the job triggers it stores with (HMAC-SHA256).
TRIGGER_SEAL_SECRET = "iam/job-trigger-seal"
TRIGGER_SEAL_VERSION = "v1"
ENGINE_KEY_DESCRIPTION = "client-role engines"
_LAST_USED_RESOLUTION = timedelta(minutes=1)
_CI_KEY_EXPIRY = timedelta(days=90)


class _TTLCache:
    """A bounded LRU whose entries expire.

    ``clear`` bumps a generation: a value computed while a clear happened is
    returned to its caller but never stored, so a change cannot be undone by a
    lookup that read the store just before it.
    """

    def __init__(self, ttl_seconds: float, size: int) -> None:
        self._ttl = ttl_seconds
        self._size = size
        self._entries: OrderedDict[Any, tuple[float, Any]] = OrderedDict()
        self._generation = 0
        self._lock = threading.Lock()

    def get(self, key: Any, compute: Callable[[], _T]) -> _T:
        now = time.monotonic()
        with self._lock:
            found = self._entries.get(key)
            if found is not None and found[0] > now:
                self._entries.move_to_end(key)
                return found[1]
            generation = self._generation
        value = compute()
        with self._lock:
            if generation != self._generation:
                return value
            self._entries[key] = (now + self._ttl, value)
            self._entries.move_to_end(key)
            while len(self._entries) > self._size:
                self._entries.popitem(last=False)
        return value

    def clear(self) -> None:
        with self._lock:
            self._generation += 1
            self._entries.clear()


class IAMService(IIAMService, PolicySource):
    def __init__(
        self,
        store: IAMStore,
        authorizer: AuthorizerFactory | None = None,
        *,
        cache_ttl_seconds: float = 60.0,
        cache_size: int = 4096,
        seals: Sequence[Seal] = SEALS,
        secrets: IAMSecrets | None = None,
        access_ttl_seconds: int = 600,
        key_rotation_days: int = 30,
        auto_approve: bool = False,
    ) -> None:
        self.store = store
        self._registry = CatalogRegistry()
        self._seals = tuple(seals)
        self._subjects = _TTLCache(cache_ttl_seconds, cache_size)
        self._policies = _TTLCache(cache_ttl_seconds, cache_size)
        self._placements = _TTLCache(cache_ttl_seconds, 2)
        self._feature_ids = _TTLCache(cache_ttl_seconds, 2)
        self._sets = _TTLCache(cache_ttl_seconds, 1)
        self._platform_grants: tuple[roles.PlatformGrant, ...] = ()
        self._floors = _TTLCache(cache_ttl_seconds, 1)
        self._pending_index: tuple[int, frozenset[tuple[str, str]]] | None = None
        self._listeners: list[Callable[[int], None]] = []
        self._seen_revision: int | None = None
        self._seal_key: bytes | None = None
        self._seal_lock = threading.Lock()
        self._approve_lock = threading.Lock()
        for catalog in store.list_catalogs():
            self._registry.register(catalog)
        self._registry.register(CATALOG)
        self.authorizer = (authorizer or PolicyAuthorizer)(self)
        if secrets is None:
            from naas_abi_core.services.iam.adapters.secondary.IAMSecretsMemory import (
                IAMSecretsMemory,
            )

            secrets = IAMSecretsMemory()
        self.secrets = secrets
        self.tokens = TokenIssuer(
            store,
            secrets,
            access_ttl_seconds=access_ttl_seconds,
            rotation_days=key_rotation_days,
        )
        self.auto_approve = auto_approve
        # What reads an identity provider's token, for the exchange to a session
        # (set by the engine once the identity service is loaded).
        self.identity_authenticator: IdentityAuthenticator | None = None
        self._exchanger = TokenExchanger(self)
        # Whatever a token exchange accepts as its subject: a session or any
        # delegated token, and tokens a revocation cut off are refused.
        self.exchange_verifier = JWKSVerifier(
            self.jwks,
            audiences=(SESSION_AUDIENCE, *DELEGATED_AUDIENCES),
            revoked=self.token_revoked,
        )

    # =========================================================================
    # Decisions: the caller is the current CallContext.
    # =========================================================================

    def authorize(self, action: str, resource: str) -> Decision:
        """Whether the current caller may perform ``action`` on ``resource``."""
        return self.authorizer.check(current_call_context(), action, resource)

    def authorize_declared(
        self,
        action: str,
        resource_type: str,
        parts: Sequence[str],
        *,
        workspace: str | None = None,
    ) -> tuple[Decision, str]:
        service, _, name = action.partition(":")
        catalog = self._registry.get(service)
        if (
            catalog is None
            or not catalog.module
            or catalog.action(name) is None
            or catalog.resource_type(resource_type) is None
        ):
            raise IAMNotFoundError(
                f"No module declares {action} on {service}:{resource_type}"
            )
        where = workspace or current_call_context().workspace_id or ""
        org = self.workspace_org(where) if where else None
        resource = module_scopes.declared_resource(
            catalog,
            resource_type,
            list(parts),
            org=org or NONE,
            workspace=where if org else NONE,
        )
        return self.authorize(action, resource), resource

    def filter(self, action: str, resources: Iterable[str]) -> FilterResult:
        """The resources the current caller may perform ``action`` on, in order,
        plus prefix hints a store can push down."""
        return self.authorizer.filter(current_call_context(), action, resources)

    def allows_every(self, action: str, service: str, resource_type: str) -> bool:
        """Whether the current caller may perform ``action`` on every resource
        of the type: a whole-store read can then skip per-item checks."""
        return self.authorizer.allows_every(
            current_call_context(), action, service, resource_type
        )

    def explain(
        self, action: str, resource: str, *, principal_id: str | None = None
    ) -> Explanation:
        """Which statement decides, for the caller or for ``principal_id``.

        Needs ``iam:Explain`` on the principal asked about.
        """
        current = current_call_context()
        subject_id = principal_id if principal_id is not None else current.principal.id
        # Authorized before anything is read: a caller without iam:Explain learns
        # nothing about the principal, not even whether it exists or is a group.
        self.require(
            "iam:Explain",
            principal_resource(subject_id),
            not_found=lambda: IAMNotFoundError(f"Principal {subject_id} not found"),
        )
        if principal_id is None:
            return self.authorizer.explain(current, action, resource)
        record = self._get_principal(principal_id)
        if record.kind == "group":
            raise ValueError("Explain a user or a service account, not a group")
        ctx = CallContext(principal=_call_principal(record))
        return self.authorizer.explain(ctx, action, resource)

    # =========================================================================
    # PolicySource: what the policy authorizer reads.
    # =========================================================================

    @property
    def catalogs(self) -> CatalogRegistry:
        return self._registry

    def seals(self) -> Sequence[Seal]:
        return self._seals

    def has_sets(self) -> bool:
        return bool(self._recorded_sets())

    def scope_sets(
        self, org: str, workspace: str
    ) -> tuple[ScopeSet | None, ScopeSet | None]:
        found = self._recorded_sets()
        org_set = found.get((org, NONE)) if org not in (NONE, ALL_ORGS) else None
        workspace_set = (
            found.get((org, workspace))
            if workspace not in (NONE, ALL_WORKSPACES)
            else None
        )
        return org_set, workspace_set

    def _recorded_sets(self) -> dict[tuple[str, str], ScopeSet]:
        return self._sets.get(
            "sets",
            lambda: {(s.org, s.workspace): s for s in self.store.list_scope_sets()},
        )

    def subject(
        self, ctx: CallContext, side: Literal["actor", "user"]
    ) -> Subject | None:
        principal = ctx.principal if side == "actor" else ctx.on_behalf_of
        if principal is None:
            return None
        key = (principal.kind, principal.id, principal.name, principal.groups)
        subject = self._subjects.get(key, lambda: self._compute_subject(principal))
        issued_at = ctx.token_issued_at
        if (
            issued_at is not None
            and subject.status == "active"
            and self._revoked_since(principal.id, issued_at)
        ):
            # The token was issued before its principal's tokens were revoked:
            # it is no longer honoured, however long the call that holds it runs.
            return replace(subject, status="suspended")
        return subject

    def _held_attachments(
        self, principal: CallPrincipal, record: PrincipalRecord | None
    ) -> list[tuple[Attachment, str | None]]:
        """The attachments of ``principal`` and of each of its active groups,
        static or carried in the token's ``grp``: each with the group it came
        through (None: its own)."""
        holders: list[tuple[str, str | None]] = []
        if record is not None:
            holders.append((record.id, None))
            for group_id in self.store.groups_of(record.id):
                holders.append((group_id, group_id))
        # Mapped IdP groups travel in the token's grp claim (§2). Only ids of
        # groups count: an id of a user or an account must never lend its
        # policies.
        for group_id in sorted(principal.groups):
            if all(group_id != held for held, _ in holders) and self._is_group(
                group_id
            ):
                holders.append((group_id, group_id))
        active_groups = {
            group_id for _, group_id in holders if group_id and self._active(group_id)
        }
        via = dict(holders)
        return [
            (attachment, via.get(attachment.principal_id))
            for attachment in self.store.attachments_for([held for held, _ in holders])
            # A suspended group grants nothing.
            if via.get(attachment.principal_id) in (None, *active_groups)
        ]

    def _compute_subject(
        self, principal: CallPrincipal, *, fresh: bool = False
    ) -> Subject:
        """``fresh``: read every policy from the store, never from the cache."""
        if principal.kind == "anonymous":
            return Subject(principal.id, "active", ())
        record = self._resolve(principal)
        status = record.status if record is not None else "active"
        statements: list[EffectiveStatement] = []
        platform_admin = False
        for attachment, group in self._held_attachments(principal, record):
            # Only the platform's own attachment of it: one at an org or a
            # workspace grants there and never takes its holder out of the sets.
            platform_admin |= attachment.policy_id == roles.PLATFORM_ADMIN and (
                attachment.scope in (None, PLATFORM_SCOPE)
            )
            statements += self._statements_of(
                attachment.policy_id, attachment, group, fresh=fresh
            )
        if principal.kind == "user":
            # builtin.self is held by every user, implicitly.
            statements += self._statements_of(roles.SELF, None, None, fresh=fresh)
        # ${module.*} name the module of a module's account; for any other
        # principal they match nothing.
        variables = modules.variables(record.name if record is not None else None)
        statements = [
            replace(
                effective,
                statement=bound,
                bounds=_bind_bounds(effective.bounds, variables),
            )
            for effective in statements
            if (bound := bind_variables(effective.statement, variables)) is not None
        ]
        # The sets bound users; the platform admin, who sets the orgs' sets and
        # supports every org, and service accounts, bound by their own
        # policies, are not.
        bounded = principal.kind == "user" and not platform_admin
        return Subject(principal.id, status, tuple(statements), bounded)

    def _statements_of(
        self,
        policy_id: str,
        attachment: Attachment | None,
        group: str | None,
        *,
        fresh: bool = False,
    ) -> list[EffectiveStatement]:
        """What a policy attached at ``attachment`` gives: its statements and,
        for a sub-policy, the Denies of its chain, its Allows bounded by the
        chain's ("Sub-policies"). A chain that cannot be read whole leaves its
        Allows out."""
        policy = (
            self._load_policy(policy_id) if fresh else self._cached_policy(policy_id)
        )
        if policy is None:
            return []
        chain, whole = self._chain(policy, fresh=fresh)
        bounds = tuple(
            Bound(
                parent.id,
                tuple(
                    (index, statement)
                    for index, statement in enumerate(parent.document.statements)
                    if statement.effect == "Allow"
                ),
            )
            for parent in chain
        )
        scope = attachment.scope if attachment else None

        def reached(
            owner: Policy, index: int, statement: Statement, through: tuple[str, ...]
        ) -> EffectiveStatement:
            return EffectiveStatement(
                statement=statement,
                policy_id=owner.id,
                statement_index=index,
                attachment_id=attachment.id if attachment else None,
                scope=scope,
                via_group=group,
                bounds=bounds if statement.effect == "Allow" else (),
                through=through,
            )

        effective: list[EffectiveStatement] = []
        for index, statement in enumerate(policy.document.statements):
            # A scoped attachment grants within its scope only, whatever the
            # policy says now (attach_policy refuses the rest up front).
            granted = within_scope(statement) if scope is not None else statement
            if granted is None or (granted.effect == "Allow" and not whole):
                continue
            effective.append(reached(policy, index, granted, ()))
        through: tuple[str, ...] = (policy.id,)
        for parent in chain:
            for index, statement in enumerate(parent.document.statements):
                if statement.effect == "Deny":
                    effective.append(reached(parent, index, statement, through))
            through += (parent.id,)
        return effective

    def _chain(
        self, policy: Policy, *, fresh: bool = False
    ) -> tuple[list[Policy], bool]:
        """The parents of ``policy``, nearest first, and whether that is its
        whole chain: False when a parent is missing, the chain loops or it is
        deeper than ``MAX_DEPTH`` (what concurrent writes may leave)."""
        chain: list[Policy] = []
        seen = {policy.id}
        parent_id = policy.parent_id
        while parent_id is not None:
            if parent_id in seen or len(chain) + 1 >= MAX_DEPTH:
                return chain, False
            parent = (
                self._load_policy(parent_id)
                if fresh
                else self._cached_policy(parent_id)
            )
            if parent is None:
                return chain, False
            chain.append(parent)
            seen.add(parent.id)
            parent_id = parent.parent_id
        return chain, True

    def _cached_policy(self, policy_id: str) -> Policy | None:
        return self._policies.get(policy_id, lambda: self._load_policy(policy_id))

    def _load_policy(self, policy_id: str) -> Policy | None:
        try:
            return self.store.get_policy(policy_id)
        except IAMNotFoundError:
            return None

    def _active(self, principal_id: str) -> bool:
        try:
            return self.store.get_principal(principal_id).active
        except IAMNotFoundError:
            return False

    def _is_group(self, principal_id: str) -> bool:
        try:
            return self.store.get_principal(principal_id).kind == "group"
        except IAMNotFoundError:
            return False

    def active_groups(self, group_ids: Iterable[str]) -> tuple[str, ...]:
        """The ids among ``group_ids`` that are active groups, sorted, once each."""
        found = set()
        for group_id in group_ids:
            try:
                record = self.store.get_principal(group_id)
            except IAMNotFoundError:
                continue
            if record.kind == "group" and record.active:
                found.add(record.id)
        return tuple(sorted(found))

    def _resolve(self, principal: CallPrincipal) -> PrincipalRecord | None:
        """The stored principal a call names, if IAM has one."""
        record: PrincipalRecord | None
        if _PRINCIPAL_ID.match(principal.id):
            try:
                record = self.store.get_principal(principal.id)
            except IAMNotFoundError:
                return None
        elif principal.kind == "service_account":
            record = self.store.find_service_account(principal.name or principal.id)
        elif principal.kind == "user":
            record = self.store.find_user(LEGACY_NEXUS_ISSUER, principal.id)
        else:
            return None
        if record is None or record.kind != principal.kind:
            return None
        return record

    # =========================================================================
    # Placements
    # =========================================================================

    def placement_of(self, service: str, canonical_id: str) -> Placement | None:
        """The placement covering a resource: the exact key, else the longest
        matching prefix, else None (the platform)."""
        exact, prefixes = self._placement_index().get(service, ({}, []))
        found = exact.get(canonical_id)
        if found is not None:
            return found
        # Longest prefix first: the first match is the most specific.
        for placement in prefixes:
            if canonical_id.startswith(placement.id_key[:-1]):
                return placement
        return None

    def _all_placements(self) -> list[Placement]:
        return self._placements.get("all", self.store.list_placements)

    def _placement_index(
        self,
    ) -> dict[str, tuple[dict[str, Placement], list[Placement]]]:
        """Per service: exact keys, and prefixes longest first. Cached with the
        placements, so naming each item of a list costs no scan."""

        def build() -> dict[str, tuple[dict[str, Placement], list[Placement]]]:
            index: dict[str, tuple[dict[str, Placement], list[Placement]]] = {}
            for placement in self._all_placements():
                exact, prefixes = index.setdefault(placement.service, ({}, []))
                if placement.id_key.endswith("*"):
                    prefixes.append(placement)
                else:
                    exact[placement.id_key] = placement
            for _, prefixes in index.values():
                prefixes.sort(key=lambda p: len(p.id_key), reverse=True)
            return index

        return self._placements.get("index", build)

    def put_placement(
        self, service: str, id_key: str, org: str = NONE, workspace: str = NONE
    ) -> Placement:
        placement = Placement(service, id_key, org, workspace)
        _check_placement(placement)
        self.require("iam:PutPlacement", placement_resource(service, id_key))
        self.store.put_placement(placement)
        self._changed()
        return placement

    def delete_placement(self, service: str, id_key: str) -> bool:
        self.require("iam:DeletePlacement", placement_resource(service, id_key))
        deleted = self.store.delete_placement(service, id_key)
        if deleted:
            self._changed()
        return deleted

    def list_placements(self, service: str | None = None) -> list[Placement]:
        placements = self.store.list_placements(service)
        allowed = set(
            self.filter(
                "iam:ListPlacements",
                (placement_resource(p.service, p.id_key) for p in placements),
            ).allowed
        )
        return [
            p for p in placements if placement_resource(p.service, p.id_key) in allowed
        ]

    # =========================================================================
    # Scopes: the orgs and workspaces Nexus registers.
    # =========================================================================

    def put_scope(self, org: str, workspace: str = NONE) -> ScopeRecord:
        scope = ScopeRecord(org, workspace)
        resource_name(
            "iam", "scope", org, org=org, workspace=workspace
        )  # validates ids
        if org == NONE:
            raise ValueError("A scope names an org")
        self.require("iam:PutScope", scope_resource(org, workspace))
        self.store.put_scope(scope)
        self._changed()
        return scope

    def delete_scope(self, org: str, workspace: str = NONE) -> bool:
        """Forget a deleted workspace, or an org (``workspace`` ``-``) with its
        workspaces: what it owns (``_drop_owned``), then every attachment left
        at it. A user left with no attachment in the org leaves its groups."""
        self.require("iam:DeleteScope", scope_resource(org, workspace))
        changed = self._drop_owned(org, workspace)
        changed |= self.store.delete_scope_sets(org, workspace)
        detached = self._detach_scope(org, workspace)
        deleted = self.store.delete_scope(org, workspace)
        for principal_id in detached:
            self._leave_groups_of(principal_id, org)
        if deleted or detached or changed:
            self._changed()
        return deleted

    def _detach_scope(self, org: str, workspace: str) -> set[str]:
        """Detach every attachment at a deleted workspace, or anywhere in a
        deleted org; the principals that held one."""

        def at(scope: str | None) -> bool:
            if scope is None:
                return False
            scope_org, scope_workspace = scope_fields(scope)
            return scope_org == org and workspace in (NONE, scope_workspace)

        held: set[str] = set()
        for attachment in self.store.list_attachments():
            if not at(attachment.scope):
                continue
            if self.store.detach(
                attachment.policy_id, attachment.principal_id, attachment.scope
            ):
                held.add(attachment.principal_id)
                if attachment.policy_id in roles.ROLES:
                    self._sync_platform_roles(attachment.principal_id)
                    self._sync_feature_policies(attachment.principal_id)
        return held

    def workspace_org(self, workspace: str) -> str | None:
        """The org a workspace was registered in (``iam:PutScope``). ``-`` and ``*``
        are not workspaces (an org's own scope is ``(org, -)``): they have no org."""
        if workspace in ("", "-", "*"):
            return None
        return next(
            (s.org for s in self.store.list_scopes() if s.workspace == workspace), None
        )

    # =========================================================================
    # Sets: what an org or a workspace may use (sets.py).
    # =========================================================================

    def get_set(self, org: str, workspace: str = NONE) -> ScopeSet:
        """The set recorded for an org or a workspace; one of everything (both
        parts None) when none is. Needs ``iam:GetSet`` on it, at its scope."""
        self._check_set_scope(org, workspace)
        self._require_set("iam:GetSet", read_resource(org, workspace))
        org_set, workspace_set = self.scope_sets(org, workspace)
        found = workspace_set if workspace != NONE else org_set
        return found or ScopeSet(org, workspace)

    def effective_set(self, org: str, workspace: str = NONE) -> ScopeSet:
        """What an org or a workspace may use: a workspace's set within its org's.
        Needs ``iam:GetSet`` on the set asked for."""
        self._check_set_scope(org, workspace)
        self._require_set("iam:GetSet", read_resource(org, workspace))
        org_set, workspace_set = self.scope_sets(org, workspace)
        return replace(
            intersect(org_set or ScopeSet(org), workspace_set),
            org=org,
            workspace=workspace,
        )

    def list_sets(self, org: str | None = None) -> list[ScopeSet]:
        """The recorded sets the caller may read (``iam:GetSet``)."""
        found = [
            s for s in self._recorded_sets().values() if org is None or s.org == org
        ]
        allowed = set(
            self.filter(
                "iam:GetSet", [read_resource(s.org, s.workspace) for s in found]
            ).allowed
        )
        return sorted(
            (s for s in found if read_resource(s.org, s.workspace) in allowed),
            key=lambda s: (s.org, s.workspace),
        )

    def put_set(
        self,
        org: str,
        workspace: str = NONE,
        *,
        modules: Iterable[str] | None = None,
        features: Iterable[str] | None = None,
    ) -> ScopeSet:
        """Record the set of an org (``iam:PutSet`` on ``abi:%2A:%2A:iam:set/<org>``,
        the platform admin's) or of a workspace (on ``abi:<org>:%2A:iam:set/<ws>``,
        an org-wide role's). A part left None is everything; for a workspace that
        is its org's. A workspace's items must be within its org's set
        (``SetValidationError`` naming the extra ones). Narrowing applies at the
        next decision: the change drops every cache, here and over NATS."""
        self._check_set_scope(org, workspace)
        self._require_set("iam:PutSet", write_resource(org, workspace))
        kept_modules, kept_features = normalize(modules, features)
        if workspace != NONE and self.workspace_org(workspace) != org:
            raise IAMNotFoundError(f"Workspace {workspace} is not in org {org}")
        recorded = ScopeSet(org, workspace, kept_modules, kept_features)
        if workspace != NONE:
            org_set, _ = self.scope_sets(org, workspace)
            extra = outside(recorded, org_set)
            if extra:
                raise SetValidationError(
                    f"Not in the set of organization {org}: {', '.join(extra)}"
                )
        self.store.put_scope_set(recorded)
        self._changed()
        return recorded

    def _require_set(self, action: str, resource: str) -> None:
        # Every org and workspace has a set: a refusal is never "not found".
        self.require(
            action, resource, not_found=lambda: PermissionDeniedError(action, resource)
        )

    @staticmethod
    def _check_set_scope(org: str, workspace: str) -> None:
        if org in (NONE, ALL_ORGS) or workspace == ALL_WORKSPACES:
            raise ValueError("A set is an org's or a workspace's in an org")
        scope_name(org, workspace)  # validates the ids

    # =========================================================================
    # Catalogs
    # =========================================================================

    def register_catalog(self, catalog: ActionCatalog | Mapping[str, Any]) -> bool:
        """Register a service's catalog; the highest version wins.

        Refuses a version that drops an action a policy still names explicitly.
        The built-in roles are regenerated when the catalog changes.
        """
        if not isinstance(catalog, ActionCatalog):
            catalog = ActionCatalog.from_dict(catalog)
        self.require("iam:RegisterCatalog", catalog_resource(catalog.service))
        return self._register_catalog(catalog)

    def _register_catalog(self, catalog: ActionCatalog) -> bool:
        current = self._registry.get(catalog.service)
        if catalog.module:
            # A module's own catalog: checked again whoever registers it.
            module_scopes.module_catalog(catalog, catalog.module)
        if current is not None and current.module != catalog.module:
            raise IAMConflictError(
                f"Catalog {catalog.service} is "
                + (f"module {current.module!r}'s" if current.module else "reserved")
                + (f", not module {catalog.module!r}'s" if catalog.module else "")
            )
        if current is not None and current.version > catalog.version:
            return False
        if current is not None:
            dropped = set(removed_actions(current, catalog))
            if dropped:
                still_named = sorted(
                    action
                    for policy in self._all_policies()
                    if not policy.managed
                    for statement in policy.document.statements
                    for action in statement.actions
                    if action in dropped
                )
                if still_named:
                    raise IAMConflictError(
                        f"Catalog {catalog.service} v{catalog.version} drops actions "
                        f"policies still name: {', '.join(sorted(set(still_named)))}"
                    )
        self.store.put_catalog(catalog)
        changed = current != catalog
        self._registry.register(catalog)
        if changed:
            self._refresh_builtin_policies()
        self._changed()
        return True

    def list_catalogs(self) -> list[ActionCatalog]:
        """The registered catalogs. Public metadata: no action needed."""
        return self._registry.all()

    # =========================================================================
    # Principals
    # =========================================================================

    def ensure_user(
        self,
        issuer: str,
        subject: str,
        *,
        provider: str | None = None,
        email: str | None = None,
        email_verified: bool = False,
        display_name: str | None = None,
    ) -> PrincipalRecord:
        """The user for a verified ``(issuer, subject)``, created on first sight.

        The profile fields are informational and refreshed when they change.
        """
        if not issuer or not subject:
            raise ValueError("A user is an issuer and a subject")
        existing = self.store.find_user(issuer, subject)
        principal_id = existing.id if existing is not None else new_id("usr")
        self.require("iam:CreateUser", principal_resource(principal_id))
        profile = {
            "provider": provider,
            "email": email,
            "email_verified": email_verified,
            "display_name": display_name,
        }
        if existing is None:
            try:
                record = self.store.create_principal(
                    PrincipalRecord(
                        id=principal_id,
                        kind="user",
                        issuer=issuer,
                        subject=subject,
                        **profile,  # type: ignore[arg-type]
                    )
                )
            except IAMConflictError:
                # Another first sighting of the same identity created it: the
                # profile update below is authorized on that principal.
                existing = self.store.find_user(issuer, subject)
                if existing is None:
                    raise
                self.require("iam:CreateUser", principal_resource(existing.id))
            else:
                self._changed()
                return record
        if all(getattr(existing, k) == v for k, v in profile.items()):
            return existing
        record = self.store.update_principal(replace(existing, **profile))  # type: ignore[arg-type]
        self._changed()
        return record

    def identity_at(self, principal_id: str, issuer: str) -> str | None:
        record = self._get_principal(principal_id)
        if record.kind != "user":
            return None
        if record.issuer == issuer and record.subject:
            return record.subject
        return next(
            (s for i, s in self.store.linked_identities(principal_id) if i == issuer),
            None,
        )

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
        built-in login ``principal_id``: its roles, groups and keys
        stay, and the user is found by the identity from now on.

        Only a user of the built-in login (issuer ``urn:abi:nexus``) is linked,
        and an identity belongs to one user. A user the identity already made
        (the first sign-in creates one before a relying party can link it) is
        merged into the linked one: its roles and groups move, it is retired,
        and a user holding keys is refused, since the keys name it. The caller
        is the one who checked that the person owns the identity (a verified
        email at a provider that proves it); IAM only needs ``iam:LinkUser``.
        """
        if not issuer or not subject:
            raise ValueError("An identity is an issuer and a subject")
        self.require(
            "iam:LinkUser",
            principal_resource(principal_id),
            not_found=lambda: IAMNotFoundError(f"Principal {principal_id} not found"),
        )
        target = self._get_principal(principal_id)
        if target.kind != "user" or target.issuer != LEGACY_NEXUS_ISSUER:
            raise IAMConflictError(
                f"{principal_id} is not a user of the built-in login: "
                "only those are linked to an identity provider"
            )
        if target.status != "active":
            raise IAMConflictError(f"Principal {principal_id} is {target.status}")
        existing = self.store.find_user(issuer, subject)
        if existing is not None and existing.id != target.id:
            if existing.issuer != issuer or existing.subject != subject:
                # Reached through a link: another user's, which a user keeps.
                raise IAMConflictError("This identity belongs to another user")
            self._merge_user(existing, target)
        self.store.link_identity(issuer, subject, target.id)
        profile = {
            "provider": provider,
            "email": email,
            "email_verified": email_verified,
            "display_name": display_name,
        }
        record = target
        if not all(getattr(target, k) == v for k, v in profile.items()):
            record = self.store.update_principal(replace(target, **profile))  # type: ignore[arg-type]
        self._changed()
        return record

    def _merge_user(self, source: PrincipalRecord, target: PrincipalRecord) -> None:
        """Move what ``source`` holds to ``target`` and retire ``source``."""
        if source.kind != "user":
            raise IAMConflictError(f"{source.id} is not a user")
        if source.status != "active":
            # A suspension of the identity is not lifted by linking it.
            raise IAMConflictError(f"Principal {source.id} is {source.status}")
        if self.store.list_keys(source.id):
            raise IAMConflictError(
                f"{source.id} holds keys: revoke or delete them before linking"
            )
        for attachment in self.store.list_attachments(principal_id=source.id):
            if (
                self._find_attachment(attachment.policy_id, target.id, attachment.scope)
                is None
            ):
                self.store.attach(
                    Attachment(
                        new_id("att"),
                        attachment.policy_id,
                        target.id,
                        attachment.scope,
                    )
                )
            self.store.detach(attachment.policy_id, source.id, attachment.scope)
        for group_id in self.store.groups_of(source.id):
            self.store.add_group_member(group_id, target.id)
            self.store.remove_group_member(group_id, source.id)
        self._sync_platform_roles(source.id)
        self._sync_platform_roles(target.id)
        self.store.update_principal(replace(source, status="deleted"))

    def create_service_account(
        self, name: str, *, owner_id: str | None = None
    ) -> PrincipalRecord:
        _check_service_account_name(name)
        principal_id = new_id("sa")
        self.require("iam:CreateServiceAccount", principal_resource(principal_id))
        record = self.store.create_principal(
            PrincipalRecord(
                id=principal_id, kind="service_account", name=name, owner_id=owner_id
            )
        )
        if modules.parse_account(name) is not None:
            # A module's account always holds its bootstrap.
            self.store.attach(
                Attachment(new_id("att"), roles.MODULE_BOOTSTRAP, record.id)
            )
        self._changed()
        return record

    def find_service_account(self, name: str) -> PrincipalRecord:
        """The service account named ``name`` (``iam:GetPrincipal`` on it)."""
        record = self.store.find_service_account(name)
        missing = lambda: IAMNotFoundError(f"Service account {name!r} not found")
        if record is None:
            # Same answer as for an account the caller may not see.
            raise missing()
        self.require(
            "iam:GetPrincipal", principal_resource(record.id), not_found=missing
        )
        return record

    def get_principal(self, principal_id: str) -> PrincipalRecord:
        self.require(
            "iam:GetPrincipal",
            principal_resource(principal_id),
            not_found=lambda: IAMNotFoundError(f"Principal {principal_id} not found"),
        )
        return self._get_principal(principal_id)

    def list_principals(
        self,
        kind: PrincipalKind | None = None,
        *,
        limit: int = 100,
        after: str | None = None,
    ) -> Page:
        return self._filtered_page(
            lambda size, cursor: self.store.list_principals(
                kind, limit=size, after=cursor
            ),
            "iam:ListPrincipals",
            lambda record: principal_resource(record.id),
            limit,
            after,
        )

    def suspend_principal(self, principal_id: str) -> PrincipalRecord:
        return self._set_status(principal_id, "suspended", "iam:SuspendPrincipal")

    def resume_principal(self, principal_id: str) -> PrincipalRecord:
        return self._set_status(principal_id, "active", "iam:ResumePrincipal")

    def delete_principal(self, principal_id: str) -> PrincipalRecord:
        """Mark a user or service account deleted: its id stays, for audit; its
        attachments and memberships go."""
        record = self._set_status(principal_id, "deleted", "iam:DeletePrincipal")
        self._unlink(record)
        return record

    def _set_status(
        self, principal_id: str, status: str, action: str
    ) -> PrincipalRecord:
        self.require(
            action,
            principal_resource(principal_id),
            not_found=lambda: IAMNotFoundError(f"Principal {principal_id} not found"),
        )
        record = self._get_principal(principal_id)
        if record.kind == "group":
            raise ValueError(f"{principal_id} is a group: use the group operations")
        if record.kind == "service_account" and record.name in roles.SERVICE_ACCOUNTS:
            raise IAMConflictError(
                f"The built-in service account {record.name!r} stays active"
            )
        if record.status == "deleted":
            raise IAMConflictError(f"Principal {principal_id} is deleted")
        if record.status == status:
            return record
        updated = self.store.update_principal(replace(record, status=status))  # type: ignore[arg-type]
        self._changed()
        return updated

    def _unlink(self, record: PrincipalRecord) -> None:
        for attachment in self.store.list_attachments(principal_id=record.id):
            self.store.detach(attachment.policy_id, record.id, attachment.scope)
        for group_id in self.store.groups_of(record.id):
            self.store.remove_group_member(group_id, record.id)
        if record.kind == "group":
            for member_id in self.store.list_group_members(record.id):
                self.store.remove_group_member(record.id, member_id)
            for mapping in self.store.list_idp_group_mappings(record.id):
                self.store.unmap_idp_group(mapping)
        self._changed()

    def _get_principal(self, principal_id: str) -> PrincipalRecord:
        return self.store.get_principal(principal_id)

    # =========================================================================
    # Groups
    # =========================================================================

    def create_group(
        self, name: str, *, org: str | None = None, scope: str | None = None
    ) -> PrincipalRecord:
        """A group owned by ``scope``: the platform (``abi:-:-``, the default),
        an org (``abi:<org>:-``, also what ``org`` alone means) or a workspace
        (``abi:<org>:<ws>``). Its name carries the owner, so whoever may
        ``iam:CreateGroup`` there creates it."""
        if not name:
            raise ValueError("A group needs a name")
        owner = _owner_scope(scope, org)
        group_id = new_id("grp")
        self.require("iam:CreateGroup", group_resource(group_id, owner))
        self._check_owner_known(owner)
        owner_org = scope_fields(owner)[0]
        record = self.store.create_principal(
            PrincipalRecord(
                id=group_id,
                kind="group",
                name=name,
                org=owner_org if owner_org != NONE else None,
                owner_scope=owner,
            )
        )
        self._changed()
        return record

    def get_group(self, group_id: str) -> PrincipalRecord:
        return self._require_group("iam:GetGroup", group_id)

    def list_groups(
        self, *, limit: int = 100, after: str | None = None, scope: str | None = None
    ) -> Page:
        """The groups the caller may list. With ``scope``, the groups it owns; at
        a workspace, also its org's groups, which receive attachments there, for
        whoever may list that workspace's attachments to them."""
        if scope is None:
            return self._filtered_page(
                lambda size, cursor: self.store.list_principals(
                    "group", limit=size, after=cursor
                ),
                "iam:ListGroups",
                lambda record: group_resource(record.id, record.owner_scope),
                limit,
                after,
            )
        validate_owner_scope(scope)
        org, workspace = scope_fields(scope)
        above = [scope_name(org)] if NONE not in (org, workspace) else []

        def keep(groups: list[PrincipalRecord]) -> set[str]:
            own = {
                g.id: group_resource(g.id, g.owner_scope)
                for g in groups
                if g.owner_scope == scope
            }
            inherited = {
                g.id: attachment_resource("*", g.id, scope)
                for g in groups
                if g.owner_scope != scope
            }
            allowed = set(self.filter("iam:ListGroups", own.values()).allowed)
            allowed |= set(
                self.filter("iam:ListAttachments", inherited.values()).allowed
            )
            return {i for i, n in {**own, **inherited}.items() if n in allowed}

        return self._kept_page(
            lambda size, cursor: self.store.list_principals(
                "group", limit=size, after=cursor, owner_scopes=[scope, *above]
            ),
            keep,
            ("iam:ListGroups", "iam:ListAttachments"),
            limit,
            after,
        )

    def delete_group(self, group_id: str) -> PrincipalRecord:
        group = self._require_group("iam:DeleteGroup", group_id)
        if group.status == "deleted":
            return group
        return self._delete_group(group)

    def _delete_group(self, group: PrincipalRecord) -> PrincipalRecord:
        record = self.store.update_principal(replace(group, status="deleted"))
        self._unlink(record)
        return record

    def add_group_member(self, group_id: str, member_id: str) -> None:
        """Static membership. Groups cannot contain groups. A group owned by an
        org or a workspace holds only users of that org: users with an
        attachment of their own under ``abi:<org>:``. The new member gets every
        attachment of the group, so the caller holds what each grants at its
        scope (``_require_held``), but for the companions IAM keeps in step with
        the group's roles (``_companions``): they follow the roles."""
        group = self._require_group("iam:AddGroupMember", group_id)
        member = self._get_principal(member_id)
        if member.kind == "group":
            raise ValueError("Groups cannot contain groups")
        if "deleted" in (group.status, member.status):
            raise IAMConflictError("Nothing joins or holds a deleted principal")
        if group.owner_scope != PLATFORM_SCOPE:
            org = scope_fields(group.owner_scope)[0]
            if member.kind != "user":
                raise ValueError(
                    f"Group {group_id} belongs to {group.owner_scope}: it holds "
                    "users only (a module's account is approved by its manifest)"
                )
            if not self._belongs_to(member_id, org):
                raise ValueError(
                    f"Group {group_id} belongs to {group.owner_scope}: "
                    f"{member_id} is not a member of org {org}"
                )
        if member_id in self.store.list_group_members(group_id):
            return
        attachments = self.store.list_attachments(principal_id=group_id)
        companions = self._companions(attachments)
        held: dict[str, list[str | None]] = {}
        for attachment in attachments:
            if (attachment.policy_id, attachment.scope) not in companions:
                held.setdefault(attachment.policy_id, []).append(attachment.scope)
        with grants.budget():  # one budget for every attachment of the group
            for policy_id, scopes in sorted(held.items()):
                policy = self._load_policy(policy_id)
                if policy is not None:
                    self._require_held(
                        policy.document,
                        scopes,
                        policy_id=policy_id,
                        parents=self._parents(policy),
                    )
        self.store.add_group_member(group_id, member_id)
        self._changed()

    def remove_group_member(self, group_id: str, member_id: str) -> bool:
        self._require_group("iam:RemoveGroupMember", group_id)
        removed = self.store.remove_group_member(group_id, member_id)
        if removed:
            self._changed()
        return removed

    def list_group_members(self, group_id: str) -> list[str]:
        self._require_group("iam:GetGroup", group_id)
        return self.store.list_group_members(group_id)

    def map_idp_group(
        self, provider: str, claim_value: str, group_id: str
    ) -> GroupMapping:
        """Members of ``claim_value`` in ``provider``'s groups claim join the group.
        The platform admin's, whatever owns the group (``_require_mapping``)."""
        if not provider or not claim_value:
            raise ValueError("A mapping names a provider and a claim value")
        self._require_mapping("iam:MapIdpGroup", group_id)
        if self._group(group_id).status == "deleted":
            raise IAMConflictError(f"Group {group_id} is deleted")
        mapping = GroupMapping(provider, claim_value, group_id)
        self.store.map_idp_group(mapping)
        self._changed()
        return mapping

    def unmap_idp_group(self, provider: str, claim_value: str, group_id: str) -> bool:
        self._require_mapping("iam:UnmapIdpGroup", group_id)
        removed = self.store.unmap_idp_group(
            GroupMapping(provider, claim_value, group_id)
        )
        if removed:
            self._changed()
        return removed

    def list_idp_group_mappings(self, group_id: str) -> list[GroupMapping]:
        self._require_group("iam:GetGroup", group_id)
        return self.store.list_idp_group_mappings(group_id)

    def resolve_idp_groups(
        self, provider: str, claim_values: Iterable[str]
    ) -> list[str]:
        """The group ids an IdP token's groups claim maps to, for token exchange."""
        return self.store.resolve_idp_groups(provider, claim_values)

    def _find_group(self, group_id: str) -> PrincipalRecord | None:
        try:
            record = self._get_principal(group_id)
        except IAMNotFoundError:
            return None
        return record if record.kind == "group" else None

    def _require_group(self, action: str, group_id: str) -> PrincipalRecord:
        """``action`` on the group as named at its owner scope. A group that does
        not exist is named at the platform, so the answer is the same as for
        one the caller may not see."""
        group = self._find_group(group_id)
        self.require(
            action,
            group_resource(group_id, group.owner_scope if group else PLATFORM_SCOPE),
            not_found=lambda: IAMNotFoundError(f"Group {group_id} not found"),
        )
        if group is None:
            raise IAMNotFoundError(f"Group {group_id} not found")
        return group

    def _require_mapping(self, action: str, group_id: str) -> None:
        """IdP group mappings are the platform's: decided on the group's platform
        name, which no grant at an org or a workspace reaches."""
        self.require(
            action,
            group_resource(group_id),
            not_found=lambda: IAMNotFoundError(f"Group {group_id} not found"),
        )

    def _group(self, group_id: str) -> PrincipalRecord:
        record = self._find_group(group_id)
        if record is None:
            raise IAMNotFoundError(f"Group {group_id} not found")
        return record

    def _belongs_to(self, principal_id: str, org: str) -> bool:
        """Whether a principal has an attachment of its own under ``abi:<org>:``."""
        return any(
            a.scope is not None and scope_fields(a.scope)[0] == org
            for a in self.store.list_attachments(principal_id=principal_id)
        )

    def _leave_groups_of(self, principal_id: str, org: str) -> None:
        """A user who no longer belongs to ``org`` leaves the groups it owns."""
        if org == NONE or self._belongs_to(principal_id, org):
            return
        for group_id in self.store.groups_of(principal_id):
            group = self._find_group(group_id)
            if group is not None and group.owner_scope != PLATFORM_SCOPE:
                if scope_fields(group.owner_scope)[0] == org:
                    self.store.remove_group_member(group_id, principal_id)

    def _check_owner_known(self, owner: str) -> None:
        """An org or a workspace owns something only once Nexus registered it
        (``iam:PutScope``), a workspace in that org."""
        org, workspace = scope_fields(owner)
        if org == NONE:
            return
        known = self.store.list_scopes(org)
        if not any(s.workspace == workspace for s in known):
            raise ValueError(f"{owner} is not a registered org or workspace")

    # =========================================================================
    # Policies
    # =========================================================================

    def create_policy(
        self,
        name: str,
        document: Mapping[str, Any] | str | PolicyDocument,
        *,
        description: str = "",
        scope: str | None = None,
        parent: str | None = None,
    ) -> Policy:
        """A customer policy, validated against the registered catalogs, owned by
        ``scope``: the platform (the default), an org (``abi:<org>:-``) or a
        workspace (``abi:<org>:<ws>``). Its name carries the owner, so whoever
        may ``iam:CreatePolicy`` there creates it. An owned policy is written
        for its scope: every resource pattern starts with ``${scope}:``. With
        ``parent``, a sub-policy of it ("Sub-policies"): owned at the parent's
        owner or below, derived only from a policy the caller holds there. The
        caller holds what it allows (``_require_held``), within the chain."""
        if not name:
            raise ValueError("A policy needs a name")
        owner = validate_owner_scope(scope) if scope is not None else PLATFORM_SCOPE
        parsed = parse_policy_document(document, self._registry)
        policy_id = new_id("pol")
        self.require("iam:CreatePolicy", policy_resource(policy_id, owner))
        self._check_owner_known(owner)
        check_owned_document(parsed, owner)
        chain: list[Policy] = []
        if parent:
            chain = self._new_chain(policy_id, owner, parent, height=1)
            self._require_derivable(chain[0], owner)
        self._require_held(
            parsed,
            _written_for(owner),
            policy_id=policy_id,
            parents=[p.document for p in chain],
        )
        policy = self.store.create_policy(
            Policy(
                id=policy_id,
                name=name,
                description=description,
                document=parsed,
                owner_scope=owner,
                parent_id=chain[0].id if chain else None,
            )
        )
        self._changed()
        return policy

    def get_policy(self, policy_id: str) -> Policy:
        return self._require_policy("iam:GetPolicy", policy_id)

    def list_policies(
        self, *, limit: int = 100, after: str | None = None, scope: str | None = None
    ) -> Page:
        """The policies the caller may list. With ``scope``, the policies it
        owns, plus those of the levels above (its org's, the platform's) that
        the caller may attach there."""
        if scope is None:
            return self._filtered_page(
                lambda size, cursor: self.store.list_policies(limit=size, after=cursor),
                "iam:ListPolicies",
                lambda policy: policy_resource(policy.id, policy.owner_scope),
                limit,
                after,
            )
        validate_owner_scope(scope)

        def keep(found: list[Policy]) -> set[str]:
            own = {
                p.id: policy_resource(p.id, p.owner_scope)
                for p in found
                if p.owner_scope == scope
            }
            inherited = {
                p.id: attachment_resource(p.id, "*", scope)
                for p in found
                if p.owner_scope != scope and p.document.confined_to_scope
            }
            # A Deny beyond ${scope}, its own or its chain's: offered only to
            # whoever may attach it unscoped too (``_require_attach``).
            unscoped = {
                p.id: attachment_resource(p.id, "*", None)
                for p in found
                if p.id in inherited and self._denies_beyond_scope(p)
            }
            allowed = set(self.filter("iam:ListPolicies", own.values()).allowed)
            allowed |= set(self.filter("iam:AttachPolicy", inherited.values()).allowed)
            reach = set(self.filter("iam:AttachPolicy", unscoped.values()).allowed)
            return {
                i
                for i, n in {**own, **inherited}.items()
                if n in allowed and (i not in unscoped or unscoped[i] in reach)
            }

        return self._kept_page(
            lambda size, cursor: self.store.list_policies(
                limit=size, after=cursor, owner_scopes=[scope, *owner_ancestors(scope)]
            ),
            keep,
            ("iam:ListPolicies", "iam:AttachPolicy"),
            limit,
            after,
        )

    def update_policy(
        self,
        policy_id: str,
        *,
        expected_revision: int,
        document: Mapping[str, Any] | str | PolicyDocument | None = None,
        name: str | None = None,
        description: str | None = None,
        parent: str | None = None,
    ) -> Policy:
        """Optimistic update: ``RevisionConflictError`` when someone got there
        first. The owner scope never changes. ``parent``: None keeps it, ``""``
        removes it, an id sets it, checked as on create ("Sub-policies"). A new
        document or parent is held by the caller, within the new chain, where
        it is written for and at every scope it is attached or invited to, and
        so is each policy below it, at its own (``_require_held``)."""
        current = self._require_policy("iam:UpdatePolicy", policy_id)
        if current.managed:
            raise IAMConflictError(f"{policy_id} is managed: only IAM rewrites it")
        parent_id = current.parent_id if parent is None else (parent or None)
        updated = replace(
            current,
            name=name if name is not None else current.name,
            description=description if description is not None else current.description,
            document=parse_policy_document(document, self._registry)
            if document is not None
            else current.document,
            parent_id=parent_id,
        )
        check_owned_document(updated.document, current.owner_scope)
        attachments = self.store.list_attachments(policy_id=policy_id)
        if not updated.document.confined_to_scope and any(
            a.scope is not None for a in attachments
        ):
            # Evaluation would ignore the rest at those scopes: say so instead.
            raise ValueError(
                f"{policy_id} is attached at a scope: every Allow resource must "
                "start with ${scope}:"
            )
        reparented = parent_id != current.parent_id
        if reparented and parent_id is not None:
            chain = self._new_chain(
                policy_id,
                current.owner_scope,
                parent_id,
                height=self._height(policy_id),
            )
            self._require_derivable(chain[0], current.owner_scope)
        else:
            chain, _whole = self._chain(updated, fresh=True)
        if reparented or updated.document != current.document:
            below = self._below(policy_id)
            self._check_unscoped_chain(updated, chain, below)
            with grants.budget():  # one budget for this policy and those below
                self._require_held(
                    updated.document,
                    self._held_scopes(updated, attachments),
                    policy_id=policy_id,
                    parents=[p.document for p in chain],
                )
                for sub, its_chain in (
                    below
                    if reparented or self._widens(current.document, updated.document)
                    else ()
                ):
                    self._require_held(
                        sub.document,
                        self._held_scopes(sub),
                        policy_id=sub.id,
                        parents=[p.document for p in [*its_chain, updated, *chain]],
                    )
        policy = self.store.update_policy(updated, expected_revision)
        self._changed()
        return policy

    def list_sub_policies(self, policy_id: str) -> list[Policy]:
        """The direct sub-policies of ``policy_id`` the caller may list
        (``iam:ListPolicies`` at each's owner), after ``iam:GetPolicy`` on it."""
        self._require_policy("iam:GetPolicy", policy_id)
        found = self.store.list_sub_policies(policy_id)
        names = {p.id: policy_resource(p.id, p.owner_scope) for p in found}
        allowed = set(self.filter("iam:ListPolicies", names.values()).allowed)
        return [p for p in found if names[p.id] in allowed]

    def delete_policy(self, policy_id: str) -> None:
        """``IAMConflictError`` while the policy is attached, is a parent, or
        when it is managed."""
        if self._require_policy("iam:DeletePolicy", policy_id).managed:
            raise IAMConflictError(f"{policy_id} is managed: only IAM removes it")
        subs = self.store.list_sub_policies(policy_id)
        if subs:
            raise IAMConflictError(
                f"Policy {policy_id} has sub-policies: "
                + ", ".join(f"{p.id} ({p.name})" for p in subs)
                + ". Delete them or give them another parent first"
            )
        self.store.delete_policy(policy_id)
        self._changed()

    # -- sub-policies (AGENTS.md, "Sub-policies") ----------------------------------

    def _new_chain(
        self, policy_id: str, owner: str, parent_id: str, *, height: int
    ) -> list[Policy]:
        """The chain ``policy_id`` (owned by ``owner``, ``height`` policies deep
        with those below it) would have under ``parent_id``, nearest first.
        Refuses a parent that does not exist (``IAMNotFoundError``), a cycle, a
        chain deeper than ``MAX_DEPTH`` and an owner outside the parent's."""
        parent = self._load_policy(parent_id)
        if parent is None:
            raise IAMNotFoundError(f"Policy {parent_id} not found")
        above, whole = self._chain(parent, fresh=True)
        chain = [parent, *above]
        if any(p.id == policy_id for p in chain):
            raise ValueError(
                f"{parent_id} is {policy_id} or one of its sub-policies: "
                "a parent there would make a cycle"
            )
        if not whole or len(chain) + height > MAX_DEPTH:
            raise ValueError(
                f"Under {parent_id}, {policy_id} would sit deeper than "
                f"{MAX_DEPTH} policies"
            )
        if not within_owner(parent.owner_scope, owner):
            raise ValueError(
                f"A sub-policy of {parent_id} is owned by {parent.owner_scope} or "
                f"below it, not {owner}"
            )
        return chain

    def _height(self, policy_id: str) -> int:
        """How many policies deep ``policy_id`` and those below it go (1: none
        below), bounded by ``MAX_DEPTH`` plus one."""
        level, height = [policy_id], 0
        while level and height <= MAX_DEPTH:
            height += 1
            level = [p.id for i in level for p in self.store.list_sub_policies(i)]
        return height

    def _below(self, policy_id: str) -> list[tuple[Policy, list[Policy]]]:
        """Every policy below ``policy_id``, each with its chain up to, not
        including, ``policy_id`` (nearest first)."""
        found: list[tuple[Policy, list[Policy]]] = []
        level: list[tuple[str, list[Policy]]] = [(policy_id, [])]
        seen = {policy_id}
        for _depth in range(MAX_DEPTH):
            following: list[tuple[str, list[Policy]]] = []
            for parent_id, chain in level:
                parent = None if not chain else chain[0]
                for sub in self.store.list_sub_policies(parent_id):
                    if sub.id in seen:
                        continue
                    seen.add(sub.id)
                    its_chain = [] if parent is None else [parent, *chain[1:]]
                    found.append((sub, its_chain))
                    following.append((sub.id, [sub, *its_chain]))
            level = following
        return found

    def _held_scopes(
        self, policy: Policy, attachments: Sequence[Attachment] | None = None
    ) -> list[str | None]:
        """Where a policy's grant is checked: where it is written for, and every
        scope it is attached or invited at."""
        if attachments is None:
            attachments = self.store.list_attachments(policy_id=policy.id)
        return [
            *_written_for(policy.owner_scope),
            *(a.scope for a in attachments),
            *(g.scope for g in self.store.list_pending_grants(policy_id=policy.id)),
        ]

    def _check_unscoped_chain(
        self,
        policy: Policy,
        chain: Sequence[Policy],
        below: Sequence[tuple[Policy, list[Policy]]],
    ) -> None:
        """A policy attached unscoped never gets a chain that names ``${scope}``:
        unresolved there, its Denies would refuse nothing."""
        for held, above in [(policy, []), *below]:
            documents = [p.document for p in [held, *above, policy, *chain]]
            if any(d.uses_scope for d in documents) and any(
                a.scope is None for a in self.store.list_attachments(policy_id=held.id)
            ):
                raise ValueError(
                    f"{held.id} is attached unscoped: its chain may not name ${{scope}}"
                )

    def _widens(self, before: PolicyDocument, after: PolicyDocument) -> bool:
        """Whether ``after`` may allow something ``before`` does not: only then
        can a change of a parent widen what the policies below it grant. Its
        Allows are compared as grants are, written unscoped and at any scope;
        unproven is a widening."""
        held = grants.Holdings(
            [
                grants.Side(
                    tuple(
                        grants.held_statement(
                            statement, scope, principal_id="-", user_id=None
                        )
                        for statement in before.statements
                        if statement.effect == "Allow"
                    ),
                    "",
                )
                for scope in (None, _ANY_SCOPE)
            ],
            self._registry,
        )
        return any(
            grants.Holdings([side], self._registry).first_uncovered(
                after.statements, scope
            )
            is not None
            for side, scope in zip(held.sides, (None, _ANY_SCOPE))
        )

    def _denies_beyond_scope(self, policy: Policy) -> bool:
        """Whether a Deny of the policy or of its chain names anything outside
        ``${scope}:``: it refuses beyond the scope it is attached at."""
        chain, _whole = self._chain(policy)
        return _denies_beyond_scope([policy.document, *(p.document for p in chain)])

    def _uses_scope(self, policy: Policy) -> bool:
        """Whether the policy or a policy of its chain names ``${scope}``."""
        chain, _whole = self._chain(policy)
        return any(p.document.uses_scope for p in [policy, *chain])

    def _parents(self, policy: Policy) -> list[PolicyDocument] | None:
        """The documents of a policy's chain, nearest first; None when it cannot
        be read whole, and the policy grants nothing."""
        chain, whole = self._chain(policy)
        return [p.document for p in chain] if whole else None

    def _require_derivable(self, parent: Policy, owner: str) -> None:
        """Derive only from what you hold: ``parent`` is attached to the caller,
        or to one of their groups, at ``owner`` or above, unless they hold
        ``builtin.platform_admin`` there (unscoped or at the platform). The
        caller is the call's user when there is one, plus an actor that is not
        first-party; a first-party account acting for no user is not checked."""
        ctx = current_call_context()
        if ctx.on_behalf_of is None and self._first_party(ctx.principal):
            return
        callers = [ctx.on_behalf_of or ctx.principal]
        if ctx.on_behalf_of is not None and not self._first_party(ctx.principal):
            callers.append(ctx.principal)
        for caller in callers:
            held = [
                attachment
                for attachment, _group in self._held_attachments(
                    caller, self._resolve(caller)
                )
            ]
            if any(
                a.policy_id == roles.PLATFORM_ADMIN
                and a.scope in (None, PLATFORM_SCOPE)
                for a in held
            ):
                continue
            if any(
                a.policy_id == parent.id and within_owner(_as_owner(a.scope), owner)
                for a in held
            ):
                continue
            who = "you" if caller is callers[0] else (caller.name or caller.id)
            raise PermissionDeniedError(
                "iam:CreatePolicy",
                policy_resource(parent.id, parent.owner_scope),
                message=(
                    "You derive only from a policy attached to you or to one of "
                    f"your groups at {owner} or above: {parent.id} is not"
                    + ("" if who == "you" else f" ({who}, acting for you)")
                ),
            )

    def _find_policy(self, policy_id: str) -> Policy | None:
        try:
            return self.store.get_policy(policy_id)
        except IAMNotFoundError:
            return None

    def _require_policy(self, action: str, policy_id: str) -> Policy:
        """``action`` on the policy as named at its owner scope. A policy that
        does not exist is named at the platform, so the answer is the same as
        for one the caller may not see."""
        policy = self._find_policy(policy_id)
        self.require(
            action,
            policy_resource(
                policy_id, policy.owner_scope if policy else PLATFORM_SCOPE
            ),
            not_found=lambda: IAMNotFoundError(f"Policy {policy_id} not found"),
        )
        if policy is None:
            raise IAMNotFoundError(f"Policy {policy_id} not found")
        return policy

    def _drop_owned(self, org: str, workspace: str) -> bool:
        """Delete what a deleted workspace owns, or, for an org (``workspace``
        ``-``), what the org and each of its workspaces own: policies with their
        attachments and invitations, and groups with their attachments,
        members and mappings. Whether anything went."""
        if workspace != NONE:
            owners = [scope_name(org, workspace)]
        else:
            owners = [scope_name(org)] + [
                scope_name(org, s.workspace)
                for s in self.store.list_scopes(org)
                if s.workspace != NONE
            ]
        changed = False
        # Sub-policies first, the deepest first: a parent is never deleted
        # while one is left (each is owned at or below its parent's owner).
        owned = self._all_policies(owners)
        depth = {p.id: len(self._chain(p, fresh=True)[0]) for p in owned}
        for policy in sorted(owned, key=lambda p: -depth[p.id]):
            for attachment in self.store.list_attachments(policy_id=policy.id):
                self.store.detach(policy.id, attachment.principal_id, attachment.scope)
            for grant in self.store.list_pending_grants(policy_id=policy.id):
                self.store.remove_pending_grant(grant.id)
            self.store.delete_policy(policy.id)
            changed = True
        after: str | None = None
        while True:
            page = self.store.list_principals(
                "group", limit=500, after=after, owner_scopes=owners
            )
            for group in page.items:
                if group.status != "deleted":
                    self._delete_group(group)
                    changed = True
            if page.next_after is None:
                return changed
            after = page.next_after

    def _all_policies(self, owner_scopes: Sequence[str] | None = None) -> list[Policy]:
        found: list[Policy] = []
        after: str | None = None
        while True:
            page = self.store.list_policies(
                limit=1000, after=after, owner_scopes=owner_scopes
            )
            found += page.items
            if page.next_after is None:
                return found
            after = page.next_after

    # =========================================================================
    # Attachments
    # =========================================================================

    def attach_policy(
        self, policy_id: str, principal_id: str, scope: str | None = None
    ) -> Attachment:
        """Attach a policy to a principal, optionally at a scope. Idempotent.

        Attaching a workspace role keeps the principal's platform companion
        (``builtin.platform.member`` or ``.viewer``) in step.
        """
        if scope is not None:
            validate_scope(scope)
        self._require_attach(policy_id, principal_id, scope)
        return self._attach(policy_id, principal_id, scope)

    def _require_attach(
        self, policy_id: str, principal_id: str, scope: str | None
    ) -> None:
        """``iam:AttachPolicy`` on the attachment, for ``attach_policy``,
        ``create_pending_grant`` and ``bind_idp_group``.

        A policy confined to ``${scope}:`` but not wholly within it (a Deny
        naming anything, which a scope does not narrow) is attached at a scope
        only by whoever may attach it unscoped, the platform admin: a scope's
        admin or owner could otherwise impose that Deny on anyone, in any org.
        One with an Allow outside it is refused to everyone
        (``_check_attachable``)."""
        self.require(
            "iam:AttachPolicy",
            attachment_resource(policy_id, principal_id, scope),
            not_found=lambda: IAMNotFoundError("Policy or principal not found"),
        )
        if scope is None:
            return
        policy = self._find_policy(policy_id)
        if (
            policy is None
            or not policy.document.confined_to_scope
            or not self._denies_beyond_scope(policy)
        ):
            return
        unscoped = attachment_resource(policy_id, principal_id, None)
        if not self.authorize("iam:AttachPolicy", unscoped).allowed:
            raise PermissionDeniedError(
                "iam:AttachPolicy",
                unscoped,
                message=(
                    f"{policy_id} denies beyond ${{scope}}: only whoever may "
                    "attach it unscoped (the platform admin) attaches it at a scope"
                ),
            )

    def _attach(
        self,
        policy_id: str,
        principal_id: str,
        scope: str | None,
        *,
        held: bool = False,
    ) -> Attachment:
        """``held``: the caller was already found to hold what it grants."""
        policy = self.store.get_policy(policy_id)
        principal = self._get_principal(principal_id)
        if principal.status == "deleted":
            raise IAMConflictError(f"Principal {principal_id} is deleted")
        self._check_attachable(policy, scope)
        self._check_receives(principal, scope)
        existing = self._find_attachment(policy_id, principal_id, scope)
        if existing is not None:
            return existing
        if not held:
            self._require_held(
                policy.document,
                [scope],
                policy_id=policy_id,
                parents=self._parents(policy),
            )
        attachment = self.store.attach(
            Attachment(new_id("att"), policy_id, principal_id, scope)
        )
        if policy_id in roles.ROLES:
            self._sync_platform_roles(principal_id)
            self._sync_feature_policies(principal_id)
        self._changed()
        return attachment

    def _check_attachable(self, policy: Policy, scope: str | None) -> None:
        if not within_owner(policy.owner_scope, scope):
            self._outside_owner(
                "iam:GetPolicy",
                policy_resource(policy.id, policy.owner_scope),
                f"Policy {policy.id} belongs to {policy.owner_scope}: it is attached "
                "there or below, always at a scope",
            )
        if scope is None and self._uses_scope(policy):
            raise ValueError(
                f"{policy.id} uses ${{scope}}, or its chain does: attach it at a scope"
            )
        if scope is not None and not policy.document.confined_to_scope:
            # A scope only fills ${scope}: anything else would reach past it.
            raise ValueError(
                f"{policy.id} names resources outside ${{scope}}: "
                "only a policy confined to its scope is attached at one"
            )

    def _check_receives(self, principal: PrincipalRecord, scope: str | None) -> None:
        """A group owned by an org or a workspace receives attachments at its
        scope or below."""
        if principal.kind == "group" and not within_owner(principal.owner_scope, scope):
            self._outside_owner(
                "iam:GetGroup",
                group_resource(principal.id, principal.owner_scope),
                f"Group {principal.id} belongs to {principal.owner_scope}: it "
                "receives attachments there or below, always at a scope",
            )

    def _outside_owner(self, read: str, name: str, message: str) -> NoReturn:
        """Refuse an attachment beyond its owner: saying why to whoever may read
        the policy or the group, "not found" to anyone else."""
        if self.authorize(read, name).allowed:
            raise ValueError(message)
        raise IAMNotFoundError("Policy or principal not found")

    def detach_policy(
        self, policy_id: str, principal_id: str, scope: str | None = None
    ) -> bool:
        if scope is not None:
            validate_scope(scope)
        self.require(
            "iam:DetachPolicy",
            attachment_resource(policy_id, principal_id, scope),
            not_found=lambda: IAMNotFoundError("Attachment not found"),
        )
        detached = self.store.detach(policy_id, principal_id, scope)
        if detached:
            if policy_id in roles.ROLES:
                self._sync_platform_roles(principal_id)
                self._sync_feature_policies(principal_id)
            if scope is not None:
                self._leave_groups_of(principal_id, scope_fields(scope)[0])
            self._changed()
        return detached

    def list_attachments(
        self, *, principal_id: str | None = None, policy_id: str | None = None
    ) -> list[Attachment]:
        found = self.store.list_attachments(
            principal_id=principal_id, policy_id=policy_id
        )
        allowed = set(
            self.filter(
                "iam:ListAttachments",
                (
                    attachment_resource(a.policy_id, a.principal_id, a.scope)
                    for a in found
                ),
            ).allowed
        )
        return [
            a
            for a in found
            if attachment_resource(a.policy_id, a.principal_id, a.scope) in allowed
        ]

    def _find_attachment(
        self, policy_id: str, principal_id: str, scope: str | None
    ) -> Attachment | None:
        return next(
            (
                a
                for a in self.store.list_attachments(
                    principal_id=principal_id, policy_id=policy_id
                )
                if a.scope == scope
            ),
            None,
        )

    def _sync_platform_roles(self, principal_id: str) -> None:
        """Hold ``builtin.platform.member`` while a member, admin or owner role is
        attached at a workspace or org-wide scope; ``.viewer`` with only viewer
        roles there. Org-level roles (``abi:<org>:-``) bring neither."""
        wanted = _platform_companion(
            self.store.list_attachments(principal_id=principal_id)
        )
        for companion in (roles.PLATFORM_MEMBER, roles.PLATFORM_VIEWER):
            present = self._find_attachment(companion, principal_id, None) is not None
            if companion == wanted and not present:
                self.store.attach(Attachment(new_id("att"), companion, principal_id))
            elif companion != wanted and present:
                self.store.detach(companion, principal_id, None)

    # =========================================================================
    # Grant only what you hold (AGENTS.md, "Grant only what you hold")
    # =========================================================================

    def grantable(self, scope: str) -> list[GrantableCatalog]:
        """What the caller may grant at ``scope``: per catalog, the actions they
        hold there and the resource patterns they hold them on, minus their
        Denies. About the caller only, like ``explain`` of oneself, it needs no
        ``iam:*`` action."""
        validate_scope(scope)
        return self._holdings(current_call_context(), scope).grantable(scope)

    def _require_held(
        self,
        document: PolicyDocument,
        scopes: Iterable[str | None],
        *,
        policy_id: str,
        parents: Sequence[PolicyDocument] | None = (),
    ) -> None:
        """``GrantNotHeldError`` unless the caller holds, at each scope, what
        ``document`` allows there, within ``parents`` for a sub-policy (its
        chain, nearest first; None: a chain that cannot be read whole, which
        grants nothing). A write a first-party account (``engine``, ``api``)
        makes for no user is its own: the route or the boot step that made it
        authorized what it stands for."""
        ctx = current_call_context()
        if ctx.on_behalf_of is None and self._first_party(ctx.principal):
            return
        if parents is None:
            return
        chain = [p.statements for p in parents]
        with grants.budget():  # one budget for every scope
            for scope in dict.fromkeys(scopes):
                holdings = self._holdings(ctx, scope)
                found = holdings.first_uncovered(
                    document.statements, scope, parents=chain
                )
                if found is not None:
                    raise GrantNotHeldError(
                        found.action,
                        found.resource,
                        policy_id=policy_id,
                        statement=found.statement,
                        sid=found.sid,
                        scope=scope,
                        reason=found.reason,
                    )

    def _holdings(self, ctx: CallContext, scope: str | None = None) -> grants.Holdings:
        """What decides for the caller, side by side: the user a call acts for
        (never the first-party account acting, whose statements would stand in
        for the user's), an actor that is not first-party, the credential's
        narrowing, and, for a caller the sets bound, the sets of ``scope``."""
        actor = ctx.principal
        user_id = ctx.user.id if ctx.user is not None else None
        sides: list[grants.Side] = []
        bounded = False
        if ctx.on_behalf_of is not None:
            side, bounded = self._held_side(
                ctx, "user", user_id, "you do not hold it there"
            )
            sides.append(side)
            if not self._first_party(actor):
                side, _ = self._held_side(
                    ctx,
                    "actor",
                    user_id,
                    f"{actor.name or actor.id}, acting for you, does not hold it there",
                )
                sides.append(side)
        else:
            side, bounded = self._held_side(
                ctx, "actor", user_id, "you do not hold it there"
            )
            sides.append(side)
        if bounded and scope is not None:
            sides += self._set_sides(scope)
        if ctx.scope is not None:
            narrowing = tuple(
                grants.held_statement(
                    statement, None, principal_id=actor.id, user_id=user_id
                )
                for statement in token_statements(ctx)
            )
            sides.append(
                grants.Side(narrowing, "the scope of your credential does not allow it")
            )
        return grants.Holdings(sides, self._registry)

    def _held_side(
        self,
        ctx: CallContext,
        side: Literal["actor", "user"],
        user_id: str | None,
        lacks: str,
    ) -> tuple[grants.Side, bool]:
        subject = self.subject(ctx, side)
        if subject is None:
            return grants.Side((), lacks, active=False), False
        return (
            grants.Side(
                tuple(
                    grants.held_statement(
                        statement,
                        effective.scope,
                        principal_id=subject.principal_id,
                        user_id=user_id,
                        policy_id=effective.policy_id,
                    )
                    for effective in subject.statements
                    for statement in _unbounded(effective)
                ),
                lacks,
                active=subject.status == "active",
            ),
            subject.bounded,
        )

    def _set_sides(self, scope: str) -> list[grants.Side]:
        """The sets of ``scope`` as Allow-only sides: an org's set at the org,
        org-wide and at each of its workspaces, a workspace's at the workspace.
        Nobody the sets bound grants, there, what they leave out."""
        try:
            org, workspace = scope_fields(scope)
        except ValueError:
            return []  # a platform policy's abi:*:*: no org's set applies
        if org == NONE:
            return []
        org_set, workspace_set = self.scope_sets(
            org, workspace if workspace not in ("*", NONE) else NONE
        )
        return [
            grants.Side(
                (),
                f"{found.label()} does not include it",
                allowed_for=partial(
                    sets.held_patterns, found, self._registry, scope=scope
                ),
                bound=True,
            )
            for found in (org_set, workspace_set)
            if found is not None
        ]

    def _first_party(self, principal: CallPrincipal) -> bool:
        if principal.kind != "service_account":
            return False
        record = self._resolve(principal)
        return record is not None and record.name in FIRST_PARTY_ACCOUNTS

    # =========================================================================
    # Feature policies: UseFeature comes only from them.
    # =========================================================================

    def put_feature_policies(self, grants: Mapping[str, Sequence[str]]) -> None:
        """Replace the feature policies: ``{key: [feature, ...]}``.

        A key is ``<role>`` (the deployment's grant), ``<org>.<role>`` (an org's
        overlay) or ``<org>.<workspace>.<role>`` (a workspace's override). Each
        becomes the managed policy ``builtin.features.<key>``, and a role
        attached at a workspace scope brings the most specific one that
        exists, attached at the same scope. The set is replaced as a whole:
        keys not named are removed with their attachments. Needs
        ``iam:RegisterCatalog`` on ``nexus``, as the catalog that names the
        features does.
        """
        self.require("iam:RegisterCatalog", catalog_resource("nexus"))
        wanted: dict[str, Policy] = {}
        for key, features in grants.items():
            roles.parse_feature_key(key)
            for feature in features:
                if not _FEATURE_NAME.match(feature):
                    raise ValueError(f"Invalid feature {feature!r}")
            wanted[roles.feature_policy_id(key)] = roles.feature_policy(key, features)
        existing = {p.id for p in self._all_policies() if _is_feature_policy(p.id)}
        for policy in wanted.values():
            self.store.put_managed_policy(policy)
        for stale in existing - wanted.keys():
            for attachment in self.store.list_attachments(policy_id=stale):
                self.store.detach(stale, attachment.principal_id, attachment.scope)
            self._delete_managed(stale)
        holders = {
            a.principal_id
            for role in roles.ROLES
            for a in self.store.list_attachments(policy_id=role)
        }
        for principal_id in sorted(holders):
            self._sync_feature_policies(principal_id, available=set(wanted))
        self._changed()

    def feature_policy_keys(self) -> list[str]:
        """The keys of the feature policies in force (public metadata)."""
        return sorted(
            p.id.removeprefix(roles.FEATURES_PREFIX)
            for p in self._all_policies()
            if _is_feature_policy(p.id)
        )

    def _feature_policy_ids(self) -> set[str]:
        return self._feature_ids.get(
            "ids",
            lambda: {p.id for p in self._all_policies() if _is_feature_policy(p.id)},
        )

    def _companions(
        self, attachments: Sequence[Attachment]
    ) -> set[tuple[str, str | None]]:
        """The (policy, scope) of ``attachments`` IAM's role sync keeps there:
        the feature policies and the platform companion their roles bring. A
        feature or platform policy attached by hand is not one of them."""
        found: set[tuple[str, str | None]] = set(
            _feature_companions(attachments, self._feature_policy_ids())
        )
        platform = _platform_companion(attachments)
        if platform is not None:
            found.add((platform, None))
        return found

    def _sync_feature_policies(
        self, principal_id: str, *, available: set[str] | None = None
    ) -> None:
        """Hold, at each workspace scope a role is attached at, the most
        specific feature policy that exists for that role and scope."""
        known = available if available is not None else self._feature_policy_ids()
        attachments = self.store.list_attachments(principal_id=principal_id)
        wanted = _feature_companions(attachments, known)
        present = {
            (a.policy_id, a.scope)
            for a in attachments
            if _is_feature_policy(a.policy_id) and a.scope is not None
        }
        for policy_id, scope in sorted(wanted - present):
            self.store.attach(Attachment(new_id("att"), policy_id, principal_id, scope))
        for policy_id, scope in sorted(present - wanted):
            self.store.detach(policy_id, principal_id, scope)

    # =========================================================================
    # Invitations and IdP group bindings
    # =========================================================================

    def create_pending_grant(
        self, provider: str, email: str, policy_id: str, scope: str | None = None
    ) -> PendingGrant:
        """Attach ``policy_id`` at ``scope`` to whoever first signs in through
        ``provider`` with ``email`` verified.

        Authorized exactly as attaching it to a user would be: the invitee is
        named in the attachment's resource, so a workspace admin can invite to
        that workspace and no further, and the owner rules of the roles hold.
        """
        provider, email = _grantee(provider, email)
        if scope is not None:
            validate_scope(scope)
        self._require_attach(policy_id, _invitee(provider, email), scope)
        policy = self.store.get_policy(policy_id)
        self._check_attachable(policy, scope)
        existing = next(
            (
                g
                for g in self.store.list_pending_grants(
                    provider=provider, email=email, policy_id=policy_id
                )
                if g.scope == scope
            ),
            None,
        )
        if existing is not None:
            return existing
        self._require_held(
            policy.document, [scope], policy_id=policy_id, parents=self._parents(policy)
        )
        try:
            grant = self.store.add_pending_grant(
                PendingGrant(
                    new_id("pgr"),
                    provider,
                    email,
                    policy_id,
                    scope,
                    created_by=self.current_user_or_actor(),
                )
            )
        except IAMConflictError:
            # The same invitation, made at the same time.
            return next(
                g
                for g in self.store.list_pending_grants(
                    provider=provider, email=email, policy_id=policy_id
                )
                if g.scope == scope
            )
        self._changed()
        return grant

    def list_pending_grants(
        self,
        *,
        provider: str | None = None,
        email: str | None = None,
        policy_id: str | None = None,
    ) -> list[PendingGrant]:
        if email is not None:
            email = email.strip().lower()
        found = self.store.list_pending_grants(
            provider=provider, email=email, policy_id=policy_id
        )
        allowed = set(
            self.filter(
                "iam:ListAttachments", (_grant_resource(g) for g in found)
            ).allowed
        )
        return [g for g in found if _grant_resource(g) in allowed]

    def revoke_pending_grant(self, grant_id: str) -> bool:
        grant = self.store.get_pending_grant(grant_id)
        if grant is None:
            return False
        self.require(
            "iam:DetachPolicy",
            _grant_resource(grant),
            not_found=lambda: IAMNotFoundError("Pending grant not found"),
        )
        removed = self.store.remove_pending_grant(grant_id)
        if removed:
            self._changed()
        return removed

    def claim_pending_grants(self, principal_id: str) -> list[Attachment]:
        """The grants the user's provider and verified email were invited with.

        Never by a supplied email: the user's own record says which provider
        vouched for which address, so a grant reaches that person on that
        provider only, and nobody who merely typed the address.
        """
        self.require(
            "iam:ClaimPendingGrants",
            principal_resource(principal_id),
            not_found=lambda: IAMNotFoundError(f"Principal {principal_id} not found"),
        )
        user = self._get_principal(principal_id)
        if (
            user.kind != "user"
            or user.status != "active"
            or not user.email_verified
            or not user.email
            or not user.provider
        ):
            return []
        email = user.email.strip().lower()
        # Every sign-in asks: the common answer (no invitation for this person)
        # costs one read of the revision, the index of who has pending grants
        # being rebuilt only when the store changed.
        if (user.provider, email) not in self._pending_keys():
            return []
        claimed: list[Attachment] = []
        for grant in self.store.list_pending_grants(
            provider=user.provider, email=email
        ):
            attachment = self.store.claim_pending_grant(
                grant.id, principal_id, new_id("att")
            )
            if attachment is None:
                continue  # another sign-in of this user claimed it first
            claimed.append(attachment)
        if any(a.policy_id in roles.ROLES for a in claimed):
            # The roles' companions, as for attached ones: once for them all.
            self._sync_platform_roles(principal_id)
            self._sync_feature_policies(principal_id)
        if claimed:
            self._changed()
        return claimed

    def _pending_keys(self) -> frozenset[tuple[str, str]]:
        revision = self.store.revision()
        held = self._pending_index
        if held is None or held[0] != revision:
            held = (
                revision,
                frozenset(
                    (g.provider, g.email) for g in self.store.list_pending_grants()
                ),
            )
            self._pending_index = held
        return held[1]

    def bind_idp_group(
        self, provider: str, claim_value: str, policy_id: str, scope: str | None = None
    ) -> IdpBinding:
        """Give the members of ``provider``'s group ``claim_value`` the policy at
        ``scope``. The ABI group that carries it is created and mapped here, as
        part of the one operation the caller was authorized for: attaching that
        policy at that scope, which is all the binding can ever grant."""
        provider, claim_value = _grantee(provider, claim_value, email=False)
        if scope is not None:
            validate_scope(scope)
        self._require_attach(policy_id, _bound_group(provider, claim_value), scope)
        policy = self.store.get_policy(policy_id)
        self._check_attachable(policy, scope)
        group = self._find_binding_group(provider, claim_value, scope)
        if group is None or self._find_attachment(policy_id, group.id, scope) is None:
            # Re-binding what is bound grants nothing new. Otherwise, before the
            # group is made: a refused binding leaves nothing behind.
            self._require_held(
                policy.document,
                [scope],
                policy_id=policy_id,
                parents=self._parents(policy),
            )
            group = self._binding_group(provider, claim_value, scope)
        attachment = self._attach(policy_id, group.id, scope, held=True)
        return IdpBinding(
            provider, claim_value, group.id, policy_id, scope, attachment.id
        )

    def _binding_group(
        self, provider: str, claim_value: str, scope: str | None
    ) -> PrincipalRecord:
        """The group of a claim value for the org of ``scope`` (the platform's
        for a platform or unscoped binding), made when there is none: it
        belongs to that org, so it holds that org's attachments only."""
        found = self._find_binding_group(provider, claim_value, scope)
        if found is not None:
            return found
        org = scope_fields(scope)[0] if scope is not None else NONE
        owner = scope_name(org) if org != NONE else PLATFORM_SCOPE
        name = _bound_group(provider, claim_value)
        group = self.store.create_principal(
            PrincipalRecord(
                id=new_id("grp"),
                kind="group",
                name=name,
                org=org if org != NONE else None,
                owner_scope=owner,
            )
        )
        self.store.map_idp_group(GroupMapping(provider, claim_value, group.id))
        self._changed()
        return group

    def _find_binding_group(
        self, provider: str, claim_value: str, scope: str | None
    ) -> PrincipalRecord | None:
        org = scope_fields(scope)[0] if scope is not None else NONE
        owner = scope_name(org) if org != NONE else PLATFORM_SCOPE
        for group_id in self._binding_groups(provider, claim_value):
            record = self.store.get_principal(group_id)
            if record.owner_scope == owner:
                return record
        return None

    def unbind_idp_group(
        self, provider: str, claim_value: str, policy_id: str, scope: str | None = None
    ) -> bool:
        provider, claim_value = _grantee(provider, claim_value, email=False)
        if scope is not None:
            validate_scope(scope)
        self._require_detach_binding(policy_id, provider, claim_value, scope)
        # Only the groups bindings made: the caller was authorized for these, not
        # for a hand-made group that maps the same claim.
        removed = False
        for group_id in self._binding_groups(provider, claim_value):
            if self.store.detach(policy_id, group_id, scope):
                self._sync_platform_roles(group_id)
                self._sync_feature_policies(group_id)
                removed = True
        if removed:
            self._changed()
        return removed

    def _binding_groups(self, provider: str, claim_value: str) -> list[str]:
        name = _bound_group(provider, claim_value)
        found: list[str] = []
        for group_id in self.store.resolve_idp_groups(provider, [claim_value]):
            record = self.store.get_principal(group_id)
            if (
                record.kind == "group"
                and record.status == "active"
                and record.name == name
            ):
                found.append(group_id)
        return found

    def _require_detach_binding(
        self, policy_id: str, provider: str, claim_value: str, scope: str | None
    ) -> None:
        self.require(
            "iam:DetachPolicy",
            attachment_resource(policy_id, _bound_group(provider, claim_value), scope),
            not_found=lambda: IAMNotFoundError("Binding not found"),
        )

    def list_idp_bindings(
        self, *, provider: str | None = None, policy_id: str | None = None
    ) -> list[IdpBinding]:
        found: list[IdpBinding] = []
        after: str | None = None
        while True:
            page = self.store.list_principals("group", limit=500, after=after)
            for group in page.items:
                # Only the groups bindings made (hand-made groups that map a claim
                # are managed as groups). Following up: a store query for them,
                # instead of one read of the mappings per group.
                if group.status != "active" or not (group.name or "").startswith(
                    "idp:"
                ):
                    continue
                mappings = [
                    m
                    for m in self.store.list_idp_group_mappings(group.id)
                    if provider in (None, m.provider)
                    and group.name == _bound_group(m.provider, m.claim_value)
                ]
                if not mappings:
                    continue
                for attachment in self.store.list_attachments(
                    principal_id=group.id, policy_id=policy_id
                ):
                    if _is_feature_policy(attachment.policy_id) or (
                        attachment.scope is None
                        and attachment.policy_id
                        in (roles.PLATFORM_MEMBER, roles.PLATFORM_VIEWER)
                    ):
                        continue  # IAM's companions of the roles, not bindings
                    found += [
                        IdpBinding(
                            m.provider,
                            m.claim_value,
                            group.id,
                            attachment.policy_id,
                            attachment.scope,
                            attachment.id,
                        )
                        for m in mappings
                    ]
            if page.next_after is None:
                break
            after = page.next_after
        allowed = set(
            self.filter(
                "iam:ListAttachments",
                (attachment_resource(b.policy_id, b.group_id, b.scope) for b in found),
            ).allowed
        )
        return [
            b
            for b in found
            if attachment_resource(b.policy_id, b.group_id, b.scope) in allowed
        ]

    # =========================================================================
    # Tokens: the engine signs, everyone verifies with the JWKS.
    # =========================================================================

    def jwks(self) -> dict[str, Any]:
        """The public signing keys and the issuer. Public: no action needed."""
        return self.tokens.jwks()

    def verifier(self, audiences: Iterable[str] = KERNEL_AUDIENCES) -> JWKSVerifier:
        """A verifier reading this process's JWKS, with no NATS hop. By default
        it accepts what every kernel endpoint does: a service's own token and a
        module's delegation for a user. It refuses what was revoked."""
        return JWKSVerifier(self.jwks, audiences=audiences, revoked=self.token_revoked)

    def token_revoked(self, claims: TokenClaims) -> bool:
        """Whether ``revoke_tokens`` cut this token off: it was issued at or
        before the floor of its subject or of its actor."""
        return any(
            self._revoked_since(principal_id, claims.issued_at)
            for principal_id in (claims.subject, claims.actor)
            if principal_id
        )

    def issue_after_floor(self, *principal_ids: str | None) -> int | None:
        """The earliest ``iat`` a token for these principals may carry: one
        second past their latest revocation, so a token made right after
        ``revoke_tokens`` is not cut off with the ones it revoked. None when no
        revocation applies."""
        floors = self._token_floors()
        latest = max(
            (floors[p].timestamp() for p in principal_ids if p and p in floors),
            default=None,
        )
        return None if latest is None else int(latest) + 1

    def revoked_since(self, principal_id: str, issued_at: int) -> bool:
        """Whether ``revoke_tokens`` cut off what was issued to or for
        ``principal_id`` (the id a call names it by) at ``issued_at``: for the
        sessions a service signs itself."""
        return self._revoked_since(principal_id, issued_at)

    def _revoked_since(self, principal_id: str, issued_at: int) -> bool:
        floor = self._token_floors().get(principal_id)
        return floor is not None and issued_at <= floor.timestamp()

    def _token_floors(self) -> dict[str, datetime]:
        return self._floors.get("floors", self._load_floors)

    def _load_floors(self) -> dict[str, datetime]:
        """Floors by the id calls name a principal by: its own, and for a user
        of the old Nexus login not yet linked, the Nexus id its tokens carry."""
        floors: dict[str, datetime] = {}
        for principal_id, floor in self.store.token_floors().items():
            floors[principal_id] = floor
            try:
                record = self.store.get_principal(principal_id)
            except IAMNotFoundError:
                continue
            if record.issuer == LEGACY_NEXUS_ISSUER and record.subject:
                floors[record.subject] = max(floor, floors.get(record.subject, floor))
        return floors

    def issue_service_token(
        self, name: str, *, audience: str = NATS_AUDIENCE
    ) -> IssuedToken:
        """A token for the engine's own service account ``name`` (``engine``,
        ``api``), for code running in this process. Not exposed over NATS:
        remote callers exchange a key."""
        if not issuable_audience(audience):
            raise ValueError(f"No tokens for audience {audience!r}")
        record = self.store.find_service_account(name)
        if record is None or not record.active:
            raise IAMNotFoundError(f"No active service account {name!r}")
        return self.tokens.issue(
            record.id,
            kind="service_account",
            audience=audience,
            name=record.name,
            min_issued_at=self.issue_after_floor(record.id),
        )

    def exchange_key(self, value: str, audience: str = NATS_AUDIENCE) -> IssuedToken:
        """A service account's key for an access token: ``abi:nats``
        for the kernel services, or ``abi:host:<recipient>`` for one module
        host it calls (the host forwards it to discovery, which accepts it from
        that host only, and no kernel service accepts it).

        The key is the credential: no caller is checked. ``KeyRefusedError``
        for every refusal, whatever its cause.
        """
        principal, _ = self.authenticate_key(value)
        if not issuable_audience(audience):
            raise ValueError(f"No tokens for audience {audience!r}")
        return self.tokens.issue(
            principal.id,
            kind="service_account",
            audience=audience,
            name=principal.name,
            min_issued_at=self.issue_after_floor(principal.id),
        )

    def issue_host_token(
        self,
        caller: CallPrincipal,
        recipient: str,
        on_behalf_of: CallPrincipal | None = None,
        scope: Sequence[Mapping[str, Any]] | None = None,
    ) -> IssuedToken:
        """A token for one host (``recipient``: its subject token) for an
        already verified ``caller``: what the engine stores with a job trigger
        or cancel, in place of the caller's own ``abi:nats`` token that the
        job's host would otherwise hold. With ``on_behalf_of`` the token names
        that user and ``caller`` as the one acting for them, as a delegation
        does, but is addressed to the host alone: no kernel service accepts it.
        ``scope`` is the limit the caller's own credential carried (a key's),
        which what the job runs for the user stays within. In process only."""
        if on_behalf_of is None:
            return self.tokens.issue(
                caller.id,
                kind=caller.kind,
                audience=host_audience(recipient),
                name=caller.name if caller.kind == "service_account" else None,
            )
        return self.tokens.issue(
            on_behalf_of.id,
            kind="user",
            audience=host_audience(recipient),
            actor=caller.id,
            actor_name=caller.name if caller.kind == "service_account" else None,
            groups=self.active_groups(on_behalf_of.groups),
            scope=scope,
        )

    def authenticate_key(self, value: str) -> tuple[PrincipalRecord, KeyRecord]:
        """The active service account a valid ``abi_sk_`` key belongs to.

        Revocation, expiry and suspension take effect at once: nothing here is
        cached. Records the key's last use, at most once a minute: a storm of
        reconnects or exchanges writes nothing to the store.
        """
        record, principal = self._authenticate(value, ("service",), "service_account")
        return principal, record

    def authenticate_user_key(self, value: str) -> tuple[KeyRecord, PrincipalRecord]:
        """The key and the active user of a valid ``abi_pk_`` or ``abi_gk_`` key.
        ``KeyRefusedError``, one message, for every refusal."""
        return self._authenticate(value, ("personal", "grant"), "user")

    def _authenticate(
        self, value: str, kinds: tuple[KeyKind, ...], owner_kind: PrincipalKind
    ) -> tuple[KeyRecord, PrincipalRecord]:
        try:
            presented = keys.parse(value)
            record = self.store.get_key(presented.key_id)
            principal = self.store.get_principal(record.principal_id)
        except (ValueError, IAMNotFoundError):
            raise KeyRefusedError() from None
        now = datetime.now(UTC)
        if (
            presented.kind not in kinds
            or record.kind != presented.kind
            or not presented.matches(record.secret_hash)
            or not record.usable(now)
            or principal.kind != owner_kind
            or not principal.active
        ):
            raise KeyRefusedError()
        if (
            record.last_used_at is None
            or now - record.last_used_at >= _LAST_USED_RESOLUTION
        ):
            self.store.touch_key(record.key_id, now)
        return record, principal

    # =========================================================================
    # Token exchange and revocation
    # =========================================================================

    def exchange_token(self, request: TokenExchange) -> IssuedToken:
        return self._exchanger.exchange(request)

    def revoke_tokens(self, principal_id: str, *, include_keys: bool = False) -> None:
        """Every token issued so far to or for ``principal_id`` stops working
        (the next verification refuses it), and so do its links and coding
        keys, which would otherwise mint new ones. Personal API keys are kept
        unless ``include_keys``: changing a password is no reason to break a
        script. Needs ``iam:RevokeTokens``, which every user holds on
        themselves."""
        self.require(
            "iam:RevokeTokens",
            principal_resource(principal_id),
            not_found=lambda: IAMNotFoundError(f"Principal {principal_id} not found"),
        )
        record = self._user_or_account(principal_id, create=True)
        now = self.tokens.now()
        self.store.set_token_floor(record.id, now)
        for key in self.store.list_keys(record.id):
            ends = (
                include_keys
                or key.kind == "grant"
                or (key.kind == "personal" and key.audience == CODING_AUDIENCE)
            )
            if ends and key.revoked_at is None:
                self.store.revoke_key(key.key_id, now)
        self._changed()

    def resolve_user(self, user_id: str) -> PrincipalRecord | None:
        """The stored user a call names by ``user_id``: its principal id, or for
        a user of the old Nexus login not yet linked, the Nexus id."""
        return self._resolve(CallPrincipal(id=user_id, kind="user"))

    def resolve_principal(self, principal: CallPrincipal) -> PrincipalRecord | None:
        return self._resolve(principal)

    @staticmethod
    def user_name(record: PrincipalRecord) -> str:
        """The id calls name ``record`` by: its principal id, or for a user of
        the old Nexus login not yet linked the Nexus id its sessions carry."""
        if record.issuer == LEGACY_NEXUS_ISSUER and record.subject:
            return record.subject
        return record.id

    def _user_or_account(self, principal_id: str, *, create: bool) -> PrincipalRecord:
        """The principal named ``principal_id``; a built-in login user IAM has
        no record of yet is recorded (as engine) when ``create``."""
        try:
            return self._get_principal(principal_id)
        except IAMNotFoundError:
            pass
        legacy = self.store.find_user(LEGACY_NEXUS_ISSUER, principal_id)
        if legacy is not None:
            return legacy
        if create and not _PRINCIPAL_ID.match(principal_id):
            with as_service_account("engine"):
                return self.ensure_user(LEGACY_NEXUS_ISSUER, principal_id)
        raise IAMNotFoundError(f"Principal {principal_id} not found")

    # =========================================================================
    # Job trigger seals
    # =========================================================================

    def seal_trigger(self, fields: Sequence[Any]) -> str:
        """The seal of a job trigger the engine stores: an HMAC over
        ``fields`` (its subject, kind, body hash and claim-check headers, as
        the broker control lists them), with a key in ``IAMSecrets``. A job
        host stores no key: it asks the engine whether a seal is its own
        (``trigger_sealed``). In process only."""
        import base64
        import hashlib
        import hmac
        import json

        digest = hmac.new(
            self._trigger_seal_key(),
            json.dumps(list(fields), separators=(",", ":")).encode(),
            hashlib.sha256,
        ).digest()
        return f"{TRIGGER_SEAL_VERSION}.{base64.urlsafe_b64encode(digest).decode()}"

    def trigger_sealed(self, fields: Sequence[Any], seal: str) -> bool:
        """Whether ``seal`` is this engine's over ``fields``."""
        import hmac

        return bool(seal) and hmac.compare_digest(self.seal_trigger(fields), seal)

    def _trigger_seal_key(self) -> bytes:
        import base64
        import secrets as random

        with self._seal_lock:
            if self._seal_key is None:
                stored = self.secrets.get(TRIGGER_SEAL_SECRET)
                if not stored:
                    self.secrets.put(
                        TRIGGER_SEAL_SECRET,
                        base64.urlsafe_b64encode(random.token_bytes(32)).decode(),
                    )
                    # Another engine may have written it meanwhile: the stored one wins.
                    stored = self.secrets.get(TRIGGER_SEAL_SECRET)
                self._seal_key = base64.urlsafe_b64decode(str(stored))
            return self._seal_key

    def engine_service_key(self) -> str:
        """The engine's own key, kept in ``IAMSecrets`` for client-role engines
        of this deployment, created on first use. In process only."""
        stored = self.secrets.get(ENGINE_KEY_SECRET)
        if stored:
            try:
                self.authenticate_key(stored)
                return stored
            except KeyRefusedError:
                logger.info("The stored engine service key is no longer valid")
        engine = self.store.find_service_account("engine")
        if engine is None:
            raise IAMNotFoundError("IAM is not bootstrapped")
        # One such key at a time: a process that never saw the stored key (its
        # secret service read before another wrote it) replaces it.
        now = datetime.now(UTC)
        for earlier in self.store.list_keys(engine.id):
            if earlier.description == ENGINE_KEY_DESCRIPTION and earlier.usable(now):
                self.store.revoke_key(earlier.key_id, now)
        created = self._create_key(engine, description=ENGINE_KEY_DESCRIPTION)
        self.secrets.put(ENGINE_KEY_SECRET, created.value)
        return created.value

    # =========================================================================
    # Keys
    # =========================================================================

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

        * A service account's key is ``service``: at most five active;
          ``ci/*`` keys expire in 90 days unless told otherwise, module keys
          never do.
        * A user's key is ``personal`` (default): an API key for
          ``abi:delegated:api-key``, or a coding environment's with
          ``audience=abi:delegated:coding`` and the environment as ``resource``.
          It always expires, in a year at most (the default). Five active API
          keys, fifty coding keys.
        * ``kind="grant"``: the link of an app or a preview (audience app or
          preview), always expiring, in 8 hours at most.

        ``scope`` narrows every token the key buys.
        """
        named = principal_id
        found = self._find_key_owner(principal_id)
        owner_kind = found.kind if found is not None else self._unrecorded_kind(named)
        spec = _key_spec(owner_kind, kind, audience, resource, scope, expires_at)
        new = keys.generate_key(spec.kind)
        self.require(
            "iam:CreateKey",
            key_resource(named, new.key_id),
            not_found=lambda: IAMNotFoundError(f"Principal {principal_id} not found"),
        )
        owner = (
            found if found is not None else self._user_or_account(named, create=True)
        )
        if owner.status == "deleted":
            raise IAMConflictError(f"Principal {principal_id} is deleted")
        return self._store_key(owner, new, spec, description, expires_at)

    def _create_key(
        self,
        principal: PrincipalRecord,
        *,
        description: str = "",
        expires_at: datetime | None = None,
    ) -> CreatedKey:
        """A service key made by the engine itself (its own, the engine's)."""
        spec = _key_spec(principal.kind, None, None, None, None, expires_at)
        return self._store_key(
            principal, keys.generate_key("service"), spec, description, expires_at
        )

    def _store_key(
        self,
        principal: PrincipalRecord,
        new: keys.NewKey,
        spec: _KeySpec,
        description: str,
        expires_at: datetime | None,
    ) -> CreatedKey:
        now = datetime.now(UTC)
        expires_at = spec.expiry(now, expires_at, principal.name)
        bucket = spec.bucket
        held = self.store.list_keys(principal.id)
        if spec.kind == "grant":
            held = self._prune_grants(held, now)
        active = [k for k in held if k.usable(now) and _bucket(k) == bucket]
        if len(active) >= spec.limit:
            raise IAMConflictError(
                f"{principal.id} holds {spec.limit} active keys of this kind: "
                "revoke one first"
            )
        record = self.store.create_key(
            KeyRecord(
                key_id=new.key_id,
                principal_id=principal.id,
                secret_hash=new.secret_hash,
                kind=spec.kind,
                description=description,
                created_at=now,
                expires_at=expires_at,
                audience=spec.audience,
                resource=spec.resource,
                scope=spec.scope,
            )
        )
        self._changed()
        return CreatedKey(record, new.value)

    def _prune_grants(self, held: list[KeyRecord], now: datetime) -> list[KeyRecord]:
        """``held`` without the grants (links) that ended more than a day ago,
        expired or revoked: nothing can use them, and a user who opens many
        links would otherwise keep them, and have them listed at every mint,
        for good. Within the day they stay, for whoever looks into a link."""
        cutoff = now - _GRANT_RETENTION
        dead = [
            k.key_id
            for k in held
            if k.kind == "grant"
            and not k.usable(now)
            and min(t for t in (k.revoked_at, k.expires_at) if t is not None) < cutoff
        ]
        if not dead:
            return held
        self.store.delete_keys(dead)
        return [k for k in held if k.key_id not in set(dead)]

    def _find_key_owner(self, principal_id: str) -> PrincipalRecord | None:
        try:
            return self._get_principal(principal_id)
        except IAMNotFoundError:
            return self.store.find_user(LEGACY_NEXUS_ISSUER, principal_id)

    @staticmethod
    def _unrecorded_kind(principal_id: str) -> PrincipalKind | None:
        """A principal IAM has no record of: only a user of the built-in login
        (a Nexus id) is recorded on demand."""
        return None if _PRINCIPAL_ID.match(principal_id) else "user"

    def list_keys(self, principal_id: str) -> list[KeyRecord]:
        owner = self._find_key_owner(principal_id)
        if owner is None:
            return []
        found = self.store.list_keys(owner.id)
        allowed = set(
            self.filter(
                "iam:ListKeys", (key_resource(principal_id, k.key_id) for k in found)
            ).allowed
        )
        return [k for k in found if key_resource(principal_id, k.key_id) in allowed]

    def revoke_key(self, principal_id: str, key_id: str) -> KeyRecord:
        """Takes effect at the next exchange and the next broker connection;
        tokens already issued expire within ten minutes."""
        missing = lambda: IAMNotFoundError(f"Key {key_id} not found")
        self.require(
            "iam:RevokeKey", key_resource(principal_id, key_id), not_found=missing
        )
        owner = self._find_key_owner(principal_id)
        try:
            record = self.store.get_key(key_id)
        except IAMNotFoundError:
            raise missing() from None
        if owner is None or record.principal_id != owner.id:
            raise missing()
        revoked = self.store.revoke_key(key_id, datetime.now(UTC))
        self._changed()
        return revoked

    # =========================================================================
    # Module permission manifests
    # =========================================================================

    def submit_manifest(
        self,
        module_id: str,
        project: str,
        document: Mapping[str, Any] | str | PolicyDocument,
    ) -> ManifestSubmission:
        """The calling module's manifest: pending until an admin approves it.

        The caller must be the service account ``module/<project>/<module_id>``:
        that binds the module's logical name to its credential. Submitting the
        approved version again changes nothing; a new version is pending while
        the approved policy stays in force, unless ``modules.auto_approve``.
        """
        modules.check_module(project, module_id)
        account = self._calling_module_account(project, module_id)
        self.require(
            "iam:SubmitManifest",
            manifest_resource(account.id),
            not_found=lambda: IAMNotFoundError(f"Manifest of {account.id} not found"),
        )
        policy, declared = modules.split_manifest(document)
        parsed = parse_policy_document(policy)
        _refuse_reserved_topics(modules.bind(parsed, project, module_id))
        catalog = self._manifest_catalog(declared, module_id, project)
        raw = modules.manifest_document(parsed, catalog)
        sha256 = modules.manifest_sha256(raw)
        try:
            existing: ManifestRecord | None = self.store.get_manifest(
                account.id, sha256
            )
        except IAMNotFoundError:
            existing = None
        in_force = bool(self.store.list_manifests(account.id, "approved"))
        if existing is not None and existing.status in ("approved", "rejected"):
            return ManifestSubmission(existing, in_force=in_force)
        if existing is not None and existing.status == "superseded":
            # A rollback to an earlier version: it waits for approval again,
            # like a new one (the version in force stays in force).
            existing = self.store.put_manifest(
                replace(existing, status="pending", decided_at=None, decided_by=None)
            )
            if not self.auto_approve:
                logger.info(
                    f"Module {account.name} submitted manifest {sha256[:12]} again: "
                    f"approve it with `abi iam module approve {account.name}`"
                )
                self._changed()
                return ManifestSubmission(existing, in_force=in_force)
        record = existing or self.store.put_manifest(
            ManifestRecord(
                principal_id=account.id,
                sha256=sha256,
                module_id=module_id,
                project=project,
                document=raw,
            )
        )
        if not self.auto_approve:
            if existing is None:
                logger.info(
                    f"Module {account.name} submitted manifest {sha256[:12]}: "
                    f"approve it with `abi iam module approve {account.name}`"
                )
                self._changed()
            return ManifestSubmission(record, in_force=in_force)
        approved = self._approve(record, parsed, decided_by="auto_approve")
        return ManifestSubmission(approved, approved_now=True, in_force=True)

    def _manifest_catalog(
        self, declared: Mapping[str, Any] | None, module_id: str, project: str
    ) -> ActionCatalog | None:
        """The catalog a manifest declares, checked as the module's own: refused
        when it names a reserved service or one another module registered.

        A catalog's service comes from the module id alone, so the same module id
        in two projects would share one: the module of another project whose
        approved manifest declares it keeps it, and this one is refused."""
        if declared is None:
            return None
        catalog = module_scopes.module_catalog(declared, module_id)
        current = self._registry.get(catalog.service)
        if current is not None and current.module != catalog.module:
            raise IAMConflictError(
                f"Catalog {catalog.service} is "
                + (f"module {current.module!r}'s" if current.module else "reserved")
            )
        for other in self.store.list_manifests(None, "approved"):
            if (
                other.module_id == module_id
                and other.project != project
                and modules.split_manifest(other.document)[1] is not None
            ):
                raise IAMConflictError(
                    f"Catalog {catalog.service} is module {module_id!r}'s of project "
                    f"{other.project!r}: one module id declares a catalog in one project"
                )
        return catalog

    def get_manifest(
        self, principal_id: str, sha256: str | None = None
    ) -> ManifestRecord:
        """A manifest version, by default the latest one submitted."""
        missing = lambda: IAMNotFoundError(f"Manifest of {principal_id} not found")
        self.require(
            "iam:GetManifest", manifest_resource(principal_id), not_found=missing
        )
        return self._manifest(principal_id, sha256, missing)

    def list_manifests(
        self, *, principal_id: str | None = None, status: ManifestStatus | None = None
    ) -> list[ManifestRecord]:
        found = self.store.list_manifests(principal_id, status)
        allowed = set(
            self.filter(
                "iam:ListManifests", (manifest_resource(m.principal_id) for m in found)
            ).allowed
        )
        return [m for m in found if manifest_resource(m.principal_id) in allowed]

    def approve_manifest(
        self,
        principal_id: str,
        sha256: str | None = None,
        *,
        document: Mapping[str, Any] | str | PolicyDocument | None = None,
    ) -> ManifestRecord:
        """Approve a module's manifest as submitted, or narrowed to ``document``.

        Without ``sha256``, the latest pending version, and none other: a
        rejected or superseded version is approved by naming its ``sha256``.
        The approved document becomes the managed policy
        ``module.<project>.<module_id>``, attached unscoped: the approver holds
        what it allows, its module variables bound (``_require_held``).
        """
        missing = lambda: IAMNotFoundError(f"Manifest of {principal_id} not found")
        self.require(
            "iam:ApproveManifest", manifest_resource(principal_id), not_found=missing
        )
        record = self._manifest(principal_id, sha256, missing, pending_only=True)
        # A narrowing names the policy alone: the catalog is the record's.
        submitted, _catalog = modules.split_manifest(record.document)
        parsed = parse_policy_document(
            modules.split_manifest(document)[0] if document is not None else submitted
        )
        self._require_held(
            modules.bind(parsed, record.project, record.module_id),
            [None],
            policy_id=modules.policy_id(record.project, record.module_id),
        )
        current = self.current_user_or_actor()
        return self._approve(record, parsed, decided_by=current)

    def reject_manifest(
        self, principal_id: str, sha256: str | None = None, *, reason: str = ""
    ) -> ManifestRecord:
        """Refuse a version; an approved policy in force stays in force."""
        missing = lambda: IAMNotFoundError(f"Manifest of {principal_id} not found")
        self.require(
            "iam:RejectManifest", manifest_resource(principal_id), not_found=missing
        )
        record = self._manifest(principal_id, sha256, missing, pending_only=True)
        if record.status == "approved":
            raise IAMConflictError(
                f"Manifest {record.sha256[:12]} is approved: approve another "
                "version, or suspend the service account"
            )
        rejected = self.store.put_manifest(
            replace(
                record,
                status="rejected",
                decided_at=datetime.now(UTC),
                decided_by=self.current_user_or_actor(),
                reason=reason,
            )
        )
        self._changed()
        return rejected

    def current_user_or_actor(self) -> str:
        current = current_call_context()
        user = current.user
        return (user or current.principal).id

    def _calling_module_account(self, project: str, module_id: str) -> PrincipalRecord:
        caller = current_call_context().principal
        record = self._resolve(caller) if caller.kind == "service_account" else None
        if record is None or record.name != modules.account_name(project, module_id):
            raise PermissionDeniedError(
                "iam:SubmitManifest",
                manifest_resource(record.id if record else caller.id),
                message=(
                    f"Module {module_id!r} of project {project!r} runs as the service "
                    f"account {modules.account_name(project, module_id)!r}, not "
                    f"{(record.name if record else caller.name) or caller.id!r}"
                ),
            )
        return record

    def _manifest(
        self,
        principal_id: str,
        sha256: str | None,
        missing: Callable[[], BaseException],
        *,
        pending_only: bool = False,
    ) -> ManifestRecord:
        """The version ``sha256``; without it the latest one, or with
        ``pending_only`` the latest pending one (``IAMNotFoundError`` when
        nothing waits for a decision)."""
        if sha256:
            try:
                return self.store.get_manifest(principal_id, sha256)
            except IAMNotFoundError:
                raise missing() from None
        found = self.store.list_manifests(principal_id)
        if pending_only:
            found = [m for m in found if m.status == "pending"]
            if not found:
                raise IAMNotFoundError(
                    f"No manifest of {principal_id} waits for a decision: "
                    "name a version (sha256) to decide on another one"
                )
        if not found:
            raise missing()
        return found[-1]

    def _approve(
        self, record: ManifestRecord, document: PolicyDocument, *, decided_by: str
    ) -> ManifestRecord:
        # One approval at a time in this process: the nested-topic check reads
        # what earlier approvals wrote. (Engines and abi iam sharing a store can
        # still race; the broker then grants both topics, JetStream refuses the
        # second queue stream.)
        with self._approve_lock:
            return self._approve_now(record, document, decided_by=decided_by)

    def _approve_now(
        self, record: ManifestRecord, document: PolicyDocument, *, decided_by: str
    ) -> ManifestRecord:
        account = self._get_principal(record.principal_id)
        bound = modules.bind(document, record.project, record.module_id)
        _refuse_reserved_topics(bound)
        self._refuse_nested_topics(account.id, bound)
        # The module's own catalog is part of what is approved: registered with
        # it, and the module's side of its declared actions joins its policy.
        declared = modules.split_manifest(record.document)[1]
        catalog = self._manifest_catalog(declared, record.module_id, record.project)
        if catalog is not None:
            self._register_catalog(catalog)
            bound = replace(
                bound,
                statements=(*bound.statements, modules.own_catalog_statement(catalog)),
            )
        policy_id = modules.policy_id(record.project, record.module_id)
        self.store.put_managed_policy(
            Policy(
                id=policy_id,
                name=f"Module {record.project}/{record.module_id}",
                description=f"The approved permission manifest of {account.name}.",
                document=bound,
                managed=True,
            )
        )
        if self._find_attachment(policy_id, account.id, None) is None:
            self.store.attach(Attachment(new_id("att"), policy_id, account.id))
        for other in self.store.list_manifests(account.id, "approved"):
            if other.sha256 != record.sha256:
                self.store.put_manifest(replace(other, status="superseded"))
        placed = {(p.service, p.id_key) for p in self.store.list_placements()}
        for service, id_key in modules.namespace_placements(record.module_id):
            if (service, id_key) not in placed:
                self.store.put_placement(Placement(service, id_key))
        approved = self.store.put_manifest(
            replace(
                record,
                status="approved",
                decided_at=datetime.now(UTC),
                decided_by=decided_by,
                reason="",
            )
        )
        logger.info(f"Manifest {record.sha256[:12]} of {account.name} approved")
        self._changed()
        return approved

    def _refuse_nested_topics(
        self, principal_id: str, document: PolicyDocument
    ) -> None:
        """No granted topic may sit inside another (``broker.nested_topic_problems``):
        the topics the Allow statements of every policy attached to another
        principal name, managed (approved manifests) or not."""
        others: list[str] = []
        policies = {
            a.policy_id
            for a in self.store.list_attachments()
            if a.principal_id != principal_id
        }
        for policy_id in sorted(policies):
            policy = self._load_policy(policy_id)
            if policy is not None:
                others += broker.topics_of(policy.document.statements)
        problems = broker.nested_topic_problems(
            broker.topics_of(document.statements), others
        )
        if problems:
            raise PolicyValidationError(problems)

    # =========================================================================
    # Broker permissions
    # =========================================================================

    def broker_permissions(
        self, principal: PrincipalRecord, key: KeyRecord
    ) -> broker.BrokerPermissions:
        """The subjects a connection authenticated by ``key`` may use.

        Computed from the store, never from the cache: an approval made a
        moment ago counts at the next connection.
        """
        return self._derive(principal, key.key_id)

    def broker_grants(self, principal_id: str) -> broker.BrokerPermissions:
        """What ``principal_id``'s connections are granted, for the engine's
        broker control to check a request against (no inbox: no key). In
        process only; from the store, never from the cache. A principal that
        is not active is granted nothing (``IAMNotFoundError`` when unknown)."""
        principal = self._get_principal(principal_id)
        if principal.status != "active":
            raise PermissionDeniedError(
                "broker", principal_resource(principal.id), message="not active"
            )
        return self._derive(principal, "-")

    def _derive(
        self, principal: PrincipalRecord, key_id: str
    ) -> broker.BrokerPermissions:
        ctx = CallContext(principal=_call_principal(principal))
        subject = self._compute_subject(ctx.principal, fresh=True)
        # What a module holds only for the actor side of a delegation opens no
        # subject (``roles.DELEGATION_SIDS``).
        statements = [
            effective
            for effective in subject.statements
            if not (
                effective.policy_id == roles.MODULE_BOOTSTRAP
                and effective.statement.sid in roles.DELEGATION_SIDS
            )
            # A module's declared actions are checked in process: no subject.
            and effective.statement.sid != modules.OWN_CATALOG
        ]
        # A sub-policy's Allow opens what is shown within its chain, no more.
        statements = [
            replace(effective, statement=statement, bounds=())
            for effective in statements
            for statement in _unbounded(effective)
        ]
        return broker.derive(
            principal_id=principal.id,
            key_id=key_id,
            statements=statements,
            catalogs=self._registry,
            module=modules.parse_account(principal.name),
        )

    # =========================================================================
    # Boot
    # =========================================================================

    def bootstrap(self) -> None:
        """Seed what every other grant rests on. In process, at engine boot only.

        This is the root of trust, so it runs unchecked: IAM's catalog, the
        managed policies, the built-in service accounts (``engine``, ``api``,
        ``idp``) and their policies (``builtin.engine`` and ``builtin.api`` are
        enumerated statements), and it retires the managed policies an older
        version stored.
        """
        self._register_catalog(CATALOG)
        self._refresh_builtin_policies()
        self._retire_policies()
        for name, policy_id in roles.SERVICE_ACCOUNTS.items():
            record = self.store.find_service_account(name)
            if record is None:
                record = self.store.create_principal(
                    PrincipalRecord(id=new_id("sa"), kind="service_account", name=name)
                )
            if self._find_attachment(policy_id, record.id, None) is None:
                self.store.attach(Attachment(new_id("att"), policy_id, record.id))
        self._changed()

    def _retire_policies(self) -> None:
        for policy_id in roles.RETIRED_POLICIES:
            try:
                self.store.get_policy(policy_id)
            except IAMNotFoundError:
                continue
            for attachment in self.store.list_attachments(policy_id=policy_id):
                self.store.detach(policy_id, attachment.principal_id, attachment.scope)
            self._delete_managed(policy_id)

    def _delete_managed(self, policy_id: str) -> None:
        """Delete a managed policy IAM no longer generates, once detached. One
        that is a parent stays, so its sub-policies stay bounded by it rather
        than lose their chain: an administrator re-parents them first."""
        subs = self.store.list_sub_policies(policy_id)
        if subs:
            logger.warning(
                f"IAM keeps {policy_id}, which it no longer generates: it is the "
                f"parent of {', '.join(p.id for p in subs)}. Give them another "
                "parent, then it goes."
            )
            return
        self.store.delete_policy(policy_id)

    def set_platform_grants(self, grants: Sequence[roles.PlatformGrant]) -> None:
        """The deployment's own platform-level resources every workspace member
        reaches by role level (``roles.PlatformGrant``: Nexus's shared repository).
        Replaces the previous set; kept in memory and applied again whenever the
        managed policies are regenerated. Needs ``iam:RegisterCatalog`` on ``nexus``."""
        self.require("iam:RegisterCatalog", catalog_resource("nexus"))
        self._platform_grants = tuple(grants)
        self._refresh_builtin_policies()
        self._changed()

    def _refresh_builtin_policies(self) -> None:
        for policy in roles.builtin_policies(self._registry, self._platform_grants):
            self.store.put_managed_policy(policy)

    # =========================================================================
    # Changes
    # =========================================================================

    def add_change_listener(self, listener: Callable[[int], None]) -> None:
        """``listener(revision)`` after every change made through this service."""
        self._listeners.append(listener)

    def remove_change_listener(self, listener: Callable[[int], None]) -> None:
        if listener in self._listeners:
            self._listeners.remove(listener)

    def invalidate(self) -> None:
        """Drop every cached policy, subject and placement."""
        self._subjects.clear()
        self._policies.clear()
        self._placements.clear()
        self._feature_ids.clear()
        self._sets.clear()
        self._floors.clear()

    def refresh_if_changed(self) -> bool:
        """Drop the caches when the store's revision differs from the last one
        this service saw (another process wrote, or the store was restored to
        an older revision). A change notice is only a hint: its number is
        never trusted."""
        revision = self.store.revision()
        if revision == self._seen_revision:
            return False
        self._seen_revision = revision
        self.invalidate()
        # Catalogs another process registered (a module's, at its approval).
        for catalog in self.store.list_catalogs():
            self._registry.register(catalog)
        return True

    def _changed(self) -> None:
        # The revision first: a write of another process between the two would
        # otherwise be recorded as seen, and its notice ignored.
        revision = self.store.revision()
        self.invalidate()
        self._seen_revision = revision
        for listener in list(self._listeners):
            try:
                listener(revision)
            except Exception as exc:  # noqa: BLE001 - a listener never fails a write
                logger.warning(f"IAM change listener failed: {exc!r}")

    # =========================================================================
    # Helpers
    # =========================================================================

    def _filtered_page(
        self,
        fetch: Callable[[int, str | None], Page],
        action: str,
        name: Callable[[Any], str],
        limit: int,
        after: str | None,
    ) -> Page:
        """A page of allowed items; paging applies after filtering."""

        def keep(items: list[Any]) -> set[str]:
            allowed = set(self.filter(action, (name(i) for i in items)).allowed)
            return {i.id for i in items if name(i) in allowed}

        return self._kept_page(fetch, keep, (action,), limit, after)

    def _kept_page(
        self,
        fetch: Callable[[int, str | None], Page],
        keep: Callable[[list[Any]], set[str]],
        actions: Sequence[str],
        limit: int,
        after: str | None,
    ) -> Page:
        """A page of the items ``keep`` admits (it returns their ids), which it
        decides with ``actions``; paging applies after it."""
        if not 1 <= limit <= 1000:
            raise ValueError("limit must be between 1 and 1000")
        if not any(self.filter(action, ()).prefix_hints for action in actions):
            # No Allow of the caller's can admit an item: nothing to scan for.
            return Page([], None)
        items: list[Any] = []
        cursor = after
        while True:
            page = fetch(limit, cursor)
            kept = keep(page.items)
            for item in page.items:
                if item.id in kept:
                    items.append(item)
                    if len(items) == limit:
                        more = item is not page.items[-1] or page.next_after is not None
                        return Page(items, item.id if more else None)
            if page.next_after is None:
                return Page(items, None)
            cursor = page.next_after

    def close(self) -> None:
        self.store.close()


def _owner_scope(scope: str | None, org: str | None) -> str:
    """The owner of a new group: ``scope``, else ``abi:<org>:-``, else the
    platform. ``org`` and ``scope`` together must agree."""
    if scope is None:
        return scope_name(org) if org is not None else PLATFORM_SCOPE
    validate_owner_scope(scope)
    if org is not None and scope_fields(scope)[0] != org:
        raise ValueError(f"Scope {scope} is not in org {org}")
    return scope


# Where a platform policy's ``${scope}`` may be filled: any scope, as a pattern.
_ANY_SCOPE = "abi:*:*"


def _bind_bounds(
    bounds: tuple[Bound, ...], values: Mapping[str, str | None]
) -> tuple[Bound, ...]:
    """A chain's Allows with the module variables bound, as the sub-policy's
    own: a statement left naming nothing bounds nothing through."""
    return tuple(
        Bound(
            bound.policy_id,
            tuple(
                (index, kept)
                for index, statement in bound.allows
                if (kept := bind_variables(statement, values)) is not None
            ),
        )
        for bound in bounds
    )


def _unbounded(effective: EffectiveStatement) -> list[Statement]:
    """A statement as what it holds with no chain: an Allow of a sub-policy
    narrowed to what is shown within its chain (``grants.within_chain``)."""
    if not effective.bounds:
        return [effective.statement]
    return grants.within_chain(
        effective.statement,
        [
            [statement for _index, statement in bound.allows]
            for bound in effective.bounds
        ],
        effective.scope,
    )


def _as_owner(scope: str | None) -> str:
    """The owner level an attachment at ``scope`` reaches from: unscoped and the
    platform's the platform, an org-wide one its org."""
    if scope is None:
        return PLATFORM_SCOPE
    org, workspace = scope_fields(scope)
    return scope_name(org) if workspace == "*" else scope


def _denies_beyond_scope(documents: Iterable[PolicyDocument]) -> bool:
    """Whether a Deny of one of ``documents`` names anything outside
    ``${scope}:``: then it refuses beyond the scope it is attached at."""
    return any(
        not pattern.startswith(SCOPE_PREFIX)
        for document in documents
        for statement in document.statements
        if statement.effect == "Deny"
        for pattern in statement.resources
    )


def _written_for(owner: str) -> list[str | None]:
    """The scopes a policy is held at when it is written: its owner's for an
    org's or a workspace's (it is attached there or below, and checked again
    there); for the platform's, as written unscoped and at any scope."""
    return [owner] if owner != PLATFORM_SCOPE else [None, _ANY_SCOPE]


def _workspace_roles(
    attachments: Iterable[Attachment],
) -> Iterator[tuple[str, str]]:
    """The (role, scope) attached at a workspace or org-wide scope
    (``abi:<org>:<ws>``, neither ``-``): org-level roles bring no companion."""
    for attachment in attachments:
        if attachment.policy_id not in roles.ROLES or attachment.scope is None:
            continue
        org, workspace = scope_fields(attachment.scope)
        if org != NONE and workspace != NONE:
            yield attachment.policy_id, attachment.scope


def _platform_companion(attachments: Iterable[Attachment]) -> str | None:
    """``builtin.platform.member`` while a member, admin or owner role is
    attached at a workspace or org-wide scope; ``.viewer`` with only viewer
    roles there."""
    held = {role for role, _scope in _workspace_roles(attachments)}
    if held & roles.PLATFORM_MEMBER_ROLES:
        return roles.PLATFORM_MEMBER
    if roles.VIEWER in held:
        return roles.PLATFORM_VIEWER
    return None


def _feature_companions(
    attachments: Iterable[Attachment], known: set[str]
) -> set[tuple[str, str]]:
    """At each workspace scope a role is attached at, the most specific feature
    policy of ``known`` for that role and scope."""
    wanted: set[tuple[str, str]] = set()
    for role, scope in _workspace_roles(attachments):
        org, workspace = scope_fields(scope)
        policy_id = roles.feature_policy_for(role, org, workspace, known)
        if policy_id is not None:
            wanted.add((policy_id, scope))
    return wanted


def _is_feature_policy(policy_id: str) -> bool:
    return policy_id.startswith(roles.FEATURES_PREFIX)


# Keys a principal may hold at once, per bucket: a service account's keys, a
# user's API keys, coding keys (one per environment), grants (one per open link).
_KEY_LIMITS = {"service": 5, "api-key": 5, "coding": 50, "grant": 1000}
_PERSONAL_YEAR = timedelta(days=365)
_GRANT_LIFE = timedelta(hours=8)
_GRANT_RETENTION = timedelta(days=1)


@dataclass(frozen=True)
class _KeySpec:
    kind: KeyKind
    audience: str | None
    resource: str | None
    scope: tuple[dict[str, Any], ...] | None

    @property
    def bucket(self) -> str:
        if self.kind == "service":
            return "service"
        if self.kind == "grant":
            return "grant"
        return "coding" if self.audience == CODING_AUDIENCE else "api-key"

    @property
    def limit(self) -> int:
        return _KEY_LIMITS[self.bucket]

    def expiry(
        self, now: datetime, requested: datetime | None, name: str | None
    ) -> datetime | None:
        """When the key expires: what was asked for within the kind's limit,
        else the kind's default."""
        if requested is not None and requested <= now:
            raise ValueError("A key cannot expire in the past")
        if self.kind == "service":
            if requested is None and (name or "").startswith("ci/"):
                return now + timedelta(days=90)
            return requested
        if self.kind == "grant":
            if requested is None:
                raise ValueError("A grant always expires: say when")
            if requested > now + _GRANT_LIFE:
                raise ValueError("A grant lasts at most 8 hours")
            return requested
        if requested is None:
            return now + _PERSONAL_YEAR
        if requested > now + _PERSONAL_YEAR + timedelta(days=1):
            raise ValueError("A personal key lasts one year at most")
        return requested


def _bucket(key: KeyRecord) -> str:
    return _KeySpec(key.kind, key.audience, key.resource, key.scope).bucket  # type: ignore[arg-type]


def _key_spec(
    owner_kind: PrincipalKind | None,
    kind: KeyKind | None,
    audience: str | None,
    resource: str | None,
    scope: Sequence[Mapping[str, Any]] | None,
    expires_at: datetime | None,
) -> _KeySpec:
    """What a key is, checked: the kinds an owner may hold, the audience each
    reaches and what it names."""
    if owner_kind == "service_account":
        if kind not in (None, "service") or audience or resource or scope is not None:
            raise ValueError(
                "A service account's key is a service key: no kind, audience, "
                "resource or scope"
            )
        return _KeySpec("service", None, None, None)
    if owner_kind != "user":
        raise IAMNotFoundError("Only users and service accounts hold keys")
    kind = kind or "personal"
    if kind == "service":
        raise ValueError("A user holds personal keys and grants: not kind service")
    narrowed = normalize_scope(scope)
    if kind == "grant":
        if audience not in (APP_AUDIENCE, PREVIEW_AUDIENCE):
            raise ValueError("A grant's audience is app or preview")
        return _KeySpec("grant", audience, resource, narrowed)
    audience = audience or API_KEY_AUDIENCE
    if audience not in (API_KEY_AUDIENCE, CODING_AUDIENCE):
        raise ValueError("A personal key's audience is api-key or coding")
    if audience == CODING_AUDIENCE and not resource:
        raise ValueError("A coding key names its environment: say the resource")
    return _KeySpec("personal", audience, resource, narrowed)


def _named_by_nexus(principal: CallPrincipal, record: PrincipalRecord | None) -> bool:
    """A user Nexus names on a call by its Nexus id: IAM's user of issuer
    ``urn:abi:nexus``, or a Nexus id IAM has no record of."""
    if record is not None:
        return record.issuer == LEGACY_NEXUS_ISSUER
    return not _PRINCIPAL_ID.match(principal.id)


def _call_principal(record: PrincipalRecord) -> CallPrincipal:
    return CallPrincipal(id=record.id, kind=record.kind, name=record.name)  # type: ignore[arg-type]


def _check_service_account_name(name: str) -> None:
    if not name or len(name) > 255 or name != name.strip():
        raise ValueError(f"Invalid service account name {name!r}")
    if _PRINCIPAL_ID.match(name) or any(
        name.startswith(prefix + "_") for prefix in KIND_PREFIXES.values()
    ):
        raise ValueError(f"A service account name cannot look like an id: {name!r}")


def _check_placement(placement: Placement) -> None:
    resource_name(
        placement.service,
        "placement",
        "x",
        org=placement.org,
        workspace=placement.workspace,
    )
    key = placement.id_key
    if not key or "*" in key[:-1] or "?" in key:
        raise ValueError(f"A placement key is an id or a prefix ending in '*': {key!r}")


def _refuse_reserved_topics(document: PolicyDocument) -> None:
    """A manifest naming a bus topic under a platform root (``abi``, ``evt``,
    ``_INBOX``, ``$...``) would reach those subjects through the broker; one
    naming a variable its module variables do not fill (``${principal.id}``)
    would be granted it as written. ``document`` has its module variables bound."""
    errors = [
        f"statement {index}: {problem}"
        for index, statement in enumerate(document.statements)
        for problem in broker.reserved_topic_problems(statement.resources)
    ]
    if errors:
        raise PolicyValidationError(errors)
