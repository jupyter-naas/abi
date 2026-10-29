"""IAM over NATS for engines in the client role: the serving engine's IAM.

Implements ``IIAMService``, so a client engine's ``services.iam`` behaves like
the serving engine's. Decisions are about the caller the server verifies: this
client's identity, and the current call's user when that identity may name one
(``NatsRPCClient._on_behalf_of``). Calls are never replayed after a failure.
"""

from __future__ import annotations

import json
import time
from collections.abc import Iterable, Mapping, Sequence
from datetime import datetime
from typing import Any

from naas_abi_core.engine.nats_auth import IssuedToken
from naas_abi_core.engine.nats_rpc import NatsRPCClient
from naas_abi_core.services.iam.adapters import iam_nats_codec as codec
from naas_abi_core.services.iam.catalog import ActionCatalog
from naas_abi_core.services.iam.IAMPorts import (
    GRANT_TYPE_TOKEN_EXCHANGE,
    Attachment,
    ContainerRecord,
    CreatedKey,
    Decision,
    Explanation,
    FilterResult,
    GrantableCatalog,
    GroupMapping,
    IdpBinding,
    IIAMService,
    KeyKind,
    KeyRecord,
    ManifestRecord,
    ManifestStatus,
    ManifestSubmission,
    Page,
    PendingGrant,
    Placement,
    Policy,
    PrincipalKind,
    PrincipalRecord,
    TokenExchange,
)
from naas_abi_core.services.iam.listing import ResourcePage
from naas_abi_core.services.iam.names import PLATFORM_SCOPE
from naas_abi_core.services.iam.policy import PolicyDocument
from naas_abi_proto.iam.v1 import iam_pb2 as pb


def _document_text(document: Any) -> str:
    if isinstance(document, PolicyDocument):
        return document.to_json()
    if isinstance(document, Mapping):
        return json.dumps(document)
    return str(document)


class IAMSecondaryAdapterNATSClient(NatsRPCClient, IIAMService):
    def _request(
        self, operation: str, *, _subject_refusal: bool = False, **fields: Any
    ) -> Any:
        name = codec.OPERATIONS[operation]
        request = getattr(pb, f"{name}Request")(context=self._context(), **fields)
        response = self._call(
            f"{codec.SUBJECT_PREFIX}.{operation}",
            request,
            getattr(pb, f"{name}Response"),
        )
        if response.HasField("error") and response.error.code:
            codec.raise_for(response.error, subject_refusal=_subject_refusal)
        return response

    # -- decisions ------------------------------------------------------------------

    def authorize(self, action: str, resource: str) -> Decision:
        response = self._request("authorize", action=action, resource=resource)
        return codec.decision_from_pb(response.decision)

    def authorize_declared(
        self,
        action: str,
        resource_type: str,
        parts: Sequence[str],
        *,
        container: str | None = None,
    ) -> tuple[Decision, str]:
        response = self._request(
            "authorize_declared",
            action=action,
            resource_type=resource_type,
            parts=list(parts),
            container=container or "",
        )
        return codec.decision_from_pb(response.decision), response.resource

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

    def grantable(self, scope: str) -> list[GrantableCatalog]:
        response = self._request("grantable", scope=scope)
        return [codec.grantable_from_pb(c) for c in response.catalogs]

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
    ) -> ResourcePage:
        response = self._request(
            "list_resources",
            service=service,
            type=type,
            scope=scope,
            text=text,
            cursor=cursor or "",
            limit=limit or 0,
            module=module,
        )
        return codec.resource_page_from_pb(response)

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

    def create_group(self, name: str, *, scope: str | None = None) -> PrincipalRecord:
        return codec.principal_from_pb(
            self._request("create_group", name=name, scope=scope).group
        )

    def get_group(self, group_id: str) -> PrincipalRecord:
        return codec.principal_from_pb(
            self._request("get_group", group_id=group_id).group
        )

    def list_groups(
        self, *, limit: int = 100, after: str | None = None, scope: str | None = None
    ) -> Page:
        response = self._request("list_groups", limit=limit, after=after, scope=scope)
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
        self,
        name: str,
        document: Any,
        *,
        description: str = "",
        scope: str | None = None,
        parent: str | None = None,
    ) -> Policy:
        response = self._request(
            "create_policy",
            name=name,
            document_json=_document_text(document),
            description=description,
            scope=scope,
            parent=parent,
        )
        return codec.policy_from_pb(response.policy)

    def get_policy(self, policy_id: str) -> Policy:
        return codec.policy_from_pb(
            self._request("get_policy", policy_id=policy_id).policy
        )

    def list_policies(
        self, *, limit: int = 100, after: str | None = None, scope: str | None = None
    ) -> Page:
        response = self._request("list_policies", limit=limit, after=after, scope=scope)
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
        parent: str | None = None,
    ) -> Policy:
        response = self._request(
            "update_policy",
            policy_id=policy_id,
            expected_revision=expected_revision,
            document_json=_document_text(document) if document is not None else None,
            name=name,
            description=description,
            parent=parent,
        )
        return codec.policy_from_pb(response.policy)

    def list_sub_policies(self, policy_id: str) -> list[Policy]:
        response = self._request("list_sub_policies", policy_id=policy_id)
        return [codec.policy_from_pb(p) for p in response.policies]

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

    # -- invitations and IdP group bindings ------------------------------------------------

    def create_pending_grant(
        self, provider: str, email: str, policy_id: str, scope: str | None = None
    ) -> PendingGrant:
        response = self._request(
            "create_pending_grant",
            provider=provider,
            email=email,
            policy_id=policy_id,
            scope=scope,
        )
        return codec.pending_grant_from_pb(response.grant)

    def list_pending_grants(
        self,
        *,
        provider: str | None = None,
        email: str | None = None,
        policy_id: str | None = None,
    ) -> list[PendingGrant]:
        response = self._request(
            "list_pending_grants", provider=provider, email=email, policy_id=policy_id
        )
        return [codec.pending_grant_from_pb(g) for g in response.grants]

    def revoke_pending_grant(self, grant_id: str) -> bool:
        return self._request("revoke_pending_grant", grant_id=grant_id).revoked

    def claim_pending_grants(self, principal_id: str) -> list[Attachment]:
        response = self._request("claim_pending_grants", principal_id=principal_id)
        return [codec.attachment_from_pb(a) for a in response.attachments]

    def bind_idp_group(
        self, provider: str, claim_value: str, policy_id: str, scope: str | None = None
    ) -> IdpBinding:
        response = self._request(
            "bind_idp_group",
            provider=provider,
            claim_value=claim_value,
            policy_id=policy_id,
            scope=scope,
        )
        return codec.binding_from_pb(response.binding)

    def unbind_idp_group(
        self, provider: str, claim_value: str, policy_id: str, scope: str | None = None
    ) -> bool:
        return self._request(
            "unbind_idp_group",
            provider=provider,
            claim_value=claim_value,
            policy_id=policy_id,
            scope=scope,
        ).removed

    def list_idp_bindings(
        self, *, provider: str | None = None, policy_id: str | None = None
    ) -> list[IdpBinding]:
        response = self._request(
            "list_idp_bindings", provider=provider, policy_id=policy_id
        )
        return [codec.binding_from_pb(b) for b in response.bindings]

    # -- placements, scopes, catalogs -----------------------------------------------------

    def put_placement(
        self, service: str, id_key: str, container: str = PLATFORM_SCOPE
    ) -> Placement:
        response = self._request(
            "put_placement",
            placement=codec.placement_to_pb(Placement(service, id_key, container)),
        )
        return codec.placement_from_pb(response.placement)

    def delete_placement(self, service: str, id_key: str) -> bool:
        return self._request("delete_placement", service=service, id_key=id_key).deleted

    def list_placements(self, service: str | None = None) -> list[Placement]:
        response = self._request("list_placements", service=service)
        return [codec.placement_from_pb(p) for p in response.placements]

    def placement_of(self, service: str, canonical_id: str) -> Placement | None:
        raise NotImplementedError(
            "Placements are resolved by the service owning the resource, on the "
            "serving engine, never through a NATS facade"
        )

    def register_container(
        self, service: str, type: str, id: str, *, parent: str = PLATFORM_SCOPE
    ) -> ContainerRecord:
        response = self._request(
            "register_container", service=service, type=type, id=id, parent=parent
        )
        return codec.container_from_pb(response.container)

    def delete_container(self, service: str, type: str, id: str) -> bool:
        return self._request(
            "delete_container", service=service, type=type, id=id
        ).deleted

    def container(self, service: str, type: str, id: str) -> str | None:
        return (
            self._request("get_container", service=service, type=type, id=id).name
            or None
        )

    def register_catalog(self, catalog: Any) -> bool:
        if not isinstance(catalog, ActionCatalog):
            catalog = ActionCatalog.from_dict(catalog)
        response = self._request(
            "register_catalog", catalog=codec.catalog_to_pb(catalog)
        )
        return response.registered

    # -- service accounts, keys and manifests ----------------------------------------------

    def find_service_account(self, name: str) -> PrincipalRecord:
        response = self._request("find_service_account", name=name)
        return codec.principal_from_pb(response.principal)

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
        request = pb.CreateKeyRequest(
            context=self._context(),
            principal_id=principal_id,
            description=description,
            kind=kind or "",
            audience=audience or "",
            resource=resource or "",
            scope_json=codec.scope_to_json(scope),
        )
        if expires_at is not None:
            request.expires_at.FromDatetime(expires_at)
        response = self._call(
            f"{codec.SUBJECT_PREFIX}.create_key", request, pb.CreateKeyResponse
        )
        if response.HasField("error") and response.error.code:
            codec.raise_for(response.error)
        return CreatedKey(codec.key_from_pb(response.key), response.value)

    def list_keys(self, principal_id: str) -> list[KeyRecord]:
        response = self._request("list_keys", principal_id=principal_id)
        return [codec.key_from_pb(k) for k in response.keys]

    def revoke_key(self, principal_id: str, key_id: str) -> KeyRecord:
        response = self._request("revoke_key", principal_id=principal_id, key_id=key_id)
        return codec.key_from_pb(response.key)

    def submit_manifest(
        self, module_id: str, project: str, document: Any
    ) -> ManifestSubmission:
        response = self._request(
            "submit_manifest",
            module_id=module_id,
            project=project,
            document_json=_document_text(document),
        )
        return ManifestSubmission(
            codec.manifest_from_pb(response.manifest),
            response.approved_now,
            response.in_force,
        )

    def get_manifest(
        self, principal_id: str, sha256: str | None = None
    ) -> ManifestRecord:
        response = self._request(
            "get_manifest", principal_id=principal_id, sha256=sha256
        )
        return codec.manifest_from_pb(response.manifest)

    def list_manifests(
        self, *, principal_id: str | None = None, status: ManifestStatus | None = None
    ) -> list[ManifestRecord]:
        response = self._request(
            "list_manifests", principal_id=principal_id, status=status
        )
        return [codec.manifest_from_pb(m) for m in response.manifests]

    def approve_manifest(
        self, principal_id: str, sha256: str | None = None, *, document: Any = None
    ) -> ManifestRecord:
        response = self._request(
            "approve_manifest",
            principal_id=principal_id,
            sha256=sha256,
            document_json=_document_text(document) if document is not None else None,
        )
        return codec.manifest_from_pb(response.manifest)

    def reject_manifest(
        self, principal_id: str, sha256: str | None = None, *, reason: str = ""
    ) -> ManifestRecord:
        response = self._request(
            "reject_manifest", principal_id=principal_id, sha256=sha256, reason=reason
        )
        return codec.manifest_from_pb(response.manifest)

    def exchange_token(self, request: TokenExchange) -> IssuedToken:
        response = self._request(
            "exchange_token",
            _subject_refusal=True,
            grant_type=GRANT_TYPE_TOKEN_EXCHANGE,
            subject_token=request.subject_token,
            subject_token_type=request.subject_token_type,
            audience=request.audience,
            resource=request.resource or "",
            scope_json=codec.scope_to_json(request.scope),
            groups=list(request.groups),
            session_id=request.session_id or "",
            ttl_seconds=request.ttl_seconds or 0,
        )
        return IssuedToken(
            response.access_token,
            time.time() + response.expires_in,
            response.principal_id,
            "",
            response.audience,
        )

    def revoke_tokens(self, principal_id: str, *, include_keys: bool = False) -> None:
        self._request(
            "revoke_tokens", principal_id=principal_id, include_keys=include_keys
        )

    def jwks(self) -> dict[str, Any]:
        return json.loads(self._request("jwks").jwks_json)
