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
from dataclasses import replace
from typing import Any, Literal, TypeVar

from naas_abi_core import logger
from naas_abi_core.engine.call_context import (
    CallContext,
    current_call_context,
)
from naas_abi_core.engine.call_context import (
    Principal as CallPrincipal,
)
from naas_abi_core.services.iam import roles
from naas_abi_core.services.iam.adapters.secondary.authorizer__policy import (
    PolicyAuthorizer,
)
from naas_abi_core.services.iam.catalog import (
    ActionCatalog,
    CatalogRegistry,
    removed_actions,
)
from naas_abi_core.services.iam.iam_catalog import CATALOG, SEALS
from naas_abi_core.services.iam.IAMPorts import (
    KIND_PREFIXES,
    Attachment,
    Decision,
    EffectiveStatement,
    Explanation,
    FilterResult,
    GroupMapping,
    IAMConflictError,
    IAMNotFoundError,
    IAMStore,
    IAuthorizer,
    IIAMService,
    Page,
    Placement,
    Policy,
    PolicySource,
    PrincipalKind,
    PrincipalRecord,
    ScopeRecord,
    Seal,
    Subject,
    new_id,
)
from naas_abi_core.services.iam.names import (
    ALL_WORKSPACES,
    NONE,
    resource_name,
    scope_fields,
    validate_scope,
)
from naas_abi_core.services.iam.policy import (
    PolicyDocument,
    parse_policy_document,
)

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
    """Named at the attachment's scope (§6.4).

    An org-wide one (``abi:<org>:*``) is named in workspace ``%2A``
    (``ALL_WORKSPACES``): an ``abi:<org>:*`` grant reaches it, an org-level
    ``abi:<org>:-`` one does not, so an org admin cannot widen itself to every
    workspace.
    """
    org, workspace = scope_fields(scope) if scope else (NONE, NONE)
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


def placement_resource(service: str, id_key: str) -> str:
    return resource_name("iam", "placement", [service, id_key], kind="path")


def scope_resource(org: str, workspace: str = NONE) -> str:
    parts = [org] if workspace == NONE else [org, workspace]
    return resource_name("iam", "scope", parts, kind="path")


def catalog_resource(service: str) -> str:
    return resource_name("iam", "catalog", service)


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
    ) -> None:
        self.store = store
        self._registry = CatalogRegistry()
        self._seals = tuple(seals)
        self._subjects = _TTLCache(cache_ttl_seconds, cache_size)
        self._policies = _TTLCache(cache_ttl_seconds, cache_size)
        self._placements = _TTLCache(cache_ttl_seconds, 1)
        self._listeners: list[Callable[[int], None]] = []
        for catalog in store.list_catalogs():
            self._registry.register(catalog)
        self._registry.register(CATALOG)
        self.authorizer = (authorizer or PolicyAuthorizer)(self)

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
        return self._subjects.get(key, lambda: self._compute_subject(principal))

    def _compute_subject(self, principal: CallPrincipal) -> Subject:
        if principal.kind == "anonymous":
            return Subject(principal.id, "active", ())
        record = self._resolve(principal)
        status = record.status if record is not None else "active"
        holders: list[tuple[str, str | None]] = []
        if record is not None:
            holders.append((record.id, None))
            for group_id in self.store.groups_of(record.id):
                holders.append((group_id, group_id))
        # Mapped IdP groups travel in the token's grp claim (§2).
        for group_id in sorted(principal.groups):
            if all(group_id != held for held, _ in holders):
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
            statements += self._statements_of(attachment.policy_id, attachment, group)
        if principal.kind == "user":
            # builtin.self is held by every user, implicitly.
            statements += self._statements_of(roles.SELF, None, None)
        elif (
            principal.kind == "service_account"
            and record is None
            and (principal.name or principal.id) not in roles.SERVICE_ACCOUNTS
        ):
            # TRANSITIONAL (#60): a remote module's service account.
            statements += self._statements_of(roles.TRANSITIONAL_MODULE, None, None)
        return Subject(principal.id, status, tuple(statements))

    def _statements_of(
        self, policy_id: str, attachment: Attachment | None, group: str | None
    ) -> list[EffectiveStatement]:
        policy = self._cached_policy(policy_id)
        if policy is None:
            return []
        return [
            EffectiveStatement(
                statement=statement,
                policy_id=policy.id,
                statement_index=index,
                attachment_id=attachment.id if attachment else None,
                scope=attachment.scope if attachment else None,
                via_group=group,
            )
            for index, statement in enumerate(policy.document.statements)
        ]

    def _cached_policy(self, policy_id: str) -> Policy | None:
        def load() -> Policy | None:
            try:
                return self.store.get_policy(policy_id)
            except IAMNotFoundError:
                return None

        return self._policies.get(policy_id, load)

    def _active(self, principal_id: str) -> bool:
        try:
            return self.store.get_principal(principal_id).active
        except IAMNotFoundError:
            return False

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

    def resolve_placement(self, service: str, canonical_id: str) -> tuple[str, str]:
        """``(org, workspace)`` of a resource: the exact key, else the longest
        matching prefix, else the platform."""
        best: Placement | None = None
        for placement in self._all_placements():
            if placement.service != service:
                continue
            if placement.id_key == canonical_id:
                return placement.org, placement.workspace
            if placement.id_key.endswith("*") and canonical_id.startswith(
                placement.id_key[:-1]
            ):
                if best is None or len(placement.id_key) > len(best.id_key):
                    best = placement
        return (best.org, best.workspace) if best is not None else (NONE, NONE)

    def _all_placements(self) -> list[Placement]:
        return self._placements.get("all", self.store.list_placements)

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
                # Another first sighting of the same identity created it.
                existing = self.store.find_user(issuer, subject)
                if existing is None:
                    raise
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
        self._changed()
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
        self.require(
            "iam:AttachPolicy",
            attachment_resource(policy_id, principal_id, scope),
            not_found=lambda: IAMNotFoundError("Policy or principal not found"),
        )
        policy = self.store.get_policy(policy_id)
        principal = self._get_principal(principal_id)
        if principal.status == "deleted":
            raise IAMConflictError(f"Principal {principal_id} is deleted")
        if scope is None and policy.document.uses_scope:
            raise ValueError(f"{policy_id} uses ${{scope}}: attach it at a scope")
        if scope is not None and not policy.document.confined_to_scope:
            # A scope only fills ${scope}: anything else would reach past it.
            raise ValueError(
                f"{policy_id} names resources outside ${{scope}}: "
                "only a policy confined to its scope is attached at one"
            )
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

    def _changed(self) -> None:
        self.invalidate()
        revision = self.store.revision()
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
