from naas_abi_proto.common.v1 import common_pb2 as _common_pb2
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from collections.abc import Mapping as _Mapping
from typing import ClassVar as _ClassVar, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class InvokeToolRequest(_message.Message):
    __slots__ = ("context", "tool", "version", "arguments_json", "config_json", "call_id")
    CONTEXT_FIELD_NUMBER: _ClassVar[int]
    TOOL_FIELD_NUMBER: _ClassVar[int]
    VERSION_FIELD_NUMBER: _ClassVar[int]
    ARGUMENTS_JSON_FIELD_NUMBER: _ClassVar[int]
    CONFIG_JSON_FIELD_NUMBER: _ClassVar[int]
    CALL_ID_FIELD_NUMBER: _ClassVar[int]
    context: _common_pb2.CallContext
    tool: str
    version: str
    arguments_json: bytes
    config_json: bytes
    call_id: str
    def __init__(self, context: _Optional[_Union[_common_pb2.CallContext, _Mapping]] = ..., tool: _Optional[str] = ..., version: _Optional[str] = ..., arguments_json: _Optional[bytes] = ..., config_json: _Optional[bytes] = ..., call_id: _Optional[str] = ...) -> None: ...

class InvokeToolResponse(_message.Message):
    __slots__ = ("result_json", "error")
    RESULT_JSON_FIELD_NUMBER: _ClassVar[int]
    ERROR_FIELD_NUMBER: _ClassVar[int]
    result_json: bytes
    error: _common_pb2.CallError
    def __init__(self, result_json: _Optional[bytes] = ..., error: _Optional[_Union[_common_pb2.CallError, _Mapping]] = ...) -> None: ...

class CancelToolRequest(_message.Message):
    __slots__ = ("context", "call_id")
    CONTEXT_FIELD_NUMBER: _ClassVar[int]
    CALL_ID_FIELD_NUMBER: _ClassVar[int]
    context: _common_pb2.CallContext
    call_id: str
    def __init__(self, context: _Optional[_Union[_common_pb2.CallContext, _Mapping]] = ..., call_id: _Optional[str] = ...) -> None: ...

class CancelToolResponse(_message.Message):
    __slots__ = ("cancelled", "error")
    CANCELLED_FIELD_NUMBER: _ClassVar[int]
    ERROR_FIELD_NUMBER: _ClassVar[int]
    cancelled: bool
    error: _common_pb2.CallError
    def __init__(self, cancelled: bool = ..., error: _Optional[_Union[_common_pb2.CallError, _Mapping]] = ...) -> None: ...
