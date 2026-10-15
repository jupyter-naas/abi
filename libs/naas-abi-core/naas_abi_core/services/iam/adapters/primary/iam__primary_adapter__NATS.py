"""IAM over NATS: ``abi.iam.v1.<operation>`` (proto ``iam/v1``).

Each request runs under the ``CallContext`` built from its verified
credentials (``nats_rpc.authenticate_request``), so ``authorize`` and
``filter`` answer for the caller, and every other operation is authorized
with IAM's own ``iam:*`` catalog inside ``IAMService``, never here.

After every change it publishes ``abi.iam.v1.changed`` (a ``ChangeEvent``
with the store revision), so remote caches can drop their entries.
"""

from __future__ import annotations

import asyncio
from functools import partial
from typing import Any

import nats
from google.protobuf.message import DecodeError
from naas_abi_core import logger
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
from naas_abi_core.services.iam.IAMService import IAMService
from naas_abi_proto.common.v1 import common_pb2
from naas_abi_proto.iam.v1 import iam_pb2 as pb


def _opt(message: Any, field: str) -> Any:
    return getattr(message, field) if message.HasField(field) else None


class IAMPrimaryAdapterNATS(ServicePrimary):
    def __init__(self, service: IAMService, jwt_secret: str) -> None:
        self._iam = service
        self._jwt_secret = jwt_secret
        self._dispatch = DomainRPCDispatcher(codec.SERVICE_NAME)
        self._service: TracedService | None = None
        self._nc: nats.NATS | None = None
        self._loop: asyncio.AbstractEventLoop | None = None

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

    async def stop(self) -> None:
        self._iam.remove_change_listener(self._publish_change)
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

    async def _handle(self, request, *, operation: str) -> None:
        name = codec.OPERATIONS[operation]
        response_type = getattr(pb, f"{name}Response")
        caller = await authenticate_request(request, self._jwt_secret, response_type)
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
                logger.opt(exception=exc).error(f"iam NATS {operation} failed")
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
        record = self._iam.create_group(req.name, org=_opt(req, "org"))
        return pb.CreateGroupResponse(group=codec.principal_to_pb(record))

    def _call_get_group(self, req: pb.GetGroupRequest) -> pb.GetGroupResponse:
        return pb.GetGroupResponse(
            group=codec.principal_to_pb(self._iam.get_group(req.group_id))
        )

    def _call_list_groups(self, req: pb.ListGroupsRequest) -> pb.ListGroupsResponse:
        page = self._iam.list_groups(limit=req.limit or 100, after=_opt(req, "after"))
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
            req.name, req.document_json, description=req.description
        )
        return pb.CreatePolicyResponse(policy=codec.policy_to_pb(policy))

    def _call_get_policy(self, req: pb.GetPolicyRequest) -> pb.GetPolicyResponse:
        return pb.GetPolicyResponse(
            policy=codec.policy_to_pb(self._iam.get_policy(req.policy_id))
        )

    def _call_list_policies(
        self, req: pb.ListPoliciesRequest
    ) -> pb.ListPoliciesResponse:
        page = self._iam.list_policies(limit=req.limit or 100, after=_opt(req, "after"))
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
        )
        return pb.UpdatePolicyResponse(policy=codec.policy_to_pb(policy))

    def _call_delete_policy(
        self, req: pb.DeletePolicyRequest
    ) -> pb.DeletePolicyResponse:
        self._iam.delete_policy(req.policy_id)
        return pb.DeletePolicyResponse()

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

    def _call_register_catalog(
        self, req: pb.RegisterCatalogRequest
    ) -> pb.RegisterCatalogResponse:
        registered = self._iam.register_catalog(codec.catalog_from_pb(req.catalog))
        return pb.RegisterCatalogResponse(registered=registered)
