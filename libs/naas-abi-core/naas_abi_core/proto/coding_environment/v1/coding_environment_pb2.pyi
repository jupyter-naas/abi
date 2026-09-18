from naas_abi_core.proto.common.v1 import common_pb2 as _common_pb2
from google.protobuf.internal import containers as _containers
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from collections.abc import Iterable as _Iterable, Mapping as _Mapping
from typing import ClassVar as _ClassVar, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class WorkspaceTemplate(_message.Message):
    __slots__ = ("id", "name", "active_version_id")
    ID_FIELD_NUMBER: _ClassVar[int]
    NAME_FIELD_NUMBER: _ClassVar[int]
    ACTIVE_VERSION_ID_FIELD_NUMBER: _ClassVar[int]
    id: str
    name: str
    active_version_id: str
    def __init__(self, id: _Optional[str] = ..., name: _Optional[str] = ..., active_version_id: _Optional[str] = ...) -> None: ...

class WorkspaceStatus(_message.Message):
    __slots__ = ("id", "name", "phase", "agent_ready")
    ID_FIELD_NUMBER: _ClassVar[int]
    NAME_FIELD_NUMBER: _ClassVar[int]
    PHASE_FIELD_NUMBER: _ClassVar[int]
    AGENT_READY_FIELD_NUMBER: _ClassVar[int]
    id: str
    name: str
    phase: str
    agent_ready: bool
    def __init__(self, id: _Optional[str] = ..., name: _Optional[str] = ..., phase: _Optional[str] = ..., agent_ready: _Optional[bool] = ...) -> None: ...

class WorkspaceAccess(_message.Message):
    __slots__ = ("url", "token", "expires_at")
    URL_FIELD_NUMBER: _ClassVar[int]
    TOKEN_FIELD_NUMBER: _ClassVar[int]
    EXPIRES_AT_FIELD_NUMBER: _ClassVar[int]
    url: str
    token: str
    expires_at: str
    def __init__(self, url: _Optional[str] = ..., token: _Optional[str] = ..., expires_at: _Optional[str] = ...) -> None: ...

class EnsureUserRequest(_message.Message):
    __slots__ = ("context", "external_id", "email", "username")
    CONTEXT_FIELD_NUMBER: _ClassVar[int]
    EXTERNAL_ID_FIELD_NUMBER: _ClassVar[int]
    EMAIL_FIELD_NUMBER: _ClassVar[int]
    USERNAME_FIELD_NUMBER: _ClassVar[int]
    context: _common_pb2.CallContext
    external_id: str
    email: str
    username: str
    def __init__(self, context: _Optional[_Union[_common_pb2.CallContext, _Mapping]] = ..., external_id: _Optional[str] = ..., email: _Optional[str] = ..., username: _Optional[str] = ...) -> None: ...

class EnsureUserResponse(_message.Message):
    __slots__ = ("user_id", "error")
    USER_ID_FIELD_NUMBER: _ClassVar[int]
    ERROR_FIELD_NUMBER: _ClassVar[int]
    user_id: str
    error: _common_pb2.CallError
    def __init__(self, user_id: _Optional[str] = ..., error: _Optional[_Union[_common_pb2.CallError, _Mapping]] = ...) -> None: ...

class ListTemplatesRequest(_message.Message):
    __slots__ = ("context",)
    CONTEXT_FIELD_NUMBER: _ClassVar[int]
    context: _common_pb2.CallContext
    def __init__(self, context: _Optional[_Union[_common_pb2.CallContext, _Mapping]] = ...) -> None: ...

class ListTemplatesResponse(_message.Message):
    __slots__ = ("templates", "error")
    TEMPLATES_FIELD_NUMBER: _ClassVar[int]
    ERROR_FIELD_NUMBER: _ClassVar[int]
    templates: WorkspaceTemplates
    error: _common_pb2.CallError
    def __init__(self, templates: _Optional[_Union[WorkspaceTemplates, _Mapping]] = ..., error: _Optional[_Union[_common_pb2.CallError, _Mapping]] = ...) -> None: ...

class WorkspaceTemplates(_message.Message):
    __slots__ = ("templates",)
    TEMPLATES_FIELD_NUMBER: _ClassVar[int]
    templates: _containers.RepeatedCompositeFieldContainer[WorkspaceTemplate]
    def __init__(self, templates: _Optional[_Iterable[_Union[WorkspaceTemplate, _Mapping]]] = ...) -> None: ...

class ProvisionRequest(_message.Message):
    __slots__ = ("context", "user_id", "template_id", "name", "params")
    class ParamsEntry(_message.Message):
        __slots__ = ("key", "value")
        KEY_FIELD_NUMBER: _ClassVar[int]
        VALUE_FIELD_NUMBER: _ClassVar[int]
        key: str
        value: str
        def __init__(self, key: _Optional[str] = ..., value: _Optional[str] = ...) -> None: ...
    CONTEXT_FIELD_NUMBER: _ClassVar[int]
    USER_ID_FIELD_NUMBER: _ClassVar[int]
    TEMPLATE_ID_FIELD_NUMBER: _ClassVar[int]
    NAME_FIELD_NUMBER: _ClassVar[int]
    PARAMS_FIELD_NUMBER: _ClassVar[int]
    context: _common_pb2.CallContext
    user_id: str
    template_id: str
    name: str
    params: _containers.ScalarMap[str, str]
    def __init__(self, context: _Optional[_Union[_common_pb2.CallContext, _Mapping]] = ..., user_id: _Optional[str] = ..., template_id: _Optional[str] = ..., name: _Optional[str] = ..., params: _Optional[_Mapping[str, str]] = ...) -> None: ...

class ProvisionResponse(_message.Message):
    __slots__ = ("status", "error")
    STATUS_FIELD_NUMBER: _ClassVar[int]
    ERROR_FIELD_NUMBER: _ClassVar[int]
    status: WorkspaceStatus
    error: _common_pb2.CallError
    def __init__(self, status: _Optional[_Union[WorkspaceStatus, _Mapping]] = ..., error: _Optional[_Union[_common_pb2.CallError, _Mapping]] = ...) -> None: ...

class StartRequest(_message.Message):
    __slots__ = ("context", "workspace_id", "params")
    class ParamsEntry(_message.Message):
        __slots__ = ("key", "value")
        KEY_FIELD_NUMBER: _ClassVar[int]
        VALUE_FIELD_NUMBER: _ClassVar[int]
        key: str
        value: str
        def __init__(self, key: _Optional[str] = ..., value: _Optional[str] = ...) -> None: ...
    CONTEXT_FIELD_NUMBER: _ClassVar[int]
    WORKSPACE_ID_FIELD_NUMBER: _ClassVar[int]
    PARAMS_FIELD_NUMBER: _ClassVar[int]
    context: _common_pb2.CallContext
    workspace_id: str
    params: _containers.ScalarMap[str, str]
    def __init__(self, context: _Optional[_Union[_common_pb2.CallContext, _Mapping]] = ..., workspace_id: _Optional[str] = ..., params: _Optional[_Mapping[str, str]] = ...) -> None: ...

class StartResponse(_message.Message):
    __slots__ = ("status", "error")
    STATUS_FIELD_NUMBER: _ClassVar[int]
    ERROR_FIELD_NUMBER: _ClassVar[int]
    status: WorkspaceStatus
    error: _common_pb2.CallError
    def __init__(self, status: _Optional[_Union[WorkspaceStatus, _Mapping]] = ..., error: _Optional[_Union[_common_pb2.CallError, _Mapping]] = ...) -> None: ...

class StopRequest(_message.Message):
    __slots__ = ("context", "workspace_id")
    CONTEXT_FIELD_NUMBER: _ClassVar[int]
    WORKSPACE_ID_FIELD_NUMBER: _ClassVar[int]
    context: _common_pb2.CallContext
    workspace_id: str
    def __init__(self, context: _Optional[_Union[_common_pb2.CallContext, _Mapping]] = ..., workspace_id: _Optional[str] = ...) -> None: ...

class StopResponse(_message.Message):
    __slots__ = ("status", "error")
    STATUS_FIELD_NUMBER: _ClassVar[int]
    ERROR_FIELD_NUMBER: _ClassVar[int]
    status: WorkspaceStatus
    error: _common_pb2.CallError
    def __init__(self, status: _Optional[_Union[WorkspaceStatus, _Mapping]] = ..., error: _Optional[_Union[_common_pb2.CallError, _Mapping]] = ...) -> None: ...

class DeleteRequest(_message.Message):
    __slots__ = ("context", "workspace_id")
    CONTEXT_FIELD_NUMBER: _ClassVar[int]
    WORKSPACE_ID_FIELD_NUMBER: _ClassVar[int]
    context: _common_pb2.CallContext
    workspace_id: str
    def __init__(self, context: _Optional[_Union[_common_pb2.CallContext, _Mapping]] = ..., workspace_id: _Optional[str] = ...) -> None: ...

class DeleteResponse(_message.Message):
    __slots__ = ("error",)
    ERROR_FIELD_NUMBER: _ClassVar[int]
    error: _common_pb2.CallError
    def __init__(self, error: _Optional[_Union[_common_pb2.CallError, _Mapping]] = ...) -> None: ...

class ListEnvironmentsRequest(_message.Message):
    __slots__ = ("context", "user_id")
    CONTEXT_FIELD_NUMBER: _ClassVar[int]
    USER_ID_FIELD_NUMBER: _ClassVar[int]
    context: _common_pb2.CallContext
    user_id: str
    def __init__(self, context: _Optional[_Union[_common_pb2.CallContext, _Mapping]] = ..., user_id: _Optional[str] = ...) -> None: ...

class ListEnvironmentsResponse(_message.Message):
    __slots__ = ("environments", "error")
    ENVIRONMENTS_FIELD_NUMBER: _ClassVar[int]
    ERROR_FIELD_NUMBER: _ClassVar[int]
    environments: WorkspaceStatuses
    error: _common_pb2.CallError
    def __init__(self, environments: _Optional[_Union[WorkspaceStatuses, _Mapping]] = ..., error: _Optional[_Union[_common_pb2.CallError, _Mapping]] = ...) -> None: ...

class WorkspaceStatuses(_message.Message):
    __slots__ = ("environments",)
    ENVIRONMENTS_FIELD_NUMBER: _ClassVar[int]
    environments: _containers.RepeatedCompositeFieldContainer[WorkspaceStatus]
    def __init__(self, environments: _Optional[_Iterable[_Union[WorkspaceStatus, _Mapping]]] = ...) -> None: ...

class GetStatusRequest(_message.Message):
    __slots__ = ("context", "workspace_id")
    CONTEXT_FIELD_NUMBER: _ClassVar[int]
    WORKSPACE_ID_FIELD_NUMBER: _ClassVar[int]
    context: _common_pb2.CallContext
    workspace_id: str
    def __init__(self, context: _Optional[_Union[_common_pb2.CallContext, _Mapping]] = ..., workspace_id: _Optional[str] = ...) -> None: ...

class GetStatusResponse(_message.Message):
    __slots__ = ("status", "error")
    STATUS_FIELD_NUMBER: _ClassVar[int]
    ERROR_FIELD_NUMBER: _ClassVar[int]
    status: WorkspaceStatus
    error: _common_pb2.CallError
    def __init__(self, status: _Optional[_Union[WorkspaceStatus, _Mapping]] = ..., error: _Optional[_Union[_common_pb2.CallError, _Mapping]] = ...) -> None: ...

class GetLogsRequest(_message.Message):
    __slots__ = ("context", "workspace_id")
    CONTEXT_FIELD_NUMBER: _ClassVar[int]
    WORKSPACE_ID_FIELD_NUMBER: _ClassVar[int]
    context: _common_pb2.CallContext
    workspace_id: str
    def __init__(self, context: _Optional[_Union[_common_pb2.CallContext, _Mapping]] = ..., workspace_id: _Optional[str] = ...) -> None: ...

class GetLogsResponse(_message.Message):
    __slots__ = ("lines", "error")
    LINES_FIELD_NUMBER: _ClassVar[int]
    ERROR_FIELD_NUMBER: _ClassVar[int]
    lines: LogLines
    error: _common_pb2.CallError
    def __init__(self, lines: _Optional[_Union[LogLines, _Mapping]] = ..., error: _Optional[_Union[_common_pb2.CallError, _Mapping]] = ...) -> None: ...

class LogLines(_message.Message):
    __slots__ = ("lines",)
    LINES_FIELD_NUMBER: _ClassVar[int]
    lines: _containers.RepeatedScalarFieldContainer[str]
    def __init__(self, lines: _Optional[_Iterable[str]] = ...) -> None: ...

class GetAccessRequest(_message.Message):
    __slots__ = ("context", "workspace_id", "user_id", "app_slug")
    CONTEXT_FIELD_NUMBER: _ClassVar[int]
    WORKSPACE_ID_FIELD_NUMBER: _ClassVar[int]
    USER_ID_FIELD_NUMBER: _ClassVar[int]
    APP_SLUG_FIELD_NUMBER: _ClassVar[int]
    context: _common_pb2.CallContext
    workspace_id: str
    user_id: str
    app_slug: str
    def __init__(self, context: _Optional[_Union[_common_pb2.CallContext, _Mapping]] = ..., workspace_id: _Optional[str] = ..., user_id: _Optional[str] = ..., app_slug: _Optional[str] = ...) -> None: ...

class GetAccessResponse(_message.Message):
    __slots__ = ("access", "error")
    ACCESS_FIELD_NUMBER: _ClassVar[int]
    ERROR_FIELD_NUMBER: _ClassVar[int]
    access: WorkspaceAccess
    error: _common_pb2.CallError
    def __init__(self, access: _Optional[_Union[WorkspaceAccess, _Mapping]] = ..., error: _Optional[_Union[_common_pb2.CallError, _Mapping]] = ...) -> None: ...
