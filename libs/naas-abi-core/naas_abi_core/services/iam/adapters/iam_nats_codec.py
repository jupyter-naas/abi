"""IAM records and errors on the wire (``naas_abi_proto/iam/v1/iam.proto``).

Shared by the NATS primary and the NATS client, so neither imports the other.
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from naas_abi_core.services.iam.catalog import (
    ActionCatalog,
    ActionSpec,
    CatalogError,
    ResourceType,
)
from naas_abi_core.services.iam.IAMPorts import (
    Attachment,
    DecidingStatement,
    Decision,
    Explanation,
    GroupMapping,
    IAMConflictError,
    IAMNotFoundError,
    PermissionDeniedError,
    Placement,
    Policy,
    PrincipalRecord,
    RevisionConflictError,
    ScopeRecord,
)
from naas_abi_core.services.iam.policy import PolicyDocument
from naas_abi_proto.iam.v1 import iam_pb2 as pb

SUBJECT_PREFIX = "abi.iam.v1"
CHANGED_SUBJECT = f"{SUBJECT_PREFIX}.changed"
SERVICE_NAME = "iam"
SERVICE_VERSION = "1.0.0"

# Operation (subject suffix) -> message name, one per Request/Response pair.
OPERATIONS = {
    "authorize": "Authorize",
    "filter": "Filter",
    "explain": "Explain",
    "ensure_user": "EnsureUser",
    "create_service_account": "CreateServiceAccount",
    "get_principal": "GetPrincipal",
    "list_principals": "ListPrincipals",
    "suspend_principal": "SuspendPrincipal",
    "resume_principal": "ResumePrincipal",
    "delete_principal": "DeletePrincipal",
    "create_group": "CreateGroup",
    "get_group": "GetGroup",
    "list_groups": "ListGroups",
    "delete_group": "DeleteGroup",
    "add_group_member": "AddGroupMember",
    "remove_group_member": "RemoveGroupMember",
    "list_group_members": "ListGroupMembers",
    "map_idp_group": "MapIdpGroup",
    "unmap_idp_group": "UnmapIdpGroup",
    "list_idp_group_mappings": "ListIdpGroupMappings",
    "create_policy": "CreatePolicy",
    "get_policy": "GetPolicy",
    "list_policies": "ListPolicies",
    "update_policy": "UpdatePolicy",
    "delete_policy": "DeletePolicy",
    "attach_policy": "AttachPolicy",
    "detach_policy": "DetachPolicy",
    "list_attachments": "ListAttachments",
    "put_placement": "PutPlacement",
    "delete_placement": "DeletePlacement",
    "list_placements": "ListPlacements",
    "put_scope": "PutScope",
    "delete_scope": "DeleteScope",
    "register_catalog": "RegisterCatalog",
}

# Wire code -> exception. INVALID_ARGUMENT covers policy validation: its
# message lists every error.
ERRORS: dict[str, type[Exception]] = {
    "PERMISSION_DENIED": PermissionDeniedError,
    "NOT_FOUND": IAMNotFoundError,
    "CONFLICT": IAMConflictError,
    "REVISION_CONFLICT": RevisionConflictError,
    "INVALID_ARGUMENT": ValueError,
}


def error_code(exc: BaseException) -> str:
    if isinstance(exc, PermissionDeniedError):
        return "PERMISSION_DENIED"
    if isinstance(exc, IAMNotFoundError):
        return "NOT_FOUND"
    if isinstance(exc, RevisionConflictError):
        return "REVISION_CONFLICT"
    if isinstance(exc, IAMConflictError):
        return "CONFLICT"
    if isinstance(exc, (ValueError, CatalogError)):
        return "INVALID_ARGUMENT"
    return "INTERNAL"


def raise_for(error: Any) -> None:
    """Raise the exception a ``CallError`` stands for."""
    cls = ERRORS.get(error.code)
    if cls is PermissionDeniedError:
        raise PermissionDeniedError(message=error.message)
    if cls is not None:
        raise cls(error.message)
    raise RuntimeError(f"iam NATS RPC failed ({error.code}): {error.message}")


# -- helpers ---------------------------------------------------------------------


def _stamped(message: Any, **times: datetime | None) -> Any:
    """``message`` with its Timestamp fields set from ``times`` (None stays unset)."""
    for field, value in times.items():
        if value is not None:
            getattr(message, field).FromDatetime(value)
    return message


def _datetime(message: Any, field: str) -> datetime | None:
    if not message.HasField(field):
        return None
    from datetime import UTC

    return getattr(message, field).ToDatetime(tzinfo=UTC)


def _optional(message: Any, field: str) -> Any:
    return getattr(message, field) if message.HasField(field) else None


# -- records ---------------------------------------------------------------------


def principal_to_pb(record: PrincipalRecord) -> pb.Principal:
    message = pb.Principal(
        id=record.id,
        kind=record.kind,
        status=record.status,
        name=record.name,
        issuer=record.issuer,
        subject=record.subject,
        provider=record.provider,
        email=record.email,
        email_verified=record.email_verified,
        display_name=record.display_name,
        org=record.org,
        owner_id=record.owner_id,
    )
    return _stamped(message, created_at=record.created_at, updated_at=record.updated_at)


def principal_from_pb(message: pb.Principal) -> PrincipalRecord:
    return PrincipalRecord(
        id=message.id,
        kind=message.kind,  # type: ignore[arg-type]
        status=message.status,  # type: ignore[arg-type]
        name=_optional(message, "name"),
        issuer=_optional(message, "issuer"),
        subject=_optional(message, "subject"),
        provider=_optional(message, "provider"),
        email=_optional(message, "email"),
        email_verified=message.email_verified,
        display_name=_optional(message, "display_name"),
        org=_optional(message, "org"),
        owner_id=_optional(message, "owner_id"),
        created_at=_datetime(message, "created_at"),
        updated_at=_datetime(message, "updated_at"),
    )


def policy_to_pb(policy: Policy) -> pb.Policy:
    message = pb.Policy(
        id=policy.id,
        name=policy.name,
        description=policy.description,
        document_json=policy.document.to_json(),
        managed=policy.managed,
        revision=policy.revision,
    )
    return _stamped(message, created_at=policy.created_at, updated_at=policy.updated_at)


def policy_from_pb(message: pb.Policy) -> Policy:
    return Policy(
        id=message.id,
        name=message.name,
        description=message.description,
        document=PolicyDocument.from_dict(json.loads(message.document_json)),
        managed=message.managed,
        revision=message.revision,
        created_at=_datetime(message, "created_at"),
        updated_at=_datetime(message, "updated_at"),
    )


def attachment_to_pb(attachment: Attachment) -> pb.Attachment:
    message = pb.Attachment(
        id=attachment.id,
        policy_id=attachment.policy_id,
        principal_id=attachment.principal_id,
        scope=attachment.scope,
    )
    return _stamped(message, created_at=attachment.created_at)


def attachment_from_pb(message: pb.Attachment) -> Attachment:
    return Attachment(
        id=message.id,
        policy_id=message.policy_id,
        principal_id=message.principal_id,
        scope=_optional(message, "scope"),
        created_at=_datetime(message, "created_at"),
    )


def mapping_to_pb(mapping: GroupMapping) -> pb.GroupMapping:
    return pb.GroupMapping(
        provider=mapping.provider,
        claim_value=mapping.claim_value,
        group_id=mapping.group_id,
    )


def mapping_from_pb(message: pb.GroupMapping) -> GroupMapping:
    return GroupMapping(message.provider, message.claim_value, message.group_id)


def placement_to_pb(placement: Placement) -> pb.Placement:
    return pb.Placement(
        service=placement.service,
        id_key=placement.id_key,
        org=placement.org,
        workspace=placement.workspace,
    )


def placement_from_pb(message: pb.Placement) -> Placement:
    return Placement(
        message.service, message.id_key, message.org or "-", message.workspace or "-"
    )


def scope_to_pb(scope: ScopeRecord) -> pb.Scope:
    return pb.Scope(org=scope.org, workspace=scope.workspace)


def scope_from_pb(message: pb.Scope) -> ScopeRecord:
    return ScopeRecord(message.org, message.workspace or "-")


def catalog_to_pb(catalog: ActionCatalog) -> pb.ActionCatalog:
    return pb.ActionCatalog(
        service=catalog.service,
        version=catalog.version,
        resource_types=[
            pb.ResourceType(
                name=t.name,
                id=t.id,
                placement=t.placement,
                container=t.container,
                personal=t.personal,
                description=t.description,
            )
            for t in catalog.resource_types
        ],
        actions=[
            pb.ActionSpec(
                name=a.name,
                level=a.level,
                resource_types=list(a.resource_types),
                creates=a.creates,
                subjects=list(a.subjects),
                description=a.description,
            )
            for a in catalog.actions
        ],
    )


def catalog_from_pb(message: pb.ActionCatalog) -> ActionCatalog:
    return ActionCatalog(
        service=message.service,
        version=message.version,
        resource_types=tuple(
            ResourceType(
                name=t.name,
                id=t.id or "opaque",  # type: ignore[arg-type]
                placement=t.placement or "placed",  # type: ignore[arg-type]
                container=t.container,
                personal=t.personal,
                description=t.description,
            )
            for t in message.resource_types
        ),
        actions=tuple(
            ActionSpec(
                name=a.name,
                level=a.level,  # type: ignore[arg-type]
                resource_types=tuple(a.resource_types),
                creates=a.creates,
                subjects=tuple(a.subjects),
                description=a.description,
            )
            for a in message.actions
        ),
    )


# -- decisions ---------------------------------------------------------------------


def decision_to_pb(decision: Decision) -> pb.Decision:
    return pb.Decision(
        allowed=decision.allowed, visible=decision.visible, reason=decision.reason
    )


def decision_from_pb(message: pb.Decision) -> Decision:
    return Decision(message.allowed, message.visible, message.reason)  # type: ignore[arg-type]


def explanation_to_pb(explanation: Explanation) -> pb.Explanation:
    message = pb.Explanation(
        allowed=explanation.allowed,
        reason=explanation.reason,
        action=explanation.action,
        resource=explanation.resource,
    )
    statement = explanation.statement
    if statement is not None:
        message.statement.CopyFrom(
            pb.DecidingStatement(
                side=statement.side,
                principal_id=statement.principal_id,
                effect=statement.effect,
                policy_id=statement.policy_id,
                statement_index=statement.statement_index,
                sid=statement.sid,
                attachment_id=statement.attachment_id,
                scope=statement.scope,
                via_group=statement.via_group,
            )
        )
    return message


def explanation_from_pb(message: pb.Explanation) -> Explanation:
    statement = None
    if message.HasField("statement"):
        s = message.statement
        statement = DecidingStatement(
            side=s.side,  # type: ignore[arg-type]
            principal_id=s.principal_id,
            effect=s.effect,
            policy_id=_optional(s, "policy_id"),
            statement_index=s.statement_index,
            sid=_optional(s, "sid"),
            attachment_id=_optional(s, "attachment_id"),
            scope=_optional(s, "scope"),
            via_group=_optional(s, "via_group"),
        )
    return Explanation(
        allowed=message.allowed,
        reason=message.reason,  # type: ignore[arg-type]
        action=message.action,
        resource=message.resource,
        statement=statement,
    )
