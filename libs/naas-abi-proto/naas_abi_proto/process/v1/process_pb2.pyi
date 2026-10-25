from naas_abi_proto.common.v1 import common_pb2 as _common_pb2
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from collections.abc import Mapping as _Mapping
from typing import ClassVar as _ClassVar, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class RunRequest(_message.Message):
    __slots__ = ("context", "name", "parameters_json", "deadline_seconds", "parameters_inbox", "parameters_bytes")
    CONTEXT_FIELD_NUMBER: _ClassVar[int]
    NAME_FIELD_NUMBER: _ClassVar[int]
    PARAMETERS_JSON_FIELD_NUMBER: _ClassVar[int]
    DEADLINE_SECONDS_FIELD_NUMBER: _ClassVar[int]
    PARAMETERS_INBOX_FIELD_NUMBER: _ClassVar[int]
    PARAMETERS_BYTES_FIELD_NUMBER: _ClassVar[int]
    context: _common_pb2.CallContext
    name: str
    parameters_json: bytes
    deadline_seconds: float
    parameters_inbox: str
    parameters_bytes: int
    def __init__(self, context: _Optional[_Union[_common_pb2.CallContext, _Mapping]] = ..., name: _Optional[str] = ..., parameters_json: _Optional[bytes] = ..., deadline_seconds: _Optional[float] = ..., parameters_inbox: _Optional[str] = ..., parameters_bytes: _Optional[int] = ...) -> None: ...

class RunResponse(_message.Message):
    __slots__ = ("error", "result_json", "graph_nt", "body_inbox", "body_bytes")
    ERROR_FIELD_NUMBER: _ClassVar[int]
    RESULT_JSON_FIELD_NUMBER: _ClassVar[int]
    GRAPH_NT_FIELD_NUMBER: _ClassVar[int]
    BODY_INBOX_FIELD_NUMBER: _ClassVar[int]
    BODY_BYTES_FIELD_NUMBER: _ClassVar[int]
    error: _common_pb2.CallError
    result_json: bytes
    graph_nt: bytes
    body_inbox: str
    body_bytes: int
    def __init__(self, error: _Optional[_Union[_common_pb2.CallError, _Mapping]] = ..., result_json: _Optional[bytes] = ..., graph_nt: _Optional[bytes] = ..., body_inbox: _Optional[str] = ..., body_bytes: _Optional[int] = ...) -> None: ...

class DescribeRequest(_message.Message):
    __slots__ = ("context", "name")
    CONTEXT_FIELD_NUMBER: _ClassVar[int]
    NAME_FIELD_NUMBER: _ClassVar[int]
    context: _common_pb2.CallContext
    name: str
    def __init__(self, context: _Optional[_Union[_common_pb2.CallContext, _Mapping]] = ..., name: _Optional[str] = ...) -> None: ...

class DescribeResponse(_message.Message):
    __slots__ = ("error", "parameters_schema_json", "description", "kind")
    ERROR_FIELD_NUMBER: _ClassVar[int]
    PARAMETERS_SCHEMA_JSON_FIELD_NUMBER: _ClassVar[int]
    DESCRIPTION_FIELD_NUMBER: _ClassVar[int]
    KIND_FIELD_NUMBER: _ClassVar[int]
    error: _common_pb2.CallError
    parameters_schema_json: bytes
    description: str
    kind: str
    def __init__(self, error: _Optional[_Union[_common_pb2.CallError, _Mapping]] = ..., parameters_schema_json: _Optional[bytes] = ..., description: _Optional[str] = ..., kind: _Optional[str] = ...) -> None: ...
