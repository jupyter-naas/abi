"""``/api/iam/admin``: the IAM admin pages' routes.

Every route is a call to the engine's IAM made as the signed-in user, so IAM's own
``iam:*`` actions decide: a 403 is a user who sees the resource and may not do this, a
404 one who cannot see it. Each route names the action it performs with ``declares``
(the route matrix reads them); the check itself is IAM's, inside the call.

Changes are audited first (``service.py``): the audit is the System app's fail-closed
log, so a change that cannot be recorded is not made (503).

Session only (``/api/iam/`` takes no API key): a key cannot administer permissions.
Keys' values appear in the one answer that made them and never again.
"""

from __future__ import annotations

from collections.abc import Awaitable
from typing import Any, Literal, TypeVar

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from naas_abi.apps.nexus.apps.api.app.services.auth.adapters.primary.auth__primary_adapter__dependencies import (  # noqa: E501
    get_current_user_required,
    require_superadmin,
)
from naas_abi.apps.nexus.apps.api.app.services.auth.adapters.primary.auth__primary_adapter__schemas import (  # noqa: E501
    User,
)
from naas_abi.apps.nexus.apps.api.app.services.iam.guards import declares
from naas_abi.apps.nexus.apps.api.app.services.iam_admin.port import IamUnavailableError
from naas_abi.apps.nexus.apps.api.app.services.iam_admin.runtime import get_iam_admin_service
from naas_abi.apps.nexus.apps.api.app.services.iam_admin.service import IamAdminService
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.resources import AuditUnavailable
from naas_abi_core.services.iam.IAMPorts import (
    IAMConflictError,
    IAMNotFoundError,
    PermissionDeniedError,
    RevisionConflictError,
)
from naas_abi_core.services.iam.policy import PolicyValidationError
from pydantic import BaseModel, Field

router = APIRouter()
T = TypeVar("T")

PrincipalKindName = Literal["user", "group", "service_account"]
ManifestStatusName = Literal["pending", "approved", "rejected", "superseded"]


async def _call(call: Awaitable[T]) -> T:
    """IAM's answer, or its refusal as the HTTP response it is."""
    try:
        return await call
    except PolicyValidationError as exc:
        raise HTTPException(
            422, detail={"message": "The policy is not valid", "errors": list(exc.errors)}
        ) from exc
    except ValueError as exc:
        raise HTTPException(422, detail=str(exc)) from exc
    except PermissionDeniedError as exc:
        raise HTTPException(403, detail=str(exc)) from exc
    except IAMNotFoundError as exc:
        raise HTTPException(404, detail=str(exc)) from exc
    except RevisionConflictError as exc:
        raise HTTPException(
            409, detail="The policy changed since you opened it: reload it and try again"
        ) from exc
    except IAMConflictError as exc:
        raise HTTPException(409, detail=str(exc)) from exc
    except AuditUnavailable as exc:
        raise HTTPException(503, detail=f"No change made: {exc}") from exc
    except IamUnavailableError as exc:
        raise HTTPException(503, detail=str(exc)) from exc


Service = Depends(get_iam_admin_service)
Signed = Depends(get_current_user_required)


class PolicySourceBody(BaseModel):
    """A policy document as an object, or as YAML or JSON text."""

    document: dict[str, Any] | None = None
    text: str | None = Field(default=None, max_length=64 * 1024)

    def source(self) -> dict[str, Any]:
        return {"document": self.document, "text": self.text}


class PolicyCreateBody(PolicySourceBody):
    name: str = Field(min_length=1, max_length=128)
    description: str = Field(default="", max_length=1000)
    # The owner: abi:-:- (the default), abi:<org>:- or abi:<org>:<ws>.
    scope: str | None = None


class PolicyUpdateBody(PolicySourceBody):
    expected_revision: int
    name: str | None = Field(default=None, min_length=1, max_length=128)
    description: str | None = Field(default=None, max_length=1000)


class AttachBody(BaseModel):
    policy_id: str = Field(min_length=1)
    principal_id: str = Field(min_length=1)
    scope: str | None = None


class GroupCreateBody(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    org: str | None = None
    # The owner: abi:-:- (the default), abi:<org>:- or abi:<org>:<ws>.
    scope: str | None = None


class IdpMappingBody(BaseModel):
    provider: str = Field(min_length=1, max_length=32)
    claim_value: str = Field(min_length=1, max_length=256)


class ServiceAccountBody(BaseModel):
    name: str = Field(min_length=1, max_length=128)


class KeyBody(BaseModel):
    description: str = Field(default="", max_length=200)
    expires_in_days: int | None = None


class ApproveBody(BaseModel):
    document: dict[str, Any] | None = None


class RejectBody(BaseModel):
    reason: str = Field(default="", max_length=500)


class SimulateBody(BaseModel):
    principal_id: str = Field(min_length=1)
    action: str = Field(min_length=1)
    resource: str = Field(min_length=1)


# -- what the caller may do ---------------------------------------------------------------


@router.get("/access")
async def access(
    scope: str | None = Query(None),
    user: User = Signed,
    service: IamAdminService = Service,
) -> dict[str, Any]:
    """The caller's own permissions, decided by IAM: which pages and buttons will answer."""
    return await _call(service.access(user, scope))


@router.get("/catalogs", dependencies=[declares("iam:ListPolicies")])
async def catalogs(
    scope: str | None = None, user: User = Signed, service: IamAdminService = Service
) -> dict[str, Any]:
    return await _call(service.catalogs(user, scope))


# -- policies -----------------------------------------------------------------------------


@router.post("/policies/validate", dependencies=[declares("iam:CreatePolicy")])
async def validate_policy(
    body: PolicySourceBody,
    scope: str | None = None,
    user: User = Signed,
    service: IamAdminService = Service,
) -> dict[str, Any]:
    return await _call(service.validate_policy(user, body.source(), scope))


@router.get("/policies", dependencies=[declares("iam:ListPolicies")])
async def list_policies(
    after: str | None = None,
    scope: str | None = None,
    user: User = Signed,
    service: IamAdminService = Service,
) -> dict[str, Any]:
    return await _call(service.list_policies(user, after, scope))


@router.get("/policies/{policy_id}", dependencies=[declares("iam:GetPolicy")])
async def get_policy(
    policy_id: str, user: User = Signed, service: IamAdminService = Service
) -> dict[str, Any]:
    return await _call(service.get_policy(user, policy_id))


@router.post("/policies", status_code=201, dependencies=[declares("iam:CreatePolicy")])
async def create_policy(
    body: PolicyCreateBody, user: User = Signed, service: IamAdminService = Service
) -> dict[str, Any]:
    return await _call(
        service.create_policy(user, body.name, body.source(), body.description, body.scope)
    )


@router.put("/policies/{policy_id}", dependencies=[declares("iam:UpdatePolicy")])
async def update_policy(
    policy_id: str,
    body: PolicyUpdateBody,
    user: User = Signed,
    service: IamAdminService = Service,
) -> dict[str, Any]:
    has_source = body.document is not None or body.text is not None
    return await _call(
        service.update_policy(
            user,
            policy_id,
            expected_revision=body.expected_revision,
            source=body.source() if has_source else None,
            name=body.name,
            description=body.description,
        )
    )


@router.delete(
    "/policies/{policy_id}", status_code=204, dependencies=[declares("iam:DeletePolicy")]
)
async def delete_policy(
    policy_id: str, user: User = Signed, service: IamAdminService = Service
) -> Response:
    await _call(service.delete_policy(user, policy_id))
    return Response(status_code=204)


# -- attachments --------------------------------------------------------------------------


@router.get("/attachments", dependencies=[declares("iam:ListAttachments")])
async def list_attachments(
    principal_id: str | None = None,
    policy_id: str | None = None,
    scope: str | None = None,
    user: User = Signed,
    service: IamAdminService = Service,
) -> dict[str, Any]:
    return await _call(
        service.list_attachments(user, principal_id=principal_id, policy_id=policy_id, scope=scope)
    )


@router.get("/attachable-policies", dependencies=[declares("iam:AttachPolicy")])
async def attachable_policies(
    scope: str | None = None,
    principal_id: str | None = None,
    user: User = Signed,
    service: IamAdminService = Service,
) -> dict[str, Any]:
    return await _call(service.attachable(user, scope, principal_id))


@router.post("/attachments", status_code=201, dependencies=[declares("iam:AttachPolicy")])
async def attach(
    body: AttachBody, user: User = Signed, service: IamAdminService = Service
) -> dict[str, Any]:
    return await _call(service.attach(user, body.policy_id, body.principal_id, body.scope))


@router.delete("/attachments", status_code=204, dependencies=[declares("iam:DetachPolicy")])
async def detach(
    policy_id: str,
    principal_id: str,
    scope: str | None = None,
    user: User = Signed,
    service: IamAdminService = Service,
) -> Response:
    await _call(service.detach(user, policy_id, principal_id, scope))
    return Response(status_code=204)


# -- principals ---------------------------------------------------------------------------


@router.get("/principals", dependencies=[declares("iam:ListPrincipals")])
async def list_principals(
    kind: PrincipalKindName | None = None,
    after: str | None = None,
    user: User = Signed,
    service: IamAdminService = Service,
) -> dict[str, Any]:
    return await _call(service.list_principals(user, kind, after))


@router.get("/principals/{principal_id}", dependencies=[declares("iam:GetPrincipal")])
async def get_principal(
    principal_id: str, user: User = Signed, service: IamAdminService = Service
) -> dict[str, Any]:
    return await _call(service.get_principal(user, principal_id))


@router.post("/principals/{principal_id}/suspend", dependencies=[declares("iam:SuspendPrincipal")])
async def suspend_principal(
    principal_id: str, user: User = Signed, service: IamAdminService = Service
) -> dict[str, Any]:
    return await _call(service.suspend(user, principal_id))


@router.post("/principals/{principal_id}/resume", dependencies=[declares("iam:ResumePrincipal")])
async def resume_principal(
    principal_id: str, user: User = Signed, service: IamAdminService = Service
) -> dict[str, Any]:
    return await _call(service.resume(user, principal_id))


# -- groups -------------------------------------------------------------------------------


@router.get("/groups", dependencies=[declares("iam:ListGroups")])
async def list_groups(
    scope: str | None = None, user: User = Signed, service: IamAdminService = Service
) -> dict[str, Any]:
    return await _call(service.list_groups(user, scope))


@router.get("/groups/{group_id}", dependencies=[declares("iam:GetGroup")])
async def get_group(
    group_id: str, user: User = Signed, service: IamAdminService = Service
) -> dict[str, Any]:
    return await _call(service.get_group(user, group_id))


@router.post("/groups", status_code=201, dependencies=[declares("iam:CreateGroup")])
async def create_group(
    body: GroupCreateBody, user: User = Signed, service: IamAdminService = Service
) -> dict[str, Any]:
    return await _call(service.create_group(user, body.name, body.org, body.scope))


@router.delete("/groups/{group_id}", status_code=204, dependencies=[declares("iam:DeleteGroup")])
async def delete_group(
    group_id: str, user: User = Signed, service: IamAdminService = Service
) -> Response:
    await _call(service.delete_group(user, group_id))
    return Response(status_code=204)


@router.put("/groups/{group_id}/members/{member_id}", dependencies=[declares("iam:AddGroupMember")])
async def add_member(
    group_id: str, member_id: str, user: User = Signed, service: IamAdminService = Service
) -> dict[str, Any]:
    return await _call(service.add_member(user, group_id, member_id))


@router.delete(
    "/groups/{group_id}/members/{member_id}", dependencies=[declares("iam:RemoveGroupMember")]
)
async def remove_member(
    group_id: str, member_id: str, user: User = Signed, service: IamAdminService = Service
) -> dict[str, Any]:
    return await _call(service.remove_member(user, group_id, member_id))


@router.put("/groups/{group_id}/idp-mappings", dependencies=[declares("iam:MapIdpGroup")])
async def map_idp_group(
    group_id: str, body: IdpMappingBody, user: User = Signed, service: IamAdminService = Service
) -> dict[str, Any]:
    return await _call(service.map_idp_group(user, group_id, body.provider, body.claim_value))


@router.delete("/groups/{group_id}/idp-mappings", dependencies=[declares("iam:UnmapIdpGroup")])
async def unmap_idp_group(
    group_id: str,
    provider: str,
    claim_value: str,
    user: User = Signed,
    service: IamAdminService = Service,
) -> dict[str, Any]:
    return await _call(service.unmap_idp_group(user, group_id, provider, claim_value))


# -- service accounts and keys -------------------------------------------------------------


@router.get("/service-accounts", dependencies=[declares("iam:ListPrincipals")])
async def list_service_accounts(
    user: User = Signed, service: IamAdminService = Service
) -> dict[str, Any]:
    return await _call(service.list_service_accounts(user))


@router.post(
    "/service-accounts", status_code=201, dependencies=[declares("iam:CreateServiceAccount")]
)
async def create_service_account(
    body: ServiceAccountBody, user: User = Signed, service: IamAdminService = Service
) -> dict[str, Any]:
    return await _call(service.create_service_account(user, body.name))


@router.delete(
    "/service-accounts/{account_id}",
    status_code=204,
    dependencies=[declares("iam:DeletePrincipal")],
)
async def delete_service_account(
    account_id: str, user: User = Signed, service: IamAdminService = Service
) -> Response:
    await _call(service.delete_service_account(user, account_id))
    return Response(status_code=204)


@router.get("/service-accounts/{account_id}/keys", dependencies=[declares("iam:ListKeys")])
async def list_keys(
    account_id: str, user: User = Signed, service: IamAdminService = Service
) -> dict[str, Any]:
    return await _call(service.list_keys(user, account_id))


@router.post(
    "/service-accounts/{account_id}/keys",
    status_code=201,
    dependencies=[declares("iam:CreateKey")],
)
async def create_key(
    account_id: str, body: KeyBody, user: User = Signed, service: IamAdminService = Service
) -> Response:
    created = await _call(
        service.create_key(user, account_id, body.description, body.expires_in_days)
    )
    return _no_store(created, 201)


@router.delete(
    "/service-accounts/{account_id}/keys/{key_id}", dependencies=[declares("iam:RevokeKey")]
)
async def revoke_key(
    account_id: str, key_id: str, user: User = Signed, service: IamAdminService = Service
) -> dict[str, Any]:
    return await _call(service.revoke_key(user, account_id, key_id))


@router.post(
    "/service-accounts/{account_id}/keys/{key_id}/rotate", dependencies=[declares("iam:CreateKey")]
)
async def rotate_key(
    account_id: str, key_id: str, user: User = Signed, service: IamAdminService = Service
) -> Response:
    return _no_store(await _call(service.rotate_key(user, account_id, key_id)), 200)


def _no_store(body: dict[str, Any], status: int) -> Response:
    """The answer that carries a key's value: shown once, never cached."""
    import json

    return Response(
        content=json.dumps(body),
        status_code=status,
        media_type="application/json",
        headers={"Cache-Control": "no-store"},
    )


# -- module permission approvals ------------------------------------------------------------


@router.get("/manifests", dependencies=[declares("iam:ListManifests")])
async def list_manifests(
    status: ManifestStatusName | None = None,
    user: User = Signed,
    service: IamAdminService = Service,
) -> dict[str, Any]:
    return await _call(service.list_manifests(user, status))


@router.post(
    "/manifests/{principal_id}/{sha256}/approve", dependencies=[declares("iam:ApproveManifest")]
)
async def approve_manifest(
    principal_id: str,
    sha256: str,
    body: ApproveBody | None = None,
    user: User = Signed,
    service: IamAdminService = Service,
) -> dict[str, Any]:
    document = body.document if body is not None else None
    return await _call(service.approve_manifest(user, principal_id, sha256, document))


@router.post(
    "/manifests/{principal_id}/{sha256}/reject", dependencies=[declares("iam:RejectManifest")]
)
async def reject_manifest(
    principal_id: str,
    sha256: str,
    body: RejectBody | None = None,
    user: User = Signed,
    service: IamAdminService = Service,
) -> dict[str, Any]:
    reason = body.reason if body is not None else ""
    return await _call(service.reject_manifest(user, principal_id, sha256, reason))


# -- the simulator and the audit --------------------------------------------------------------


@router.post("/simulate", dependencies=[declares("iam:Explain")])
async def simulate(
    body: SimulateBody, user: User = Signed, service: IamAdminService = Service
) -> dict[str, Any]:
    return await _call(service.simulate(user, body.principal_id, body.action, body.resource))


@router.get("/audit", dependencies=[Depends(require_superadmin)])
async def audit(
    operation: str | None = None,
    resource_id: str | None = None,
    limit: int = Query(100, ge=1, le=500),
    service: IamAdminService = Service,
) -> dict[str, Any]:
    return await _call(service.history(operation=operation, resource_id=resource_id, limit=limit))
