"""IAM over NATS: ``abi.iam.v1.<operation>`` (proto ``iam/v1``).

Each request runs under the ``CallContext`` built from its verified
credentials (``nats_rpc.authenticate_request``), so ``authorize`` and
``filter`` answer for the caller, and every other operation is authorized
with IAM's own ``iam:*`` catalog inside ``IAMService``, never here.

After every change it publishes ``abi.iam.v1.changed`` (a ``ChangeEvent``
with the store revision), so remote caches can drop their entries. It hears
the same subject too: a change written to the store by another process (the
``abi iam`` CLI) drops this process's cache at once.

``abi.iam.v1.token`` and ``abi.iam.v1.jwks`` need no credentials: the key is
one, and the JWKS is public.
"""

from __future__ import annotations

import asyncio
import json
from datetime import UTC
from functools import partial
from typing import Any

import nats
from google.protobuf.message import DecodeError
from naas_abi_core import logger
from naas_abi_core.engine.call_context import ANONYMOUS, CallContext
from naas_abi_core.engine.nats_auth import NATS_AUDIENCE, TokenVerifier
from naas_abi_core.engine.nats_dispatch import DomainRPCDispatcher
from naas_abi_core.engine.nats_rpc import (
    RequestPayloadError,
    authenticate_request,
    request_payload,
    respond_protobuf,
)
from naas_abi_core.engine.nats_sessions import ServicePrimary
from naas_abi_core.engine.nats_tracing import TracedService, add_traced_service
from naas_abi_core.services.iam.adapters import iam_nats_codec as codec
from naas_abi_core.services.iam.IAMPorts import (
    GRANT_TYPE_TOKEN_EXCHANGE,
    TOKEN_TYPE_JWT,
    TokenExchange,
)
from naas_abi_core.services.iam.IAMService import IAMService
from naas_abi_proto.common.v1 import common_pb2
from naas_abi_proto.iam.v1 import iam_pb2 as pb


def _opt(message: Any, field: str) -> Any:
    return getattr(message, field) if message.HasField(field) else None


class IAMPrimaryAdapterNATS(ServicePrimary):
    def __init__(self, service: IAMService, verifier: TokenVerifier) -> None:
        self._iam = service
        self._verifier = verifier
        self._dispatch = DomainRPCDispatcher(codec.SERVICE_NAME)
        self._service: TracedService | None = None
        self._nc: nats.NATS | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._changes: Any = None

    async def start(self, nc: nats.NATS) -> None:
        if self._service is not None:
            return
        service = await add_traced_service(
            nc,
            name=codec.SERVICE_NAME,
            version=codec.SERVICE_VERSION,
            description="ABI kernel IAM, exposed over NATS RPC (v1).",
        )
        for operation in codec.OPERATIONS:
            await service.add_endpoint(
                name=operation,
                subject=f"{codec.SUBJECT_PREFIX}.{operation}",
                handler=partial(self._handle, operation=operation),
            )
        self._service = service
        self._nc = nc
        self._loop = asyncio.get_running_loop()
        self._iam.add_change_listener(self._publish_change)
        self._changes = await nc.subscribe(codec.CHANGED_SUBJECT, cb=self._heard_change)

    async def stop(self) -> None:
        self._iam.remove_change_listener(self._publish_change)
        if self._changes is not None:
            await self._changes.unsubscribe()
            self._changes = None
        service, self._service = self._service, None
        try:
            if service is not None:
                await service.stop()
        finally:
            self._dispatch.close()

    def _publish_change(self, revision: int) -> None:
        """Called from the writing thread: hand the publish to the NATS loop."""
        nc, loop = self._nc, self._loop
        if nc is None or loop is None or loop.is_closed() or nc.is_closed:
            return
        payload = pb.ChangeEvent(revision=revision).SerializeToString()
        asyncio.run_coroutine_threadsafe(
            nc.publish(codec.CHANGED_SUBJECT, payload), loop
        )

    async def _heard_change(self, msg: Any) -> None:
        """Another process changed the store: drop what this one cached."""
        try:
            pb.ChangeEvent.FromString(msg.data)
        except DecodeError:
            return
        # The notice's revision is never trusted (a forged or huge one would
        # stop invalidation): the store's is read, and compared with the last
        # one this process saw.
        await asyncio.to_thread(self._iam.refresh_if_changed)

    async def _handle(self, request, *, operation: str) -> None:
        name = codec.OPERATIONS[operation]
        response_type = getattr(pb, f"{name}Response")
        caller: CallContext | None
        if operation in codec.PUBLIC_OPERATIONS:
            caller = ANONYMOUS
        else:
            caller = await authenticate_request(request, self._verifier, response_type)
        if caller is None:
            return
        try:
            parsed = getattr(pb, f"{name}Request").FromString(
                await request_payload(request)
            )
            call = getattr(self, f"_call_{operation}")
            result = await self._dispatch.call(call, parsed, caller)
        except Exception as exc:  # noqa: BLE001 - translate at the RPC boundary
            code = codec.error_code(exc)
            if isinstance(exc, DecodeError):
                code = "INVALID_ARGUMENT"
            if isinstance(exc, RequestPayloadError):
                code = exc.code
            if code == "INTERNAL":
                # The type only: the frames of a key exchange or a key creation
                # hold the key.
                logger.error(f"iam NATS {operation} failed ({type(exc).__name__})")
            result = response_type(
                error=common_pb2.CallError(
                    code=code,
                    message=str(exc) if code != "INTERNAL" else "internal error",
                    retryable=code == "INTERNAL",
                )
            )
        await respond_protobuf(request, result, response_type)

    # -- decisions --------------------------------------------------------------

    def _call_authorize(self, req: pb.AuthorizeRequest) -> pb.AuthorizeResponse:
        decision = self._iam.authorize(req.action, req.resource)
        return pb.AuthorizeResponse(decision=codec.decision_to_pb(decision))

    def _call_authorize_declared(
        self, req: pb.AuthorizeDeclaredRequest
    ) -> pb.AuthorizeDeclaredResponse:
        decision, resource = self._iam.authorize_declared(
            req.action,
            req.resource_type,
            list(req.parts),
            workspace=req.workspace_id or None,
        )
        return pb.AuthorizeDeclaredResponse(
            decision=codec.decision_to_pb(decision), resource=resource
        )

    def _call_filter(self, req: pb.FilterRequest) -> pb.FilterResponse:
        result = self._iam.filter(req.action, list(req.resources))
        return pb.FilterResponse(
            allowed=result.allowed, prefix_hints=result.prefix_hints
        )

    def _call_explain(self, req: pb.ExplainRequest) -> pb.ExplainResponse:
        explanation = self._iam.explain(
            req.action, req.resource, principal_id=_opt(req, "principal_id")
        )
        return pb.ExplainResponse(explanation=codec.explanation_to_pb(explanation))

    def _call_grantable(self, req: pb.GrantableRequest) -> pb.GrantableResponse:
        return pb.GrantableResponse(
            catalogs=[codec.grantable_to_pb(c) for c in self._iam.grantable(req.scope)]
        )

    # -- principals ---------------------------------------------------------------

    def _call_ensure_user(self, req: pb.EnsureUserRequest) -> pb.EnsureUserResponse:
        record = self._iam.ensure_user(
            req.issuer,
            req.subject,
            provider=_opt(req, "provider"),
            email=_opt(req, "email"),
            email_verified=req.email_verified,
            display_name=_opt(req, "display_name"),
        )
        return pb.EnsureUserResponse(principal=codec.principal_to_pb(record))

    def _call_create_service_account(
        self, req: pb.CreateServiceAccountRequest
    ) -> pb.CreateServiceAccountResponse:
        record = self._iam.create_service_account(
            req.name, owner_id=_opt(req, "owner_id")
        )
        return pb.CreateServiceAccountResponse(principal=codec.principal_to_pb(record))

    def _call_get_principal(
        self, req: pb.GetPrincipalRequest
    ) -> pb.GetPrincipalResponse:
        record = self._iam.get_principal(req.principal_id)
        return pb.GetPrincipalResponse(principal=codec.principal_to_pb(record))

    def _call_list_principals(
        self, req: pb.ListPrincipalsRequest
    ) -> pb.ListPrincipalsResponse:
        page = self._iam.list_principals(
            _opt(req, "kind"), limit=req.limit or 100, after=_opt(req, "after")
        )
        return pb.ListPrincipalsResponse(
            principals=[codec.principal_to_pb(p) for p in page.items],
            next_after=page.next_after,
        )

    def _call_suspend_principal(
        self, req: pb.SuspendPrincipalRequest
    ) -> pb.SuspendPrincipalResponse:
        record = self._iam.suspend_principal(req.principal_id)
        return pb.SuspendPrincipalResponse(principal=codec.principal_to_pb(record))

    def _call_resume_principal(
        self, req: pb.ResumePrincipalRequest
    ) -> pb.ResumePrincipalResponse:
        record = self._iam.resume_principal(req.principal_id)
        return pb.ResumePrincipalResponse(principal=codec.principal_to_pb(record))

    def _call_delete_principal(
        self, req: pb.DeletePrincipalRequest
    ) -> pb.DeletePrincipalResponse:
        record = self._iam.delete_principal(req.principal_id)
        return pb.DeletePrincipalResponse(principal=codec.principal_to_pb(record))

    # -- groups ---------------------------------------------------------------------

    def _call_create_group(self, req: pb.CreateGroupRequest) -> pb.CreateGroupResponse:
        record = self._iam.create_group(
            req.name, org=_opt(req, "org"), scope=_opt(req, "scope")
        )
        return pb.CreateGroupResponse(group=codec.principal_to_pb(record))

    def _call_get_group(self, req: pb.GetGroupRequest) -> pb.GetGroupResponse:
        return pb.GetGroupResponse(
            group=codec.principal_to_pb(self._iam.get_group(req.group_id))
        )

    def _call_list_groups(self, req: pb.ListGroupsRequest) -> pb.ListGroupsResponse:
        page = self._iam.list_groups(
            limit=req.limit or 100, after=_opt(req, "after"), scope=_opt(req, "scope")
        )
        return pb.ListGroupsResponse(
            groups=[codec.principal_to_pb(g) for g in page.items],
            next_after=page.next_after,
        )

    def _call_delete_group(self, req: pb.DeleteGroupRequest) -> pb.DeleteGroupResponse:
        return pb.DeleteGroupResponse(
            group=codec.principal_to_pb(self._iam.delete_group(req.group_id))
        )

    def _call_add_group_member(
        self, req: pb.AddGroupMemberRequest
    ) -> pb.AddGroupMemberResponse:
        self._iam.add_group_member(req.group_id, req.member_id)
        return pb.AddGroupMemberResponse()

    def _call_remove_group_member(
        self, req: pb.RemoveGroupMemberRequest
    ) -> pb.RemoveGroupMemberResponse:
        removed = self._iam.remove_group_member(req.group_id, req.member_id)
        return pb.RemoveGroupMemberResponse(removed=removed)

    def _call_list_group_members(
        self, req: pb.ListGroupMembersRequest
    ) -> pb.ListGroupMembersResponse:
        return pb.ListGroupMembersResponse(
            member_ids=self._iam.list_group_members(req.group_id)
        )

    def _call_map_idp_group(self, req: pb.MapIdpGroupRequest) -> pb.MapIdpGroupResponse:
        mapping = self._iam.map_idp_group(req.provider, req.claim_value, req.group_id)
        return pb.MapIdpGroupResponse(mapping=codec.mapping_to_pb(mapping))

    def _call_unmap_idp_group(
        self, req: pb.UnmapIdpGroupRequest
    ) -> pb.UnmapIdpGroupResponse:
        removed = self._iam.unmap_idp_group(req.provider, req.claim_value, req.group_id)
        return pb.UnmapIdpGroupResponse(removed=removed)

    def _call_list_idp_group_mappings(
        self, req: pb.ListIdpGroupMappingsRequest
    ) -> pb.ListIdpGroupMappingsResponse:
        mappings = self._iam.list_idp_group_mappings(req.group_id)
        return pb.ListIdpGroupMappingsResponse(
            mappings=[codec.mapping_to_pb(m) for m in mappings]
        )

    # -- policies and attachments ---------------------------------------------------

    def _call_create_policy(
        self, req: pb.CreatePolicyRequest
    ) -> pb.CreatePolicyResponse:
        policy = self._iam.create_policy(
            req.name,
            req.document_json,
            description=req.description,
            scope=_opt(req, "scope"),
            parent=_opt(req, "parent"),
        )
        return pb.CreatePolicyResponse(policy=codec.policy_to_pb(policy))

    def _call_get_policy(self, req: pb.GetPolicyRequest) -> pb.GetPolicyResponse:
        return pb.GetPolicyResponse(
            policy=codec.policy_to_pb(self._iam.get_policy(req.policy_id))
        )

    def _call_list_policies(
        self, req: pb.ListPoliciesRequest
    ) -> pb.ListPoliciesResponse:
        page = self._iam.list_policies(
            limit=req.limit or 100, after=_opt(req, "after"), scope=_opt(req, "scope")
        )
        return pb.ListPoliciesResponse(
            policies=[codec.policy_to_pb(p) for p in page.items],
            next_after=page.next_after,
        )

    def _call_update_policy(
        self, req: pb.UpdatePolicyRequest
    ) -> pb.UpdatePolicyResponse:
        policy = self._iam.update_policy(
            req.policy_id,
            expected_revision=req.expected_revision,
            document=_opt(req, "document_json"),
            name=_opt(req, "name"),
            description=_opt(req, "description"),
            parent=_opt(req, "parent"),
        )
        return pb.UpdatePolicyResponse(policy=codec.policy_to_pb(policy))

    def _call_delete_policy(
        self, req: pb.DeletePolicyRequest
    ) -> pb.DeletePolicyResponse:
        self._iam.delete_policy(req.policy_id)
        return pb.DeletePolicyResponse()

    def _call_list_sub_policies(
        self, req: pb.ListSubPoliciesRequest
    ) -> pb.ListSubPoliciesResponse:
        return pb.ListSubPoliciesResponse(
            policies=[
                codec.policy_to_pb(p)
                for p in self._iam.list_sub_policies(req.policy_id)
            ]
        )

    def _call_attach_policy(
        self, req: pb.AttachPolicyRequest
    ) -> pb.AttachPolicyResponse:
        attachment = self._iam.attach_policy(
            req.policy_id, req.principal_id, _opt(req, "scope")
        )
        return pb.AttachPolicyResponse(attachment=codec.attachment_to_pb(attachment))

    def _call_detach_policy(
        self, req: pb.DetachPolicyRequest
    ) -> pb.DetachPolicyResponse:
        detached = self._iam.detach_policy(
            req.policy_id, req.principal_id, _opt(req, "scope")
        )
        return pb.DetachPolicyResponse(detached=detached)

    def _call_list_attachments(
        self, req: pb.ListAttachmentsRequest
    ) -> pb.ListAttachmentsResponse:
        found = self._iam.list_attachments(
            principal_id=_opt(req, "principal_id"), policy_id=_opt(req, "policy_id")
        )
        return pb.ListAttachmentsResponse(
            attachments=[codec.attachment_to_pb(a) for a in found]
        )

    # -- invitations and IdP group bindings ------------------------------------------

    def _call_create_pending_grant(
        self, req: pb.CreatePendingGrantRequest
    ) -> pb.CreatePendingGrantResponse:
        grant = self._iam.create_pending_grant(
            req.provider, req.email, req.policy_id, _opt(req, "scope")
        )
        return pb.CreatePendingGrantResponse(grant=codec.pending_grant_to_pb(grant))

    def _call_list_pending_grants(
        self, req: pb.ListPendingGrantsRequest
    ) -> pb.ListPendingGrantsResponse:
        found = self._iam.list_pending_grants(
            provider=_opt(req, "provider"),
            email=_opt(req, "email"),
            policy_id=_opt(req, "policy_id"),
        )
        return pb.ListPendingGrantsResponse(
            grants=[codec.pending_grant_to_pb(g) for g in found]
        )

    def _call_revoke_pending_grant(
        self, req: pb.RevokePendingGrantRequest
    ) -> pb.RevokePendingGrantResponse:
        return pb.RevokePendingGrantResponse(
            revoked=self._iam.revoke_pending_grant(req.grant_id)
        )

    def _call_claim_pending_grants(
        self, req: pb.ClaimPendingGrantsRequest
    ) -> pb.ClaimPendingGrantsResponse:
        claimed = self._iam.claim_pending_grants(req.principal_id)
        return pb.ClaimPendingGrantsResponse(
            attachments=[codec.attachment_to_pb(a) for a in claimed]
        )

    def _call_bind_idp_group(
        self, req: pb.BindIdpGroupRequest
    ) -> pb.BindIdpGroupResponse:
        binding = self._iam.bind_idp_group(
            req.provider, req.claim_value, req.policy_id, _opt(req, "scope")
        )
        return pb.BindIdpGroupResponse(binding=codec.binding_to_pb(binding))

    def _call_unbind_idp_group(
        self, req: pb.UnbindIdpGroupRequest
    ) -> pb.UnbindIdpGroupResponse:
        return pb.UnbindIdpGroupResponse(
            removed=self._iam.unbind_idp_group(
                req.provider, req.claim_value, req.policy_id, _opt(req, "scope")
            )
        )

    def _call_list_idp_bindings(
        self, req: pb.ListIdpBindingsRequest
    ) -> pb.ListIdpBindingsResponse:
        found = self._iam.list_idp_bindings(
            provider=_opt(req, "provider"), policy_id=_opt(req, "policy_id")
        )
        return pb.ListIdpBindingsResponse(
            bindings=[codec.binding_to_pb(b) for b in found]
        )

    # -- placements, scopes, catalogs ------------------------------------------------

    def _call_put_placement(
        self, req: pb.PutPlacementRequest
    ) -> pb.PutPlacementResponse:
        wanted = codec.placement_from_pb(req.placement)
        placement = self._iam.put_placement(
            wanted.service, wanted.id_key, wanted.org, wanted.workspace
        )
        return pb.PutPlacementResponse(placement=codec.placement_to_pb(placement))

    def _call_delete_placement(
        self, req: pb.DeletePlacementRequest
    ) -> pb.DeletePlacementResponse:
        deleted = self._iam.delete_placement(req.service, req.id_key)
        return pb.DeletePlacementResponse(deleted=deleted)

    def _call_list_placements(
        self, req: pb.ListPlacementsRequest
    ) -> pb.ListPlacementsResponse:
        found = self._iam.list_placements(_opt(req, "service"))
        return pb.ListPlacementsResponse(
            placements=[codec.placement_to_pb(p) for p in found]
        )

    def _call_put_scope(self, req: pb.PutScopeRequest) -> pb.PutScopeResponse:
        scope = self._iam.put_scope(req.org, req.workspace or "-")
        return pb.PutScopeResponse(scope=codec.scope_to_pb(scope))

    def _call_delete_scope(self, req: pb.DeleteScopeRequest) -> pb.DeleteScopeResponse:
        deleted = self._iam.delete_scope(req.org, req.workspace or "-")
        return pb.DeleteScopeResponse(deleted=deleted)

    def _call_get_set(self, req: pb.GetSetRequest) -> pb.GetSetResponse:
        found = self._iam.get_set(req.org, req.workspace or "-")
        return pb.GetSetResponse(scope_set=codec.scope_set_to_pb(found))

    def _call_effective_set(
        self, req: pb.EffectiveSetRequest
    ) -> pb.EffectiveSetResponse:
        found = self._iam.effective_set(req.org, req.workspace or "-")
        return pb.EffectiveSetResponse(scope_set=codec.scope_set_to_pb(found))

    def _call_list_sets(self, req: pb.ListSetsRequest) -> pb.ListSetsResponse:
        found = self._iam.list_sets(_opt(req, "org"))
        return pb.ListSetsResponse(sets=[codec.scope_set_to_pb(s) for s in found])

    def _call_put_set(self, req: pb.PutSetRequest) -> pb.PutSetResponse:
        recorded = self._iam.put_set(
            req.org,
            req.workspace or "-",
            modules=codec.set_items_from_pb(req, "modules"),
            features=codec.set_items_from_pb(req, "features"),
        )
        return pb.PutSetResponse(scope_set=codec.scope_set_to_pb(recorded))

    def _call_register_catalog(
        self, req: pb.RegisterCatalogRequest
    ) -> pb.RegisterCatalogResponse:
        registered = self._iam.register_catalog(codec.catalog_from_pb(req.catalog))
        return pb.RegisterCatalogResponse(registered=registered)

    # -- tokens (no credentials) ------------------------------------------------------

    def _call_token(self, req: pb.TokenRequest) -> pb.TokenResponse:
        import time

        issued = self._iam.exchange_key(req.key, req.audience or NATS_AUDIENCE)
        return pb.TokenResponse(
            access_token=issued.token,
            expires_in=max(0, int(issued.expires_at - time.time())),
            principal_id=issued.principal_id,
            name=issued.name,
        )

    def _call_exchange_token(
        self, req: pb.ExchangeTokenRequest
    ) -> pb.ExchangeTokenResponse:
        import time

        if req.grant_type and req.grant_type != GRANT_TYPE_TOKEN_EXCHANGE:
            raise ValueError(f"grant_type must be {GRANT_TYPE_TOKEN_EXCHANGE}")
        issued = self._iam.exchange_token(
            TokenExchange(
                subject_token=req.subject_token,
                subject_token_type=req.subject_token_type,
                audience=req.audience,
                resource=req.resource or None,
                scope=codec.scope_from_json(_opt(req, "scope_json")),
                groups=tuple(req.groups),
                session_id=req.session_id or None,
                ttl_seconds=req.ttl_seconds or None,
            )
        )
        return pb.ExchangeTokenResponse(
            access_token=issued.token,
            issued_token_type=TOKEN_TYPE_JWT,
            token_type="Bearer",
            expires_in=max(0, int(issued.expires_at - time.time())),
            audience=issued.audience,
            principal_id=issued.principal_id,
        )

    def _call_revoke_tokens(
        self, req: pb.RevokeTokensRequest
    ) -> pb.RevokeTokensResponse:
        self._iam.revoke_tokens(req.principal_id, include_keys=req.include_keys)
        return pb.RevokeTokensResponse()

    def _call_jwks(self, req: pb.JwksRequest) -> pb.JwksResponse:
        return pb.JwksResponse(jwks_json=json.dumps(self._iam.jwks(), sort_keys=True))

    # -- service accounts and keys ------------------------------------------------------

    def _call_find_service_account(
        self, req: pb.FindServiceAccountRequest
    ) -> pb.FindServiceAccountResponse:
        record = self._iam.find_service_account(req.name)
        return pb.FindServiceAccountResponse(principal=codec.principal_to_pb(record))

    def _call_create_key(self, req: pb.CreateKeyRequest) -> pb.CreateKeyResponse:
        expires_at = (
            req.expires_at.ToDatetime(tzinfo=UTC)
            if req.HasField("expires_at")
            else None
        )
        created = self._iam.create_key(
            req.principal_id,
            description=req.description,
            expires_at=expires_at,
            kind=req.kind or None,  # type: ignore[arg-type]
            audience=req.audience or None,
            resource=req.resource or None,
            scope=codec.scope_from_json(_opt(req, "scope_json")),
        )
        return pb.CreateKeyResponse(
            key=codec.key_to_pb(created.record), value=created.value
        )

    def _call_list_keys(self, req: pb.ListKeysRequest) -> pb.ListKeysResponse:
        found = self._iam.list_keys(req.principal_id)
        return pb.ListKeysResponse(keys=[codec.key_to_pb(k) for k in found])

    def _call_revoke_key(self, req: pb.RevokeKeyRequest) -> pb.RevokeKeyResponse:
        record = self._iam.revoke_key(req.principal_id, req.key_id)
        return pb.RevokeKeyResponse(key=codec.key_to_pb(record))

    # -- manifests -------------------------------------------------------------------------

    def _call_submit_manifest(
        self, req: pb.SubmitManifestRequest
    ) -> pb.SubmitManifestResponse:
        submitted = self._iam.submit_manifest(
            req.module_id, req.project, json.loads(req.document_json or "{}")
        )
        return pb.SubmitManifestResponse(
            manifest=codec.manifest_to_pb(submitted.manifest),
            approved_now=submitted.approved_now,
            in_force=submitted.in_force,
        )

    def _call_get_manifest(self, req: pb.GetManifestRequest) -> pb.GetManifestResponse:
        record = self._iam.get_manifest(req.principal_id, _opt(req, "sha256"))
        return pb.GetManifestResponse(manifest=codec.manifest_to_pb(record))

    def _call_list_manifests(
        self, req: pb.ListManifestsRequest
    ) -> pb.ListManifestsResponse:
        found = self._iam.list_manifests(
            principal_id=_opt(req, "principal_id"), status=_opt(req, "status")
        )
        return pb.ListManifestsResponse(
            manifests=[codec.manifest_to_pb(m) for m in found]
        )

    def _call_approve_manifest(
        self, req: pb.ApproveManifestRequest
    ) -> pb.ApproveManifestResponse:
        document = _opt(req, "document_json")
        record = self._iam.approve_manifest(
            req.principal_id,
            _opt(req, "sha256"),
            document=json.loads(document) if document else None,
        )
        return pb.ApproveManifestResponse(manifest=codec.manifest_to_pb(record))

    def _call_reject_manifest(
        self, req: pb.RejectManifestRequest
    ) -> pb.RejectManifestResponse:
        record = self._iam.reject_manifest(
            req.principal_id, _opt(req, "sha256"), reason=req.reason
        )
        return pb.RejectManifestResponse(manifest=codec.manifest_to_pb(record))
