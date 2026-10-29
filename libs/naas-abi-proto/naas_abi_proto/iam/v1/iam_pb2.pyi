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
    __slots__ = ("id", "kind", "status", "name", "issuer", "subject", "provider", "email", "email_verified", "display_name", "owner_id", "created_at", "updated_at", "owner_scope")
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
    OWNER_ID_FIELD_NUMBER: _ClassVar[int]
    CREATED_AT_FIELD_NUMBER: _ClassVar[int]
    UPDATED_AT_FIELD_NUMBER: _ClassVar[int]
    OWNER_SCOPE_FIELD_NUMBER: _ClassVar[int]
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
    owner_id: str
    created_at: _timestamp_pb2.Timestamp
    updated_at: _timestamp_pb2.Timestamp
    owner_scope: str
    def __init__(self, id: _Optional[str] = ..., kind: _Optional[str] = ..., status: _Optional[str] = ..., name: _Optional[str] = ..., issuer: _Optional[str] = ..., subject: _Optional[str] = ..., provider: _Optional[str] = ..., email: _Optional[str] = ..., email_verified: bool = ..., display_name: _Optional[str] = ..., owner_id: _Optional[str] = ..., created_at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., updated_at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., owner_scope: _Optional[str] = ...) -> None: ...

class Policy(_message.Message):
    __slots__ = ("id", "name", "description", "document_json", "managed", "revision", "created_at", "updated_at", "owner_scope", "parent_id")
    ID_FIELD_NUMBER: _ClassVar[int]
    NAME_FIELD_NUMBER: _ClassVar[int]
    DESCRIPTION_FIELD_NUMBER: _ClassVar[int]
    DOCUMENT_JSON_FIELD_NUMBER: _ClassVar[int]
    MANAGED_FIELD_NUMBER: _ClassVar[int]
    REVISION_FIELD_NUMBER: _ClassVar[int]
    CREATED_AT_FIELD_NUMBER: _ClassVar[int]
    UPDATED_AT_FIELD_NUMBER: _ClassVar[int]
    OWNER_SCOPE_FIELD_NUMBER: _ClassVar[int]
    PARENT_ID_FIELD_NUMBER: _ClassVar[int]
    id: str
    name: str
    description: str
    document_json: str
    managed: bool
    revision: int
    created_at: _timestamp_pb2.Timestamp
    updated_at: _timestamp_pb2.Timestamp
    owner_scope: str
    parent_id: str
    def __init__(self, id: _Optional[str] = ..., name: _Optional[str] = ..., description: _Optional[str] = ..., document_json: _Optional[str] = ..., managed: bool = ..., revision: _Optional[int] = ..., created_at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., updated_at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., owner_scope: _Optional[str] = ..., parent_id: _Optional[str] = ...) -> None: ...

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

class PendingGrant(_message.Message):
    __slots__ = ("id", "provider", "email", "policy_id", "scope", "created_by", "created_at")
    ID_FIELD_NUMBER: _ClassVar[int]
    PROVIDER_FIELD_NUMBER: _ClassVar[int]
    EMAIL_FIELD_NUMBER: _ClassVar[int]
    POLICY_ID_FIELD_NUMBER: _ClassVar[int]
    SCOPE_FIELD_NUMBER: _ClassVar[int]
    CREATED_BY_FIELD_NUMBER: _ClassVar[int]
    CREATED_AT_FIELD_NUMBER: _ClassVar[int]
    id: str
    provider: str
    email: str
    policy_id: str
    scope: str
    created_by: str
    created_at: _timestamp_pb2.Timestamp
    def __init__(self, id: _Optional[str] = ..., provider: _Optional[str] = ..., email: _Optional[str] = ..., policy_id: _Optional[str] = ..., scope: _Optional[str] = ..., created_by: _Optional[str] = ..., created_at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ...) -> None: ...

class IdpBinding(_message.Message):
    __slots__ = ("provider", "claim_value", "group_id", "policy_id", "scope", "attachment_id")
    PROVIDER_FIELD_NUMBER: _ClassVar[int]
    CLAIM_VALUE_FIELD_NUMBER: _ClassVar[int]
    GROUP_ID_FIELD_NUMBER: _ClassVar[int]
    POLICY_ID_FIELD_NUMBER: _ClassVar[int]
    SCOPE_FIELD_NUMBER: _ClassVar[int]
    ATTACHMENT_ID_FIELD_NUMBER: _ClassVar[int]
    provider: str
    claim_value: str
    group_id: str
    policy_id: str
    scope: str
    attachment_id: str
    def __init__(self, provider: _Optional[str] = ..., claim_value: _Optional[str] = ..., group_id: _Optional[str] = ..., policy_id: _Optional[str] = ..., scope: _Optional[str] = ..., attachment_id: _Optional[str] = ...) -> None: ...

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
    __slots__ = ("service", "id_key", "container")
    SERVICE_FIELD_NUMBER: _ClassVar[int]
    ID_KEY_FIELD_NUMBER: _ClassVar[int]
    CONTAINER_FIELD_NUMBER: _ClassVar[int]
    service: str
    id_key: str
    container: str
    def __init__(self, service: _Optional[str] = ..., id_key: _Optional[str] = ..., container: _Optional[str] = ...) -> None: ...

class Container(_message.Message):
    __slots__ = ("service", "type", "id", "parent", "name")
    SERVICE_FIELD_NUMBER: _ClassVar[int]
    TYPE_FIELD_NUMBER: _ClassVar[int]
    ID_FIELD_NUMBER: _ClassVar[int]
    PARENT_FIELD_NUMBER: _ClassVar[int]
    NAME_FIELD_NUMBER: _ClassVar[int]
    service: str
    type: str
    id: str
    parent: str
    name: str
    def __init__(self, service: _Optional[str] = ..., type: _Optional[str] = ..., id: _Optional[str] = ..., parent: _Optional[str] = ..., name: _Optional[str] = ...) -> None: ...

class ResourceType(_message.Message):
    __slots__ = ("name", "id", "placement", "id_prefix", "personal", "description", "module_scope", "policy_only", "container", "platform_companions", "parents")
    NAME_FIELD_NUMBER: _ClassVar[int]
    ID_FIELD_NUMBER: _ClassVar[int]
    PLACEMENT_FIELD_NUMBER: _ClassVar[int]
    ID_PREFIX_FIELD_NUMBER: _ClassVar[int]
    PERSONAL_FIELD_NUMBER: _ClassVar[int]
    DESCRIPTION_FIELD_NUMBER: _ClassVar[int]
    MODULE_SCOPE_FIELD_NUMBER: _ClassVar[int]
    POLICY_ONLY_FIELD_NUMBER: _ClassVar[int]
    CONTAINER_FIELD_NUMBER: _ClassVar[int]
    PLATFORM_COMPANIONS_FIELD_NUMBER: _ClassVar[int]
    PARENTS_FIELD_NUMBER: _ClassVar[int]
    name: str
    id: str
    placement: str
    id_prefix: bool
    personal: bool
    description: str
    module_scope: bool
    policy_only: bool
    container: bool
    platform_companions: bool
    parents: _containers.RepeatedScalarFieldContainer[str]
    def __init__(self, name: _Optional[str] = ..., id: _Optional[str] = ..., placement: _Optional[str] = ..., id_prefix: bool = ..., personal: bool = ..., description: _Optional[str] = ..., module_scope: bool = ..., policy_only: bool = ..., container: bool = ..., platform_companions: bool = ..., parents: _Optional[_Iterable[str]] = ...) -> None: ...

class ActionSpec(_message.Message):
    __slots__ = ("name", "level", "resource_types", "creates", "subjects", "description", "owner_only", "deletes")
    NAME_FIELD_NUMBER: _ClassVar[int]
    LEVEL_FIELD_NUMBER: _ClassVar[int]
    RESOURCE_TYPES_FIELD_NUMBER: _ClassVar[int]
    CREATES_FIELD_NUMBER: _ClassVar[int]
    SUBJECTS_FIELD_NUMBER: _ClassVar[int]
    DESCRIPTION_FIELD_NUMBER: _ClassVar[int]
    OWNER_ONLY_FIELD_NUMBER: _ClassVar[int]
    DELETES_FIELD_NUMBER: _ClassVar[int]
    name: str
    level: str
    resource_types: _containers.RepeatedScalarFieldContainer[str]
    creates: bool
    subjects: _containers.RepeatedScalarFieldContainer[str]
    description: str
    owner_only: bool
    deletes: bool
    def __init__(self, name: _Optional[str] = ..., level: _Optional[str] = ..., resource_types: _Optional[_Iterable[str]] = ..., creates: bool = ..., subjects: _Optional[_Iterable[str]] = ..., description: _Optional[str] = ..., owner_only: bool = ..., deletes: bool = ...) -> None: ...

class PlatformAccess(_message.Message):
    __slots__ = ("resources", "viewer", "member", "self")
    RESOURCES_FIELD_NUMBER: _ClassVar[int]
    VIEWER_FIELD_NUMBER: _ClassVar[int]
    MEMBER_FIELD_NUMBER: _ClassVar[int]
    SELF_FIELD_NUMBER: _ClassVar[int]
    resources: _containers.RepeatedScalarFieldContainer[str]
    viewer: _containers.RepeatedScalarFieldContainer[str]
    member: _containers.RepeatedScalarFieldContainer[str]
    self: _containers.RepeatedScalarFieldContainer[str]
    def __init__(self_, resources: _Optional[_Iterable[str]] = ..., viewer: _Optional[_Iterable[str]] = ..., member: _Optional[_Iterable[str]] = ..., self: _Optional[_Iterable[str]] = ...) -> None: ...

class ActionCatalog(_message.Message):
    __slots__ = ("service", "version", "resource_types", "actions", "module", "platform_access", "format")
    SERVICE_FIELD_NUMBER: _ClassVar[int]
    VERSION_FIELD_NUMBER: _ClassVar[int]
    RESOURCE_TYPES_FIELD_NUMBER: _ClassVar[int]
    ACTIONS_FIELD_NUMBER: _ClassVar[int]
    MODULE_FIELD_NUMBER: _ClassVar[int]
    PLATFORM_ACCESS_FIELD_NUMBER: _ClassVar[int]
    FORMAT_FIELD_NUMBER: _ClassVar[int]
    service: str
    version: int
    resource_types: _containers.RepeatedCompositeFieldContainer[ResourceType]
    actions: _containers.RepeatedCompositeFieldContainer[ActionSpec]
    module: str
    platform_access: _containers.RepeatedCompositeFieldContainer[PlatformAccess]
    format: int
    def __init__(self, service: _Optional[str] = ..., version: _Optional[int] = ..., resource_types: _Optional[_Iterable[_Union[ResourceType, _Mapping]]] = ..., actions: _Optional[_Iterable[_Union[ActionSpec, _Mapping]]] = ..., module: _Optional[str] = ..., platform_access: _Optional[_Iterable[_Union[PlatformAccess, _Mapping]]] = ..., format: _Optional[int] = ...) -> None: ...

class Decision(_message.Message):
    __slots__ = ("allowed", "visible", "reason")
    ALLOWED_FIELD_NUMBER: _ClassVar[int]
    VISIBLE_FIELD_NUMBER: _ClassVar[int]
    REASON_FIELD_NUMBER: _ClassVar[int]
    allowed: bool
    visible: bool
    reason: str
    def __init__(self, allowed: bool = ..., visible: bool = ..., reason: _Optional[str] = ...) -> None: ...

class BoundingStatement(_message.Message):
    __slots__ = ("policy_id", "statement_index", "sid")
    POLICY_ID_FIELD_NUMBER: _ClassVar[int]
    STATEMENT_INDEX_FIELD_NUMBER: _ClassVar[int]
    SID_FIELD_NUMBER: _ClassVar[int]
    policy_id: str
    statement_index: int
    sid: str
    def __init__(self, policy_id: _Optional[str] = ..., statement_index: _Optional[int] = ..., sid: _Optional[str] = ...) -> None: ...

class DecidingStatement(_message.Message):
    __slots__ = ("side", "principal_id", "effect", "policy_id", "statement_index", "sid", "attachment_id", "scope", "via_group", "bounded_by", "through")
    SIDE_FIELD_NUMBER: _ClassVar[int]
    PRINCIPAL_ID_FIELD_NUMBER: _ClassVar[int]
    EFFECT_FIELD_NUMBER: _ClassVar[int]
    POLICY_ID_FIELD_NUMBER: _ClassVar[int]
    STATEMENT_INDEX_FIELD_NUMBER: _ClassVar[int]
    SID_FIELD_NUMBER: _ClassVar[int]
    ATTACHMENT_ID_FIELD_NUMBER: _ClassVar[int]
    SCOPE_FIELD_NUMBER: _ClassVar[int]
    VIA_GROUP_FIELD_NUMBER: _ClassVar[int]
    BOUNDED_BY_FIELD_NUMBER: _ClassVar[int]
    THROUGH_FIELD_NUMBER: _ClassVar[int]
    side: str
    principal_id: str
    effect: str
    policy_id: str
    statement_index: int
    sid: str
    attachment_id: str
    scope: str
    via_group: str
    bounded_by: _containers.RepeatedCompositeFieldContainer[BoundingStatement]
    through: _containers.RepeatedScalarFieldContainer[str]
    def __init__(self, side: _Optional[str] = ..., principal_id: _Optional[str] = ..., effect: _Optional[str] = ..., policy_id: _Optional[str] = ..., statement_index: _Optional[int] = ..., sid: _Optional[str] = ..., attachment_id: _Optional[str] = ..., scope: _Optional[str] = ..., via_group: _Optional[str] = ..., bounded_by: _Optional[_Iterable[_Union[BoundingStatement, _Mapping]]] = ..., through: _Optional[_Iterable[str]] = ...) -> None: ...

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

class Key(_message.Message):
    __slots__ = ("key_id", "principal_id", "kind", "description", "created_at", "expires_at", "last_used_at", "revoked_at", "audience", "resource", "scope_json")
    KEY_ID_FIELD_NUMBER: _ClassVar[int]
    PRINCIPAL_ID_FIELD_NUMBER: _ClassVar[int]
    KIND_FIELD_NUMBER: _ClassVar[int]
    DESCRIPTION_FIELD_NUMBER: _ClassVar[int]
    CREATED_AT_FIELD_NUMBER: _ClassVar[int]
    EXPIRES_AT_FIELD_NUMBER: _ClassVar[int]
    LAST_USED_AT_FIELD_NUMBER: _ClassVar[int]
    REVOKED_AT_FIELD_NUMBER: _ClassVar[int]
    AUDIENCE_FIELD_NUMBER: _ClassVar[int]
    RESOURCE_FIELD_NUMBER: _ClassVar[int]
    SCOPE_JSON_FIELD_NUMBER: _ClassVar[int]
    key_id: str
    principal_id: str
    kind: str
    description: str
    created_at: _timestamp_pb2.Timestamp
    expires_at: _timestamp_pb2.Timestamp
    last_used_at: _timestamp_pb2.Timestamp
    revoked_at: _timestamp_pb2.Timestamp
    audience: str
    resource: str
    scope_json: str
    def __init__(self, key_id: _Optional[str] = ..., principal_id: _Optional[str] = ..., kind: _Optional[str] = ..., description: _Optional[str] = ..., created_at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., expires_at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., last_used_at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., revoked_at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., audience: _Optional[str] = ..., resource: _Optional[str] = ..., scope_json: _Optional[str] = ...) -> None: ...

class Manifest(_message.Message):
    __slots__ = ("principal_id", "sha256", "module_id", "project", "document_json", "status", "submitted_at", "decided_at", "decided_by", "reason")
    PRINCIPAL_ID_FIELD_NUMBER: _ClassVar[int]
    SHA256_FIELD_NUMBER: _ClassVar[int]
    MODULE_ID_FIELD_NUMBER: _ClassVar[int]
    PROJECT_FIELD_NUMBER: _ClassVar[int]
    DOCUMENT_JSON_FIELD_NUMBER: _ClassVar[int]
    STATUS_FIELD_NUMBER: _ClassVar[int]
    SUBMITTED_AT_FIELD_NUMBER: _ClassVar[int]
    DECIDED_AT_FIELD_NUMBER: _ClassVar[int]
    DECIDED_BY_FIELD_NUMBER: _ClassVar[int]
    REASON_FIELD_NUMBER: _ClassVar[int]
    principal_id: str
    sha256: str
    module_id: str
    project: str
    document_json: str
    status: str
    submitted_at: _timestamp_pb2.Timestamp
    decided_at: _timestamp_pb2.Timestamp
    decided_by: str
    reason: str
    def __init__(self, principal_id: _Optional[str] = ..., sha256: _Optional[str] = ..., module_id: _Optional[str] = ..., project: _Optional[str] = ..., document_json: _Optional[str] = ..., status: _Optional[str] = ..., submitted_at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., decided_at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., decided_by: _Optional[str] = ..., reason: _Optional[str] = ...) -> None: ...

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

class AuthorizeDeclaredRequest(_message.Message):
    __slots__ = ("context", "action", "resource_type", "parts", "container")
    CONTEXT_FIELD_NUMBER: _ClassVar[int]
    ACTION_FIELD_NUMBER: _ClassVar[int]
    RESOURCE_TYPE_FIELD_NUMBER: _ClassVar[int]
    PARTS_FIELD_NUMBER: _ClassVar[int]
    CONTAINER_FIELD_NUMBER: _ClassVar[int]
    context: _common_pb2.CallContext
    action: str
    resource_type: str
    parts: _containers.RepeatedScalarFieldContainer[str]
    container: str
    def __init__(self, context: _Optional[_Union[_common_pb2.CallContext, _Mapping]] = ..., action: _Optional[str] = ..., resource_type: _Optional[str] = ..., parts: _Optional[_Iterable[str]] = ..., container: _Optional[str] = ...) -> None: ...

class AuthorizeDeclaredResponse(_message.Message):
    __slots__ = ("error", "decision", "resource")
    ERROR_FIELD_NUMBER: _ClassVar[int]
    DECISION_FIELD_NUMBER: _ClassVar[int]
    RESOURCE_FIELD_NUMBER: _ClassVar[int]
    error: _common_pb2.CallError
    decision: Decision
    resource: str
    def __init__(self, error: _Optional[_Union[_common_pb2.CallError, _Mapping]] = ..., decision: _Optional[_Union[Decision, _Mapping]] = ..., resource: _Optional[str] = ...) -> None: ...

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

class GrantableAction(_message.Message):
    __slots__ = ("action", "resources", "excluded")
    ACTION_FIELD_NUMBER: _ClassVar[int]
    RESOURCES_FIELD_NUMBER: _ClassVar[int]
    EXCLUDED_FIELD_NUMBER: _ClassVar[int]
    action: str
    resources: _containers.RepeatedScalarFieldContainer[str]
    excluded: _containers.RepeatedScalarFieldContainer[str]
    def __init__(self, action: _Optional[str] = ..., resources: _Optional[_Iterable[str]] = ..., excluded: _Optional[_Iterable[str]] = ...) -> None: ...

class GrantableCatalog(_message.Message):
    __slots__ = ("service", "actions")
    SERVICE_FIELD_NUMBER: _ClassVar[int]
    ACTIONS_FIELD_NUMBER: _ClassVar[int]
    service: str
    actions: _containers.RepeatedCompositeFieldContainer[GrantableAction]
    def __init__(self, service: _Optional[str] = ..., actions: _Optional[_Iterable[_Union[GrantableAction, _Mapping]]] = ...) -> None: ...

class GrantableRequest(_message.Message):
    __slots__ = ("context", "scope")
    CONTEXT_FIELD_NUMBER: _ClassVar[int]
    SCOPE_FIELD_NUMBER: _ClassVar[int]
    context: _common_pb2.CallContext
    scope: str
    def __init__(self, context: _Optional[_Union[_common_pb2.CallContext, _Mapping]] = ..., scope: _Optional[str] = ...) -> None: ...

class GrantableResponse(_message.Message):
    __slots__ = ("error", "catalogs")
    ERROR_FIELD_NUMBER: _ClassVar[int]
    CATALOGS_FIELD_NUMBER: _ClassVar[int]
    error: _common_pb2.CallError
    catalogs: _containers.RepeatedCompositeFieldContainer[GrantableCatalog]
    def __init__(self, error: _Optional[_Union[_common_pb2.CallError, _Mapping]] = ..., catalogs: _Optional[_Iterable[_Union[GrantableCatalog, _Mapping]]] = ...) -> None: ...

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
    __slots__ = ("context", "name", "scope")
    CONTEXT_FIELD_NUMBER: _ClassVar[int]
    NAME_FIELD_NUMBER: _ClassVar[int]
    SCOPE_FIELD_NUMBER: _ClassVar[int]
    context: _common_pb2.CallContext
    name: str
    scope: str
    def __init__(self, context: _Optional[_Union[_common_pb2.CallContext, _Mapping]] = ..., name: _Optional[str] = ..., scope: _Optional[str] = ...) -> None: ...

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
    __slots__ = ("context", "limit", "after", "scope")
    CONTEXT_FIELD_NUMBER: _ClassVar[int]
    LIMIT_FIELD_NUMBER: _ClassVar[int]
    AFTER_FIELD_NUMBER: _ClassVar[int]
    SCOPE_FIELD_NUMBER: _ClassVar[int]
    context: _common_pb2.CallContext
    limit: int
    after: str
    scope: str
    def __init__(self, context: _Optional[_Union[_common_pb2.CallContext, _Mapping]] = ..., limit: _Optional[int] = ..., after: _Optional[str] = ..., scope: _Optional[str] = ...) -> None: ...

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
    __slots__ = ("context", "name", "document_json", "description", "scope", "parent")
    CONTEXT_FIELD_NUMBER: _ClassVar[int]
    NAME_FIELD_NUMBER: _ClassVar[int]
    DOCUMENT_JSON_FIELD_NUMBER: _ClassVar[int]
    DESCRIPTION_FIELD_NUMBER: _ClassVar[int]
    SCOPE_FIELD_NUMBER: _ClassVar[int]
    PARENT_FIELD_NUMBER: _ClassVar[int]
    context: _common_pb2.CallContext
    name: str
    document_json: str
    description: str
    scope: str
    parent: str
    def __init__(self, context: _Optional[_Union[_common_pb2.CallContext, _Mapping]] = ..., name: _Optional[str] = ..., document_json: _Optional[str] = ..., description: _Optional[str] = ..., scope: _Optional[str] = ..., parent: _Optional[str] = ...) -> None: ...

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
    __slots__ = ("context", "limit", "after", "scope")
    CONTEXT_FIELD_NUMBER: _ClassVar[int]
    LIMIT_FIELD_NUMBER: _ClassVar[int]
    AFTER_FIELD_NUMBER: _ClassVar[int]
    SCOPE_FIELD_NUMBER: _ClassVar[int]
    context: _common_pb2.CallContext
    limit: int
    after: str
    scope: str
    def __init__(self, context: _Optional[_Union[_common_pb2.CallContext, _Mapping]] = ..., limit: _Optional[int] = ..., after: _Optional[str] = ..., scope: _Optional[str] = ...) -> None: ...

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
    __slots__ = ("context", "policy_id", "expected_revision", "document_json", "name", "description", "parent")
    CONTEXT_FIELD_NUMBER: _ClassVar[int]
    POLICY_ID_FIELD_NUMBER: _ClassVar[int]
    EXPECTED_REVISION_FIELD_NUMBER: _ClassVar[int]
    DOCUMENT_JSON_FIELD_NUMBER: _ClassVar[int]
    NAME_FIELD_NUMBER: _ClassVar[int]
    DESCRIPTION_FIELD_NUMBER: _ClassVar[int]
    PARENT_FIELD_NUMBER: _ClassVar[int]
    context: _common_pb2.CallContext
    policy_id: str
    expected_revision: int
    document_json: str
    name: str
    description: str
    parent: str
    def __init__(self, context: _Optional[_Union[_common_pb2.CallContext, _Mapping]] = ..., policy_id: _Optional[str] = ..., expected_revision: _Optional[int] = ..., document_json: _Optional[str] = ..., name: _Optional[str] = ..., description: _Optional[str] = ..., parent: _Optional[str] = ...) -> None: ...

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

class ListSubPoliciesRequest(_message.Message):
    __slots__ = ("context", "policy_id")
    CONTEXT_FIELD_NUMBER: _ClassVar[int]
    POLICY_ID_FIELD_NUMBER: _ClassVar[int]
    context: _common_pb2.CallContext
    policy_id: str
    def __init__(self, context: _Optional[_Union[_common_pb2.CallContext, _Mapping]] = ..., policy_id: _Optional[str] = ...) -> None: ...

class ListSubPoliciesResponse(_message.Message):
    __slots__ = ("error", "policies")
    ERROR_FIELD_NUMBER: _ClassVar[int]
    POLICIES_FIELD_NUMBER: _ClassVar[int]
    error: _common_pb2.CallError
    policies: _containers.RepeatedCompositeFieldContainer[Policy]
    def __init__(self, error: _Optional[_Union[_common_pb2.CallError, _Mapping]] = ..., policies: _Optional[_Iterable[_Union[Policy, _Mapping]]] = ...) -> None: ...

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

class RegisterContainerRequest(_message.Message):
    __slots__ = ("context", "service", "type", "id", "parent")
    CONTEXT_FIELD_NUMBER: _ClassVar[int]
    SERVICE_FIELD_NUMBER: _ClassVar[int]
    TYPE_FIELD_NUMBER: _ClassVar[int]
    ID_FIELD_NUMBER: _ClassVar[int]
    PARENT_FIELD_NUMBER: _ClassVar[int]
    context: _common_pb2.CallContext
    service: str
    type: str
    id: str
    parent: str
    def __init__(self, context: _Optional[_Union[_common_pb2.CallContext, _Mapping]] = ..., service: _Optional[str] = ..., type: _Optional[str] = ..., id: _Optional[str] = ..., parent: _Optional[str] = ...) -> None: ...

class RegisterContainerResponse(_message.Message):
    __slots__ = ("error", "container")
    ERROR_FIELD_NUMBER: _ClassVar[int]
    CONTAINER_FIELD_NUMBER: _ClassVar[int]
    error: _common_pb2.CallError
    container: Container
    def __init__(self, error: _Optional[_Union[_common_pb2.CallError, _Mapping]] = ..., container: _Optional[_Union[Container, _Mapping]] = ...) -> None: ...

class DeleteContainerRequest(_message.Message):
    __slots__ = ("context", "service", "type", "id")
    CONTEXT_FIELD_NUMBER: _ClassVar[int]
    SERVICE_FIELD_NUMBER: _ClassVar[int]
    TYPE_FIELD_NUMBER: _ClassVar[int]
    ID_FIELD_NUMBER: _ClassVar[int]
    context: _common_pb2.CallContext
    service: str
    type: str
    id: str
    def __init__(self, context: _Optional[_Union[_common_pb2.CallContext, _Mapping]] = ..., service: _Optional[str] = ..., type: _Optional[str] = ..., id: _Optional[str] = ...) -> None: ...

class DeleteContainerResponse(_message.Message):
    __slots__ = ("error", "deleted")
    ERROR_FIELD_NUMBER: _ClassVar[int]
    DELETED_FIELD_NUMBER: _ClassVar[int]
    error: _common_pb2.CallError
    deleted: bool
    def __init__(self, error: _Optional[_Union[_common_pb2.CallError, _Mapping]] = ..., deleted: bool = ...) -> None: ...

class GetContainerRequest(_message.Message):
    __slots__ = ("context", "service", "type", "id")
    CONTEXT_FIELD_NUMBER: _ClassVar[int]
    SERVICE_FIELD_NUMBER: _ClassVar[int]
    TYPE_FIELD_NUMBER: _ClassVar[int]
    ID_FIELD_NUMBER: _ClassVar[int]
    context: _common_pb2.CallContext
    service: str
    type: str
    id: str
    def __init__(self, context: _Optional[_Union[_common_pb2.CallContext, _Mapping]] = ..., service: _Optional[str] = ..., type: _Optional[str] = ..., id: _Optional[str] = ...) -> None: ...

class GetContainerResponse(_message.Message):
    __slots__ = ("error", "name")
    ERROR_FIELD_NUMBER: _ClassVar[int]
    NAME_FIELD_NUMBER: _ClassVar[int]
    error: _common_pb2.CallError
    name: str
    def __init__(self, error: _Optional[_Union[_common_pb2.CallError, _Mapping]] = ..., name: _Optional[str] = ...) -> None: ...

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

class TokenRequest(_message.Message):
    __slots__ = ("context", "key", "audience")
    CONTEXT_FIELD_NUMBER: _ClassVar[int]
    KEY_FIELD_NUMBER: _ClassVar[int]
    AUDIENCE_FIELD_NUMBER: _ClassVar[int]
    context: _common_pb2.CallContext
    key: str
    audience: str
    def __init__(self, context: _Optional[_Union[_common_pb2.CallContext, _Mapping]] = ..., key: _Optional[str] = ..., audience: _Optional[str] = ...) -> None: ...

class TokenResponse(_message.Message):
    __slots__ = ("error", "access_token", "expires_in", "principal_id", "name")
    ERROR_FIELD_NUMBER: _ClassVar[int]
    ACCESS_TOKEN_FIELD_NUMBER: _ClassVar[int]
    EXPIRES_IN_FIELD_NUMBER: _ClassVar[int]
    PRINCIPAL_ID_FIELD_NUMBER: _ClassVar[int]
    NAME_FIELD_NUMBER: _ClassVar[int]
    error: _common_pb2.CallError
    access_token: str
    expires_in: int
    principal_id: str
    name: str
    def __init__(self, error: _Optional[_Union[_common_pb2.CallError, _Mapping]] = ..., access_token: _Optional[str] = ..., expires_in: _Optional[int] = ..., principal_id: _Optional[str] = ..., name: _Optional[str] = ...) -> None: ...

class JwksRequest(_message.Message):
    __slots__ = ("context",)
    CONTEXT_FIELD_NUMBER: _ClassVar[int]
    context: _common_pb2.CallContext
    def __init__(self, context: _Optional[_Union[_common_pb2.CallContext, _Mapping]] = ...) -> None: ...

class JwksResponse(_message.Message):
    __slots__ = ("error", "jwks_json")
    ERROR_FIELD_NUMBER: _ClassVar[int]
    JWKS_JSON_FIELD_NUMBER: _ClassVar[int]
    error: _common_pb2.CallError
    jwks_json: str
    def __init__(self, error: _Optional[_Union[_common_pb2.CallError, _Mapping]] = ..., jwks_json: _Optional[str] = ...) -> None: ...

class ExchangeTokenRequest(_message.Message):
    __slots__ = ("context", "grant_type", "subject_token", "subject_token_type", "audience", "resource", "scope_json", "groups", "session_id", "ttl_seconds")
    CONTEXT_FIELD_NUMBER: _ClassVar[int]
    GRANT_TYPE_FIELD_NUMBER: _ClassVar[int]
    SUBJECT_TOKEN_FIELD_NUMBER: _ClassVar[int]
    SUBJECT_TOKEN_TYPE_FIELD_NUMBER: _ClassVar[int]
    AUDIENCE_FIELD_NUMBER: _ClassVar[int]
    RESOURCE_FIELD_NUMBER: _ClassVar[int]
    SCOPE_JSON_FIELD_NUMBER: _ClassVar[int]
    GROUPS_FIELD_NUMBER: _ClassVar[int]
    SESSION_ID_FIELD_NUMBER: _ClassVar[int]
    TTL_SECONDS_FIELD_NUMBER: _ClassVar[int]
    context: _common_pb2.CallContext
    grant_type: str
    subject_token: str
    subject_token_type: str
    audience: str
    resource: str
    scope_json: str
    groups: _containers.RepeatedScalarFieldContainer[str]
    session_id: str
    ttl_seconds: int
    def __init__(self, context: _Optional[_Union[_common_pb2.CallContext, _Mapping]] = ..., grant_type: _Optional[str] = ..., subject_token: _Optional[str] = ..., subject_token_type: _Optional[str] = ..., audience: _Optional[str] = ..., resource: _Optional[str] = ..., scope_json: _Optional[str] = ..., groups: _Optional[_Iterable[str]] = ..., session_id: _Optional[str] = ..., ttl_seconds: _Optional[int] = ...) -> None: ...

class ExchangeTokenResponse(_message.Message):
    __slots__ = ("error", "access_token", "issued_token_type", "token_type", "expires_in", "audience", "principal_id")
    ERROR_FIELD_NUMBER: _ClassVar[int]
    ACCESS_TOKEN_FIELD_NUMBER: _ClassVar[int]
    ISSUED_TOKEN_TYPE_FIELD_NUMBER: _ClassVar[int]
    TOKEN_TYPE_FIELD_NUMBER: _ClassVar[int]
    EXPIRES_IN_FIELD_NUMBER: _ClassVar[int]
    AUDIENCE_FIELD_NUMBER: _ClassVar[int]
    PRINCIPAL_ID_FIELD_NUMBER: _ClassVar[int]
    error: _common_pb2.CallError
    access_token: str
    issued_token_type: str
    token_type: str
    expires_in: int
    audience: str
    principal_id: str
    def __init__(self, error: _Optional[_Union[_common_pb2.CallError, _Mapping]] = ..., access_token: _Optional[str] = ..., issued_token_type: _Optional[str] = ..., token_type: _Optional[str] = ..., expires_in: _Optional[int] = ..., audience: _Optional[str] = ..., principal_id: _Optional[str] = ...) -> None: ...

class RevokeTokensRequest(_message.Message):
    __slots__ = ("context", "principal_id", "include_keys")
    CONTEXT_FIELD_NUMBER: _ClassVar[int]
    PRINCIPAL_ID_FIELD_NUMBER: _ClassVar[int]
    INCLUDE_KEYS_FIELD_NUMBER: _ClassVar[int]
    context: _common_pb2.CallContext
    principal_id: str
    include_keys: bool
    def __init__(self, context: _Optional[_Union[_common_pb2.CallContext, _Mapping]] = ..., principal_id: _Optional[str] = ..., include_keys: bool = ...) -> None: ...

class RevokeTokensResponse(_message.Message):
    __slots__ = ("error",)
    ERROR_FIELD_NUMBER: _ClassVar[int]
    error: _common_pb2.CallError
    def __init__(self, error: _Optional[_Union[_common_pb2.CallError, _Mapping]] = ...) -> None: ...

class FindServiceAccountRequest(_message.Message):
    __slots__ = ("context", "name")
    CONTEXT_FIELD_NUMBER: _ClassVar[int]
    NAME_FIELD_NUMBER: _ClassVar[int]
    context: _common_pb2.CallContext
    name: str
    def __init__(self, context: _Optional[_Union[_common_pb2.CallContext, _Mapping]] = ..., name: _Optional[str] = ...) -> None: ...

class FindServiceAccountResponse(_message.Message):
    __slots__ = ("error", "principal")
    ERROR_FIELD_NUMBER: _ClassVar[int]
    PRINCIPAL_FIELD_NUMBER: _ClassVar[int]
    error: _common_pb2.CallError
    principal: Principal
    def __init__(self, error: _Optional[_Union[_common_pb2.CallError, _Mapping]] = ..., principal: _Optional[_Union[Principal, _Mapping]] = ...) -> None: ...

class CreateKeyRequest(_message.Message):
    __slots__ = ("context", "principal_id", "description", "expires_at", "kind", "audience", "resource", "scope_json")
    CONTEXT_FIELD_NUMBER: _ClassVar[int]
    PRINCIPAL_ID_FIELD_NUMBER: _ClassVar[int]
    DESCRIPTION_FIELD_NUMBER: _ClassVar[int]
    EXPIRES_AT_FIELD_NUMBER: _ClassVar[int]
    KIND_FIELD_NUMBER: _ClassVar[int]
    AUDIENCE_FIELD_NUMBER: _ClassVar[int]
    RESOURCE_FIELD_NUMBER: _ClassVar[int]
    SCOPE_JSON_FIELD_NUMBER: _ClassVar[int]
    context: _common_pb2.CallContext
    principal_id: str
    description: str
    expires_at: _timestamp_pb2.Timestamp
    kind: str
    audience: str
    resource: str
    scope_json: str
    def __init__(self, context: _Optional[_Union[_common_pb2.CallContext, _Mapping]] = ..., principal_id: _Optional[str] = ..., description: _Optional[str] = ..., expires_at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., kind: _Optional[str] = ..., audience: _Optional[str] = ..., resource: _Optional[str] = ..., scope_json: _Optional[str] = ...) -> None: ...

class CreateKeyResponse(_message.Message):
    __slots__ = ("error", "key", "value")
    ERROR_FIELD_NUMBER: _ClassVar[int]
    KEY_FIELD_NUMBER: _ClassVar[int]
    VALUE_FIELD_NUMBER: _ClassVar[int]
    error: _common_pb2.CallError
    key: Key
    value: str
    def __init__(self, error: _Optional[_Union[_common_pb2.CallError, _Mapping]] = ..., key: _Optional[_Union[Key, _Mapping]] = ..., value: _Optional[str] = ...) -> None: ...

class ListKeysRequest(_message.Message):
    __slots__ = ("context", "principal_id")
    CONTEXT_FIELD_NUMBER: _ClassVar[int]
    PRINCIPAL_ID_FIELD_NUMBER: _ClassVar[int]
    context: _common_pb2.CallContext
    principal_id: str
    def __init__(self, context: _Optional[_Union[_common_pb2.CallContext, _Mapping]] = ..., principal_id: _Optional[str] = ...) -> None: ...

class ListKeysResponse(_message.Message):
    __slots__ = ("error", "keys")
    ERROR_FIELD_NUMBER: _ClassVar[int]
    KEYS_FIELD_NUMBER: _ClassVar[int]
    error: _common_pb2.CallError
    keys: _containers.RepeatedCompositeFieldContainer[Key]
    def __init__(self, error: _Optional[_Union[_common_pb2.CallError, _Mapping]] = ..., keys: _Optional[_Iterable[_Union[Key, _Mapping]]] = ...) -> None: ...

class RevokeKeyRequest(_message.Message):
    __slots__ = ("context", "principal_id", "key_id")
    CONTEXT_FIELD_NUMBER: _ClassVar[int]
    PRINCIPAL_ID_FIELD_NUMBER: _ClassVar[int]
    KEY_ID_FIELD_NUMBER: _ClassVar[int]
    context: _common_pb2.CallContext
    principal_id: str
    key_id: str
    def __init__(self, context: _Optional[_Union[_common_pb2.CallContext, _Mapping]] = ..., principal_id: _Optional[str] = ..., key_id: _Optional[str] = ...) -> None: ...

class RevokeKeyResponse(_message.Message):
    __slots__ = ("error", "key")
    ERROR_FIELD_NUMBER: _ClassVar[int]
    KEY_FIELD_NUMBER: _ClassVar[int]
    error: _common_pb2.CallError
    key: Key
    def __init__(self, error: _Optional[_Union[_common_pb2.CallError, _Mapping]] = ..., key: _Optional[_Union[Key, _Mapping]] = ...) -> None: ...

class SubmitManifestRequest(_message.Message):
    __slots__ = ("context", "module_id", "project", "document_json")
    CONTEXT_FIELD_NUMBER: _ClassVar[int]
    MODULE_ID_FIELD_NUMBER: _ClassVar[int]
    PROJECT_FIELD_NUMBER: _ClassVar[int]
    DOCUMENT_JSON_FIELD_NUMBER: _ClassVar[int]
    context: _common_pb2.CallContext
    module_id: str
    project: str
    document_json: str
    def __init__(self, context: _Optional[_Union[_common_pb2.CallContext, _Mapping]] = ..., module_id: _Optional[str] = ..., project: _Optional[str] = ..., document_json: _Optional[str] = ...) -> None: ...

class SubmitManifestResponse(_message.Message):
    __slots__ = ("error", "manifest", "approved_now", "in_force")
    ERROR_FIELD_NUMBER: _ClassVar[int]
    MANIFEST_FIELD_NUMBER: _ClassVar[int]
    APPROVED_NOW_FIELD_NUMBER: _ClassVar[int]
    IN_FORCE_FIELD_NUMBER: _ClassVar[int]
    error: _common_pb2.CallError
    manifest: Manifest
    approved_now: bool
    in_force: bool
    def __init__(self, error: _Optional[_Union[_common_pb2.CallError, _Mapping]] = ..., manifest: _Optional[_Union[Manifest, _Mapping]] = ..., approved_now: bool = ..., in_force: bool = ...) -> None: ...

class GetManifestRequest(_message.Message):
    __slots__ = ("context", "principal_id", "sha256")
    CONTEXT_FIELD_NUMBER: _ClassVar[int]
    PRINCIPAL_ID_FIELD_NUMBER: _ClassVar[int]
    SHA256_FIELD_NUMBER: _ClassVar[int]
    context: _common_pb2.CallContext
    principal_id: str
    sha256: str
    def __init__(self, context: _Optional[_Union[_common_pb2.CallContext, _Mapping]] = ..., principal_id: _Optional[str] = ..., sha256: _Optional[str] = ...) -> None: ...

class GetManifestResponse(_message.Message):
    __slots__ = ("error", "manifest")
    ERROR_FIELD_NUMBER: _ClassVar[int]
    MANIFEST_FIELD_NUMBER: _ClassVar[int]
    error: _common_pb2.CallError
    manifest: Manifest
    def __init__(self, error: _Optional[_Union[_common_pb2.CallError, _Mapping]] = ..., manifest: _Optional[_Union[Manifest, _Mapping]] = ...) -> None: ...

class ListManifestsRequest(_message.Message):
    __slots__ = ("context", "principal_id", "status")
    CONTEXT_FIELD_NUMBER: _ClassVar[int]
    PRINCIPAL_ID_FIELD_NUMBER: _ClassVar[int]
    STATUS_FIELD_NUMBER: _ClassVar[int]
    context: _common_pb2.CallContext
    principal_id: str
    status: str
    def __init__(self, context: _Optional[_Union[_common_pb2.CallContext, _Mapping]] = ..., principal_id: _Optional[str] = ..., status: _Optional[str] = ...) -> None: ...

class ListManifestsResponse(_message.Message):
    __slots__ = ("error", "manifests")
    ERROR_FIELD_NUMBER: _ClassVar[int]
    MANIFESTS_FIELD_NUMBER: _ClassVar[int]
    error: _common_pb2.CallError
    manifests: _containers.RepeatedCompositeFieldContainer[Manifest]
    def __init__(self, error: _Optional[_Union[_common_pb2.CallError, _Mapping]] = ..., manifests: _Optional[_Iterable[_Union[Manifest, _Mapping]]] = ...) -> None: ...

class ApproveManifestRequest(_message.Message):
    __slots__ = ("context", "principal_id", "sha256", "document_json")
    CONTEXT_FIELD_NUMBER: _ClassVar[int]
    PRINCIPAL_ID_FIELD_NUMBER: _ClassVar[int]
    SHA256_FIELD_NUMBER: _ClassVar[int]
    DOCUMENT_JSON_FIELD_NUMBER: _ClassVar[int]
    context: _common_pb2.CallContext
    principal_id: str
    sha256: str
    document_json: str
    def __init__(self, context: _Optional[_Union[_common_pb2.CallContext, _Mapping]] = ..., principal_id: _Optional[str] = ..., sha256: _Optional[str] = ..., document_json: _Optional[str] = ...) -> None: ...

class ApproveManifestResponse(_message.Message):
    __slots__ = ("error", "manifest")
    ERROR_FIELD_NUMBER: _ClassVar[int]
    MANIFEST_FIELD_NUMBER: _ClassVar[int]
    error: _common_pb2.CallError
    manifest: Manifest
    def __init__(self, error: _Optional[_Union[_common_pb2.CallError, _Mapping]] = ..., manifest: _Optional[_Union[Manifest, _Mapping]] = ...) -> None: ...

class RejectManifestRequest(_message.Message):
    __slots__ = ("context", "principal_id", "sha256", "reason")
    CONTEXT_FIELD_NUMBER: _ClassVar[int]
    PRINCIPAL_ID_FIELD_NUMBER: _ClassVar[int]
    SHA256_FIELD_NUMBER: _ClassVar[int]
    REASON_FIELD_NUMBER: _ClassVar[int]
    context: _common_pb2.CallContext
    principal_id: str
    sha256: str
    reason: str
    def __init__(self, context: _Optional[_Union[_common_pb2.CallContext, _Mapping]] = ..., principal_id: _Optional[str] = ..., sha256: _Optional[str] = ..., reason: _Optional[str] = ...) -> None: ...

class RejectManifestResponse(_message.Message):
    __slots__ = ("error", "manifest")
    ERROR_FIELD_NUMBER: _ClassVar[int]
    MANIFEST_FIELD_NUMBER: _ClassVar[int]
    error: _common_pb2.CallError
    manifest: Manifest
    def __init__(self, error: _Optional[_Union[_common_pb2.CallError, _Mapping]] = ..., manifest: _Optional[_Union[Manifest, _Mapping]] = ...) -> None: ...

class CreatePendingGrantRequest(_message.Message):
    __slots__ = ("context", "provider", "email", "policy_id", "scope")
    CONTEXT_FIELD_NUMBER: _ClassVar[int]
    PROVIDER_FIELD_NUMBER: _ClassVar[int]
    EMAIL_FIELD_NUMBER: _ClassVar[int]
    POLICY_ID_FIELD_NUMBER: _ClassVar[int]
    SCOPE_FIELD_NUMBER: _ClassVar[int]
    context: _common_pb2.CallContext
    provider: str
    email: str
    policy_id: str
    scope: str
    def __init__(self, context: _Optional[_Union[_common_pb2.CallContext, _Mapping]] = ..., provider: _Optional[str] = ..., email: _Optional[str] = ..., policy_id: _Optional[str] = ..., scope: _Optional[str] = ...) -> None: ...

class CreatePendingGrantResponse(_message.Message):
    __slots__ = ("error", "grant")
    ERROR_FIELD_NUMBER: _ClassVar[int]
    GRANT_FIELD_NUMBER: _ClassVar[int]
    error: _common_pb2.CallError
    grant: PendingGrant
    def __init__(self, error: _Optional[_Union[_common_pb2.CallError, _Mapping]] = ..., grant: _Optional[_Union[PendingGrant, _Mapping]] = ...) -> None: ...

class ListPendingGrantsRequest(_message.Message):
    __slots__ = ("context", "provider", "email", "policy_id")
    CONTEXT_FIELD_NUMBER: _ClassVar[int]
    PROVIDER_FIELD_NUMBER: _ClassVar[int]
    EMAIL_FIELD_NUMBER: _ClassVar[int]
    POLICY_ID_FIELD_NUMBER: _ClassVar[int]
    context: _common_pb2.CallContext
    provider: str
    email: str
    policy_id: str
    def __init__(self, context: _Optional[_Union[_common_pb2.CallContext, _Mapping]] = ..., provider: _Optional[str] = ..., email: _Optional[str] = ..., policy_id: _Optional[str] = ...) -> None: ...

class ListPendingGrantsResponse(_message.Message):
    __slots__ = ("error", "grants")
    ERROR_FIELD_NUMBER: _ClassVar[int]
    GRANTS_FIELD_NUMBER: _ClassVar[int]
    error: _common_pb2.CallError
    grants: _containers.RepeatedCompositeFieldContainer[PendingGrant]
    def __init__(self, error: _Optional[_Union[_common_pb2.CallError, _Mapping]] = ..., grants: _Optional[_Iterable[_Union[PendingGrant, _Mapping]]] = ...) -> None: ...

class RevokePendingGrantRequest(_message.Message):
    __slots__ = ("context", "grant_id")
    CONTEXT_FIELD_NUMBER: _ClassVar[int]
    GRANT_ID_FIELD_NUMBER: _ClassVar[int]
    context: _common_pb2.CallContext
    grant_id: str
    def __init__(self, context: _Optional[_Union[_common_pb2.CallContext, _Mapping]] = ..., grant_id: _Optional[str] = ...) -> None: ...

class RevokePendingGrantResponse(_message.Message):
    __slots__ = ("error", "revoked")
    ERROR_FIELD_NUMBER: _ClassVar[int]
    REVOKED_FIELD_NUMBER: _ClassVar[int]
    error: _common_pb2.CallError
    revoked: bool
    def __init__(self, error: _Optional[_Union[_common_pb2.CallError, _Mapping]] = ..., revoked: bool = ...) -> None: ...

class ClaimPendingGrantsRequest(_message.Message):
    __slots__ = ("context", "principal_id")
    CONTEXT_FIELD_NUMBER: _ClassVar[int]
    PRINCIPAL_ID_FIELD_NUMBER: _ClassVar[int]
    context: _common_pb2.CallContext
    principal_id: str
    def __init__(self, context: _Optional[_Union[_common_pb2.CallContext, _Mapping]] = ..., principal_id: _Optional[str] = ...) -> None: ...

class ClaimPendingGrantsResponse(_message.Message):
    __slots__ = ("error", "attachments")
    ERROR_FIELD_NUMBER: _ClassVar[int]
    ATTACHMENTS_FIELD_NUMBER: _ClassVar[int]
    error: _common_pb2.CallError
    attachments: _containers.RepeatedCompositeFieldContainer[Attachment]
    def __init__(self, error: _Optional[_Union[_common_pb2.CallError, _Mapping]] = ..., attachments: _Optional[_Iterable[_Union[Attachment, _Mapping]]] = ...) -> None: ...

class BindIdpGroupRequest(_message.Message):
    __slots__ = ("context", "provider", "claim_value", "policy_id", "scope")
    CONTEXT_FIELD_NUMBER: _ClassVar[int]
    PROVIDER_FIELD_NUMBER: _ClassVar[int]
    CLAIM_VALUE_FIELD_NUMBER: _ClassVar[int]
    POLICY_ID_FIELD_NUMBER: _ClassVar[int]
    SCOPE_FIELD_NUMBER: _ClassVar[int]
    context: _common_pb2.CallContext
    provider: str
    claim_value: str
    policy_id: str
    scope: str
    def __init__(self, context: _Optional[_Union[_common_pb2.CallContext, _Mapping]] = ..., provider: _Optional[str] = ..., claim_value: _Optional[str] = ..., policy_id: _Optional[str] = ..., scope: _Optional[str] = ...) -> None: ...

class BindIdpGroupResponse(_message.Message):
    __slots__ = ("error", "binding")
    ERROR_FIELD_NUMBER: _ClassVar[int]
    BINDING_FIELD_NUMBER: _ClassVar[int]
    error: _common_pb2.CallError
    binding: IdpBinding
    def __init__(self, error: _Optional[_Union[_common_pb2.CallError, _Mapping]] = ..., binding: _Optional[_Union[IdpBinding, _Mapping]] = ...) -> None: ...

class UnbindIdpGroupRequest(_message.Message):
    __slots__ = ("context", "provider", "claim_value", "policy_id", "scope")
    CONTEXT_FIELD_NUMBER: _ClassVar[int]
    PROVIDER_FIELD_NUMBER: _ClassVar[int]
    CLAIM_VALUE_FIELD_NUMBER: _ClassVar[int]
    POLICY_ID_FIELD_NUMBER: _ClassVar[int]
    SCOPE_FIELD_NUMBER: _ClassVar[int]
    context: _common_pb2.CallContext
    provider: str
    claim_value: str
    policy_id: str
    scope: str
    def __init__(self, context: _Optional[_Union[_common_pb2.CallContext, _Mapping]] = ..., provider: _Optional[str] = ..., claim_value: _Optional[str] = ..., policy_id: _Optional[str] = ..., scope: _Optional[str] = ...) -> None: ...

class UnbindIdpGroupResponse(_message.Message):
    __slots__ = ("error", "removed")
    ERROR_FIELD_NUMBER: _ClassVar[int]
    REMOVED_FIELD_NUMBER: _ClassVar[int]
    error: _common_pb2.CallError
    removed: bool
    def __init__(self, error: _Optional[_Union[_common_pb2.CallError, _Mapping]] = ..., removed: bool = ...) -> None: ...

class ListIdpBindingsRequest(_message.Message):
    __slots__ = ("context", "provider", "policy_id")
    CONTEXT_FIELD_NUMBER: _ClassVar[int]
    PROVIDER_FIELD_NUMBER: _ClassVar[int]
    POLICY_ID_FIELD_NUMBER: _ClassVar[int]
    context: _common_pb2.CallContext
    provider: str
    policy_id: str
    def __init__(self, context: _Optional[_Union[_common_pb2.CallContext, _Mapping]] = ..., provider: _Optional[str] = ..., policy_id: _Optional[str] = ...) -> None: ...

class ListIdpBindingsResponse(_message.Message):
    __slots__ = ("error", "bindings")
    ERROR_FIELD_NUMBER: _ClassVar[int]
    BINDINGS_FIELD_NUMBER: _ClassVar[int]
    error: _common_pb2.CallError
    bindings: _containers.RepeatedCompositeFieldContainer[IdpBinding]
    def __init__(self, error: _Optional[_Union[_common_pb2.CallError, _Mapping]] = ..., bindings: _Optional[_Iterable[_Union[IdpBinding, _Mapping]]] = ...) -> None: ...
