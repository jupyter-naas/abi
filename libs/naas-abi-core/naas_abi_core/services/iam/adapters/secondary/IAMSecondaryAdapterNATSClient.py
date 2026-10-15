"""IAM over NATS for engines in the client role: the serving engine's IAM.

Implements ``IIAMService``, so a client engine's ``services.iam`` behaves like
the serving engine's. Decisions are about the caller the server verifies: this
client's identity, and the current call's user when that identity may name one
(``NatsRPCClient._on_behalf_of``). Calls are never replayed after a failure.
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Mapping
from typing import Any

from naas_abi_core.engine.nats_rpc import NatsRPCClient
from naas_abi_core.services.iam.adapters import iam_nats_codec as codec
from naas_abi_core.services.iam.catalog import ActionCatalog
from naas_abi_core.services.iam.IAMPorts import (
    Attachment,
    Decision,
    Explanation,
    FilterResult,
    GroupMapping,
    IIAMService,
    Page,
    Placement,
    Policy,
    PrincipalKind,
    PrincipalRecord,
    ScopeRecord,
)
from naas_abi_core.services.iam.policy import PolicyDocument
from naas_abi_proto.iam.v1 import iam_pb2 as pb


def _document_text(document: Any) -> str:
    if isinstance(document, PolicyDocument):
        return document.to_json()
    if isinstance(document, Mapping):
        return json.dumps(document)
    return str(document)


class IAMSecondaryAdapterNATSClient(NatsRPCClient, IIAMService):
    def _request(self, operation: str, **fields: Any) -> Any:
        name = codec.OPERATIONS[operation]
        request = getattr(pb, f"{name}Request")(context=self._context(), **fields)
        response = self._call(
            f"{codec.SUBJECT_PREFIX}.{operation}",
            request,
            getattr(pb, f"{name}Response"),
        )
        if response.HasField("error") and response.error.code:
            codec.raise_for(response.error)
        return response

    # -- decisions ------------------------------------------------------------------

    def authorize(self, action: str, resource: str) -> Decision:
        response = self._request("authorize", action=action, resource=resource)
        return codec.decision_from_pb(response.decision)

    def filter(self, action: str, resources: Iterable[str]) -> FilterResult:
        response = self._request("filter", action=action, resources=list(resources))
        return FilterResult(list(response.allowed), list(response.prefix_hints))

    def explain(
        self, action: str, resource: str, *, principal_id: str | None = None
    ) -> Explanation:
        response = self._request(
            "explain", action=action, resource=resource, principal_id=principal_id
        )
        return codec.explanation_from_pb(response.explanation)

    # -- principals ---------------------------------------------------------------------

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
        response = self._request(
            "ensure_user",
            issuer=issuer,
            subject=subject,
            provider=provider,
            email=email,
            email_verified=email_verified,
            display_name=display_name,
        )
        return codec.principal_from_pb(response.principal)

    def create_service_account(
        self, name: str, *, owner_id: str | None = None
    ) -> PrincipalRecord:
        response = self._request("create_service_account", name=name, owner_id=owner_id)
        return codec.principal_from_pb(response.principal)

    def get_principal(self, principal_id: str) -> PrincipalRecord:
        response = self._request("get_principal", principal_id=principal_id)
        return codec.principal_from_pb(response.principal)

    def list_principals(
        self,
        kind: PrincipalKind | None = None,
        *,
        limit: int = 100,
        after: str | None = None,
    ) -> Page:
        response = self._request("list_principals", kind=kind, limit=limit, after=after)
        return Page(
            [codec.principal_from_pb(p) for p in response.principals],
            response.next_after if response.HasField("next_after") else None,
        )

    def suspend_principal(self, principal_id: str) -> PrincipalRecord:
        response = self._request("suspend_principal", principal_id=principal_id)
        return codec.principal_from_pb(response.principal)

    def resume_principal(self, principal_id: str) -> PrincipalRecord:
        response = self._request("resume_principal", principal_id=principal_id)
        return codec.principal_from_pb(response.principal)

    def delete_principal(self, principal_id: str) -> PrincipalRecord:
        response = self._request("delete_principal", principal_id=principal_id)
        return codec.principal_from_pb(response.principal)

    # -- groups -------------------------------------------------------------------------

    def create_group(self, name: str, *, org: str | None = None) -> PrincipalRecord:
        return codec.principal_from_pb(
            self._request("create_group", name=name, org=org).group
        )

    def get_group(self, group_id: str) -> PrincipalRecord:
        return codec.principal_from_pb(
            self._request("get_group", group_id=group_id).group
        )

    def list_groups(self, *, limit: int = 100, after: str | None = None) -> Page:
        response = self._request("list_groups", limit=limit, after=after)
        return Page(
            [codec.principal_from_pb(g) for g in response.groups],
            response.next_after if response.HasField("next_after") else None,
        )

    def delete_group(self, group_id: str) -> PrincipalRecord:
        return codec.principal_from_pb(
            self._request("delete_group", group_id=group_id).group
        )

    def add_group_member(self, group_id: str, member_id: str) -> None:
        self._request("add_group_member", group_id=group_id, member_id=member_id)

    def remove_group_member(self, group_id: str, member_id: str) -> bool:
        return self._request(
            "remove_group_member", group_id=group_id, member_id=member_id
        ).removed

    def list_group_members(self, group_id: str) -> list[str]:
        return list(self._request("list_group_members", group_id=group_id).member_ids)

    def map_idp_group(
        self, provider: str, claim_value: str, group_id: str
    ) -> GroupMapping:
        response = self._request(
            "map_idp_group",
            provider=provider,
            claim_value=claim_value,
            group_id=group_id,
        )
        return codec.mapping_from_pb(response.mapping)

    def unmap_idp_group(self, provider: str, claim_value: str, group_id: str) -> bool:
        return self._request(
            "unmap_idp_group",
            provider=provider,
            claim_value=claim_value,
            group_id=group_id,
        ).removed

    def list_idp_group_mappings(self, group_id: str) -> list[GroupMapping]:
        response = self._request("list_idp_group_mappings", group_id=group_id)
        return [codec.mapping_from_pb(m) for m in response.mappings]

    # -- policies and attachments -----------------------------------------------------

    def create_policy(
        self, name: str, document: Any, *, description: str = ""
    ) -> Policy:
        response = self._request(
            "create_policy",
            name=name,
            document_json=_document_text(document),
            description=description,
        )
        return codec.policy_from_pb(response.policy)

    def get_policy(self, policy_id: str) -> Policy:
        return codec.policy_from_pb(
            self._request("get_policy", policy_id=policy_id).policy
        )

    def list_policies(self, *, limit: int = 100, after: str | None = None) -> Page:
        response = self._request("list_policies", limit=limit, after=after)
        return Page(
            [codec.policy_from_pb(p) for p in response.policies],
            response.next_after if response.HasField("next_after") else None,
        )

    def update_policy(
        self,
        policy_id: str,
        *,
        expected_revision: int,
        document: Any = None,
        name: str | None = None,
        description: str | None = None,
    ) -> Policy:
        response = self._request(
            "update_policy",
            policy_id=policy_id,
            expected_revision=expected_revision,
            document_json=_document_text(document) if document is not None else None,
            name=name,
            description=description,
        )
        return codec.policy_from_pb(response.policy)

    def delete_policy(self, policy_id: str) -> None:
        self._request("delete_policy", policy_id=policy_id)

    def attach_policy(
        self, policy_id: str, principal_id: str, scope: str | None = None
    ) -> Attachment:
        response = self._request(
            "attach_policy", policy_id=policy_id, principal_id=principal_id, scope=scope
        )
        return codec.attachment_from_pb(response.attachment)

    def detach_policy(
        self, policy_id: str, principal_id: str, scope: str | None = None
    ) -> bool:
        return self._request(
            "detach_policy", policy_id=policy_id, principal_id=principal_id, scope=scope
        ).detached

    def list_attachments(
        self, *, principal_id: str | None = None, policy_id: str | None = None
    ) -> list[Attachment]:
        response = self._request(
            "list_attachments", principal_id=principal_id, policy_id=policy_id
        )
        return [codec.attachment_from_pb(a) for a in response.attachments]

    # -- placements, scopes, catalogs -----------------------------------------------------

    def put_placement(
        self, service: str, id_key: str, org: str = "-", workspace: str = "-"
    ) -> Placement:
        response = self._request(
            "put_placement",
            placement=codec.placement_to_pb(Placement(service, id_key, org, workspace)),
        )
        return codec.placement_from_pb(response.placement)

    def delete_placement(self, service: str, id_key: str) -> bool:
        return self._request("delete_placement", service=service, id_key=id_key).deleted

    def list_placements(self, service: str | None = None) -> list[Placement]:
        response = self._request("list_placements", service=service)
        return [codec.placement_from_pb(p) for p in response.placements]

    def put_scope(self, org: str, workspace: str = "-") -> ScopeRecord:
        response = self._request("put_scope", org=org, workspace=workspace)
        return codec.scope_from_pb(response.scope)

    def delete_scope(self, org: str, workspace: str = "-") -> bool:
        return self._request("delete_scope", org=org, workspace=workspace).deleted

    def register_catalog(self, catalog: Any) -> bool:
        if not isinstance(catalog, ActionCatalog):
            catalog = ActionCatalog.from_dict(catalog)
        response = self._request(
            "register_catalog", catalog=codec.catalog_to_pb(catalog)
        )
        return response.registered
