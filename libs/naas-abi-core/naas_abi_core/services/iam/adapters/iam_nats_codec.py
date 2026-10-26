"""IAM records and errors on the wire (``naas_abi_proto/iam/v1/iam.proto``).

Shared by the NATS primary and the NATS client, so neither imports the other.
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from naas_abi_core.engine.nats_auth import InvalidServiceTokenError
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
    GrantableAction,
    GrantableCatalog,
    GrantNotHeldError,
    GroupMapping,
    IAMConflictError,
    IAMNotFoundError,
    IdpBinding,
    KeyRecord,
    KeyRefusedError,
    ManifestRecord,
    PendingGrant,
    PermissionDeniedError,
    Placement,
    Policy,
    PrincipalRecord,
    RevisionConflictError,
    ScopeRecord,
)
from naas_abi_core.services.iam.names import PLATFORM_SCOPE
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
    "grantable": "Grantable",
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
    "create_pending_grant": "CreatePendingGrant",
    "list_pending_grants": "ListPendingGrants",
    "revoke_pending_grant": "RevokePendingGrant",
    "claim_pending_grants": "ClaimPendingGrants",
    "bind_idp_group": "BindIdpGroup",
    "unbind_idp_group": "UnbindIdpGroup",
    "list_idp_bindings": "ListIdpBindings",
    "put_placement": "PutPlacement",
    "delete_placement": "DeletePlacement",
    "list_placements": "ListPlacements",
    "put_scope": "PutScope",
    "delete_scope": "DeleteScope",
    "register_catalog": "RegisterCatalog",
    "token": "Token",
    "jwks": "Jwks",
    "exchange_token": "ExchangeToken",
    "revoke_tokens": "RevokeTokens",
    "find_service_account": "FindServiceAccount",
    "create_key": "CreateKey",
    "list_keys": "ListKeys",
    "revoke_key": "RevokeKey",
    "submit_manifest": "SubmitManifest",
    "get_manifest": "GetManifest",
    "list_manifests": "ListManifests",
    "approve_manifest": "ApproveManifest",
    "reject_manifest": "RejectManifest",
}
# Need no credentials: the key is one; the JWKS is public.
PUBLIC_OPERATIONS = frozenset({"token", "jwks"})

# Wire code -> exception. INVALID_ARGUMENT covers policy validation: its
# message lists every error.
ERRORS: dict[str, type[Exception]] = {
    "PERMISSION_DENIED": PermissionDeniedError,
    "GRANT_NOT_HELD": GrantNotHeldError,
    "NOT_FOUND": IAMNotFoundError,
    "CONFLICT": IAMConflictError,
    "REVISION_CONFLICT": RevisionConflictError,
    "INVALID_ARGUMENT": ValueError,
    "UNAUTHENTICATED": KeyRefusedError,
}


def error_code(exc: BaseException) -> str:
    if isinstance(exc, (KeyRefusedError, InvalidServiceTokenError)):
        return "UNAUTHENTICATED"
    if isinstance(exc, GrantNotHeldError):
        return "GRANT_NOT_HELD"
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


def raise_for(error: Any, *, subject_refusal: bool = False) -> None:
    """Raise the exception a ``CallError`` stands for.

    ``subject_refusal``: the call exchanged a token, so an ``UNAUTHENTICATED``
    that is not the key refusal is a subject that failed verification
    (``InvalidServiceTokenError``), as in process."""
    cls = ERRORS.get(error.code)
    if cls is GrantNotHeldError:
        raise GrantNotHeldError(message=error.message)
    if cls is PermissionDeniedError:
        raise PermissionDeniedError(message=error.message)
    if cls is KeyRefusedError and error.message == "invalid key":
        raise KeyRefusedError()
    if cls is KeyRefusedError:  # a refused token, not a refused key
        if subject_refusal:
            raise InvalidServiceTokenError(error.message)
        cls = None
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
        owner_scope=record.owner_scope,
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
        owner_scope=message.owner_scope or PLATFORM_SCOPE,
    )


def policy_to_pb(policy: Policy) -> pb.Policy:
    message = pb.Policy(
        id=policy.id,
        name=policy.name,
        description=policy.description,
        document_json=policy.document.to_json(),
        managed=policy.managed,
        revision=policy.revision,
        owner_scope=policy.owner_scope,
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
        owner_scope=message.owner_scope or PLATFORM_SCOPE,
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


def pending_grant_to_pb(grant: PendingGrant) -> pb.PendingGrant:
    message = pb.PendingGrant(
        id=grant.id,
        provider=grant.provider,
        email=grant.email,
        policy_id=grant.policy_id,
        scope=grant.scope,
        created_by=grant.created_by,
    )
    return _stamped(message, created_at=grant.created_at)


def pending_grant_from_pb(message: pb.PendingGrant) -> PendingGrant:
    return PendingGrant(
        id=message.id,
        provider=message.provider,
        email=message.email,
        policy_id=message.policy_id,
        scope=_optional(message, "scope"),
        created_by=_optional(message, "created_by"),
        created_at=_datetime(message, "created_at"),
    )


def binding_to_pb(binding: IdpBinding) -> pb.IdpBinding:
    return pb.IdpBinding(
        provider=binding.provider,
        claim_value=binding.claim_value,
        group_id=binding.group_id,
        policy_id=binding.policy_id,
        scope=binding.scope,
        attachment_id=binding.attachment_id,
    )


def binding_from_pb(message: pb.IdpBinding) -> IdpBinding:
    return IdpBinding(
        provider=message.provider,
        claim_value=message.claim_value,
        group_id=message.group_id,
        policy_id=message.policy_id,
        scope=_optional(message, "scope"),
        attachment_id=_optional(message, "attachment_id"),
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
                module_scope=t.module_scope,
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
        module=catalog.module,
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
                module_scope=t.module_scope,
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
        module=message.module,
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


def scope_to_json(scope: Any) -> str | None:
    return json.dumps(list(scope), sort_keys=True) if scope is not None else None


def scope_from_json(text: str | None) -> tuple[dict[str, Any], ...] | None:
    return tuple(json.loads(text)) if text is not None else None


def key_to_pb(record: KeyRecord) -> pb.Key:
    return _stamped(
        pb.Key(
            key_id=record.key_id,
            principal_id=record.principal_id,
            kind=record.kind,
            description=record.description,
            audience=record.audience or "",
            resource=record.resource or "",
            scope_json=scope_to_json(record.scope),
        ),
        created_at=record.created_at,
        expires_at=record.expires_at,
        last_used_at=record.last_used_at,
        revoked_at=record.revoked_at,
    )


def key_from_pb(message: pb.Key) -> KeyRecord:
    return KeyRecord(
        key_id=message.key_id,
        principal_id=message.principal_id,
        secret_hash="",  # never on the wire
        kind=message.kind,  # type: ignore[arg-type]
        description=message.description,
        created_at=_datetime(message, "created_at"),
        expires_at=_datetime(message, "expires_at"),
        last_used_at=_datetime(message, "last_used_at"),
        revoked_at=_datetime(message, "revoked_at"),
        audience=message.audience or None,
        resource=message.resource or None,
        scope=scope_from_json(_optional(message, "scope_json")),
    )


def manifest_to_pb(record: ManifestRecord) -> pb.Manifest:
    message = pb.Manifest(
        principal_id=record.principal_id,
        sha256=record.sha256,
        module_id=record.module_id,
        project=record.project,
        document_json=json.dumps(record.document, sort_keys=True),
        status=record.status,
        reason=record.reason,
    )
    if record.decided_by is not None:
        message.decided_by = record.decided_by
    return _stamped(
        message, submitted_at=record.submitted_at, decided_at=record.decided_at
    )


def manifest_from_pb(message: pb.Manifest) -> ManifestRecord:
    return ManifestRecord(
        principal_id=message.principal_id,
        sha256=message.sha256,
        module_id=message.module_id,
        project=message.project,
        document=json.loads(message.document_json or "{}"),
        status=message.status,  # type: ignore[arg-type]
        submitted_at=_datetime(message, "submitted_at"),
        decided_at=_datetime(message, "decided_at"),
        decided_by=_optional(message, "decided_by"),
        reason=message.reason,
    )


def grantable_to_pb(catalog: GrantableCatalog) -> pb.GrantableCatalog:
    return pb.GrantableCatalog(
        service=catalog.service,
        actions=[
            pb.GrantableAction(
                action=a.action, resources=list(a.resources), excluded=list(a.excluded)
            )
            for a in catalog.actions
        ],
    )


def grantable_from_pb(message: pb.GrantableCatalog) -> GrantableCatalog:
    return GrantableCatalog(
        service=message.service,
        actions=tuple(
            GrantableAction(a.action, tuple(a.resources), tuple(a.excluded))
            for a in message.actions
        ),
    )
