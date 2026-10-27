"""The IAM admin pages' use cases.

Every call is IAM's, made as the signed-in user: the user's own policies decide
what each page may read and change, and Nexus adds no role check of its own. What
this service adds is

* **audit**: every change writes a ``requested`` record first, and nothing changes
  if it cannot be written (``run_audited``, the System app's fail-closed log);
  ``succeeded`` or ``failed`` follows. Records name the actor, the operation and
  the resource, never a key's value or a policy's text;
* **narrowing**: a module's manifest is approved as submitted or narrowed, never
  widened (``narrowing.py``);
* **names**: ids in lists come with the name of the policy or principal, read by
  the engine for ids the caller already holds;
* **what the caller may do**, so pages show only what will answer.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from typing import Any, TypeVar

from naas_abi.apps.nexus.apps.api.app.services.iam_admin import views
from naas_abi.apps.nexus.apps.api.app.services.iam_admin.narrowing import (
    is_unchanged,
    narrowing_errors,
)
from naas_abi.apps.nexus.apps.api.app.services.iam_admin.port import (
    IamGateway,
    IamUnavailableError,
    OrganizationScopes,
    ScopeDirectory,
)
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.resources import (
    AdminAction,
    AdminAuditLog,
)
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.resources_service import run_audited
from naas_abi_core.engine.call_context import current_call_context
from naas_abi_core.services.iam import roles
from naas_abi_core.services.iam.IAMPorts import (
    IAMConflictError,
    IAMNotFoundError,
    IIAMService,
    PermissionDeniedError,
    PrincipalKind,
    ScopeSet,
)
from naas_abi_core.services.iam.IAMService import (
    attachment_resource,
    group_resource,
    key_resource,
    manifest_resource,
    policy_resource,
)
from naas_abi_core.services.iam.modules import split_manifest
from naas_abi_core.services.iam.names import (
    NONE,
    PLATFORM_SCOPE,
    parse_resource_name,
    resource_name,
    scope_fields,
    scope_name,
    split_action,
    validate_owner_scope,
    validate_scope,
    within_owner,
)
from naas_abi_core.services.iam.policy import (
    PolicyDocument,
    PolicyValidationError,
    check_owned_document,
    parse_policy_document,
)
from naas_abi_core.services.iam.sets import intersect, read_resource, write_resource
from starlette.concurrency import run_in_threadpool

T = TypeVar("T")

SERVICE = "iam"
AUDIT_LIMIT = 500
# The pages of ``attachable``: policies are listed in chunks, and few installs have more.
MAX_ATTACHABLE_SCAN = 2000
# How long a service-account key lives unless told: IAM's own default applies when None.
MAX_KEY_DAYS = 365

# What each action decides on, for ``access``: the type of its resource.
_WILDCARD_TYPE = {
    "iam:ListPolicies": "policy",
    "iam:CreatePolicy": "policy",
    "iam:UpdatePolicy": "policy",
    "iam:DeletePolicy": "policy",
    "iam:ListGroups": "group",
    "iam:CreateGroup": "group",
    "iam:DeleteGroup": "group",
    "iam:AddGroupMember": "group",
    "iam:RemoveGroupMember": "group",
    "iam:MapIdpGroup": "group",
    "iam:UnmapIdpGroup": "group",
    "iam:ListPrincipals": "principal",
    "iam:CreateServiceAccount": "principal",
    "iam:DeletePrincipal": "principal",
    "iam:SuspendPrincipal": "principal",
    "iam:ResumePrincipal": "principal",
    "iam:Explain": "principal",
    "iam:ListManifests": "manifest",
    "iam:ApproveManifest": "manifest",
    "iam:RejectManifest": "manifest",
    "iam:GetSet": "set",
    "iam:PutSet": "set",
}
_ATTACHMENT_ACTIONS = ("iam:ListAttachments", "iam:AttachPolicy", "iam:DetachPolicy")
_KEY_ACTIONS = ("iam:ListKeys", "iam:CreateKey", "iam:RevokeKey")
ACCESS_ACTIONS: tuple[str, ...] = (*_WILDCARD_TYPE, *_ATTACHMENT_ACTIONS, *_KEY_ACTIONS)


class IamAdminService:
    def __init__(
        self,
        gateway: IamGateway,
        audit: AdminAuditLog,
        *,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
        directory: ScopeDirectory | None = None,
    ) -> None:
        self._gateway = gateway
        self._audit = audit
        self._clock = clock
        self._directory = directory

    # -- plumbing ---------------------------------------------------------------------

    def _session(self, user: Any) -> IIAMService:
        return self._gateway.bind(user)

    async def _read(self, user: Any, call: Callable[[IIAMService], T]) -> T:
        session = self._session(user)
        return await run_in_threadpool(call, session)

    async def _change(
        self,
        user: Any,
        operation: str,
        resource_id: str,
        call: Callable[[IIAMService], T],
        *,
        detail: str = "",
    ) -> T:
        """A change IAM decides, audited first: no record, no change."""
        session = self._session(user)
        action = AdminAction(_actor_id(user), SERVICE, operation, resource_id, detail)
        return await run_audited(self._audit, action, lambda: run_in_threadpool(call, session))

    @staticmethod
    def _wildcard(kind: str, owner: str = PLATFORM_SCOPE) -> str:
        """Any resource of ``kind``: policies and groups as named at ``owner``."""
        if kind == "policy":
            return policy_resource("*", owner)
        if kind == "group":
            return group_resource("*", owner)
        return resource_name("iam", kind, "*")

    @staticmethod
    def _listing(session: IIAMService, action: str, resource: str) -> Callable[[list[Any]], None]:
        """A page that comes back empty because the caller may list nothing is a
        refusal, not an empty page: ``check(items)`` raises for it."""

        def check(items: list[Any]) -> None:
            if not items and not session.authorize(action, resource).allowed:
                raise PermissionDeniedError(action, resource)

        return check

    # -- what the caller may do -------------------------------------------------------

    async def access(self, user: Any, scope: str | None = None) -> dict[str, Any]:
        """Which actions the caller may perform: on the platform, or (the attachment
        actions, and the policies and groups of that level) at ``scope``. Decided by
        IAM, as for any call; ``nexus:ReadSystem`` for the audit."""
        if scope is not None:
            validate_scope(scope)
        owner = _owner_of(scope)

        def decide(session: IIAMService) -> dict[str, bool]:
            result: dict[str, bool] = {}
            for action, kind in _WILDCARD_TYPE.items():
                result[action] = session.authorize(action, self._wildcard(kind, owner)).allowed
            for action in _ATTACHMENT_ACTIONS:
                # Any policy, or at least one of the roles an admin grants below owner.
                result[action] = any(
                    session.authorize(action, attachment_resource(policy, "*", scope)).allowed
                    for policy in ("*", *roles.ROLES)
                )
            for action in _KEY_ACTIONS:
                result[action] = session.authorize(action, key_resource("*", "*")).allowed
            return result

        actions = await self._read(user, decide)
        actions["nexus:ReadSystem"] = await self._reads_system(user)
        return {"actions": actions}

    async def grantable(self, user: Any, scope: str) -> dict[str, Any]:
        """What the caller may grant at ``scope``, for the policy builder: per catalog
        (a kernel service or a module), the actions they hold there and the resource
        patterns (``${scope}:...``) they hold them on, minus their Denies. IAM's
        ``grantable``, about the caller only, like ``access``: IAM validates the scope."""
        found = await self._read(user, lambda session: session.grantable(scope))
        return {"scope": scope, "catalogs": [views.grantable_view(c) for c in found]}

    async def _reads_system(self, user: Any) -> bool:
        from naas_abi.apps.nexus.apps.api.app.services.iam.authz import AUTHZ

        return await AUTHZ.allowed("ReadSystem", user=user)

    # -- catalogs and validation ------------------------------------------------------

    async def catalogs(self, user: Any, scope: str | None = None) -> dict[str, Any]:
        """The action catalogs a policy names, for the editor's autocomplete.
        For whoever may write policies or read them (at ``scope``'s level)."""
        owner = _owner_of(scope)

        def read(session: IIAMService) -> dict[str, Any]:
            self._require_any(
                session,
                ("iam:ListPolicies", "iam:CreatePolicy", "iam:UpdatePolicy"),
                self._wildcard("policy", owner),
            )
            return views.catalogs_view(self._gateway.catalogs().all())

        return await self._read(user, read)

    @staticmethod
    def _require_any(session: IIAMService, actions: tuple[str, ...], resource: str) -> None:
        if not any(session.authorize(a, resource).allowed for a in actions):
            raise PermissionDeniedError(actions[0], resource)

    async def validate_policy(
        self, user: Any, source: Mapping[str, Any], scope: str | None = None
    ) -> dict[str, Any]:
        """What IAM says of a document (its object or its YAML/JSON text), saving
        nothing; at an org or a workspace, as a policy that level owns
        (``check_owned_document``), so what passes here ``create_policy`` takes."""
        owner = _owner_of(scope)

        def check(session: IIAMService) -> dict[str, Any]:
            self._require_any(
                session,
                ("iam:CreatePolicy", "iam:UpdatePolicy"),
                self._wildcard("policy", owner),
            )
            try:
                document = self._parse(source)
                check_owned_document(document, owner)
            except PolicyValidationError as exc:
                return {"valid": False, "errors": list(exc.errors), "document": None}
            except ValueError as exc:
                return {"valid": False, "errors": [str(exc)], "document": None}
            return {"valid": True, "errors": [], "document": document.to_dict()}

        return await self._read(user, check)

    def _parse(self, source: Mapping[str, Any]) -> PolicyDocument:
        raw = source.get("document") if source.get("document") is not None else source.get("text")
        if raw is None:
            raise ValueError("Give the policy as a document or as text")
        return parse_policy_document(raw, self._gateway.catalogs())

    # -- policies ---------------------------------------------------------------------

    async def list_policies(
        self, user: Any, after: str | None = None, scope: str | None = None
    ) -> dict[str, Any]:
        """The policies the caller may list; with ``scope``, that level's own and
        those above it the caller may attach there (IAM's ``list_policies``). An
        org-wide scope lists its org's."""
        owner = validate_owner_scope(_owner_of(scope)) if scope is not None else None

        def read(session: IIAMService) -> dict[str, Any]:
            page = session.list_policies(after=after, scope=owner)
            self._listing(session, "iam:ListPolicies", self._wildcard("policy", _owner_of(owner)))(
                page.items
            )
            return {
                "items": [views.policy_view(p) for p in page.items],
                "next_after": page.next_after,
            }

        return await self._read(user, read)

    async def get_policy(self, user: Any, policy_id: str) -> dict[str, Any]:
        return await self._read(user, lambda s: views.policy_view(s.get_policy(policy_id)))

    async def create_policy(
        self,
        user: Any,
        name: str,
        source: Mapping[str, Any],
        description: str = "",
        scope: str | None = None,
    ) -> dict[str, Any]:
        """A policy owned by ``scope`` (the platform when None)."""

        def create(session: IIAMService) -> dict[str, Any]:
            document = self._parse(source)
            return views.policy_view(
                session.create_policy(name, document, description=description, scope=scope)
            )

        return await self._change(
            user, "create_policy", name, create, detail=f"{name}, {scope or PLATFORM_SCOPE}"
        )

    async def update_policy(
        self,
        user: Any,
        policy_id: str,
        *,
        expected_revision: int,
        source: Mapping[str, Any] | None,
        name: str | None,
        description: str | None,
    ) -> dict[str, Any]:
        def update(session: IIAMService) -> dict[str, Any]:
            document = self._parse(source) if source else None
            return views.policy_view(
                session.update_policy(
                    policy_id,
                    expected_revision=expected_revision,
                    document=document,
                    name=name,
                    description=description,
                )
            )

        return await self._change(
            user, "update_policy", policy_id, update, detail=f"revision {expected_revision}"
        )

    async def delete_policy(self, user: Any, policy_id: str) -> None:
        await self._change(user, "delete_policy", policy_id, lambda s: s.delete_policy(policy_id))

    # -- attachments ------------------------------------------------------------------

    async def list_attachments(
        self,
        user: Any,
        *,
        principal_id: str | None = None,
        policy_id: str | None = None,
        scope: str | None = None,
    ) -> dict[str, Any]:
        if scope is not None:
            validate_scope(scope)

        def read(session: IIAMService) -> dict[str, Any]:
            found = session.list_attachments(principal_id=principal_id, policy_id=policy_id)
            if scope is not None:
                found = [a for a in found if a.scope == scope]
            self._listing(session, "iam:ListAttachments", attachment_resource("*", "*", scope))(
                found
            )
            policies: dict[str, str | None] = {}
            principals: dict[str, Any] = {}
            items = []
            for attachment in found:
                if attachment.policy_id not in policies:
                    policy = self._gateway.policy(attachment.policy_id)
                    policies[attachment.policy_id] = policy.name if policy else None
                if attachment.principal_id not in principals:
                    principals[attachment.principal_id] = self._gateway.principal(
                        attachment.principal_id
                    )
                items.append(
                    views.attachment_view(
                        attachment,
                        policies[attachment.policy_id],
                        principals[attachment.principal_id],
                    )
                )
            return {"items": items}

        return await self._read(user, read)

    async def attachable(
        self, user: Any, scope: str | None, principal_id: str | None = None
    ) -> dict[str, Any]:
        """The policies the caller may attach at ``scope``: IAM's rule for a scope
        (every Allow starts with ``${scope}:``) and the caller's own right to attach.
        A policy not wholly within ``${scope}:`` (a Deny naming anything) is offered
        at a scope only to whoever may attach it unscoped, as IAM decides."""
        if scope is not None:
            validate_scope(scope)

        def read(session: IIAMService) -> dict[str, Any]:
            candidates = [
                p
                for p in self._gateway.policies()[:MAX_ATTACHABLE_SCAN]
                if within_owner(p.owner_scope, scope)
                and (
                    p.document.confined_to_scope if scope is not None else not p.document.uses_scope
                )
            ]
            names = {attachment_resource(p.id, principal_id or "*", scope): p for p in candidates}
            allowed = set(session.filter("iam:AttachPolicy", names).allowed)
            if scope is not None:
                unscoped = {
                    attachment_resource(p.id, principal_id or "*", None): name
                    for name, p in names.items()
                    if name in allowed and not p.document.wholly_within_scope
                }
                reach = set(session.filter("iam:AttachPolicy", unscoped).allowed)
                allowed -= {name for u, name in unscoped.items() if u not in reach}
            return {
                "items": [
                    {
                        "id": names[name].id,
                        "name": names[name].name,
                        "description": names[name].description,
                        "managed": names[name].managed,
                        "owner_scope": names[name].owner_scope,
                    }
                    for name in names
                    if name in allowed
                ]
            }

        return await self._read(user, read)

    async def attach(
        self, user: Any, policy_id: str, principal_id: str, scope: str | None
    ) -> dict[str, Any]:
        if scope is not None:
            validate_scope(scope)

        def attach(session: IIAMService) -> dict[str, Any]:
            attachment = session.attach_policy(policy_id, principal_id, scope)
            policy = self._gateway.policy(policy_id)
            return views.attachment_view(
                attachment,
                policy.name if policy else None,
                self._gateway.principal(principal_id),
            )

        return await self._change(
            user,
            "attach_policy",
            f"{policy_id}/{principal_id}",
            attach,
            detail=f"scope {scope or 'platform'}",
        )

    async def detach(self, user: Any, policy_id: str, principal_id: str, scope: str | None) -> None:
        if scope is not None:
            validate_scope(scope)

        def detach(session: IIAMService) -> None:
            if not session.detach_policy(policy_id, principal_id, scope):
                raise IAMNotFoundError("That policy is not attached there")

        await self._change(
            user,
            "detach_policy",
            f"{policy_id}/{principal_id}",
            detach,
            detail=f"scope {scope or 'platform'}",
        )

    # -- principals -------------------------------------------------------------------

    async def list_principals(
        self, user: Any, kind: PrincipalKind | None = None, after: str | None = None
    ) -> dict[str, Any]:
        def read(session: IIAMService) -> dict[str, Any]:
            page = session.list_principals(kind, after=after)
            self._listing(session, "iam:ListPrincipals", self._wildcard("principal"))(page.items)
            return {
                "items": [views.principal_view(p) for p in page.items if p.status != "deleted"],
                "next_after": page.next_after,
            }

        return await self._read(user, read)

    async def get_principal(self, user: Any, principal_id: str) -> dict[str, Any]:
        return await self._read(user, lambda s: views.principal_view(s.get_principal(principal_id)))

    async def suspend(self, user: Any, principal_id: str) -> dict[str, Any]:
        return await self._change(
            user,
            "suspend_principal",
            principal_id,
            lambda s: views.principal_view(s.suspend_principal(principal_id)),
        )

    async def resume(self, user: Any, principal_id: str) -> dict[str, Any]:
        return await self._change(
            user,
            "resume_principal",
            principal_id,
            lambda s: views.principal_view(s.resume_principal(principal_id)),
        )

    # -- groups -----------------------------------------------------------------------

    async def list_groups(self, user: Any, scope: str | None = None) -> dict[str, Any]:
        """The groups the caller may list; with ``scope``, that level's own (and,
        at a workspace, its org's the caller attaches to there). An org-wide scope
        lists its org's."""
        owner = validate_owner_scope(_owner_of(scope)) if scope is not None else None

        def read(session: IIAMService) -> dict[str, Any]:
            page = session.list_groups(scope=owner)
            self._listing(session, "iam:ListGroups", self._wildcard("group", _owner_of(owner)))(
                page.items
            )
            return {"items": [views.principal_view(g) for g in page.items if g.status != "deleted"]}

        return await self._read(user, read)

    def _group_view(self, session: IIAMService, group_id: str) -> dict[str, Any]:
        group = session.get_group(group_id)
        members = []
        for member_id in session.list_group_members(group_id):
            record = self._gateway.principal(member_id)
            if record is not None:
                members.append(views.principal_view(record))
        mappings = [
            {"provider": m.provider, "claim_value": m.claim_value}
            for m in session.list_idp_group_mappings(group_id)
        ]
        return {**views.principal_view(group), "members": members, "idp_mappings": mappings}

    async def get_group(self, user: Any, group_id: str) -> dict[str, Any]:
        return await self._read(user, lambda s: self._group_view(s, group_id))

    async def create_group(
        self, user: Any, name: str, org: str | None, scope: str | None = None
    ) -> dict[str, Any]:
        """A group owned by ``scope`` (or, with only ``org``, by that org)."""
        return await self._change(
            user,
            "create_group",
            name,
            lambda s: views.principal_view(s.create_group(name, org=org, scope=scope)),
            detail=scope or (f"org {org}" if org else "platform group"),
        )

    async def delete_group(self, user: Any, group_id: str) -> None:
        await self._change(user, "delete_group", group_id, lambda s: s.delete_group(group_id))

    async def add_member(self, user: Any, group_id: str, member_id: str) -> dict[str, Any]:
        def add(session: IIAMService) -> dict[str, Any]:
            session.add_group_member(group_id, member_id)
            return self._group_view(session, group_id)

        return await self._change(user, "add_group_member", f"{group_id}/{member_id}", add)

    async def remove_member(self, user: Any, group_id: str, member_id: str) -> dict[str, Any]:
        def remove(session: IIAMService) -> dict[str, Any]:
            if not session.remove_group_member(group_id, member_id):
                raise IAMNotFoundError("That principal is not a member")
            return self._group_view(session, group_id)

        return await self._change(user, "remove_group_member", f"{group_id}/{member_id}", remove)

    async def map_idp_group(
        self, user: Any, group_id: str, provider: str, claim_value: str
    ) -> dict[str, Any]:
        def map_(session: IIAMService) -> dict[str, Any]:
            session.map_idp_group(provider, claim_value, group_id)
            return self._group_view(session, group_id)

        return await self._change(
            user, "map_idp_group", group_id, map_, detail=f"{provider}: {claim_value}"
        )

    async def unmap_idp_group(
        self, user: Any, group_id: str, provider: str, claim_value: str
    ) -> dict[str, Any]:
        def unmap(session: IIAMService) -> dict[str, Any]:
            if not session.unmap_idp_group(provider, claim_value, group_id):
                raise IAMNotFoundError("That IdP group is not mapped to this group")
            return self._group_view(session, group_id)

        return await self._change(
            user, "unmap_idp_group", group_id, unmap, detail=f"{provider}: {claim_value}"
        )

    # -- service accounts and keys ----------------------------------------------------

    async def list_service_accounts(self, user: Any) -> dict[str, Any]:
        def read(session: IIAMService) -> dict[str, Any]:
            page = session.list_principals("service_account", limit=500)
            self._listing(session, "iam:ListPrincipals", self._wildcard("principal"))(page.items)
            builtin = frozenset(roles.SERVICE_ACCOUNTS)
            now = self._clock()
            items = []
            for record in page.items:
                if record.status == "deleted":
                    continue
                try:
                    keys = session.list_keys(record.id)
                except (PermissionDeniedError, IAMNotFoundError):
                    keys = []
                items.append(
                    {
                        **views.principal_view(record),
                        "account_kind": views.account_kind(record, builtin),
                        "active_keys": sum(1 for k in keys if k.usable(now)),
                    }
                )
            return {"items": items}

        return await self._read(user, read)

    async def create_service_account(self, user: Any, name: str) -> dict[str, Any]:
        def create(session: IIAMService) -> dict[str, Any]:
            record = session.create_service_account(name)
            return {
                **views.principal_view(record),
                "account_kind": views.account_kind(record, frozenset(roles.SERVICE_ACCOUNTS)),
                "active_keys": 0,
            }

        return await self._change(user, "create_service_account", name, create)

    async def delete_service_account(self, user: Any, account_id: str) -> None:
        def delete(session: IIAMService) -> None:
            record = session.get_principal(account_id)
            if record.kind != "service_account":
                raise IAMNotFoundError(f"Service account {account_id} not found")
            if views.account_kind(record, frozenset(roles.SERVICE_ACCOUNTS)) == "builtin":
                raise IAMConflictError("The engine's own service accounts cannot be deleted")
            session.delete_principal(account_id)

        await self._change(user, "delete_principal", account_id, delete)

    async def list_keys(self, user: Any, account_id: str) -> dict[str, Any]:
        def read(session: IIAMService) -> dict[str, Any]:
            session.require(
                "iam:ListKeys",
                key_resource(account_id, "*"),
                not_found=lambda: IAMNotFoundError(f"Service account {account_id} not found"),
            )
            return {"items": [views.key_view(k) for k in session.list_keys(account_id)]}

        return await self._read(user, read)

    async def create_key(
        self, user: Any, account_id: str, description: str, expires_in_days: int | None
    ) -> dict[str, Any]:
        if expires_in_days is not None and not 1 <= expires_in_days <= MAX_KEY_DAYS:
            raise ValueError(f"A key lasts 1 to {MAX_KEY_DAYS} days")
        expires = (
            self._clock() + timedelta(days=expires_in_days) if expires_in_days is not None else None
        )

        def create(session: IIAMService) -> dict[str, Any]:
            return views.created_key(
                session.create_key(account_id, description=description, expires_at=expires)
            )

        return await self._change(
            user, "create_key", account_id, create, detail=description or "no description"
        )

    async def revoke_key(self, user: Any, account_id: str, key_id: str) -> dict[str, Any]:
        return await self._change(
            user,
            "revoke_key",
            f"{account_id}/{key_id}",
            lambda s: views.key_view(s.revoke_key(account_id, key_id)),
        )

    async def rotate_key(self, user: Any, account_id: str, key_id: str) -> dict[str, Any]:
        return await self._change(
            user,
            "rotate_key",
            f"{account_id}/{key_id}",
            lambda s: views.created_key(s.rotate_key(account_id, key_id)),
        )

    # -- module permission approvals --------------------------------------------------

    def _account_name(self, principal_id: str) -> str | None:
        record = self._gateway.principal(principal_id)
        return record.name if record else None

    async def list_manifests(self, user: Any, status: str | None) -> dict[str, Any]:
        def read(session: IIAMService) -> dict[str, Any]:
            found = session.list_manifests(status=status)  # type: ignore[arg-type]
            self._listing(session, "iam:ListManifests", manifest_resource("*"))(found)
            return {
                "items": [views.manifest_view(m, self._account_name(m.principal_id)) for m in found]
            }

        return await self._read(user, read)

    async def approve_manifest(
        self,
        user: Any,
        principal_id: str,
        sha256: str,
        document: Mapping[str, Any] | None,
    ) -> dict[str, Any]:
        def approve(session: IIAMService) -> dict[str, Any]:
            narrowed = None
            if document is not None:
                # The policy is what an admin narrows; the catalog the module
                # declares is approved as submitted (``views.manifest_view``).
                submitted_policy, catalog = split_manifest(
                    session.get_manifest(principal_id, sha256).document
                )
                candidate_policy, echoed = split_manifest(document)
                if echoed is not None and dict(echoed) != dict(catalog or {}):
                    raise PolicyValidationError(
                        ["catalog: a module's declared catalog is approved as submitted"]
                    )
                submitted = parse_policy_document(submitted_policy)
                candidate = parse_policy_document(candidate_policy)
                problems = narrowing_errors(submitted, candidate)
                if problems:
                    raise PolicyValidationError(problems)
                if not is_unchanged(submitted, candidate):
                    narrowed = candidate
            approved = session.approve_manifest(principal_id, sha256, document=narrowed)
            return views.manifest_view(approved, self._account_name(principal_id))

        return await self._change(
            user,
            "approve_manifest",
            f"{principal_id}/{sha256}",
            approve,
            detail="narrowed" if document is not None else "as submitted",
        )

    async def reject_manifest(
        self, user: Any, principal_id: str, sha256: str, reason: str
    ) -> dict[str, Any]:
        return await self._change(
            user,
            "reject_manifest",
            f"{principal_id}/{sha256}",
            lambda s: views.manifest_view(
                s.reject_manifest(principal_id, sha256, reason=reason),
                self._account_name(principal_id),
            ),
            detail=reason[:200],
        )

    # -- the simulator ----------------------------------------------------------------

    async def simulate(
        self, user: Any, principal_id: str, action: str, resource: str
    ) -> dict[str, Any]:
        """Whether ``principal_id`` may perform ``action`` on ``resource``, and which
        statement decides: IAM's ``explain``, which needs ``iam:Explain`` on the principal."""

        # A malformed action or resource is a bad request, not a denial.
        split_action(action)
        parse_resource_name(resource)

        def explain(session: IIAMService) -> dict[str, Any]:
            explanation = session.explain(action, resource, principal_id=principal_id)
            principal = self._gateway.principal(principal_id)
            if principal is None:
                raise IAMNotFoundError(f"Principal {principal_id} not found")
            policy = None
            if explanation.statement is not None and explanation.statement.policy_id:
                try:
                    policy = session.get_policy(explanation.statement.policy_id)
                except (PermissionDeniedError, IAMNotFoundError):
                    policy = self._gateway.policy(explanation.statement.policy_id)
                    if policy is not None:
                        # The caller may not read the policy: name it, show no text.
                        policy = replace(policy, document=PolicyDocument(statements=()))
            return views.simulation_view(explanation, principal, policy)

        return await self._read(user, explain)

    # -- audit ------------------------------------------------------------------------

    async def history(
        self,
        *,
        operation: str | None = None,
        resource_id: str | None = None,
        limit: int = 100,
    ) -> dict[str, Any]:
        """Every change made through these pages, newest first (requested, then
        succeeded or failed)."""
        entries = await self._audit.history(
            service=SERVICE, resource_id=resource_id, limit=min(max(limit, 1), AUDIT_LIMIT)
        )
        return {
            "items": [
                {
                    "at": e.at,
                    "actor_id": e.actor_id,
                    "actor": e.actor,
                    "operation": e.operation,
                    "resource_id": e.resource_id,
                    "detail": e.detail,
                    "phase": e.phase,
                    "error": e.error,
                }
                for e in entries
                if operation is None or e.operation == operation
            ]
        }

    # -- sets: what each organization and workspace may use ------------------------

    def _directory_or_fail(self) -> ScopeDirectory:
        if self._directory is None:
            raise IamUnavailableError("No organizations to show sets for")
        return self._directory

    @staticmethod
    def _set_rows(
        session: IIAMService, organizations: list[OrganizationScopes]
    ) -> list[dict[str, Any]]:
        """The page's rows for ``organizations``: every column whose set the caller
        may read, what it records, what it has within its org's, and whether the
        caller may change it. Three calls whatever the size (two ``filter``, one
        ``list_sets``); a workspace whose org's set the caller may not read has
        its effective set asked of IAM, which bounds it by the org's."""
        columns = [(o.id, NONE) for o in organizations] + [
            (o.id, w.id) for o in organizations for w in o.workspaces
        ]
        read_of = {c: read_resource(*c) for c in columns}
        write_of = {c: write_resource(*c) for c in columns}
        readable = set(session.filter("iam:GetSet", list(read_of.values())).allowed)
        writable = set(session.filter("iam:PutSet", list(write_of.values())).allowed)
        only = organizations[0].id if len(organizations) == 1 else None
        recorded = {(s.org, s.workspace): s for s in session.list_sets(only)}

        def column(org: str, workspace: str, name: str) -> dict[str, Any] | None:
            if read_of[(org, workspace)] not in readable:
                return None
            own = recorded.get((org, workspace)) or ScopeSet(org, workspace)
            if workspace == NONE:
                effective = own
            elif read_of[(org, NONE)] in readable:
                effective = intersect(recorded.get((org, NONE)), own)
            else:
                effective = session.effective_set(org, workspace)
            return {
                "id": workspace if workspace != NONE else org,
                "name": name,
                "set": views.scope_set(own),
                "effective": views.scope_set(effective),
                "editable": write_of[(org, workspace)] in writable,
            }

        rows: list[dict[str, Any]] = []
        for org in organizations:
            workspaces = [
                found
                for ws in org.workspaces
                if (found := column(org.id, ws.id, ws.name)) is not None
            ]
            entry = column(org.id, NONE, org.name)
            if entry is None and not workspaces:
                continue
            if entry is None:
                # Its workspaces are the caller's to see, not the org's own set.
                entry = {
                    "id": org.id,
                    "name": org.name,
                    "set": None,
                    "effective": None,
                    "editable": False,
                }
            rows.append({**entry, "workspaces": workspaces})
        return rows

    async def sets(self, user: Any, org_id: str | None = None) -> list[dict[str, Any]]:
        """The sets of every organization (or the one named) and its workspaces
        that the caller may read, each with what it has once bounded by its org's
        and whether the caller may change it. Read as the user: a refusal of
        everything is a 403 (``iam:GetSet``)."""
        organizations = await self._directory_or_fail().organizations(org_id)

        def read(session: IIAMService) -> list[dict[str, Any]]:
            found = self._set_rows(session, organizations) if organizations else []
            if not found:
                target = read_resource(org_id) if org_id else self._wildcard("set")
                raise PermissionDeniedError("iam:GetSet", target)
            return found

        return await self._read(user, read)

    async def may_edit_set(self, user: Any, org_id: str, workspace_id: str = NONE) -> bool:
        """Whether the caller may change that set (``iam:PutSet``)."""

        def decide(session: IIAMService) -> bool:
            return session.authorize("iam:PutSet", write_resource(org_id, workspace_id)).allowed

        try:
            return await self._read(user, decide)
        except (PermissionDeniedError, IamUnavailableError):
            return False

    async def put_set(
        self,
        user: Any,
        org_id: str,
        workspace_id: str = NONE,
        *,
        modules: list[str] | None,
        features: list[str] | None,
    ) -> dict[str, Any]:
        """Record a set as the user, audited first; the page's entry for it after."""
        organizations = await self._directory_or_fail().organizations(org_id)
        org = next((o for o in organizations if o.id == org_id), None)
        if org is None or (
            workspace_id != NONE and all(w.id != workspace_id for w in org.workspaces)
        ):
            raise IAMNotFoundError("No such organization or workspace")
        where = f"{org_id}/{workspace_id}" if workspace_id != NONE else org_id
        detail = (
            f"modules={'everything' if modules is None else len(modules)} "
            f"features={'everything' if features is None else len(features)}"
        )

        def put(session: IIAMService) -> ScopeSet:
            return session.put_set(org_id, workspace_id, modules=modules, features=features)

        await self._change(user, "put_set", where, put, detail=detail)

        def read(session: IIAMService) -> dict[str, Any]:
            rows = self._set_rows(session, [org])
            entry: dict[str, Any] | None = rows[0] if rows else None
            if entry is not None and workspace_id != NONE:
                entry = next((w for w in entry["workspaces"] if w["id"] == workspace_id), None)
            if entry is None or (workspace_id == NONE and entry["set"] is None):
                raise PermissionDeniedError("iam:GetSet", read_resource(org_id, workspace_id))
            return entry

        return await self._read(user, read)


def _owner_of(scope: str | None) -> str:
    """The level whose policies and groups a scope's page shows: the scope itself,
    an org-wide scope's org, or the platform."""
    if scope is None:
        return PLATFORM_SCOPE
    org, workspace = scope_fields(scope)
    if workspace == "*":
        return scope_name(org, NONE)
    return scope


def _actor_id(user: Any) -> str:
    """Whose change it is: the user's id, else the call's own user."""
    found = user if isinstance(user, str) else getattr(user, "id", None)
    if found:
        return str(found)
    named = current_call_context().user
    return named.id if named is not None else "unknown"


__all__ = ["ACCESS_ACTIONS", "IamAdminService"]
