"""The IAM domain service: who may do what, for every kernel service.

Domain services call ``require`` and ``filter``; both read the caller from the
current ``CallContext`` (never from a request field). IAM authorizes its own
operations with its own ``iam:*`` catalog, like any other service.

Effective policies are cached per principal for at most ``cache_ttl_seconds``
(60 by default, RFC §5.6) and dropped on every change made through this
service. Change listeners (the NATS primary) hear each new store revision.
"""

from __future__ import annotations

import re
import threading
import time
from collections import OrderedDict
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from typing import Any, Literal, TypeVar

from naas_abi_core import logger
from naas_abi_core.engine.call_context import (
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
from naas_abi_core.services.iam import broker, keys, modules, roles
from naas_abi_core.services.iam.adapters.secondary.authorizer__policy import (
    PolicyAuthorizer,
)
from naas_abi_core.services.iam.catalog import (
    ActionCatalog,
    CatalogRegistry,
    removed_actions,
)
from naas_abi_core.services.iam.exchange import TokenExchanger
from naas_abi_core.services.iam.iam_catalog import CATALOG, SEALS
from naas_abi_core.services.iam.IAMPorts import (
    KIND_PREFIXES,
    Attachment,
    CreatedKey,
    Decision,
    EffectiveStatement,
    Explanation,
    FilterResult,
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
    Seal,
    Subject,
    TokenExchange,
    new_id,
)
from naas_abi_core.services.iam.names import (
    ALL_ORGS,
    ALL_WORKSPACES,
    NONE,
    resource_name,
    scope_fields,
    validate_scope,
)
from naas_abi_core.services.iam.policy import (
    PolicyDocument,
    PolicyValidationError,
    bind_variables,
    parse_policy_document,
    within_scope,
)
from naas_abi_core.services.iam.tokens import TokenIssuer, normalize_scope

# TRANSITIONAL (until subtask 7, #61): a Nexus user is named on a call by its
# Nexus user id. IAM records it as a user of this issuer, subject = that id.
LEGACY_NEXUS_ISSUER = "urn:abi:nexus"

_PRINCIPAL_ID = re.compile(r"^(usr|grp|sa)_[0-9a-z]{26}$")
_T = TypeVar("_T")

AuthorizerFactory = Callable[[PolicySource], IAuthorizer]


def principal_resource(principal_id: str) -> str:
    return resource_name("iam", "principal", principal_id)


def group_resource(group_id: str) -> str:
    return resource_name("iam", "group", group_id)


def policy_resource(policy_id: str) -> str:
    return resource_name("iam", "policy", policy_id)


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


# The engine's own service key, for its client-role engines (RFC §8.2): they
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
        self._floors = _TTLCache(cache_ttl_seconds, 1)
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

    def filter(self, action: str, resources: Iterable[str]) -> FilterResult:
        """The resources the current caller may perform ``action`` on, in order,
        plus prefix hints a store can push down (RFC §5.5)."""
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

    def _compute_subject(
        self, principal: CallPrincipal, *, fresh: bool = False
    ) -> Subject:
        """``fresh``: read every policy from the store, never from the cache."""
        if principal.kind == "anonymous":
            return Subject(principal.id, "active", ())
        record = self._resolve(principal)
        status = record.status if record is not None else "active"
        holders: list[tuple[str, str | None]] = []
        if record is not None:
            holders.append((record.id, None))
            for group_id in self.store.groups_of(record.id):
                holders.append((group_id, group_id))
        # Mapped IdP groups travel in the token's grp claim (§2). Only ids of
        # groups count: an id of a user or an account must never lend its
        # policies (the #57 review).
        for group_id in sorted(principal.groups):
            if all(group_id != held for held, _ in holders) and self._is_group(
                group_id
            ):
                holders.append((group_id, group_id))
        active_groups = {
            group_id for _, group_id in holders if group_id and self._active(group_id)
        }
        via = dict(holders)
        statements: list[EffectiveStatement] = []
        for attachment in self.store.attachments_for([held for held, _ in holders]):
            group = via.get(attachment.principal_id)
            if group is not None and group not in active_groups:
                continue  # a suspended group grants nothing
            statements += self._statements_of(
                attachment.policy_id, attachment, group, fresh=fresh
            )
        if principal.kind == "user":
            # builtin.self is held by every user, implicitly.
            statements += self._statements_of(roles.SELF, None, None, fresh=fresh)
            if _named_by_nexus(principal, record):
                # TRANSITIONAL (#65): a Nexus user, until its roles are attachments.
                statements += self._statements_of(
                    roles.TRANSITIONAL_NEXUS_USER, None, None, fresh=fresh
                )
        # ${module.*} name the module of a module's account; for any other
        # principal they match nothing.
        variables = modules.variables(record.name if record is not None else None)
        statements = [
            replace(effective, statement=bound)
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
        policy = (
            self._load_policy(policy_id) if fresh else self._cached_policy(policy_id)
        )
        if policy is None:
            return []
        scope = attachment.scope if attachment else None
        effective: list[EffectiveStatement] = []
        for index, statement in enumerate(policy.document.statements):
            # A scoped attachment grants within its scope only, whatever the
            # policy says now (attach_policy refuses the rest up front).
            granted = within_scope(statement) if scope is not None else statement
            if granted is None:
                continue
            effective.append(
                EffectiveStatement(
                    statement=granted,
                    policy_id=policy.id,
                    statement_index=index,
                    attachment_id=attachment.id if attachment else None,
                    scope=scope,
                    via_group=group,
                )
            )
        return effective

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
    # Placements (RFC §4.4)
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
        self.require("iam:DeleteScope", scope_resource(org, workspace))
        deleted = self.store.delete_scope(org, workspace)
        if deleted:
            self._changed()
        return deleted

    def workspace_org(self, workspace: str) -> str | None:
        """The org a workspace was registered in (``iam:PutScope``)."""
        return next(
            (s.org for s in self.store.list_scopes() if s.workspace == workspace), None
        )

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
            # A module's account always holds its bootstrap (RFC §8.3).
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

    def create_group(self, name: str, *, org: str | None = None) -> PrincipalRecord:
        if not name:
            raise ValueError("A group needs a name")
        if org is not None:
            resource_name("iam", "group", "x", org=org)  # validates the org id
        group_id = new_id("grp")
        self.require("iam:CreateGroup", group_resource(group_id))
        record = self.store.create_principal(
            PrincipalRecord(id=group_id, kind="group", name=name, org=org)
        )
        self._changed()
        return record

    def get_group(self, group_id: str) -> PrincipalRecord:
        self._require_group("iam:GetGroup", group_id)
        return self._group(group_id)

    def list_groups(self, *, limit: int = 100, after: str | None = None) -> Page:
        return self._filtered_page(
            lambda size, cursor: self.store.list_principals(
                "group", limit=size, after=cursor
            ),
            "iam:ListGroups",
            lambda record: group_resource(record.id),
            limit,
            after,
        )

    def delete_group(self, group_id: str) -> PrincipalRecord:
        self._require_group("iam:DeleteGroup", group_id)
        group = self._group(group_id)
        if group.status == "deleted":
            return group
        record = self.store.update_principal(replace(group, status="deleted"))
        self._unlink(record)
        return record

    def add_group_member(self, group_id: str, member_id: str) -> None:
        """Static membership. Groups cannot contain groups (RFC §2)."""
        self._require_group("iam:AddGroupMember", group_id)
        group = self._group(group_id)
        member = self._get_principal(member_id)
        if member.kind == "group":
            raise ValueError("Groups cannot contain groups")
        if "deleted" in (group.status, member.status):
            raise IAMConflictError("Nothing joins or holds a deleted principal")
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
        """Members of ``claim_value`` in ``provider``'s groups claim join the group."""
        if not provider or not claim_value:
            raise ValueError("A mapping names a provider and a claim value")
        self._require_group("iam:MapIdpGroup", group_id)
        if self._group(group_id).status == "deleted":
            raise IAMConflictError(f"Group {group_id} is deleted")
        mapping = GroupMapping(provider, claim_value, group_id)
        self.store.map_idp_group(mapping)
        self._changed()
        return mapping

    def unmap_idp_group(self, provider: str, claim_value: str, group_id: str) -> bool:
        self._require_group("iam:UnmapIdpGroup", group_id)
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

    def _require_group(self, action: str, group_id: str) -> None:
        self.require(
            action,
            group_resource(group_id),
            not_found=lambda: IAMNotFoundError(f"Group {group_id} not found"),
        )

    def _group(self, group_id: str) -> PrincipalRecord:
        record = self._get_principal(group_id)
        if record.kind != "group":
            raise IAMNotFoundError(f"Group {group_id} not found")
        return record

    # =========================================================================
    # Policies
    # =========================================================================

    def create_policy(
        self,
        name: str,
        document: Mapping[str, Any] | str | PolicyDocument,
        *,
        description: str = "",
    ) -> Policy:
        """A customer policy, validated against the registered catalogs."""
        if not name:
            raise ValueError("A policy needs a name")
        parsed = parse_policy_document(document, self._registry)
        policy_id = new_id("pol")
        self.require("iam:CreatePolicy", policy_resource(policy_id))
        policy = self.store.create_policy(
            Policy(id=policy_id, name=name, description=description, document=parsed)
        )
        self._changed()
        return policy

    def get_policy(self, policy_id: str) -> Policy:
        self._require_policy("iam:GetPolicy", policy_id)
        return self.store.get_policy(policy_id)

    def list_policies(self, *, limit: int = 100, after: str | None = None) -> Page:
        return self._filtered_page(
            lambda size, cursor: self.store.list_policies(limit=size, after=cursor),
            "iam:ListPolicies",
            lambda policy: policy_resource(policy.id),
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
    ) -> Policy:
        """Optimistic update: ``RevisionConflictError`` when someone got there first."""
        self._require_policy("iam:UpdatePolicy", policy_id)
        current = self.store.get_policy(policy_id)
        if current.managed:
            raise IAMConflictError(f"{policy_id} is managed: only IAM rewrites it")
        updated = replace(
            current,
            name=name if name is not None else current.name,
            description=description if description is not None else current.description,
            document=parse_policy_document(document, self._registry)
            if document is not None
            else current.document,
        )
        if not updated.document.confined_to_scope and any(
            a.scope is not None
            for a in self.store.list_attachments(policy_id=policy_id)
        ):
            # Evaluation would ignore the rest at those scopes: say so instead.
            raise ValueError(
                f"{policy_id} is attached at a scope: every Allow resource must "
                "start with ${scope}:"
            )
        policy = self.store.update_policy(updated, expected_revision)
        self._changed()
        return policy

    def delete_policy(self, policy_id: str) -> None:
        """``IAMConflictError`` while the policy is attached, or when it is managed."""
        self._require_policy("iam:DeletePolicy", policy_id)
        if self.store.get_policy(policy_id).managed:
            raise IAMConflictError(f"{policy_id} is managed: only IAM removes it")
        self.store.delete_policy(policy_id)
        self._changed()

    def _require_policy(self, action: str, policy_id: str) -> None:
        self.require(
            action,
            policy_resource(policy_id),
            not_found=lambda: IAMNotFoundError(f"Policy {policy_id} not found"),
        )

    def _all_policies(self) -> list[Policy]:
        found: list[Policy] = []
        after: str | None = None
        while True:
            page = self.store.list_policies(limit=1000, after=after)
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
        (``builtin.platform.member`` or ``.viewer``) in step (RFC §7).
        """
        if scope is not None:
            validate_scope(scope)
        self._require_attach(policy_id, principal_id, scope)
        return self._attach(policy_id, principal_id, scope)

    def _require_attach(
        self, policy_id: str, principal_id: str, scope: str | None
    ) -> None:
        self.require(
            "iam:AttachPolicy",
            attachment_resource(policy_id, principal_id, scope),
            not_found=lambda: IAMNotFoundError("Policy or principal not found"),
        )

    def _attach(
        self, policy_id: str, principal_id: str, scope: str | None
    ) -> Attachment:
        policy = self.store.get_policy(policy_id)
        principal = self._get_principal(principal_id)
        if principal.status == "deleted":
            raise IAMConflictError(f"Principal {principal_id} is deleted")
        self._check_attachable(policy, scope)
        existing = self._find_attachment(policy_id, principal_id, scope)
        if existing is not None:
            return existing
        attachment = self.store.attach(
            Attachment(new_id("att"), policy_id, principal_id, scope)
        )
        if policy_id in roles.ROLES:
            self._sync_platform_roles(principal_id)
        self._changed()
        return attachment

    @staticmethod
    def _check_attachable(policy: Policy, scope: str | None) -> None:
        if scope is None and policy.document.uses_scope:
            raise ValueError(f"{policy.id} uses ${{scope}}: attach it at a scope")
        if scope is not None and not policy.document.confined_to_scope:
            # A scope only fills ${scope}: anything else would reach past it.
            raise ValueError(
                f"{policy.id} names resources outside ${{scope}}: "
                "only a policy confined to its scope is attached at one"
            )

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
        roles there. Org-level roles (``abi:<org>:-``) bring neither (RFC §7)."""
        held: set[str] = set()
        for attachment in self.store.list_attachments(principal_id=principal_id):
            if attachment.policy_id not in roles.ROLES or attachment.scope is None:
                continue
            org, workspace = scope_fields(attachment.scope)
            if org == NONE or workspace == NONE:
                continue
            held.add(attachment.policy_id)
        if held & roles.PLATFORM_MEMBER_ROLES:
            wanted = roles.PLATFORM_MEMBER
        elif roles.VIEWER in held:
            wanted = roles.PLATFORM_VIEWER
        else:
            wanted = None
        for companion in (roles.PLATFORM_MEMBER, roles.PLATFORM_VIEWER):
            present = self._find_attachment(companion, principal_id, None) is not None
            if companion == wanted and not present:
                self.store.attach(Attachment(new_id("att"), companion, principal_id))
            elif companion != wanted and present:
                self.store.detach(companion, principal_id, None)

    # =========================================================================
    # Invitations and IdP group bindings (RFC §12.2)
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
        self._check_attachable(self.store.get_policy(policy_id), scope)
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
        grant = next(
            (g for g in self.store.list_pending_grants() if g.id == grant_id), None
        )
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
        claimed: list[Attachment] = []
        for grant in self.store.list_pending_grants(
            provider=user.provider, email=user.email.strip().lower()
        ):
            attachment = self.store.claim_pending_grant(
                grant.id, principal_id, new_id("att")
            )
            if attachment is None:
                continue  # another sign-in of this user claimed it first
            claimed.append(attachment)
            if grant.policy_id in roles.ROLES:
                self._sync_platform_roles(principal_id)
        if claimed:
            self._changed()
        return claimed

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
        self._check_attachable(self.store.get_policy(policy_id), scope)
        group = self._binding_group(provider, claim_value, scope)
        attachment = self._attach(policy_id, group.id, scope)
        return IdpBinding(
            provider, claim_value, group.id, policy_id, scope, attachment.id
        )

    def _binding_group(
        self, provider: str, claim_value: str, scope: str | None
    ) -> PrincipalRecord:
        name = _bound_group(provider, claim_value)
        for group_id in self.store.resolve_idp_groups(provider, [claim_value]):
            record = self.store.get_principal(group_id)
            if record.kind == "group" and record.status == "active":
                if record.name == name:
                    return record
        org = None
        if scope is not None:
            org = scope_fields(scope)[0]
            org = org if org not in (NONE, "*") else None
        group = self.store.create_principal(
            PrincipalRecord(id=new_id("grp"), kind="group", name=name, org=org)
        )
        self.store.map_idp_group(GroupMapping(provider, claim_value, group.id))
        self._changed()
        return group

    def unbind_idp_group(
        self, provider: str, claim_value: str, policy_id: str, scope: str | None = None
    ) -> bool:
        provider, claim_value = _grantee(provider, claim_value, email=False)
        if scope is not None:
            validate_scope(scope)
        self._require_detach_binding(policy_id, provider, claim_value, scope)
        removed = False
        for group_id in self.store.resolve_idp_groups(provider, [claim_value]):
            if self.store.detach(policy_id, group_id, scope):
                removed = True
        if removed:
            self._sync_bound_roles(provider, claim_value)
            self._changed()
        return removed

    def _require_detach_binding(
        self, policy_id: str, provider: str, claim_value: str, scope: str | None
    ) -> None:
        self.require(
            "iam:DetachPolicy",
            attachment_resource(policy_id, _bound_group(provider, claim_value), scope),
            not_found=lambda: IAMNotFoundError("Binding not found"),
        )

    def _sync_bound_roles(self, provider: str, claim_value: str) -> None:
        for group_id in self.store.resolve_idp_groups(provider, [claim_value]):
            self._sync_platform_roles(group_id)

    def list_idp_bindings(
        self, *, provider: str | None = None, policy_id: str | None = None
    ) -> list[IdpBinding]:
        found: list[IdpBinding] = []
        after: str | None = None
        while True:
            page = self.store.list_principals("group", limit=500, after=after)
            for group in page.items:
                if group.status != "active":
                    continue
                mappings = [
                    m
                    for m in self.store.list_idp_group_mappings(group.id)
                    if provider in (None, m.provider)
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
    # Tokens (RFC §9.1): the engine signs, everyone verifies with the JWKS.
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
        of the built-in login, the Nexus id its tokens carry (TRANSITIONAL)."""
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
        """A service account's key for an access token (RFC §8.2): ``abi:nats``
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
    # Token exchange (RFC §9.4) and revocation
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
        a user of the built-in login, the Nexus id (TRANSITIONAL)."""
        return self._resolve(CallPrincipal(id=user_id, kind="user"))

    def resolve_principal(self, principal: CallPrincipal) -> PrincipalRecord | None:
        return self._resolve(principal)

    @staticmethod
    def user_name(record: PrincipalRecord) -> str:
        """The id calls name ``record`` by: its principal id, or for a user of
        the built-in login the Nexus id its sessions carry (TRANSITIONAL)."""
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
    # Job trigger seals (RFC §8.4)
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
        of this deployment (RFC §8.2), created on first use. In process only."""
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
    # Keys (RFC §8.1)
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
    # Module permission manifests (RFC §8.3)
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
        parsed = parse_policy_document(document)
        _refuse_reserved_topics(parsed)
        raw = parsed.to_dict()
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
        ``module.<project>.<module_id>``.
        """
        missing = lambda: IAMNotFoundError(f"Manifest of {principal_id} not found")
        self.require(
            "iam:ApproveManifest", manifest_resource(principal_id), not_found=missing
        )
        record = self._manifest(principal_id, sha256, missing, pending_only=True)
        parsed = parse_policy_document(
            document if document is not None else record.document
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
        _refuse_reserved_topics(document)
        account = self._get_principal(record.principal_id)
        bound = modules.bind(document, record.project, record.module_id)
        self._refuse_nested_topics(account.id, bound)
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
    # Broker permissions (RFC §8.4)
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
        ``idp``) and their policies. ``builtin.engine`` and ``builtin.api`` are
        TRANSITIONAL broad policies until subtask 11 (#65) enumerates them.
        """
        self._register_catalog(CATALOG)
        self._refresh_builtin_policies()
        for name, policy_id in roles.SERVICE_ACCOUNTS.items():
            record = self.store.find_service_account(name)
            if record is None:
                record = self.store.create_principal(
                    PrincipalRecord(id=new_id("sa"), kind="service_account", name=name)
                )
            if self._find_attachment(policy_id, record.id, None) is None:
                self.store.attach(Attachment(new_id("att"), policy_id, record.id))
        self._changed()

    def _refresh_builtin_policies(self) -> None:
        for policy in roles.builtin_policies(self._registry):
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
        """A page of allowed items; paging applies after filtering (RFC §5.5)."""
        if not 1 <= limit <= 1000:
            raise ValueError("limit must be between 1 and 1000")
        if not self.filter(action, ()).prefix_hints:
            # No Allow of the caller's can admit an item: nothing to scan for.
            return Page([], None)
        items: list[Any] = []
        cursor = after
        while True:
            page = fetch(limit, cursor)
            allowed = set(self.filter(action, (name(i) for i in page.items)).allowed)
            for item in page.items:
                if name(item) in allowed:
                    items.append(item)
                    if len(items) == limit:
                        more = item is not page.items[-1] or page.next_after is not None
                        return Page(items, item.id if more else None)
            if page.next_after is None:
                return Page(items, None)
            cursor = page.next_after

    def close(self) -> None:
        self.store.close()


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
        else the kind's default (RFC §8.1)."""
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
    """A user Nexus names on a call (TRANSITIONAL): IAM's user of issuer
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
    ``_INBOX``, ``$...``) would reach those subjects through the broker."""
    errors = [
        f"statement {index}: {problem}"
        for index, statement in enumerate(document.statements)
        for problem in broker.reserved_topic_problems(statement.resources)
    ]
    if errors:
        raise PolicyValidationError(errors)
