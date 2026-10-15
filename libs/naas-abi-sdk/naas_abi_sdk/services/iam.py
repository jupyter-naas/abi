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
        raise not_found() if not_found else NotFound("NOT_FOUND", f"{resource} not found")

    async def filter(self, action: str, resources: Iterable[str]) -> FilterResult:
        result = await self._request(
            "filter", action=action, resources=list(resources)
        )
        return FilterResult(list(result["allowed"]), list(result["prefix_hints"]))

    async def explain(
        self, action: str, resource: str, *, principal_id: str | None = None
    ) -> dict[str, Any]:
        return await self._request(
            "explain", action=action, resource=resource, principal_id=principal_id
        )

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
        return await self._request("create_service_account", name=name, owner_id=owner_id)

    async def get_principal(self, principal_id: str) -> dict[str, Any]:
        return await self._request("get_principal", principal_id=principal_id)

    async def list_principals(
        self, kind: str | None = None, *, limit: int = 100, after: str | None = None
    ) -> dict[str, Any]:
        """``{"principals": [...], "next_after": ...}``."""
        return await self._request("list_principals", kind=kind, limit=limit, after=after)

    async def suspend_principal(self, principal_id: str) -> dict[str, Any]:
        return await self._request("suspend_principal", principal_id=principal_id)

    async def resume_principal(self, principal_id: str) -> dict[str, Any]:
        return await self._request("resume_principal", principal_id=principal_id)

    async def delete_principal(self, principal_id: str) -> dict[str, Any]:
        return await self._request("delete_principal", principal_id=principal_id)

    # -- groups ---------------------------------------------------------------------

    async def create_group(self, name: str, *, org: str | None = None) -> dict[str, Any]:
        return await self._request("create_group", name=name, org=org)

    async def get_group(self, group_id: str) -> dict[str, Any]:
        return await self._request("get_group", group_id=group_id)

    async def list_groups(
        self, *, limit: int = 100, after: str | None = None
    ) -> dict[str, Any]:
        return await self._request("list_groups", limit=limit, after=after)

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
            "map_idp_group", provider=provider, claim_value=claim_value, group_id=group_id
        )

    async def unmap_idp_group(self, provider: str, claim_value: str, group_id: str) -> bool:
        return await self._request(
            "unmap_idp_group",
            provider=provider,
            claim_value=claim_value,
            group_id=group_id,
        )

    # -- policies and attachments ------------------------------------------------------

    async def create_policy(
        self, name: str, document: Mapping[str, Any] | str, *, description: str = ""
    ) -> dict[str, Any]:
        return _policy(
            await self._request(
                "create_policy",
                name=name,
                document_json=_document(document),
                description=description,
            )
        )

    async def get_policy(self, policy_id: str) -> dict[str, Any]:
        return _policy(await self._request("get_policy", policy_id=policy_id))

    async def list_policies(
        self, *, limit: int = 100, after: str | None = None
    ) -> dict[str, Any]:
        page = await self._request("list_policies", limit=limit, after=after)
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

    async def put_scope(self, org: str, workspace: str = "-") -> dict[str, Any]:
        return await self._request("put_scope", org=org, workspace=workspace)

    async def register_catalog(self, catalog: Mapping[str, Any]) -> bool:
        """Register a service's action catalog (RFC §6.2 format, as a mapping)."""
        return await self._request("register_catalog", catalog=dict(catalog))
