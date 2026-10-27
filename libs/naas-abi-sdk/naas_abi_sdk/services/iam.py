"""``engine.services.iam``: IAM for SDK modules (``abi.iam.v1``).

Decisions are about the module's own verified caller identity (its token, and
the user it acts for when it carries one), never about an argument. Every other
operation is authorized by IAM with its own ``iam:*`` actions. Records come back
as plain dictionaries; a policy's ``document`` is the policy as a dictionary.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, field
from typing import Any

from naas_abi_sdk.services._codec import ServiceProxy
from naas_abi_sdk.services.errors import NotFound, PermissionDenied


@dataclass(frozen=True)
class Decision:
    allowed: bool
    visible: bool
    reason: str


@dataclass(frozen=True)
class FilterResult:
    allowed: list[str]
    prefix_hints: list[str] = field(default_factory=list)


def _policy(record: dict[str, Any]) -> dict[str, Any]:
    record = dict(record)
    record["document"] = json.loads(record.pop("document_json"))
    return record


def _document(document: Mapping[str, Any] | str) -> str:
    return document if isinstance(document, str) else json.dumps(document)


class IAMService(ServiceProxy):
    domain = "iam"

    # -- decisions -------------------------------------------------------------

    async def authorize(self, action: str, resource: str) -> Decision:
        decision = await self._request("authorize", action=action, resource=resource)
        return Decision(decision["allowed"], decision["visible"], decision["reason"])

    async def require(
        self,
        action: str,
        resource: str,
        *,
        not_found: Callable[[], BaseException] | None = None,
    ) -> None:
        """Raise ``PermissionDenied`` when the caller can see the resource, else
        ``not_found()`` (``NotFound`` by default), unless the action is allowed."""
        decision = await self.authorize(action, resource)
        if decision.allowed:
            return
        if decision.visible:
            raise PermissionDenied(
                "PERMISSION_DENIED", f"{action} is not allowed on {resource}"
            )
        raise (
            not_found() if not_found else NotFound("NOT_FOUND", f"{resource} not found")
        )

    async def authorize_declared(
        self,
        action: str,
        resource_type: str,
        parts: Iterable[str],
        *,
        workspace: str | None = None,
    ) -> tuple[Decision, str]:
        """The decision on an action a module declares, and the resource IAM
        named for it: ``<type>/<parts>`` of the action's catalog, in
        ``workspace`` or else the workspace of the call, platform-level with
        none. The module never builds the name."""
        found = await self._request(
            "authorize_declared",
            action=action,
            resource_type=resource_type,
            parts=list(parts),
            workspace_id=workspace or "",
        )
        decision = found["decision"]
        return (
            Decision(decision["allowed"], decision["visible"], decision["reason"]),
            found["resource"],
        )

    async def require_declared(
        self,
        action: str,
        resource_type: str,
        parts: Iterable[str],
        *,
        workspace: str | None = None,
    ) -> None:
        """``require`` for an action a module declares."""
        decision, resource = await self.authorize_declared(
            action, resource_type, parts, workspace=workspace
        )
        if decision.allowed:
            return
        if decision.visible:
            raise PermissionDenied(
                "PERMISSION_DENIED", f"{action} is not allowed on {resource}"
            )
        raise NotFound("NOT_FOUND", f"{resource} not found")

    async def filter(self, action: str, resources: Iterable[str]) -> FilterResult:
        result = await self._request("filter", action=action, resources=list(resources))
        return FilterResult(list(result["allowed"]), list(result["prefix_hints"]))

    async def explain(
        self, action: str, resource: str, *, principal_id: str | None = None
    ) -> dict[str, Any]:
        return await self._request(
            "explain", action=action, resource=resource, principal_id=principal_id
        )

    async def grantable(self, scope: str) -> list[dict[str, Any]]:
        """What the caller may grant at ``scope`` (about the caller: no permission
        needed): ``[{"service", "actions": [{"action", "resources", "excluded"}]}]``,
        resources written ``${scope}:...``. A change that gives more than the
        caller holds raises ``GrantNotHeld``."""
        return await self._request("grantable", scope=scope)

    # -- principals --------------------------------------------------------------

    async def ensure_user(
        self,
        issuer: str,
        subject: str,
        *,
        provider: str | None = None,
        email: str | None = None,
        email_verified: bool = False,
        display_name: str | None = None,
    ) -> dict[str, Any]:
        return await self._request(
            "ensure_user",
            issuer=issuer,
            subject=subject,
            provider=provider,
            email=email,
            email_verified=email_verified,
            display_name=display_name,
        )

    async def create_service_account(
        self, name: str, *, owner_id: str | None = None
    ) -> dict[str, Any]:
        return await self._request(
            "create_service_account", name=name, owner_id=owner_id
        )

    async def get_principal(self, principal_id: str) -> dict[str, Any]:
        return await self._request("get_principal", principal_id=principal_id)

    async def list_principals(
        self, kind: str | None = None, *, limit: int = 100, after: str | None = None
    ) -> dict[str, Any]:
        """``{"principals": [...], "next_after": ...}``."""
        return await self._request(
            "list_principals", kind=kind, limit=limit, after=after
        )

    async def suspend_principal(self, principal_id: str) -> dict[str, Any]:
        return await self._request("suspend_principal", principal_id=principal_id)

    async def resume_principal(self, principal_id: str) -> dict[str, Any]:
        return await self._request("resume_principal", principal_id=principal_id)

    async def delete_principal(self, principal_id: str) -> dict[str, Any]:
        return await self._request("delete_principal", principal_id=principal_id)

    # -- groups ---------------------------------------------------------------------

    async def create_group(
        self, name: str, *, org: str | None = None, scope: str | None = None
    ) -> dict[str, Any]:
        """A group owned by ``scope``: ``abi:-:-`` (the default), ``abi:<org>:-``
        (also what ``org`` alone means) or ``abi:<org>:<ws>``."""
        return await self._request("create_group", name=name, org=org, scope=scope)

    async def get_group(self, group_id: str) -> dict[str, Any]:
        return await self._request("get_group", group_id=group_id)

    async def list_groups(
        self, *, limit: int = 100, after: str | None = None, scope: str | None = None
    ) -> dict[str, Any]:
        return await self._request("list_groups", limit=limit, after=after, scope=scope)

    async def delete_group(self, group_id: str) -> dict[str, Any]:
        return await self._request("delete_group", group_id=group_id)

    async def add_group_member(self, group_id: str, member_id: str) -> None:
        await self._request("add_group_member", group_id=group_id, member_id=member_id)

    async def remove_group_member(self, group_id: str, member_id: str) -> bool:
        return await self._request(
            "remove_group_member", group_id=group_id, member_id=member_id
        )

    async def list_group_members(self, group_id: str) -> list[str]:
        return await self._request("list_group_members", group_id=group_id)

    async def map_idp_group(
        self, provider: str, claim_value: str, group_id: str
    ) -> dict[str, Any]:
        return await self._request(
            "map_idp_group",
            provider=provider,
            claim_value=claim_value,
            group_id=group_id,
        )

    async def unmap_idp_group(
        self, provider: str, claim_value: str, group_id: str
    ) -> bool:
        return await self._request(
            "unmap_idp_group",
            provider=provider,
            claim_value=claim_value,
            group_id=group_id,
        )

    async def list_idp_group_mappings(self, group_id: str) -> list[dict[str, Any]]:
        return await self._request("list_idp_group_mappings", group_id=group_id)

    # -- policies and attachments ------------------------------------------------------

    async def create_policy(
        self,
        name: str,
        document: Mapping[str, Any] | str,
        *,
        description: str = "",
        scope: str | None = None,
    ) -> dict[str, Any]:
        """A policy owned by ``scope`` (the platform when None); an org's or a
        workspace's names only ``${scope}:`` resources."""
        return _policy(
            await self._request(
                "create_policy",
                name=name,
                document_json=_document(document),
                description=description,
                scope=scope,
            )
        )

    async def get_policy(self, policy_id: str) -> dict[str, Any]:
        return _policy(await self._request("get_policy", policy_id=policy_id))

    async def list_policies(
        self, *, limit: int = 100, after: str | None = None, scope: str | None = None
    ) -> dict[str, Any]:
        page = await self._request(
            "list_policies", limit=limit, after=after, scope=scope
        )
        return {**page, "policies": [_policy(p) for p in page["policies"]]}

    async def update_policy(
        self,
        policy_id: str,
        *,
        expected_revision: int,
        document: Mapping[str, Any] | str | None = None,
        name: str | None = None,
        description: str | None = None,
    ) -> dict[str, Any]:
        return _policy(
            await self._request(
                "update_policy",
                policy_id=policy_id,
                expected_revision=expected_revision,
                document_json=_document(document) if document is not None else None,
                name=name,
                description=description,
            )
        )

    async def delete_policy(self, policy_id: str) -> None:
        await self._request("delete_policy", policy_id=policy_id)

    async def attach_policy(
        self, policy_id: str, principal_id: str, scope: str | None = None
    ) -> dict[str, Any]:
        return await self._request(
            "attach_policy", policy_id=policy_id, principal_id=principal_id, scope=scope
        )

    async def detach_policy(
        self, policy_id: str, principal_id: str, scope: str | None = None
    ) -> bool:
        return await self._request(
            "detach_policy", policy_id=policy_id, principal_id=principal_id, scope=scope
        )

    async def list_attachments(
        self, *, principal_id: str | None = None, policy_id: str | None = None
    ) -> list[dict[str, Any]]:
        return await self._request(
            "list_attachments", principal_id=principal_id, policy_id=policy_id
        )

    # -- invitations and IdP group bindings ----------------------------------------------

    async def create_pending_grant(
        self, provider: str, email: str, policy_id: str, scope: str | None = None
    ) -> dict[str, Any]:
        """Attach a policy at a scope to whoever first signs in through
        ``provider`` with ``email`` verified."""
        return await self._request(
            "create_pending_grant",
            provider=provider,
            email=email,
            policy_id=policy_id,
            scope=scope,
        )

    async def list_pending_grants(
        self,
        *,
        provider: str | None = None,
        email: str | None = None,
        policy_id: str | None = None,
    ) -> list[dict[str, Any]]:
        return await self._request(
            "list_pending_grants", provider=provider, email=email, policy_id=policy_id
        )

    async def revoke_pending_grant(self, grant_id: str) -> bool:
        return await self._request("revoke_pending_grant", grant_id=grant_id)

    async def claim_pending_grants(self, principal_id: str) -> list[dict[str, Any]]:
        return await self._request("claim_pending_grants", principal_id=principal_id)

    async def bind_idp_group(
        self, provider: str, claim_value: str, policy_id: str, scope: str | None = None
    ) -> dict[str, Any]:
        """Give the members of ``provider``'s group ``claim_value`` a policy at
        a scope."""
        return await self._request(
            "bind_idp_group",
            provider=provider,
            claim_value=claim_value,
            policy_id=policy_id,
            scope=scope,
        )

    async def unbind_idp_group(
        self, provider: str, claim_value: str, policy_id: str, scope: str | None = None
    ) -> bool:
        return await self._request(
            "unbind_idp_group",
            provider=provider,
            claim_value=claim_value,
            policy_id=policy_id,
            scope=scope,
        )

    async def list_idp_bindings(
        self, *, provider: str | None = None, policy_id: str | None = None
    ) -> list[dict[str, Any]]:
        return await self._request(
            "list_idp_bindings", provider=provider, policy_id=policy_id
        )

    # -- placements, scopes, catalogs -------------------------------------------------

    async def put_placement(
        self, service: str, id_key: str, org: str = "-", workspace: str = "-"
    ) -> dict[str, Any]:
        return await self._request(
            "put_placement",
            placement={
                "service": service,
                "id_key": id_key,
                "org": org,
                "workspace": workspace,
            },
        )

    async def delete_placement(self, service: str, id_key: str) -> bool:
        return await self._request("delete_placement", service=service, id_key=id_key)

    async def list_placements(self, service: str | None = None) -> list[dict[str, Any]]:
        return await self._request("list_placements", service=service)

    async def put_scope(self, org: str, workspace: str = "-") -> dict[str, Any]:
        return await self._request("put_scope", org=org, workspace=workspace)

    async def delete_scope(self, org: str, workspace: str = "-") -> bool:
        return await self._request("delete_scope", org=org, workspace=workspace)

    # -- sets: what an org or a workspace may use ----------------------------
    # A set is {"org", "workspace", "modules", "features"}; a part that is None
    # is everything (nothing recorded), a list the items.

    async def get_set(self, org: str, workspace: str = "-") -> dict[str, Any]:
        return await self._request("get_set", org=org, workspace=workspace)

    async def effective_set(self, org: str, workspace: str = "-") -> dict[str, Any]:
        """A workspace's set within its org's (an org's own for ``-``)."""
        return await self._request("effective_set", org=org, workspace=workspace)

    async def list_sets(self, org: str | None = None) -> list[dict[str, Any]]:
        return await self._request("list_sets", org=org)

    async def put_set(
        self,
        org: str,
        workspace: str = "-",
        *,
        modules: Iterable[str] | None = None,
        features: Iterable[str] | None = None,
    ) -> dict[str, Any]:
        """Record a set: an org's needs the platform admin, a workspace's the
        org's owners or admins; a workspace's set wider than its org's is
        refused (``InvalidArgument``) naming the extra items."""
        return await self._request(
            "put_set",
            org=org,
            workspace=workspace,
            modules=None if modules is None else {"items": list(modules)},
            features=None if features is None else {"items": list(features)},
        )

    async def register_catalog(self, catalog: Mapping[str, Any]) -> bool:
        """Register a service's action catalog (a catalog document, as a mapping)."""
        return await self._request("register_catalog", catalog=dict(catalog))

    # -- tokens, service accounts, keys and manifests ---------------------

    async def token(self, key: str) -> dict[str, Any]:
        """A service key for an access token. Transports exchange their own key
        themselves (``naas_abi_sdk.credentials``): this is for tooling."""
        return await self._request("token", key=key)

    async def jwks(self) -> dict[str, Any]:
        """The engine's public signing keys and their issuer."""
        return json.loads(await self._request("jwks"))

    async def exchange_token(
        self,
        subject_token: str,
        subject_token_type: str,
        audience: str,
        *,
        resource: str = "",
        scope: list[Mapping[str, Any]] | None = None,
        groups: list[str] | None = None,
        session_id: str = "",
    ) -> dict[str, Any]:
        """RFC 8693 token exchange: the caller needs
        ``iam:ExchangeToken`` on ``audience``. ``{"access_token": ...,
        "expires_in": ..., ...}``. A module renews the delegation it holds with
        its own token: ``subject_token_type`` the ``jwt`` type and ``audience``
        ``abi:delegated:agent``."""
        return await self._request(
            "exchange_token",
            grant_type="urn:ietf:params:oauth:grant-type:token-exchange",
            subject_token=subject_token,
            subject_token_type=subject_token_type,
            audience=audience,
            resource=resource,
            scope_json=json.dumps(scope) if scope is not None else None,
            groups=groups or [],
            session_id=session_id,
        )

    async def revoke_tokens(
        self, principal_id: str, *, include_keys: bool = False
    ) -> None:
        """Cut off every token issued so far to or for ``principal_id``."""
        await self._request(
            "revoke_tokens", principal_id=principal_id, include_keys=include_keys
        )

    async def find_service_account(self, name: str) -> dict[str, Any]:
        return await self._request("find_service_account", name=name)

    async def create_key(
        self,
        principal_id: str,
        *,
        description: str = "",
        kind: str = "",
        audience: str = "",
        resource: str = "",
        scope: list[Mapping[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """``{"key": {...}, "value": "abi_sk_..."}``: the value is shown once.

        For a user's key (``abi_pk_``, or ``kind="grant"`` for a link
        ``abi_gk_``): ``audience``, the ``resource`` it is bound to and its
        ``scope`` (Allow statements, the token's ``abi_scope``)."""
        return await self._request(
            "create_key",
            principal_id=principal_id,
            description=description,
            kind=kind,
            audience=audience,
            resource=resource,
            scope_json=json.dumps(scope) if scope is not None else None,
        )

    async def list_keys(self, principal_id: str) -> list[dict[str, Any]]:
        return await self._request("list_keys", principal_id=principal_id)

    async def revoke_key(self, principal_id: str, key_id: str) -> dict[str, Any]:
        return await self._request(
            "revoke_key", principal_id=principal_id, key_id=key_id
        )

    async def submit_manifest(
        self, module_id: str, project: str, document: Mapping[str, Any] | str
    ) -> dict[str, Any]:
        """This module's permission manifest (``run_module`` submits it)."""
        return await self._request(
            "submit_manifest",
            module_id=module_id,
            project=project,
            document_json=_document(document),
        )

    async def get_manifest(
        self, principal_id: str, sha256: str | None = None
    ) -> dict[str, Any]:
        return await self._request(
            "get_manifest", principal_id=principal_id, sha256=sha256
        )

    async def list_manifests(
        self, *, principal_id: str | None = None, status: str | None = None
    ) -> list[dict[str, Any]]:
        return await self._request(
            "list_manifests", principal_id=principal_id, status=status
        )

    async def approve_manifest(
        self,
        principal_id: str,
        sha256: str | None = None,
        *,
        document: Mapping[str, Any] | str | None = None,
    ) -> dict[str, Any]:
        return await self._request(
            "approve_manifest",
            principal_id=principal_id,
            sha256=sha256,
            document_json=_document(document) if document is not None else None,
        )

    async def reject_manifest(
        self, principal_id: str, sha256: str | None = None, *, reason: str = ""
    ) -> dict[str, Any]:
        return await self._request(
            "reject_manifest", principal_id=principal_id, sha256=sha256, reason=reason
        )
