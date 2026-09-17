from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from typing import ClassVar as _ClassVar, Optional as _Optional

DESCRIPTOR: _descriptor.FileDescriptor

class CallContext(_message.Message):
    __slots__ = ("trace_id", "timeout_ms", "principal_id", "workspace_id", "tenant_id")
    TRACE_ID_FIELD_NUMBER: _ClassVar[int]
    TIMEOUT_MS_FIELD_NUMBER: _ClassVar[int]
    PRINCIPAL_ID_FIELD_NUMBER: _ClassVar[int]
    WORKSPACE_ID_FIELD_NUMBER: _ClassVar[int]
    TENANT_ID_FIELD_NUMBER: _ClassVar[int]
    trace_id: str
    timeout_ms: int
    principal_id: str
    workspace_id: str
    tenant_id: str
    def __init__(self, trace_id: _Optional[str] = ..., timeout_ms: _Optional[int] = ..., principal_id: _Optional[str] = ..., workspace_id: _Optional[str] = ..., tenant_id: _Optional[str] = ...) -> None: ...

class CallError(_message.Message):
    __slots__ = ("code", "message", "retryable")
    CODE_FIELD_NUMBER: _ClassVar[int]
    MESSAGE_FIELD_NUMBER: _ClassVar[int]
    RETRYABLE_FIELD_NUMBER: _ClassVar[int]
    code: str
    message: str
    retryable: bool
    def __init__(self, code: _Optional[str] = ..., message: _Optional[str] = ..., retryable: _Optional[bool] = ...) -> None: ...
