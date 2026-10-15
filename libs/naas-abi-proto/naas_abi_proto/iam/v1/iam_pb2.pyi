import datetime

from google.protobuf import timestamp_pb2 as _timestamp_pb2
from naas_abi_proto.common.v1 import common_pb2 as _common_pb2
from google.protobuf.internal import containers as _containers
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from collections.abc import Iterable as _Iterable, Mapping as _Mapping
from typing import ClassVar as _ClassVar, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class Principal(_message.Message):
    __slots__ = ("id", "kind", "status", "name", "issuer", "subject", "provider", "email", "email_verified", "display_name", "org", "owner_id", "created_at", "updated_at")
    ID_FIELD_NUMBER: _ClassVar[int]
    KIND_FIELD_NUMBER: _ClassVar[int]
    STATUS_FIELD_NUMBER: _ClassVar[int]
    NAME_FIELD_NUMBER: _ClassVar[int]
    ISSUER_FIELD_NUMBER: _ClassVar[int]
    SUBJECT_FIELD_NUMBER: _ClassVar[int]
    PROVIDER_FIELD_NUMBER: _ClassVar[int]
    EMAIL_FIELD_NUMBER: _ClassVar[int]
    EMAIL_VERIFIED_FIELD_NUMBER: _ClassVar[int]
    DISPLAY_NAME_FIELD_NUMBER: _ClassVar[int]
    ORG_FIELD_NUMBER: _ClassVar[int]
    OWNER_ID_FIELD_NUMBER: _ClassVar[int]
    CREATED_AT_FIELD_NUMBER: _ClassVar[int]
    UPDATED_AT_FIELD_NUMBER: _ClassVar[int]
    id: str
    kind: str
    status: str
    name: str
    issuer: str
    subject: str
    provider: str
    email: str
    email_verified: bool
    display_name: str
    org: str
    owner_id: str
    created_at: _timestamp_pb2.Timestamp
    updated_at: _timestamp_pb2.Timestamp
    def __init__(self, id: _Optional[str] = ..., kind: _Optional[str] = ..., status: _Optional[str] = ..., name: _Optional[str] = ..., issuer: _Optional[str] = ..., subject: _Optional[str] = ..., provider: _Optional[str] = ..., email: _Optional[str] = ..., email_verified: bool = ..., display_name: _Optional[str] = ..., org: _Optional[str] = ..., owner_id: _Optional[str] = ..., created_at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., updated_at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ...) -> None: ...

class Policy(_message.Message):
    __slots__ = ("id", "name", "description", "document_json", "managed", "revision", "created_at", "updated_at")
    ID_FIELD_NUMBER: _ClassVar[int]
    NAME_FIELD_NUMBER: _ClassVar[int]
    DESCRIPTION_FIELD_NUMBER: _ClassVar[int]
    DOCUMENT_JSON_FIELD_NUMBER: _ClassVar[int]
    MANAGED_FIELD_NUMBER: _ClassVar[int]
    REVISION_FIELD_NUMBER: _ClassVar[int]
    CREATED_AT_FIELD_NUMBER: _ClassVar[int]
    UPDATED_AT_FIELD_NUMBER: _ClassVar[int]
    id: str
    name: str
    description: str
    document_json: str
    managed: bool
    revision: int
    created_at: _timestamp_pb2.Timestamp
    updated_at: _timestamp_pb2.Timestamp
    def __init__(self, id: _Optional[str] = ..., name: _Optional[str] = ..., description: _Optional[str] = ..., document_json: _Optional[str] = ..., managed: bool = ..., revision: _Optional[int] = ..., created_at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., updated_at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ...) -> None: ...

class Attachment(_message.Message):
    __slots__ = ("id", "policy_id", "principal_id", "scope", "created_at")
    ID_FIELD_NUMBER: _ClassVar[int]
    POLICY_ID_FIELD_NUMBER: _ClassVar[int]
    PRINCIPAL_ID_FIELD_NUMBER: _ClassVar[int]
    SCOPE_FIELD_NUMBER: _ClassVar[int]
    CREATED_AT_FIELD_NUMBER: _ClassVar[int]
    id: str
    policy_id: str
    principal_id: str
    scope: str
    created_at: _timestamp_pb2.Timestamp
    def __init__(self, id: _Optional[str] = ..., policy_id: _Optional[str] = ..., principal_id: _Optional[str] = ..., scope: _Optional[str] = ..., created_at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ...) -> None: ...

class GroupMapping(_message.Message):
    __slots__ = ("provider", "claim_value", "group_id")
    PROVIDER_FIELD_NUMBER: _ClassVar[int]
    CLAIM_VALUE_FIELD_NUMBER: _ClassVar[int]
    GROUP_ID_FIELD_NUMBER: _ClassVar[int]
    provider: str
    claim_value: str
    group_id: str
    def __init__(self, provider: _Optional[str] = ..., claim_value: _Optional[str] = ..., group_id: _Optional[str] = ...) -> None: ...

class Placement(_message.Message):
    __slots__ = ("service", "id_key", "org", "workspace")
    SERVICE_FIELD_NUMBER: _ClassVar[int]
    ID_KEY_FIELD_NUMBER: _ClassVar[int]
    ORG_FIELD_NUMBER: _ClassVar[int]
    WORKSPACE_FIELD_NUMBER: _ClassVar[int]
    service: str
    id_key: str
    org: str
    workspace: str
    def __init__(self, service: _Optional[str] = ..., id_key: _Optional[str] = ..., org: _Optional[str] = ..., workspace: _Optional[str] = ...) -> None: ...

class Scope(_message.Message):
    __slots__ = ("org", "workspace")
    ORG_FIELD_NUMBER: _ClassVar[int]
    WORKSPACE_FIELD_NUMBER: _ClassVar[int]
    org: str
    workspace: str
    def __init__(self, org: _Optional[str] = ..., workspace: _Optional[str] = ...) -> None: ...

class ResourceType(_message.Message):
    __slots__ = ("name", "id", "placement", "container", "personal", "description")
    NAME_FIELD_NUMBER: _ClassVar[int]
    ID_FIELD_NUMBER: _ClassVar[int]
    PLACEMENT_FIELD_NUMBER: _ClassVar[int]
    CONTAINER_FIELD_NUMBER: _ClassVar[int]
    PERSONAL_FIELD_NUMBER: _ClassVar[int]
    DESCRIPTION_FIELD_NUMBER: _ClassVar[int]
    name: str
    id: str
    placement: str
    container: bool
    personal: bool
    description: str
    def __init__(self, name: _Optional[str] = ..., id: _Optional[str] = ..., placement: _Optional[str] = ..., container: bool = ..., personal: bool = ..., description: _Optional[str] = ...) -> None: ...

class ActionSpec(_message.Message):
    __slots__ = ("name", "level", "resource_types", "creates", "subjects", "description")
    NAME_FIELD_NUMBER: _ClassVar[int]
    LEVEL_FIELD_NUMBER: _ClassVar[int]
    RESOURCE_TYPES_FIELD_NUMBER: _ClassVar[int]
    CREATES_FIELD_NUMBER: _ClassVar[int]
    SUBJECTS_FIELD_NUMBER: _ClassVar[int]
    DESCRIPTION_FIELD_NUMBER: _ClassVar[int]
    name: str
    level: str
    resource_types: _containers.RepeatedScalarFieldContainer[str]
    creates: bool
    subjects: _containers.RepeatedScalarFieldContainer[str]
    description: str
    def __init__(self, name: _Optional[str] = ..., level: _Optional[str] = ..., resource_types: _Optional[_Iterable[str]] = ..., creates: bool = ..., subjects: _Optional[_Iterable[str]] = ..., description: _Optional[str] = ...) -> None: ...

class ActionCatalog(_message.Message):
    __slots__ = ("service", "version", "resource_types", "actions")
    SERVICE_FIELD_NUMBER: _ClassVar[int]
    VERSION_FIELD_NUMBER: _ClassVar[int]
    RESOURCE_TYPES_FIELD_NUMBER: _ClassVar[int]
    ACTIONS_FIELD_NUMBER: _ClassVar[int]
    service: str
    version: int
    resource_types: _containers.RepeatedCompositeFieldContainer[ResourceType]
    actions: _containers.RepeatedCompositeFieldContainer[ActionSpec]
    def __init__(self, service: _Optional[str] = ..., version: _Optional[int] = ..., resource_types: _Optional[_Iterable[_Union[ResourceType, _Mapping]]] = ..., actions: _Optional[_Iterable[_Union[ActionSpec, _Mapping]]] = ...) -> None: ...

class Decision(_message.Message):
    __slots__ = ("allowed", "visible", "reason")
    ALLOWED_FIELD_NUMBER: _ClassVar[int]
    VISIBLE_FIELD_NUMBER: _ClassVar[int]
    REASON_FIELD_NUMBER: _ClassVar[int]
    allowed: bool
    visible: bool
    reason: str
    def __init__(self, allowed: bool = ..., visible: bool = ..., reason: _Optional[str] = ...) -> None: ...

class DecidingStatement(_message.Message):
    __slots__ = ("side", "principal_id", "effect", "policy_id", "statement_index", "sid", "attachment_id", "scope", "via_group")
    SIDE_FIELD_NUMBER: _ClassVar[int]
    PRINCIPAL_ID_FIELD_NUMBER: _ClassVar[int]
    EFFECT_FIELD_NUMBER: _ClassVar[int]
    POLICY_ID_FIELD_NUMBER: _ClassVar[int]
    STATEMENT_INDEX_FIELD_NUMBER: _ClassVar[int]
    SID_FIELD_NUMBER: _ClassVar[int]
    ATTACHMENT_ID_FIELD_NUMBER: _ClassVar[int]
    SCOPE_FIELD_NUMBER: _ClassVar[int]
    VIA_GROUP_FIELD_NUMBER: _ClassVar[int]
    side: str
    principal_id: str
    effect: str
    policy_id: str
    statement_index: int
    sid: str
    attachment_id: str
    scope: str
    via_group: str
    def __init__(self, side: _Optional[str] = ..., principal_id: _Optional[str] = ..., effect: _Optional[str] = ..., policy_id: _Optional[str] = ..., statement_index: _Optional[int] = ..., sid: _Optional[str] = ..., attachment_id: _Optional[str] = ..., scope: _Optional[str] = ..., via_group: _Optional[str] = ...) -> None: ...

class Explanation(_message.Message):
    __slots__ = ("allowed", "reason", "action", "resource", "statement")
    ALLOWED_FIELD_NUMBER: _ClassVar[int]
    REASON_FIELD_NUMBER: _ClassVar[int]
    ACTION_FIELD_NUMBER: _ClassVar[int]
    RESOURCE_FIELD_NUMBER: _ClassVar[int]
    STATEMENT_FIELD_NUMBER: _ClassVar[int]
    allowed: bool
    reason: str
    action: str
    resource: str
    statement: DecidingStatement
    def __init__(self, allowed: bool = ..., reason: _Optional[str] = ..., action: _Optional[str] = ..., resource: _Optional[str] = ..., statement: _Optional[_Union[DecidingStatement, _Mapping]] = ...) -> None: ...

class ChangeEvent(_message.Message):
    __slots__ = ("revision",)
    REVISION_FIELD_NUMBER: _ClassVar[int]
    revision: int
    def __init__(self, revision: _Optional[int] = ...) -> None: ...

class AuthorizeRequest(_message.Message):
    __slots__ = ("context", "action", "resource")
    CONTEXT_FIELD_NUMBER: _ClassVar[int]
    ACTION_FIELD_NUMBER: _ClassVar[int]
    RESOURCE_FIELD_NUMBER: _ClassVar[int]
    context: _common_pb2.CallContext
    action: str
    resource: str
    def __init__(self, context: _Optional[_Union[_common_pb2.CallContext, _Mapping]] = ..., action: _Optional[str] = ..., resource: _Optional[str] = ...) -> None: ...

class AuthorizeResponse(_message.Message):
    __slots__ = ("error", "decision")
    ERROR_FIELD_NUMBER: _ClassVar[int]
    DECISION_FIELD_NUMBER: _ClassVar[int]
    error: _common_pb2.CallError
    decision: Decision
    def __init__(self, error: _Optional[_Union[_common_pb2.CallError, _Mapping]] = ..., decision: _Optional[_Union[Decision, _Mapping]] = ...) -> None: ...

class FilterRequest(_message.Message):
    __slots__ = ("context", "action", "resources")
    CONTEXT_FIELD_NUMBER: _ClassVar[int]
    ACTION_FIELD_NUMBER: _ClassVar[int]
    RESOURCES_FIELD_NUMBER: _ClassVar[int]
    context: _common_pb2.CallContext
    action: str
    resources: _containers.RepeatedScalarFieldContainer[str]
    def __init__(self, context: _Optional[_Union[_common_pb2.CallContext, _Mapping]] = ..., action: _Optional[str] = ..., resources: _Optional[_Iterable[str]] = ...) -> None: ...

class FilterResponse(_message.Message):
    __slots__ = ("error", "allowed", "prefix_hints")
    ERROR_FIELD_NUMBER: _ClassVar[int]
    ALLOWED_FIELD_NUMBER: _ClassVar[int]
    PREFIX_HINTS_FIELD_NUMBER: _ClassVar[int]
    error: _common_pb2.CallError
    allowed: _containers.RepeatedScalarFieldContainer[str]
    prefix_hints: _containers.RepeatedScalarFieldContainer[str]
    def __init__(self, error: _Optional[_Union[_common_pb2.CallError, _Mapping]] = ..., allowed: _Optional[_Iterable[str]] = ..., prefix_hints: _Optional[_Iterable[str]] = ...) -> None: ...

class ExplainRequest(_message.Message):
    __slots__ = ("context", "action", "resource", "principal_id")
    CONTEXT_FIELD_NUMBER: _ClassVar[int]
    ACTION_FIELD_NUMBER: _ClassVar[int]
    RESOURCE_FIELD_NUMBER: _ClassVar[int]
    PRINCIPAL_ID_FIELD_NUMBER: _ClassVar[int]
    context: _common_pb2.CallContext
    action: str
    resource: str
    principal_id: str
    def __init__(self, context: _Optional[_Union[_common_pb2.CallContext, _Mapping]] = ..., action: _Optional[str] = ..., resource: _Optional[str] = ..., principal_id: _Optional[str] = ...) -> None: ...

class ExplainResponse(_message.Message):
    __slots__ = ("error", "explanation")
    ERROR_FIELD_NUMBER: _ClassVar[int]
    EXPLANATION_FIELD_NUMBER: _ClassVar[int]
    error: _common_pb2.CallError
    explanation: Explanation
    def __init__(self, error: _Optional[_Union[_common_pb2.CallError, _Mapping]] = ..., explanation: _Optional[_Union[Explanation, _Mapping]] = ...) -> None: ...

class EnsureUserRequest(_message.Message):
    __slots__ = ("context", "issuer", "subject", "provider", "email", "email_verified", "display_name")
    CONTEXT_FIELD_NUMBER: _ClassVar[int]
    ISSUER_FIELD_NUMBER: _ClassVar[int]
    SUBJECT_FIELD_NUMBER: _ClassVar[int]
    PROVIDER_FIELD_NUMBER: _ClassVar[int]
    EMAIL_FIELD_NUMBER: _ClassVar[int]
    EMAIL_VERIFIED_FIELD_NUMBER: _ClassVar[int]
    DISPLAY_NAME_FIELD_NUMBER: _ClassVar[int]
    context: _common_pb2.CallContext
    issuer: str
    subject: str
    provider: str
    email: str
    email_verified: bool
    display_name: str
    def __init__(self, context: _Optional[_Union[_common_pb2.CallContext, _Mapping]] = ..., issuer: _Optional[str] = ..., subject: _Optional[str] = ..., provider: _Optional[str] = ..., email: _Optional[str] = ..., email_verified: bool = ..., display_name: _Optional[str] = ...) -> None: ...

class EnsureUserResponse(_message.Message):
    __slots__ = ("error", "principal")
    ERROR_FIELD_NUMBER: _ClassVar[int]
    PRINCIPAL_FIELD_NUMBER: _ClassVar[int]
    error: _common_pb2.CallError
    principal: Principal
    def __init__(self, error: _Optional[_Union[_common_pb2.CallError, _Mapping]] = ..., principal: _Optional[_Union[Principal, _Mapping]] = ...) -> None: ...

class CreateServiceAccountRequest(_message.Message):
    __slots__ = ("context", "name", "owner_id")
    CONTEXT_FIELD_NUMBER: _ClassVar[int]
    NAME_FIELD_NUMBER: _ClassVar[int]
    OWNER_ID_FIELD_NUMBER: _ClassVar[int]
    context: _common_pb2.CallContext
    name: str
    owner_id: str
    def __init__(self, context: _Optional[_Union[_common_pb2.CallContext, _Mapping]] = ..., name: _Optional[str] = ..., owner_id: _Optional[str] = ...) -> None: ...

class CreateServiceAccountResponse(_message.Message):
    __slots__ = ("error", "principal")
    ERROR_FIELD_NUMBER: _ClassVar[int]
    PRINCIPAL_FIELD_NUMBER: _ClassVar[int]
    error: _common_pb2.CallError
    principal: Principal
    def __init__(self, error: _Optional[_Union[_common_pb2.CallError, _Mapping]] = ..., principal: _Optional[_Union[Principal, _Mapping]] = ...) -> None: ...

class GetPrincipalRequest(_message.Message):
    __slots__ = ("context", "principal_id")
    CONTEXT_FIELD_NUMBER: _ClassVar[int]
    PRINCIPAL_ID_FIELD_NUMBER: _ClassVar[int]
    context: _common_pb2.CallContext
    principal_id: str
    def __init__(self, context: _Optional[_Union[_common_pb2.CallContext, _Mapping]] = ..., principal_id: _Optional[str] = ...) -> None: ...

class GetPrincipalResponse(_message.Message):
    __slots__ = ("error", "principal")
    ERROR_FIELD_NUMBER: _ClassVar[int]
    PRINCIPAL_FIELD_NUMBER: _ClassVar[int]
    error: _common_pb2.CallError
    principal: Principal
    def __init__(self, error: _Optional[_Union[_common_pb2.CallError, _Mapping]] = ..., principal: _Optional[_Union[Principal, _Mapping]] = ...) -> None: ...

class ListPrincipalsRequest(_message.Message):
    __slots__ = ("context", "kind", "limit", "after")
    CONTEXT_FIELD_NUMBER: _ClassVar[int]
    KIND_FIELD_NUMBER: _ClassVar[int]
    LIMIT_FIELD_NUMBER: _ClassVar[int]
    AFTER_FIELD_NUMBER: _ClassVar[int]
    context: _common_pb2.CallContext
    kind: str
    limit: int
    after: str
    def __init__(self, context: _Optional[_Union[_common_pb2.CallContext, _Mapping]] = ..., kind: _Optional[str] = ..., limit: _Optional[int] = ..., after: _Optional[str] = ...) -> None: ...

class ListPrincipalsResponse(_message.Message):
    __slots__ = ("error", "principals", "next_after")
    ERROR_FIELD_NUMBER: _ClassVar[int]
    PRINCIPALS_FIELD_NUMBER: _ClassVar[int]
    NEXT_AFTER_FIELD_NUMBER: _ClassVar[int]
    error: _common_pb2.CallError
    principals: _containers.RepeatedCompositeFieldContainer[Principal]
    next_after: str
    def __init__(self, error: _Optional[_Union[_common_pb2.CallError, _Mapping]] = ..., principals: _Optional[_Iterable[_Union[Principal, _Mapping]]] = ..., next_after: _Optional[str] = ...) -> None: ...

class SuspendPrincipalRequest(_message.Message):
    __slots__ = ("context", "principal_id")
    CONTEXT_FIELD_NUMBER: _ClassVar[int]
    PRINCIPAL_ID_FIELD_NUMBER: _ClassVar[int]
    context: _common_pb2.CallContext
    principal_id: str
    def __init__(self, context: _Optional[_Union[_common_pb2.CallContext, _Mapping]] = ..., principal_id: _Optional[str] = ...) -> None: ...

class SuspendPrincipalResponse(_message.Message):
    __slots__ = ("error", "principal")
    ERROR_FIELD_NUMBER: _ClassVar[int]
    PRINCIPAL_FIELD_NUMBER: _ClassVar[int]
    error: _common_pb2.CallError
    principal: Principal
    def __init__(self, error: _Optional[_Union[_common_pb2.CallError, _Mapping]] = ..., principal: _Optional[_Union[Principal, _Mapping]] = ...) -> None: ...

class ResumePrincipalRequest(_message.Message):
    __slots__ = ("context", "principal_id")
    CONTEXT_FIELD_NUMBER: _ClassVar[int]
    PRINCIPAL_ID_FIELD_NUMBER: _ClassVar[int]
    context: _common_pb2.CallContext
    principal_id: str
    def __init__(self, context: _Optional[_Union[_common_pb2.CallContext, _Mapping]] = ..., principal_id: _Optional[str] = ...) -> None: ...

class ResumePrincipalResponse(_message.Message):
    __slots__ = ("error", "principal")
    ERROR_FIELD_NUMBER: _ClassVar[int]
    PRINCIPAL_FIELD_NUMBER: _ClassVar[int]
    error: _common_pb2.CallError
    principal: Principal
    def __init__(self, error: _Optional[_Union[_common_pb2.CallError, _Mapping]] = ..., principal: _Optional[_Union[Principal, _Mapping]] = ...) -> None: ...

class DeletePrincipalRequest(_message.Message):
    __slots__ = ("context", "principal_id")
    CONTEXT_FIELD_NUMBER: _ClassVar[int]
    PRINCIPAL_ID_FIELD_NUMBER: _ClassVar[int]
    context: _common_pb2.CallContext
    principal_id: str
    def __init__(self, context: _Optional[_Union[_common_pb2.CallContext, _Mapping]] = ..., principal_id: _Optional[str] = ...) -> None: ...

class DeletePrincipalResponse(_message.Message):
    __slots__ = ("error", "principal")
    ERROR_FIELD_NUMBER: _ClassVar[int]
    PRINCIPAL_FIELD_NUMBER: _ClassVar[int]
    error: _common_pb2.CallError
    principal: Principal
    def __init__(self, error: _Optional[_Union[_common_pb2.CallError, _Mapping]] = ..., principal: _Optional[_Union[Principal, _Mapping]] = ...) -> None: ...

class CreateGroupRequest(_message.Message):
    __slots__ = ("context", "name", "org")
    CONTEXT_FIELD_NUMBER: _ClassVar[int]
    NAME_FIELD_NUMBER: _ClassVar[int]
    ORG_FIELD_NUMBER: _ClassVar[int]
    context: _common_pb2.CallContext
    name: str
    org: str
    def __init__(self, context: _Optional[_Union[_common_pb2.CallContext, _Mapping]] = ..., name: _Optional[str] = ..., org: _Optional[str] = ...) -> None: ...

class CreateGroupResponse(_message.Message):
    __slots__ = ("error", "group")
    ERROR_FIELD_NUMBER: _ClassVar[int]
    GROUP_FIELD_NUMBER: _ClassVar[int]
    error: _common_pb2.CallError
    group: Principal
    def __init__(self, error: _Optional[_Union[_common_pb2.CallError, _Mapping]] = ..., group: _Optional[_Union[Principal, _Mapping]] = ...) -> None: ...

class GetGroupRequest(_message.Message):
    __slots__ = ("context", "group_id")
    CONTEXT_FIELD_NUMBER: _ClassVar[int]
    GROUP_ID_FIELD_NUMBER: _ClassVar[int]
    context: _common_pb2.CallContext
    group_id: str
    def __init__(self, context: _Optional[_Union[_common_pb2.CallContext, _Mapping]] = ..., group_id: _Optional[str] = ...) -> None: ...

class GetGroupResponse(_message.Message):
    __slots__ = ("error", "group")
    ERROR_FIELD_NUMBER: _ClassVar[int]
    GROUP_FIELD_NUMBER: _ClassVar[int]
    error: _common_pb2.CallError
    group: Principal
    def __init__(self, error: _Optional[_Union[_common_pb2.CallError, _Mapping]] = ..., group: _Optional[_Union[Principal, _Mapping]] = ...) -> None: ...

class ListGroupsRequest(_message.Message):
    __slots__ = ("context", "limit", "after")
    CONTEXT_FIELD_NUMBER: _ClassVar[int]
    LIMIT_FIELD_NUMBER: _ClassVar[int]
    AFTER_FIELD_NUMBER: _ClassVar[int]
    context: _common_pb2.CallContext
    limit: int
    after: str
    def __init__(self, context: _Optional[_Union[_common_pb2.CallContext, _Mapping]] = ..., limit: _Optional[int] = ..., after: _Optional[str] = ...) -> None: ...

class ListGroupsResponse(_message.Message):
    __slots__ = ("error", "groups", "next_after")
    ERROR_FIELD_NUMBER: _ClassVar[int]
    GROUPS_FIELD_NUMBER: _ClassVar[int]
    NEXT_AFTER_FIELD_NUMBER: _ClassVar[int]
    error: _common_pb2.CallError
    groups: _containers.RepeatedCompositeFieldContainer[Principal]
    next_after: str
    def __init__(self, error: _Optional[_Union[_common_pb2.CallError, _Mapping]] = ..., groups: _Optional[_Iterable[_Union[Principal, _Mapping]]] = ..., next_after: _Optional[str] = ...) -> None: ...

class DeleteGroupRequest(_message.Message):
    __slots__ = ("context", "group_id")
    CONTEXT_FIELD_NUMBER: _ClassVar[int]
    GROUP_ID_FIELD_NUMBER: _ClassVar[int]
    context: _common_pb2.CallContext
    group_id: str
    def __init__(self, context: _Optional[_Union[_common_pb2.CallContext, _Mapping]] = ..., group_id: _Optional[str] = ...) -> None: ...

class DeleteGroupResponse(_message.Message):
    __slots__ = ("error", "group")
    ERROR_FIELD_NUMBER: _ClassVar[int]
    GROUP_FIELD_NUMBER: _ClassVar[int]
    error: _common_pb2.CallError
    group: Principal
    def __init__(self, error: _Optional[_Union[_common_pb2.CallError, _Mapping]] = ..., group: _Optional[_Union[Principal, _Mapping]] = ...) -> None: ...

class AddGroupMemberRequest(_message.Message):
    __slots__ = ("context", "group_id", "member_id")
    CONTEXT_FIELD_NUMBER: _ClassVar[int]
    GROUP_ID_FIELD_NUMBER: _ClassVar[int]
    MEMBER_ID_FIELD_NUMBER: _ClassVar[int]
    context: _common_pb2.CallContext
    group_id: str
    member_id: str
    def __init__(self, context: _Optional[_Union[_common_pb2.CallContext, _Mapping]] = ..., group_id: _Optional[str] = ..., member_id: _Optional[str] = ...) -> None: ...

class AddGroupMemberResponse(_message.Message):
    __slots__ = ("error",)
    ERROR_FIELD_NUMBER: _ClassVar[int]
    error: _common_pb2.CallError
    def __init__(self, error: _Optional[_Union[_common_pb2.CallError, _Mapping]] = ...) -> None: ...

class RemoveGroupMemberRequest(_message.Message):
    __slots__ = ("context", "group_id", "member_id")
    CONTEXT_FIELD_NUMBER: _ClassVar[int]
    GROUP_ID_FIELD_NUMBER: _ClassVar[int]
    MEMBER_ID_FIELD_NUMBER: _ClassVar[int]
    context: _common_pb2.CallContext
    group_id: str
    member_id: str
    def __init__(self, context: _Optional[_Union[_common_pb2.CallContext, _Mapping]] = ..., group_id: _Optional[str] = ..., member_id: _Optional[str] = ...) -> None: ...

class RemoveGroupMemberResponse(_message.Message):
    __slots__ = ("error", "removed")
    ERROR_FIELD_NUMBER: _ClassVar[int]
    REMOVED_FIELD_NUMBER: _ClassVar[int]
    error: _common_pb2.CallError
    removed: bool
    def __init__(self, error: _Optional[_Union[_common_pb2.CallError, _Mapping]] = ..., removed: bool = ...) -> None: ...

class ListGroupMembersRequest(_message.Message):
    __slots__ = ("context", "group_id")
    CONTEXT_FIELD_NUMBER: _ClassVar[int]
    GROUP_ID_FIELD_NUMBER: _ClassVar[int]
    context: _common_pb2.CallContext
    group_id: str
    def __init__(self, context: _Optional[_Union[_common_pb2.CallContext, _Mapping]] = ..., group_id: _Optional[str] = ...) -> None: ...

class ListGroupMembersResponse(_message.Message):
    __slots__ = ("error", "member_ids")
    ERROR_FIELD_NUMBER: _ClassVar[int]
    MEMBER_IDS_FIELD_NUMBER: _ClassVar[int]
    error: _common_pb2.CallError
    member_ids: _containers.RepeatedScalarFieldContainer[str]
    def __init__(self, error: _Optional[_Union[_common_pb2.CallError, _Mapping]] = ..., member_ids: _Optional[_Iterable[str]] = ...) -> None: ...

class MapIdpGroupRequest(_message.Message):
    __slots__ = ("context", "provider", "claim_value", "group_id")
    CONTEXT_FIELD_NUMBER: _ClassVar[int]
    PROVIDER_FIELD_NUMBER: _ClassVar[int]
    CLAIM_VALUE_FIELD_NUMBER: _ClassVar[int]
    GROUP_ID_FIELD_NUMBER: _ClassVar[int]
    context: _common_pb2.CallContext
    provider: str
    claim_value: str
    group_id: str
    def __init__(self, context: _Optional[_Union[_common_pb2.CallContext, _Mapping]] = ..., provider: _Optional[str] = ..., claim_value: _Optional[str] = ..., group_id: _Optional[str] = ...) -> None: ...

class MapIdpGroupResponse(_message.Message):
    __slots__ = ("error", "mapping")
    ERROR_FIELD_NUMBER: _ClassVar[int]
    MAPPING_FIELD_NUMBER: _ClassVar[int]
    error: _common_pb2.CallError
    mapping: GroupMapping
    def __init__(self, error: _Optional[_Union[_common_pb2.CallError, _Mapping]] = ..., mapping: _Optional[_Union[GroupMapping, _Mapping]] = ...) -> None: ...

class UnmapIdpGroupRequest(_message.Message):
    __slots__ = ("context", "provider", "claim_value", "group_id")
    CONTEXT_FIELD_NUMBER: _ClassVar[int]
    PROVIDER_FIELD_NUMBER: _ClassVar[int]
    CLAIM_VALUE_FIELD_NUMBER: _ClassVar[int]
    GROUP_ID_FIELD_NUMBER: _ClassVar[int]
    context: _common_pb2.CallContext
    provider: str
    claim_value: str
    group_id: str
    def __init__(self, context: _Optional[_Union[_common_pb2.CallContext, _Mapping]] = ..., provider: _Optional[str] = ..., claim_value: _Optional[str] = ..., group_id: _Optional[str] = ...) -> None: ...

class UnmapIdpGroupResponse(_message.Message):
    __slots__ = ("error", "removed")
    ERROR_FIELD_NUMBER: _ClassVar[int]
    REMOVED_FIELD_NUMBER: _ClassVar[int]
    error: _common_pb2.CallError
    removed: bool
    def __init__(self, error: _Optional[_Union[_common_pb2.CallError, _Mapping]] = ..., removed: bool = ...) -> None: ...

class ListIdpGroupMappingsRequest(_message.Message):
    __slots__ = ("context", "group_id")
    CONTEXT_FIELD_NUMBER: _ClassVar[int]
    GROUP_ID_FIELD_NUMBER: _ClassVar[int]
    context: _common_pb2.CallContext
    group_id: str
    def __init__(self, context: _Optional[_Union[_common_pb2.CallContext, _Mapping]] = ..., group_id: _Optional[str] = ...) -> None: ...

class ListIdpGroupMappingsResponse(_message.Message):
    __slots__ = ("error", "mappings")
    ERROR_FIELD_NUMBER: _ClassVar[int]
    MAPPINGS_FIELD_NUMBER: _ClassVar[int]
    error: _common_pb2.CallError
    mappings: _containers.RepeatedCompositeFieldContainer[GroupMapping]
    def __init__(self, error: _Optional[_Union[_common_pb2.CallError, _Mapping]] = ..., mappings: _Optional[_Iterable[_Union[GroupMapping, _Mapping]]] = ...) -> None: ...

class CreatePolicyRequest(_message.Message):
    __slots__ = ("context", "name", "document_json", "description")
    CONTEXT_FIELD_NUMBER: _ClassVar[int]
    NAME_FIELD_NUMBER: _ClassVar[int]
    DOCUMENT_JSON_FIELD_NUMBER: _ClassVar[int]
    DESCRIPTION_FIELD_NUMBER: _ClassVar[int]
    context: _common_pb2.CallContext
    name: str
    document_json: str
    description: str
    def __init__(self, context: _Optional[_Union[_common_pb2.CallContext, _Mapping]] = ..., name: _Optional[str] = ..., document_json: _Optional[str] = ..., description: _Optional[str] = ...) -> None: ...

class CreatePolicyResponse(_message.Message):
    __slots__ = ("error", "policy")
    ERROR_FIELD_NUMBER: _ClassVar[int]
    POLICY_FIELD_NUMBER: _ClassVar[int]
    error: _common_pb2.CallError
    policy: Policy
    def __init__(self, error: _Optional[_Union[_common_pb2.CallError, _Mapping]] = ..., policy: _Optional[_Union[Policy, _Mapping]] = ...) -> None: ...

class GetPolicyRequest(_message.Message):
    __slots__ = ("context", "policy_id")
    CONTEXT_FIELD_NUMBER: _ClassVar[int]
    POLICY_ID_FIELD_NUMBER: _ClassVar[int]
    context: _common_pb2.CallContext
    policy_id: str
    def __init__(self, context: _Optional[_Union[_common_pb2.CallContext, _Mapping]] = ..., policy_id: _Optional[str] = ...) -> None: ...

class GetPolicyResponse(_message.Message):
    __slots__ = ("error", "policy")
    ERROR_FIELD_NUMBER: _ClassVar[int]
    POLICY_FIELD_NUMBER: _ClassVar[int]
    error: _common_pb2.CallError
    policy: Policy
    def __init__(self, error: _Optional[_Union[_common_pb2.CallError, _Mapping]] = ..., policy: _Optional[_Union[Policy, _Mapping]] = ...) -> None: ...

class ListPoliciesRequest(_message.Message):
    __slots__ = ("context", "limit", "after")
    CONTEXT_FIELD_NUMBER: _ClassVar[int]
    LIMIT_FIELD_NUMBER: _ClassVar[int]
    AFTER_FIELD_NUMBER: _ClassVar[int]
    context: _common_pb2.CallContext
    limit: int
    after: str
    def __init__(self, context: _Optional[_Union[_common_pb2.CallContext, _Mapping]] = ..., limit: _Optional[int] = ..., after: _Optional[str] = ...) -> None: ...

class ListPoliciesResponse(_message.Message):
    __slots__ = ("error", "policies", "next_after")
    ERROR_FIELD_NUMBER: _ClassVar[int]
    POLICIES_FIELD_NUMBER: _ClassVar[int]
    NEXT_AFTER_FIELD_NUMBER: _ClassVar[int]
    error: _common_pb2.CallError
    policies: _containers.RepeatedCompositeFieldContainer[Policy]
    next_after: str
    def __init__(self, error: _Optional[_Union[_common_pb2.CallError, _Mapping]] = ..., policies: _Optional[_Iterable[_Union[Policy, _Mapping]]] = ..., next_after: _Optional[str] = ...) -> None: ...

class UpdatePolicyRequest(_message.Message):
    __slots__ = ("context", "policy_id", "expected_revision", "document_json", "name", "description")
    CONTEXT_FIELD_NUMBER: _ClassVar[int]
    POLICY_ID_FIELD_NUMBER: _ClassVar[int]
    EXPECTED_REVISION_FIELD_NUMBER: _ClassVar[int]
    DOCUMENT_JSON_FIELD_NUMBER: _ClassVar[int]
    NAME_FIELD_NUMBER: _ClassVar[int]
    DESCRIPTION_FIELD_NUMBER: _ClassVar[int]
    context: _common_pb2.CallContext
    policy_id: str
    expected_revision: int
    document_json: str
    name: str
    description: str
    def __init__(self, context: _Optional[_Union[_common_pb2.CallContext, _Mapping]] = ..., policy_id: _Optional[str] = ..., expected_revision: _Optional[int] = ..., document_json: _Optional[str] = ..., name: _Optional[str] = ..., description: _Optional[str] = ...) -> None: ...

class UpdatePolicyResponse(_message.Message):
    __slots__ = ("error", "policy")
    ERROR_FIELD_NUMBER: _ClassVar[int]
    POLICY_FIELD_NUMBER: _ClassVar[int]
    error: _common_pb2.CallError
    policy: Policy
    def __init__(self, error: _Optional[_Union[_common_pb2.CallError, _Mapping]] = ..., policy: _Optional[_Union[Policy, _Mapping]] = ...) -> None: ...

class DeletePolicyRequest(_message.Message):
    __slots__ = ("context", "policy_id")
    CONTEXT_FIELD_NUMBER: _ClassVar[int]
    POLICY_ID_FIELD_NUMBER: _ClassVar[int]
    context: _common_pb2.CallContext
    policy_id: str
    def __init__(self, context: _Optional[_Union[_common_pb2.CallContext, _Mapping]] = ..., policy_id: _Optional[str] = ...) -> None: ...

class DeletePolicyResponse(_message.Message):
    __slots__ = ("error",)
    ERROR_FIELD_NUMBER: _ClassVar[int]
    error: _common_pb2.CallError
    def __init__(self, error: _Optional[_Union[_common_pb2.CallError, _Mapping]] = ...) -> None: ...

class AttachPolicyRequest(_message.Message):
    __slots__ = ("context", "policy_id", "principal_id", "scope")
    CONTEXT_FIELD_NUMBER: _ClassVar[int]
    POLICY_ID_FIELD_NUMBER: _ClassVar[int]
    PRINCIPAL_ID_FIELD_NUMBER: _ClassVar[int]
    SCOPE_FIELD_NUMBER: _ClassVar[int]
    context: _common_pb2.CallContext
    policy_id: str
    principal_id: str
    scope: str
    def __init__(self, context: _Optional[_Union[_common_pb2.CallContext, _Mapping]] = ..., policy_id: _Optional[str] = ..., principal_id: _Optional[str] = ..., scope: _Optional[str] = ...) -> None: ...

class AttachPolicyResponse(_message.Message):
    __slots__ = ("error", "attachment")
    ERROR_FIELD_NUMBER: _ClassVar[int]
    ATTACHMENT_FIELD_NUMBER: _ClassVar[int]
    error: _common_pb2.CallError
    attachment: Attachment
    def __init__(self, error: _Optional[_Union[_common_pb2.CallError, _Mapping]] = ..., attachment: _Optional[_Union[Attachment, _Mapping]] = ...) -> None: ...

class DetachPolicyRequest(_message.Message):
    __slots__ = ("context", "policy_id", "principal_id", "scope")
    CONTEXT_FIELD_NUMBER: _ClassVar[int]
    POLICY_ID_FIELD_NUMBER: _ClassVar[int]
    PRINCIPAL_ID_FIELD_NUMBER: _ClassVar[int]
    SCOPE_FIELD_NUMBER: _ClassVar[int]
    context: _common_pb2.CallContext
    policy_id: str
    principal_id: str
    scope: str
    def __init__(self, context: _Optional[_Union[_common_pb2.CallContext, _Mapping]] = ..., policy_id: _Optional[str] = ..., principal_id: _Optional[str] = ..., scope: _Optional[str] = ...) -> None: ...

class DetachPolicyResponse(_message.Message):
    __slots__ = ("error", "detached")
    ERROR_FIELD_NUMBER: _ClassVar[int]
    DETACHED_FIELD_NUMBER: _ClassVar[int]
    error: _common_pb2.CallError
    detached: bool
    def __init__(self, error: _Optional[_Union[_common_pb2.CallError, _Mapping]] = ..., detached: bool = ...) -> None: ...

class ListAttachmentsRequest(_message.Message):
    __slots__ = ("context", "principal_id", "policy_id")
    CONTEXT_FIELD_NUMBER: _ClassVar[int]
    PRINCIPAL_ID_FIELD_NUMBER: _ClassVar[int]
    POLICY_ID_FIELD_NUMBER: _ClassVar[int]
    context: _common_pb2.CallContext
    principal_id: str
    policy_id: str
    def __init__(self, context: _Optional[_Union[_common_pb2.CallContext, _Mapping]] = ..., principal_id: _Optional[str] = ..., policy_id: _Optional[str] = ...) -> None: ...

class ListAttachmentsResponse(_message.Message):
    __slots__ = ("error", "attachments")
    ERROR_FIELD_NUMBER: _ClassVar[int]
    ATTACHMENTS_FIELD_NUMBER: _ClassVar[int]
    error: _common_pb2.CallError
    attachments: _containers.RepeatedCompositeFieldContainer[Attachment]
    def __init__(self, error: _Optional[_Union[_common_pb2.CallError, _Mapping]] = ..., attachments: _Optional[_Iterable[_Union[Attachment, _Mapping]]] = ...) -> None: ...

class PutPlacementRequest(_message.Message):
    __slots__ = ("context", "placement")
    CONTEXT_FIELD_NUMBER: _ClassVar[int]
    PLACEMENT_FIELD_NUMBER: _ClassVar[int]
    context: _common_pb2.CallContext
    placement: Placement
    def __init__(self, context: _Optional[_Union[_common_pb2.CallContext, _Mapping]] = ..., placement: _Optional[_Union[Placement, _Mapping]] = ...) -> None: ...

class PutPlacementResponse(_message.Message):
    __slots__ = ("error", "placement")
    ERROR_FIELD_NUMBER: _ClassVar[int]
    PLACEMENT_FIELD_NUMBER: _ClassVar[int]
    error: _common_pb2.CallError
    placement: Placement
    def __init__(self, error: _Optional[_Union[_common_pb2.CallError, _Mapping]] = ..., placement: _Optional[_Union[Placement, _Mapping]] = ...) -> None: ...

class DeletePlacementRequest(_message.Message):
    __slots__ = ("context", "service", "id_key")
    CONTEXT_FIELD_NUMBER: _ClassVar[int]
    SERVICE_FIELD_NUMBER: _ClassVar[int]
    ID_KEY_FIELD_NUMBER: _ClassVar[int]
    context: _common_pb2.CallContext
    service: str
    id_key: str
    def __init__(self, context: _Optional[_Union[_common_pb2.CallContext, _Mapping]] = ..., service: _Optional[str] = ..., id_key: _Optional[str] = ...) -> None: ...

class DeletePlacementResponse(_message.Message):
    __slots__ = ("error", "deleted")
    ERROR_FIELD_NUMBER: _ClassVar[int]
    DELETED_FIELD_NUMBER: _ClassVar[int]
    error: _common_pb2.CallError
    deleted: bool
    def __init__(self, error: _Optional[_Union[_common_pb2.CallError, _Mapping]] = ..., deleted: bool = ...) -> None: ...

class ListPlacementsRequest(_message.Message):
    __slots__ = ("context", "service")
    CONTEXT_FIELD_NUMBER: _ClassVar[int]
    SERVICE_FIELD_NUMBER: _ClassVar[int]
    context: _common_pb2.CallContext
    service: str
    def __init__(self, context: _Optional[_Union[_common_pb2.CallContext, _Mapping]] = ..., service: _Optional[str] = ...) -> None: ...

class ListPlacementsResponse(_message.Message):
    __slots__ = ("error", "placements")
    ERROR_FIELD_NUMBER: _ClassVar[int]
    PLACEMENTS_FIELD_NUMBER: _ClassVar[int]
    error: _common_pb2.CallError
    placements: _containers.RepeatedCompositeFieldContainer[Placement]
    def __init__(self, error: _Optional[_Union[_common_pb2.CallError, _Mapping]] = ..., placements: _Optional[_Iterable[_Union[Placement, _Mapping]]] = ...) -> None: ...

class PutScopeRequest(_message.Message):
    __slots__ = ("context", "org", "workspace")
    CONTEXT_FIELD_NUMBER: _ClassVar[int]
    ORG_FIELD_NUMBER: _ClassVar[int]
    WORKSPACE_FIELD_NUMBER: _ClassVar[int]
    context: _common_pb2.CallContext
    org: str
    workspace: str
    def __init__(self, context: _Optional[_Union[_common_pb2.CallContext, _Mapping]] = ..., org: _Optional[str] = ..., workspace: _Optional[str] = ...) -> None: ...

class PutScopeResponse(_message.Message):
    __slots__ = ("error", "scope")
    ERROR_FIELD_NUMBER: _ClassVar[int]
    SCOPE_FIELD_NUMBER: _ClassVar[int]
    error: _common_pb2.CallError
    scope: Scope
    def __init__(self, error: _Optional[_Union[_common_pb2.CallError, _Mapping]] = ..., scope: _Optional[_Union[Scope, _Mapping]] = ...) -> None: ...

class DeleteScopeRequest(_message.Message):
    __slots__ = ("context", "org", "workspace")
    CONTEXT_FIELD_NUMBER: _ClassVar[int]
    ORG_FIELD_NUMBER: _ClassVar[int]
    WORKSPACE_FIELD_NUMBER: _ClassVar[int]
    context: _common_pb2.CallContext
    org: str
    workspace: str
    def __init__(self, context: _Optional[_Union[_common_pb2.CallContext, _Mapping]] = ..., org: _Optional[str] = ..., workspace: _Optional[str] = ...) -> None: ...

class DeleteScopeResponse(_message.Message):
    __slots__ = ("error", "deleted")
    ERROR_FIELD_NUMBER: _ClassVar[int]
    DELETED_FIELD_NUMBER: _ClassVar[int]
    error: _common_pb2.CallError
    deleted: bool
    def __init__(self, error: _Optional[_Union[_common_pb2.CallError, _Mapping]] = ..., deleted: bool = ...) -> None: ...

class RegisterCatalogRequest(_message.Message):
    __slots__ = ("context", "catalog")
    CONTEXT_FIELD_NUMBER: _ClassVar[int]
    CATALOG_FIELD_NUMBER: _ClassVar[int]
    context: _common_pb2.CallContext
    catalog: ActionCatalog
    def __init__(self, context: _Optional[_Union[_common_pb2.CallContext, _Mapping]] = ..., catalog: _Optional[_Union[ActionCatalog, _Mapping]] = ...) -> None: ...

class RegisterCatalogResponse(_message.Message):
    __slots__ = ("error", "registered")
    ERROR_FIELD_NUMBER: _ClassVar[int]
    REGISTERED_FIELD_NUMBER: _ClassVar[int]
    error: _common_pb2.CallError
    registered: bool
    def __init__(self, error: _Optional[_Union[_common_pb2.CallError, _Mapping]] = ..., registered: bool = ...) -> None: ...
