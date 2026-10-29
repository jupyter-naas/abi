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
    listing,
    module_scopes,
    modules,
    roles,
)
from naas_abi_core.services.iam.adapters.secondary.authorizer__policy import (
    PolicyAuthorizer,
)
from naas_abi_core.services.iam.catalog import (
    ActionCatalog,
    CatalogRegistry,
    ResourceType,
    removed_actions,
)
from naas_abi_core.services.iam.evaluator import token_statements
from naas_abi_core.services.iam.exchange import TokenExchanger
from naas_abi_core.services.iam.iam_catalog import CATALOG, SEALS
from naas_abi_core.services.iam.IAMPorts import (
    KIND_PREFIXES,
    Attachment,
    Bound,
    ContainerRecord,
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
    LegacyScopeSet,
    ManifestRecord,
    ManifestStatus,
    ManifestSubmission,
    NameRewriter,
    Page,
    PendingGrant,
    PermissionDeniedError,
    Placement,
    Policy,
    PolicySource,
    PrincipalKind,
    PrincipalRecord,
    Seal,
    Subject,
    TokenExchange,
    new_id,
)
from naas_abi_core.services.iam.names import (
    EVERYWHERE,
    PLATFORM_SCOPE,
    UNRESOLVED,
    as_container,
    container_name,
    container_of_scope,
    is_below,
    is_old_scope,
    owner_ancestors,
    parse_container,
    parse_resource_name,
    resource_name,
    top_container,
    validate_owner_scope,
    validate_scope,
    within,
    within_owner,
)
from naas_abi_core.services.iam.policy import (
    MAX_DEPTH,
    PolicyDocument,
    PolicyValidationError,
    Statement,
    bind_variables,
    check_owned_document,
    denies_beyond_scope,
    parse_policy_document,
    within_scope,
)
from naas_abi_core.services.iam.tokens import TokenIssuer, normalize_scope

# The legacy issuer of the accounts of the old Nexus login, kept while they
# link to an identity provider: such a user is named on a call by its Nexus
# user id. IAM records it as a user of this issuer, subject = that id.
LEGACY_NEXUS_ISSUER = "urn:abi:nexus"

_PRINCIPAL_ID = re.compile(r"^(usr|grp|sa)_[0-9a-z]{26}$")
_T = TypeVar("_T")

AuthorizerFactory = Callable[[PolicySource], IAuthorizer]


def principal_resource(principal_id: str) -> str:
    return resource_name("iam", "principal", principal_id)


def _owned_resource(type_name: str, item_id: str, owner_scope: str) -> str:
    """A policy or a group, named in the container that owns it,
    ``<owner>/iam:<type>/<id>``; the platform's ``abi:iam:<type>/<id>``, which no
    ``${scope}`` reaches, the platform's included (``AGENTS.md``, "Attachments and
    scope"). An owner of the grammar before container paths names it in
    ``names.UNRESOLVED`` until it is rewritten."""
    return resource_name("iam", type_name, item_id, container=as_container(owner_scope))


def group_resource(group_id: str, owner_scope: str = PLATFORM_SCOPE) -> str:
    return _owned_resource("group", group_id, owner_scope)


def policy_resource(policy_id: str, owner_scope: str = PLATFORM_SCOPE) -> str:
    return _owned_resource("policy", policy_id, owner_scope)


def attachment_resource(policy_id: str, principal_id: str, scope: str | None) -> str:
    """Named in the attachment's scope's container, so no ``${scope}`` grant
    reaches past its scope; below a container, in that container ("Grant only
    what you hold" checks what it grants under it). An unscoped one, and one at
    the platform, at the platform, which only unscoped grants reach (the
    platform admin's)."""
    container = (
        PLATFORM_SCOPE if scope is None else as_container(container_of_scope(scope))
    )
    return resource_name(
        "iam",
        "attachment",
        [policy_id, principal_id],
        kind="path",
        container=container,
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


def container_resource(service: str, type_name: str, id: str) -> str:
    """IAM's record of a container, at the platform: ``iam:container/<s>/<t>/<id>``."""
    return resource_name("iam", "container", [service, type_name, id], kind="path")


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
        # Every placement, their index, and the registry of containers.
        self._placements = _TTLCache(cache_ttl_seconds, 3)
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
        # The listers registered in process, by (service, type), and those remote
        # modules serve (set by a serving engine on NATS): "Publishers and listing".
        self._listers: dict[tuple[str, str], listing.ResourceLister] = {}
        self.remote_listers: listing.ListerDirectory | None = None
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
        container: str | None = None,
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
        where = self._known_container(container) if container else self.call_container()
        if where == UNRESOLVED:
            # A container IAM does not know names nothing: not found.
            unknown = container or current_call_context().container or ""
            return Decision(False, False, "implicit_deny"), unknown
        declared = catalog.resource_type(resource_type)
        if declared is not None and declared.container:
            # A container's own resource is the container: registered, never placed.
            values = [parts] if isinstance(parts, str) else list(parts)
            found = (
                self.container(service, resource_type, values[0])
                if len(values) == 1
                else None
            )
            if found is None:
                # No such container (or not one id): denied, named as it would be,
                # its parts as one id, so the name never fails.
                return Decision(False, False, "implicit_deny"), resource_name(
                    service,
                    resource_type,
                    "/".join(values) or "-",
                    container=where or PLATFORM_SCOPE,
                )
            return self.authorize(action, found), found
        resource = module_scopes.declared_resource(
            catalog, resource_type, list(parts), container=where or PLATFORM_SCOPE
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
        for attachment, group in self._held_attachments(principal, record):
            statements += self._statements_of(
                attachment.policy_id, attachment, group, fresh=fresh
            )
        if principal.kind == "user":
            # builtin.self is held by every user, implicitly.
            statements += self._statements_of(roles.SELF, None, None, fresh=fresh)
        # ${module.*} name the module of a module's account; for any other
        # principal they match nothing.
        variables = modules.variables(record.name if record is not None else None)
        # The statements of one attachment share their chain's bounds: bound once.
        bound_chains: dict[int, tuple[Bound, ...]] = {}

        def bound_chain(chain: tuple[Bound, ...]) -> tuple[Bound, ...]:
            if not chain:
                return chain
            if id(chain) not in bound_chains:
                bound_chains[id(chain)] = _bind_bounds(chain, variables)
            return bound_chains[id(chain)]

        statements = [
            replace(effective, statement=bound, bounds=bound_chain(effective.bounds))
            for effective in statements
            if (bound := bind_variables(effective.statement, variables)) is not None
        ]
        return Subject(principal.id, status, tuple(statements))

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
        self, service: str, id_key: str, container: str = PLATFORM_SCOPE
    ) -> Placement:
        placement = Placement(service, id_key, container)
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
    # Containers: what any module declares and registers (AGENTS.md, "Containers").
    # =========================================================================

    def _container_type(self, service: str, type_name: str) -> ActionCatalog:
        catalog = self._registry.get(service)
        declared = catalog.resource_type(type_name) if catalog is not None else None
        if catalog is None or declared is None or not declared.container:
            raise ValueError(
                f"{service}:{type_name} is not a registered container type"
            )
        return catalog

    def register_container(
        self, service: str, type: str, id: str, *, parent: str = PLATFORM_SCOPE
    ) -> ContainerRecord:
        """Register a container in ``parent``: a create on its name as placed,
        which needs the type's create action there. Again under the same parent
        changes nothing; under another, ``IAMConflictError``."""
        catalog = self._container_type(service, type)
        record = ContainerRecord(service, type, id, parent)
        name = record.name  # validates the id and the parent's name
        create = catalog.container_action(type, "creates")
        assert create is not None  # a container type declares one (catalog.py)
        self.require(catalog.qualified(create.name), name)
        if parent != PLATFORM_SCOPE and self._known_container(parent) != parent:
            raise IAMNotFoundError(f"No container {parent}")
        declared = catalog.resource_type(type)
        if declared is not None and declared.parents:
            steps = parse_container(parent)
            where = f"{steps[-1].service}:{steps[-1].type}" if steps else "-"
            if where not in declared.parents:
                raise ValueError(
                    f"A {service}:{type} sits in {', '.join(declared.parents)}, "
                    f"not in {parent}"
                )
        existing = self.store.get_container(service, type, id)
        if existing is not None:
            if existing.parent != parent:
                raise IAMConflictError(
                    f"{service}:{type}/{id} is registered in {existing.parent}"
                )
            return existing
        self.store.put_container(record)
        self._changed()
        return record

    def delete_container(self, service: str, type: str, id: str) -> bool:
        """Forget a deleted container and every container below it: what they own
        (``_drop_owned``), every attachment and invitation left at them (below them
        included), and their placements. A user left with no attachment within the
        top container leaves the groups owned there."""
        catalog = self._container_type(service, type)
        delete = catalog.container_action(type, "deletes")
        if delete is None:
            raise ValueError(f"{service}:{type} declares no action that deletes one")
        found = self.store.get_container(service, type, id)
        name = found.name if found is not None else container_name(service, type, id)
        self.require(catalog.qualified(delete.name), name)
        if found is None:
            return False
        doomed = [c for c in self.store.list_containers() if within(c.name, name)]
        names = {c.name for c in doomed}
        changed = self._drop_owned(names)
        detached = self._detach_at(names)
        for grant in self.store.list_pending_grants():
            if grant.scope is not None and container_of_scope(grant.scope) in names:
                changed = self.store.remove_pending_grant(grant.id) or changed
        self.store.delete_containers(doomed)
        top = top_container(name)
        for principal_id in detached:
            self._leave_groups_of(principal_id, top)
        self._changed()
        return True

    def _detach_at(self, containers: set[str]) -> set[str]:
        """Detach every attachment at one of ``containers`` (below it too); the
        principals that held one."""
        held: set[str] = set()
        for attachment in self.store.list_attachments():
            scope = attachment.scope
            if scope is None or container_of_scope(scope) not in containers:
                continue
            if self.store.detach(attachment.policy_id, attachment.principal_id, scope):
                held.add(attachment.principal_id)
                if attachment.policy_id in roles.ROLES:
                    self._sync_role_companions(attachment.principal_id)
        return held

    def container(self, service: str, type: str, id: str) -> str | None:
        return self._container_index().get((service, type, id))

    def read_container(self, service: str, type: str, id: str) -> str | None:
        """A container's name for a caller allowed some action of its type on it
        (its catalog's), as ``get_container`` answers over NATS; None otherwise,
        as for an unknown one, so nobody else learns that it exists or where."""
        name = self.container(service, type, id)
        if name is None:
            return None
        actions = self._registry.actions_on(service, type)
        return name if any(self.authorize(a, name).allowed for a in actions) else None

    def _container_index(self) -> dict[tuple[str, str, str], str]:
        def build() -> dict[tuple[str, str, str], str]:
            return {
                (c.service, c.type, c.id): c.name for c in self.store.list_containers()
            }

        return self._placements.get("containers", build)

    def _known_container(self, name: str) -> str:
        """``name`` when it is a registered container under that path, the
        platform for the platform, else ``names.UNRESOLVED``."""
        if name == PLATFORM_SCOPE:
            return name
        try:
            steps = parse_container(name)
        except ValueError:
            return UNRESOLVED
        last = steps[-1]
        return (
            name
            if self.container(last.service, last.type, last.value) == name
            else UNRESOLVED
        )

    def list_containers(self) -> list[ContainerRecord]:
        """Every registered container, unchecked (in process: what the services
        that own a resource read). A caller's listing is ``list_resources``."""
        return self.store.list_containers()

    # =========================================================================
    # Listing (AGENTS.md, "Publishers and listing")
    # =========================================================================

    def register_lister(
        self, service: str, type: str, lister: listing.ResourceLister
    ) -> None:
        """List ``service:type`` with ``lister`` (in process only). The catalog
        must be registered and declare the type; a later one replaces it."""
        if not isinstance(lister, listing.ResourceLister):
            raise TypeError("A lister is a ResourceLister")
        if self._registry.resource_type(service, type) is None:
            raise IAMNotFoundError(f"No registered catalog declares {service}:{type}")
        self._listers[(service, type)] = lister

    def has_lister(self, service: str, type: str) -> bool:
        """Whether ``service:type`` is listed, not offered as wildcards only: a
        lister in process, a container or singleton type IAM lists itself, or a
        type of a module's catalog that a ready instance of that module names
        in discovery. What ``list_resources`` would ask, so the two agree."""
        declared = self._registry.resource_type(service, type)
        if declared is None:
            return False
        if (service, type) in self._listers or declared.container:
            return True
        if declared.id == "singleton":
            return True
        catalog = self._registry.get(service)
        if catalog is None or not catalog.module or self.remote_listers is None:
            return False
        try:
            return self.remote_listers.lists(catalog.module, service, type)
        except Exception as exc:  # noqa: BLE001 - unsure: offered as wildcards
            logger.warning(
                f"Listing {service}:{type}: cannot ask module {catalog.module}: {exc}"
            )
            return False

    def list_resources(
        self,
        service: str,
        type: str,
        *,
        scope: str = PLATFORM_SCOPE,
        text: str = "",
        cursor: str | None = None,
        limit: int | None = None,
        module: str = "",
    ) -> listing.ResourcePage:
        catalog = self._registry.get(service)
        declared = catalog.resource_type(type) if catalog is not None else None
        if catalog is None or declared is None:
            raise IAMNotFoundError(f"No registered catalog declares {service}:{type}")
        container = listing.listing_scope(scope)
        if len(text) > listing.MAX_TEXT:
            raise ValueError(f"A search text is at most {listing.MAX_TEXT} characters")
        query = listing.ListingQuery(
            service=service,
            type=type,
            container=container,
            text=text,
            after=cursor or "",
            module=module,
        )
        actions = self._registry.listing_actions(service, type)

        def allowed(names: Sequence[str]) -> set[str]:
            found: set[str] = set()
            left = list(names)
            for action in actions:
                if not left:
                    break
                found.update(self.filter(action, left).allowed)
                left = [name for name in left if name not in found]
            return found

        def of_module(item: listing.ListedResource) -> bool:
            """The ``module`` catalog asked for one module: its items only."""
            if not module or service != module_scopes.SERVICE:
                return True
            segments = parse_resource_name(item.name).segments
            return bool(segments) and segments[0] == module

        keep: Callable[[listing.ListedResource], bool] = of_module
        lister = self._lister_of(catalog, declared)
        if declared.container:
            lister, keep = self._container_listing(service, type, lister, keep)
        if lister is None:
            return listing.ResourcePage(listed=False)
        return listing.run_listing(
            lister,
            query,
            limit=listing.clamp_limit(limit),
            allowed=allowed,
            keep=keep,
        )

    def _lister_of(
        self, catalog: ActionCatalog, declared: ResourceType
    ) -> listing.ResourceLister | None:
        found = self._listers.get((catalog.service, declared.name))
        if found is not None:
            return found
        if declared.id == "singleton":
            return listing.FunctionLister(
                lambda query: self._singleton(catalog.service, declared, query)
            )
        if (
            catalog.module
            and self.remote_listers is not None
            and not declared.container
        ):
            try:
                return self.remote_listers.lister(
                    catalog.module, catalog.service, declared.name
                )
            except Exception as exc:  # noqa: BLE001 - offered as wildcards instead
                logger.warning(
                    f"Listing {catalog.service}:{declared.name}: "
                    f"module {catalog.module} cannot be asked: {exc}"
                )
        return None

    @staticmethod
    def _singleton(
        service: str, declared: ResourceType, query: listing.ListingQuery
    ) -> list[listing.ListedResource]:
        """The one resource of a singleton type at the container asked: a placed
        one there (none at the platform), a platform one at the platform."""
        platform = declared.placement == "platform"
        if platform != (query.container == PLATFORM_SCOPE):
            return []
        name = resource_name(
            service, declared.name, (), kind="singleton", container=query.container
        )
        return [listing.ListedResource(name=name, id="-", label=declared.name)]

    def _container_listing(
        self,
        service: str,
        type: str,
        lister: listing.ResourceLister | None,
        keep: Callable[[listing.ListedResource], bool],
    ) -> tuple[listing.ResourceLister, Callable[[listing.ListedResource], bool]]:
        """A container type: the registry's, labelled by ``lister`` when it has
        one (an item the registry does not hold under that name is dropped);
        the registry alone when it fails."""

        def registry(query: listing.ListingQuery) -> list[listing.ListedResource]:
            return [
                listing.ListedResource(name=c.name, id=c.id)
                for c in self.store.list_containers()
                if c.service == service and c.type == type
            ]

        from_registry = listing.FunctionLister(registry)
        if lister is None:
            return from_registry, keep

        def registered(item: listing.ListedResource) -> bool:
            try:
                parsed = parse_container(item.name)
            except ValueError:
                return False
            last = parsed[-1]
            return (
                (last.service, last.type) == (service, type)
                and self.container(service, type, last.value) == item.name
                and keep(item)
            )

        return _Fallback(lister, from_registry), registered

    # =========================================================================
    # The names before container paths: rewritten once by the module that
    # defined them (AGENTS.md, "Migrating an existing install").
    # =========================================================================

    def rewrite_names(self, rewriter: NameRewriter) -> dict[str, int]:
        """Rewrite every stored name with ``rewriter`` in one store transaction;
        in process only. Needs ``iam:RewriteNames``."""
        self.require("iam:RewriteNames", container_resource("iam", "container", "-"))
        counts = self.store.rewrite_names(rewriter)
        self._changed()
        # What the roles bring, now that their scopes are containers.
        holders = {
            a.principal_id
            for a in self.store.list_attachments()
            if a.policy_id in roles.ROLES
        }
        for principal_id in sorted(holders):
            self._sync_role_companions(principal_id)
        self._changed()
        return counts

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
        if (
            current is not None
            and current.version == catalog.version
            and current.format > catalog.format
        ):
            # The same version from an older writer (no format: its flags
            # unknown) never replaces the one whose flags are read.
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

    def create_group(self, name: str, *, scope: str | None = None) -> PrincipalRecord:
        """A group owned by ``scope``: the platform (``abi:``, the default) or a
        registered container. Its name carries the owner, so whoever may
        ``iam:CreateGroup`` there creates it."""
        if not name:
            raise ValueError("A group needs a name")
        owner = validate_owner_scope(scope) if scope is not None else PLATFORM_SCOPE
        group_id = new_id("grp")
        self.require("iam:CreateGroup", group_resource(group_id, owner))
        self._check_owner_known(owner)
        record = self.store.create_principal(
            PrincipalRecord(id=group_id, kind="group", name=name, owner_scope=owner)
        )
        self._changed()
        return record

    def get_group(self, group_id: str) -> PrincipalRecord:
        return self._require_group("iam:GetGroup", group_id)

    def list_groups(
        self, *, limit: int = 100, after: str | None = None, scope: str | None = None
    ) -> Page:
        """The groups the caller may list. With ``scope``, the groups it owns, and
        those of the containers above it (not the platform's), which receive
        attachments there, for whoever may list its attachments to them."""
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
        above = [c for c in owner_ancestors(scope) if c != PLATFORM_SCOPE]

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
        """Static membership. Groups cannot contain groups. A group owned by a
        container holds only users of its top container: users with an
        attachment of their own within it. The new member gets every
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
            top = top_container(as_container(group.owner_scope))
            if member.kind != "user":
                raise ValueError(
                    f"Group {group_id} belongs to {group.owner_scope}: it holds "
                    "users only (a module's account is approved by its manifest)"
                )
            if not self._belongs_to(member_id, top):
                raise ValueError(
                    f"Group {group_id} belongs to {group.owner_scope}: "
                    f"{member_id} holds nothing in {top}"
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
        name, which no grant at a container reaches."""
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

    def _belongs_to(self, principal_id: str, top: str) -> bool:
        """Whether a principal has an attachment of its own within ``top``."""
        return any(
            a.scope is not None
            and within(as_container(container_of_scope(a.scope)), top)
            for a in self.store.list_attachments(principal_id=principal_id)
        )

    def _leave_groups_of(self, principal_id: str, top: str) -> None:
        """A user who no longer belongs to the top container ``top`` leaves the
        groups owned within it."""
        if top == PLATFORM_SCOPE or self._belongs_to(principal_id, top):
            return
        for group_id in self.store.groups_of(principal_id):
            group = self._find_group(group_id)
            if group is not None and group.owner_scope != PLATFORM_SCOPE:
                if within(as_container(group.owner_scope), top):
                    self.store.remove_group_member(group_id, principal_id)

    def _check_owner_known(self, owner: str) -> None:
        """A container owns something only once it is registered under that path
        (an owner of the old grammar, from a start-up move, waits for the
        rewrite of the names: ``_owner_checked``)."""
        if is_old_scope(owner):
            return
        if owner != PLATFORM_SCOPE and self._known_container(owner) != owner:
            raise ValueError(f"{owner} is not a registered container")

    def _old_grammar_writer(self) -> bool:
        """A first-party account (``engine``, ``api``) acting for no user: Nexus's
        start-up moves that predate container paths, which may still write the
        grammar before them (``AGENTS.md``, "Migrating an existing install")."""
        ctx = current_call_context()
        return ctx.on_behalf_of is None and self._first_party(ctx.principal)

    def _scope_checked(self, scope: str) -> str:
        """An attachment's scope, valid; one of the old grammar only from an old
        grammar writer, named in ``names.UNRESOLVED`` until the rewrite."""
        if is_old_scope(scope) and self._old_grammar_writer():
            return scope
        return validate_scope(scope)

    def _owner_checked(self, owner: str) -> str:
        if is_old_scope(owner) and self._old_grammar_writer():
            return owner
        return validate_owner_scope(owner)

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
        ``scope``: the platform (the default) or a registered container. Its
        name carries the owner, so whoever may ``iam:CreatePolicy`` there
        creates it. An owned policy is written for its scope: every resource
        pattern is ``${scope}`` or ``${scope}/...``. With
        ``parent``, a sub-policy of it ("Sub-policies"): owned at the parent's
        owner or below, derived only from a policy the caller holds there. The
        caller holds what it allows (``_require_held``), within the chain."""
        if not name:
            raise ValueError("A policy needs a name")
        owner = self._owner_checked(scope) if scope is not None else PLATFORM_SCOPE
        parsed = parse_policy_document(document, self._registry)
        policy_id = new_id("pol")
        self.require("iam:CreatePolicy", policy_resource(policy_id, owner))
        self._check_owner_known(owner)
        check_owned_document(parsed, owner)
        chain: list[Policy] = []
        if parent:
            chain = self._new_chain(policy_id, owner, parent, height=1)
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
        owns, plus those of the containers above it (and the platform's) that
        the caller may attach there and may know of (``_unknown_at``)."""
        if scope is None:
            return self._filtered_page(
                lambda size, cursor: self.store.list_policies(limit=size, after=cursor),
                "iam:ListPolicies",
                lambda policy: policy_resource(policy.id, policy.owner_scope),
                limit,
                after,
            )
        self._owner_checked(scope)

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
                if p.id in inherited and self._denies_beyond_scope(p, fresh=False)
            }
            allowed = set(self.filter("iam:ListPolicies", own.values()).allowed)
            allowed |= set(self.filter("iam:AttachPolicy", inherited.values()).allowed)
            reach = set(self.filter("iam:AttachPolicy", unscoped.values()).allowed)
            kept = {
                i
                for i, n in {**own, **inherited}.items()
                if n in allowed and (i not in unscoped or unscoped[i] in reach)
            }
            return kept - self._unknown_at(
                scope, [p for p in found if p.id in kept and p.id in inherited]
            )

        return self._kept_page(
            lambda size, cursor: self.store.list_policies(
                limit=size, after=cursor, owner_scopes=[scope, *_owners_above(scope)]
            ),
            keep,
            ("iam:ListPolicies", "iam:AttachPolicy"),
            limit,
            after,
        )

    def _unknown_at(self, scope: str, inherited: Sequence[Policy]) -> set[str]:
        """Which of ``inherited`` (policies owned above ``scope``) a list at
        ``scope`` leaves out: what another container's policy allows is said
        only to whoever may list it at its owner, or where it is attached at
        ``scope`` or above (``AGENTS.md``, "Service API"). The built-in roles are
        no one's. Otherwise "<O> access", a platform policy confined to a
        scope, would name O and what it holds to the admins of every other
        organisation."""
        customer = [p for p in inherited if not p.managed]
        if not customer:
            return set()
        names = {p.id: policy_resource(p.id, p.owner_scope) for p in customer}
        listed = set(self.filter("iam:ListPolicies", names.values()).allowed)
        here = {scope, *_owners_above(scope)}
        return {
            p.id
            for p in customer
            if names[p.id] not in listed
            and not any(
                a.scope is not None and _as_owner(a.scope) in here
                for a in self.store.list_attachments(policy_id=p.id)
            )
        }

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
        changed = reparented or updated.document != current.document
        below = self._below(policy_id) if changed else []
        if reparented and parent_id is not None:
            # Its height with those below: one more than the deepest of them.
            height = 1 + max((len(above) + 1 for _sub, above in below), default=0)
            chain = self._new_chain(
                policy_id, current.owner_scope, parent_id, height=height
            )
        else:
            chain, _whole = self._chain(updated, fresh=True)
        if changed:
            self._check_unscoped_chain(updated, chain, below)
            self._check_new_denies(current, updated, chain, below)
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
            # Named as far as the caller may list them; the rest are counted.
            names = {p.id: policy_resource(p.id, p.owner_scope) for p in subs}
            listed = set(self.filter("iam:ListPolicies", names.values()).allowed)
            shown = [f"{p.id} ({p.name})" for p in subs if names[p.id] in listed]
            hidden = len(subs) - len(shown)
            if hidden:
                shown.append(f"{'and ' if shown else ''}{hidden} you may not list")
            raise IAMConflictError(
                f"Policy {policy_id} has sub-policies: "
                + ", ".join(shown)
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
        Refuses a parent that does not exist (``IAMNotFoundError``), one the
        caller may not derive from (``_require_derivable``, before anything of
        the parent is said), a cycle, a chain deeper than ``MAX_DEPTH`` and an
        owner outside the parent's."""
        parent = self._load_policy(parent_id)
        if parent is None:
            raise IAMNotFoundError(f"Policy {parent_id} not found")
        self._require_derivable(parent, owner)
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

    def _below(self, policy_id: str) -> list[tuple[Policy, list[Policy]]]:
        """Every policy below ``policy_id``, read from the store, each with the
        policies between it and ``policy_id`` (nearest first), at most
        ``MAX_DEPTH`` levels down."""
        found: list[tuple[Policy, list[Policy]]] = []
        level: list[tuple[str, list[Policy]]] = [(policy_id, [])]
        seen = {policy_id}
        for _depth in range(MAX_DEPTH):
            following: list[tuple[str, list[Policy]]] = []
            for parent_id, above in level:
                for sub in self.store.list_sub_policies(parent_id):
                    if sub.id not in seen:
                        seen.add(sub.id)
                        found.append((sub, above))
                        following.append((sub.id, [sub, *above]))
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

    def _check_new_denies(
        self,
        current: Policy,
        updated: Policy,
        chain: Sequence[Policy],
        below: Sequence[tuple[Policy, list[Policy]]],
    ) -> None:
        """A change that gives a policy, or one below it, a chain that denies
        beyond ``${scope}:`` is that policy attached anew where it is attached
        or invited at a scope: only whoever may attach it unscoped there (the
        platform admin) makes it (``_require_attach``)."""
        for held, above in [(updated, []), *below]:
            before = [current] if held is updated else [held, *above, current]
            after = [updated] if held is updated else [held, *above, updated]
            old_chain, _whole = self._chain(before[-1], fresh=True)
            if denies_beyond_scope(
                p.document for p in [*before, *old_chain]
            ) or not denies_beyond_scope(p.document for p in [*after, *chain]):
                continue
            targets = [
                a.principal_id
                for a in self.store.list_attachments(policy_id=held.id)
                if a.scope is not None
            ] + [
                _invitee(g.provider, g.email)
                for g in self.store.list_pending_grants(policy_id=held.id)
            ]
            for principal_id in dict.fromkeys(targets):
                self._require_unscoped_attach(held.id, principal_id)

    def _widens(self, before: PolicyDocument, after: PolicyDocument) -> bool:
        """Whether ``after`` may let through something ``before`` does not: only
        then can a change of a parent widen what the policies below it grant.
        It does when one of its Allows reaches beyond ``before``'s Allows, or when
        one of ``before``'s Denies reaches beyond ``after``'s Denies (a Deny lifted
        or narrowed lets through what it refused). Both are compared as grants
        are, written unscoped and at any scope; unproven is a widening."""

        def allowed(document: PolicyDocument, effect: str) -> list[Statement]:
            return [
                replace(statement, effect="Allow")
                for statement in document.statements
                if statement.effect == effect
            ]

        return self._beyond(
            allowed(before, "Allow"), allowed(after, "Allow")
        ) or self._beyond(allowed(after, "Deny"), allowed(before, "Deny"))

    def _beyond(self, held: list[Statement], given: list[Statement]) -> bool:
        """Whether ``given`` may reach what no statement of ``held`` does, unscoped
        or at any scope; unproven is reaching beyond."""
        if not given:
            return False
        for scope in (None, _ANY_SCOPE):
            side = grants.Side(
                tuple(
                    grants.held_statement(s, scope, principal_id="-", user_id=None)
                    for s in held
                ),
                "",
            )
            if (
                grants.Holdings([side], self._registry).first_uncovered(given, scope)
                is not None
            ):
                return True
        return False

    def _denies_beyond_scope(self, policy: Policy, *, fresh: bool = True) -> bool:
        """Whether a Deny of the policy or of its chain names anything outside
        ``${scope}:``: it refuses beyond the scope it is attached at. Read from
        the store (a write's check), or from the cache (a list's)."""
        chain, _whole = self._chain(policy, fresh=fresh)
        return denies_beyond_scope([policy.document, *(p.document for p in chain)])

    def _uses_scope(self, policy: Policy) -> bool:
        """Whether the policy or a policy of its chain names ``${scope}``, its
        chain read from the store."""
        chain, _whole = self._chain(policy, fresh=True)
        return any(p.document.uses_scope for p in [policy, *chain])

    def _parents(self, policy: Policy) -> list[PolicyDocument] | None:
        """The documents of a policy's chain, nearest first, read from the store;
        None when it cannot be read whole (``_require_held`` then refuses)."""
        chain, whole = self._chain(policy, fresh=True)
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

    def _drop_owned(self, owners: set[str]) -> bool:
        """Delete what deleted containers own: policies with their attachments
        and invitations, and groups with their attachments, members and
        mappings. Whether anything went."""
        ordered = sorted(owners)
        changed = False
        for policy in self._deletion_order(self._all_policies(ordered)):
            for attachment in self.store.list_attachments(policy_id=policy.id):
                self.store.detach(policy.id, attachment.principal_id, attachment.scope)
            for grant in self.store.list_pending_grants(policy_id=policy.id):
                self.store.remove_pending_grant(grant.id)
            self.store.delete_policy(policy.id)
            changed = True
        after: str | None = None
        while True:
            page = self.store.list_principals(
                "group", limit=500, after=after, owner_scopes=ordered
            )
            for group in page.items:
                if group.status != "deleted":
                    self._delete_group(group)
                    changed = True
            if page.next_after is None:
                return changed
            after = page.next_after

    def _deletion_order(self, owned: list[Policy]) -> list[Policy]:
        """``owned``, every sub-policy before its parent, from the store's parent
        links. A cycle among them (concurrent writes) is cut first: they all go.
        A sub-policy owned elsewhere (only a write to the store bypassing IAM
        makes one) is refused before anything changes, so a deletion never
        stops halfway."""
        left = {p.id: p for p in owned}
        children = {i: self.store.list_sub_policies(i) for i in left}
        outside = [
            (i, c) for i, subs in children.items() for c in subs if c.id not in left
        ]
        if outside:
            raise IAMConflictError(
                "Nothing deleted: "
                + ", ".join(
                    f"{c.id}, owned by {c.owner_scope}, is a sub-policy of {i}"
                    for i, c in outside
                )
                + ". Give it another parent first"
            )
        order: list[Policy] = []
        while left:
            ready = [
                p
                for p in left.values()
                if not any(c.id in left for c in children[p.id])
            ]
            if not ready:
                for p in list(left.values()):
                    if p.parent_id in left:
                        left[p.id] = self.store.update_policy(
                            replace(p, parent_id=None), p.revision
                        )
                children = {i: [] for i in left}
                continue
            for p in sorted(ready, key=lambda p: p.id):
                order.append(p)
                del left[p.id]
        return order

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
            self._scope_checked(scope)
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
        self._require_unscoped_attach(policy_id, principal_id)

    def _require_unscoped_attach(self, policy_id: str, principal_id: str) -> None:
        """``iam:AttachPolicy`` on the unscoped attachment: what attaching, at a
        scope, a policy whose chain denies beyond ``${scope}:`` takes."""
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
        """A group owned by a container receives attachments at it or below."""
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
            self._scope_checked(scope)
        self.require(
            "iam:DetachPolicy",
            attachment_resource(policy_id, principal_id, scope),
            not_found=lambda: IAMNotFoundError("Attachment not found"),
        )
        detached = self.store.detach(policy_id, principal_id, scope)
        if detached:
            if policy_id in roles.ROLES:
                self._sync_role_companions(principal_id)
            if scope is not None:
                self._leave_groups_of(
                    principal_id, top_container(as_container(container_of_scope(scope)))
                )
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

    def _sync_role_companions(self, principal_id: str) -> None:
        """After a role left: the platform companion, and the retired companions
        that followed it (``_drop_retired_companions``), from one listing."""
        attachments = self.store.list_attachments(principal_id=principal_id)
        self._sync_platform_roles(principal_id, attachments)
        self._drop_retired_companions(attachments)

    def _sync_platform_roles(
        self, principal_id: str, attachments: Sequence[Attachment] | None = None
    ) -> None:
        """Hold ``builtin.platform.member`` while a member, admin or owner role is
        attached where it brings the companions (``_brings_companions``);
        ``.viewer`` with only viewer roles there."""
        attachments = (
            attachments
            if attachments is not None
            else self.store.list_attachments(principal_id=principal_id)
        )
        if any(
            a.policy_id in roles.ROLES and is_old_scope(a.scope) for a in attachments
        ):
            # A role still at a scope of the old grammar: what it brings is
            # read once the names are rewritten (``rewrite_names``).
            return
        wanted = _platform_companion(attachments, self._brings_companions)
        for companion in (roles.PLATFORM_MEMBER, roles.PLATFORM_VIEWER):
            present = self._find_attachment(companion, principal_id, None) is not None
            if companion == wanted and not present:
                self.store.attach(Attachment(new_id("att"), companion, principal_id))
            elif companion != wanted and present:
                self.store.detach(companion, principal_id, None)

    def _brings_companions(self, scope: str) -> bool:
        """Whether a role at ``scope`` brings the platform companions: below a
        container, or at a container whose type is marked
        ``platform_companions`` (Nexus's workspace)."""
        if is_below(scope):
            return True
        container = as_container(scope)
        if container in (PLATFORM_SCOPE, UNRESOLVED):
            return False
        last = parse_container(container)[-1]
        found = self._registry.resource_type(last.service, last.type)
        return found is not None and found.platform_companions

    # =========================================================================
    # Grant only what you hold (AGENTS.md, "Grant only what you hold")
    # =========================================================================

    def grantable(
        self, scope: str, *, parent: str | None = None, derive: bool = False
    ) -> list[GrantableCatalog]:
        """What the caller may grant at ``scope``: per catalog, the actions they
        hold there and the resource patterns they hold them on, minus their
        Denies. About the caller only, like ``explain`` of oneself, it needs no
        ``iam:*`` action. With ``parent``, what a sub-policy of it owned at
        ``scope`` may grant: within the parent's chain (``_grantable_chain``);
        with ``derive``, for a new one, refused as ``create_policy`` would."""
        validate_scope(scope)
        # The parent first: a refused one costs no holdings.
        chain = self._grantable_chain(parent, scope, derive=derive) if parent else None
        holdings = self._holdings(current_call_context(), scope)
        if chain is None:
            return holdings.grantable(scope)
        return holdings.grantable(scope, parents=chain)

    def _grantable_chain(
        self, parent_id: str, scope: str, *, derive: bool
    ) -> list[tuple[Statement, ...]]:
        """The statements of the chain a sub-policy of ``parent_id`` owned at
        ``scope`` would have, nearest first.

        With ``derive`` (a new sub-policy), ``_new_chain``'s verdict: a parent
        the caller may derive from there, the owner within the parent's, the
        chain not too deep; its refusal is kept. Without (an existing one being
        edited), a parent the caller may derive from or read (``iam:GetPolicy``):
        what it allows is said to no one else. One that does not exist is not
        found, as one the caller may not read."""
        owner = as_container(container_of_scope(scope))
        if derive:
            # No policy is being made yet: its id is none of the chain's.
            return [
                p.document.statements
                for p in self._new_chain("", owner, parent_id, height=1)
            ]
        parent = self._load_policy(parent_id)
        if parent is None:
            self._require_policy("iam:GetPolicy", parent_id)  # refused, or not found
            raise IAMNotFoundError(f"Policy {parent_id} not found")
        try:
            self._require_derivable(parent, owner)
        except PermissionDeniedError:
            if not self.authorize(
                "iam:GetPolicy", policy_resource(parent.id, parent.owner_scope)
            ).allowed:
                raise
        above, whole = self._chain(parent, fresh=True)
        if not whole:
            raise IAMConflictError(
                f"The chain of parents of {parent.id} cannot be read whole (a "
                f"parent missing, a cycle or deeper than {MAX_DEPTH} policies)"
            )
        return [p.document.statements for p in (parent, *above)]

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
        chain, nearest first; None: a chain that cannot be read whole, refused
        with ``IAMConflictError``). A write a first-party account (``engine``, ``api``)
        makes for no user is its own: the route or the boot step that made it
        authorized what it stands for."""
        ctx = current_call_context()
        if ctx.on_behalf_of is None and self._first_party(ctx.principal):
            return
        if parents is None:
            # Unchecked, it would grant what nobody was checked for once the
            # chain is whole again.
            raise IAMConflictError(
                f"The chain of parents of {policy_id} cannot be read whole (a "
                "parent missing, a cycle or deeper than "
                f"{MAX_DEPTH}): give it a parent that exists first"
            )
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
        narrowing."""
        actor = ctx.principal
        user_id = ctx.user.id if ctx.user is not None else None
        sides: list[grants.Side] = []
        if ctx.on_behalf_of is not None:
            sides.append(
                self._held_side(ctx, "user", user_id, "you do not hold it there")
            )
            if not self._first_party(actor):
                sides.append(
                    self._held_side(
                        ctx,
                        "actor",
                        user_id,
                        f"{actor.name or actor.id}, acting for you, does not hold it there",
                    )
                )
        else:
            sides.append(
                self._held_side(ctx, "actor", user_id, "you do not hold it there")
            )
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
    ) -> grants.Side:
        subject = self.subject(ctx, side)
        if subject is None:
            return grants.Side((), lacks, active=False)
        return grants.Side(
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
        )

    def _first_party(self, principal: CallPrincipal) -> bool:
        if principal.kind != "service_account":
            return False
        record = self._resolve(principal)
        return record is not None and record.name in FIRST_PARTY_ACCOUNTS

    # =========================================================================
    # Companions: what IAM keeps in step with the roles.
    # =========================================================================

    def _companions(
        self, attachments: Sequence[Attachment]
    ) -> set[tuple[str, str | None]]:
        """The (policy, scope) of ``attachments`` IAM's role sync keeps there:
        the platform companion their roles bring, and a retired policy an older
        version attached beside a role (until it is moved and retired: it
        follows the role, ``_drop_retired_companions``). A platform policy
        attached by hand is not one of them."""
        found: set[tuple[str, str | None]] = set(_retired_companions(attachments))
        platform = _platform_companion(attachments, self._brings_companions)
        if platform is not None:
            found.add((platform, None))
        return found

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
            self._scope_checked(scope)
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
        """The group of a claim value for the top container of ``scope`` (the
        platform's for a platform or unscoped binding), made when there is none:
        it belongs to that container, so it holds attachments within it only."""
        found = self._find_binding_group(provider, claim_value, scope)
        if found is not None:
            return found
        owner = _binding_owner(scope)
        name = _bound_group(provider, claim_value)
        group = self.store.create_principal(
            PrincipalRecord(
                id=new_id("grp"), kind="group", name=name, owner_scope=owner
            )
        )
        self.store.map_idp_group(GroupMapping(provider, claim_value, group.id))
        self._changed()
        return group

    def _find_binding_group(
        self, provider: str, claim_value: str, scope: str | None
    ) -> PrincipalRecord | None:
        owner = _binding_owner(scope)
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
                self._sync_role_companions(group_id)
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
                    if attachment.scope is None and attachment.policy_id in (
                        roles.PLATFORM_MEMBER,
                        roles.PLATFORM_VIEWER,
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
            self._drop_retired(policy_id)

    def _drop_retired(self, policy_id: str) -> bool:
        try:
            self.store.get_policy(policy_id)
        except IAMNotFoundError:
            return False
        for attachment in self.store.list_attachments(policy_id=policy_id):
            self.store.detach(policy_id, attachment.principal_id, attachment.scope)
        return self._delete_managed(policy_id)

    def retired_policies(self) -> list[Policy]:
        """The stored managed policies an older version generated by prefix
        (``roles.RETIRED_POLICY_PREFIXES``) and that are still in force: what
        they grant is moved by whoever made them before they go
        (``retire_policies``). In process only; needs ``iam:ListPolicies``."""
        return [
            p
            for p in self._all_policies()
            if p.managed
            and p.id.startswith(roles.RETIRED_POLICY_PREFIXES)
            and self.authorize(
                "iam:ListPolicies", policy_resource(p.id, p.owner_scope)
            ).allowed
        ]

    def retire_policies(self, policy_ids: Iterable[str]) -> list[str]:
        """Drop retired managed policies with what is attached to them, as boot
        does for ``roles.RETIRED_POLICIES``. Only those an older version made by
        prefix (``roles.RETIRED_POLICY_PREFIXES``), once what they granted was
        moved: they stay in force until then, so no grant is lost on the way.
        Needs ``iam:DeletePolicy`` on each. Returns the ones dropped."""
        # Every id is checked before any goes: a refusal drops nothing.
        found: list[str] = []
        for policy_id in dict.fromkeys(policy_ids):
            if not policy_id.startswith(roles.RETIRED_POLICY_PREFIXES):
                raise ValueError(f"{policy_id} is not a retired policy")
            policy = self._find_policy(policy_id)
            if policy is None:
                continue
            if not policy.managed:
                raise ValueError(f"{policy_id} is not a managed policy")
            self.require(
                "iam:DeletePolicy", policy_resource(policy_id, policy.owner_scope)
            )
            found.append(policy_id)
        dropped = [policy_id for policy_id in found if self._drop_retired(policy_id)]
        if dropped:
            self._changed()
        return dropped

    def legacy_scope_sets(self) -> list[LegacyScopeSet]:
        """The org and workspace sets an older version recorded, as stored, until
        whoever recorded them moved what they said into policies and dropped
        them (``drop_legacy_scope_sets``). IAM decides nothing with them. In
        process only; needs ``iam:DeleteScope`` on each one's scope (whoever may
        forget a scope reads what it had); the others are left out."""
        return [
            found
            for found in self.store.legacy_scope_sets()
            if self.authorize(
                "iam:DeleteScope", _legacy_scope_resource(found.org, found.workspace)
            ).allowed
        ]

    def drop_legacy_scope_sets(self) -> bool:
        """Drop the legacy sets once they were moved. Needs ``iam:DeleteScope``
        on the scope of every one, checked before anything goes."""
        for found in self.store.legacy_scope_sets():
            self.require(
                "iam:DeleteScope", _legacy_scope_resource(found.org, found.workspace)
            )
        dropped = self.store.drop_legacy_scope_sets()
        if dropped:
            self._changed()
        return dropped

    def _drop_retired_companions(self, attachments: Sequence[Attachment]) -> None:
        """A retired policy attached beside a role (an older version's
        companion, until it is moved and retired) follows its own role out: it
        is detached where that role is no longer held, whatever else is
        (an admin made viewer loses the admin's)."""
        kept = _retired_companions(attachments)
        for attachment in attachments:
            if (
                roles.retired_role(attachment.policy_id) is not None
                and (attachment.policy_id, attachment.scope) not in kept
            ):
                self.store.detach(
                    attachment.policy_id, attachment.principal_id, attachment.scope
                )

    def _delete_managed(self, policy_id: str) -> bool:
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
            return False
        self.store.delete_policy(policy_id)
        return True

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


# Where a platform policy's ``${scope}`` may be filled: any container or the
# platform, as a pattern (below the platform).
_ANY_SCOPE = EVERYWHERE


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


def _binding_owner(scope: str | None) -> str:
    """The owner of a binding's group: the top container of its scope, the
    platform for a platform or unscoped binding."""
    if scope is None:
        return PLATFORM_SCOPE
    return top_container(as_container(container_of_scope(scope)))


def _legacy_scope_resource(*fields: str) -> str:
    """The scope a legacy set was recorded for, named as ``iam:DeleteScope``
    decides it: ``abi:iam:scope/<field>/<field>``."""
    return resource_name("iam", "scope", [f for f in fields if f != "-"], kind="path")


def _owners_above(scope: str) -> list[str]:
    """The owners above ``scope`` whose policies a list there offers; none for
    an owner of the old grammar (a start-up move lists its own only)."""
    return [] if is_old_scope(scope) else owner_ancestors(scope)


def _as_owner(scope: str | None) -> str:
    """The owner level an attachment at ``scope`` reaches from: unscoped and the
    platform's the platform, one below a container that container."""
    if scope is None:
        return PLATFORM_SCOPE
    return as_container(container_of_scope(scope))


def _written_for(owner: str) -> list[str | None]:
    """The scopes a policy is held at when it is written: its owner's for a
    container's (it is attached there or below, and checked again there); for
    the platform's, as written unscoped and at any scope."""
    return [owner] if owner != PLATFORM_SCOPE else [None, _ANY_SCOPE]


def _companion_roles(
    attachments: Iterable[Attachment], brings: Callable[[str], bool]
) -> Iterator[tuple[str, str]]:
    """The (role, scope) attached where a role brings the platform companions
    (``brings``): below a container, or at a container whose type says so."""
    for attachment in attachments:
        if attachment.policy_id not in roles.ROLES or attachment.scope is None:
            continue
        if brings(attachment.scope):
            yield attachment.policy_id, attachment.scope


def _retired_companions(
    attachments: Sequence[Attachment],
) -> set[tuple[str, str | None]]:
    """The (policy, scope) of the retired companions still held beside their
    own role (``roles.retired_role``) at the same scope: an older version kept
    them in step with that role, so they stay only while it does."""
    held = {(a.policy_id, a.scope) for a in attachments if a.policy_id in roles.ROLES}
    return {
        (a.policy_id, a.scope)
        for a in attachments
        if (role := roles.retired_role(a.policy_id)) is not None
        and (role, a.scope) in held
    }


def _platform_companion(
    attachments: Iterable[Attachment], brings: Callable[[str], bool]
) -> str | None:
    """``builtin.platform.member`` while a member, admin or owner role is
    attached where it brings the companions; ``.viewer`` with only viewer roles
    there."""
    held = {role for role, _scope in _companion_roles(attachments, brings)}
    if held & roles.PLATFORM_MEMBER_ROLES:
        return roles.PLATFORM_MEMBER
    if roles.VIEWER in held:
        return roles.PLATFORM_VIEWER
    return None


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
    resource_name(placement.service, "placement", "x", container=placement.container)
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


class _Fallback(listing.ResourceLister):
    """``primary``, else ``fallback`` when it fails (logged)."""

    def __init__(
        self, primary: listing.ResourceLister, fallback: listing.ResourceLister
    ) -> None:
        self._primary, self._fallback = primary, fallback

    def list_resources(self, query: listing.ListingQuery) -> listing.ListedPage:
        try:
            return self._primary.list_resources(query)
        except Exception as exc:  # noqa: BLE001 - the registry answers instead
            logger.warning(
                f"Listing {query.service}:{query.type}: its lister failed, "
                f"the registry answers: {exc}"
            )
            return self._fallback.list_resources(query)
