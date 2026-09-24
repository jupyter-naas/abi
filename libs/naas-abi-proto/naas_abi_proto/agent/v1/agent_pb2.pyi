from naas_abi_proto.common.v1 import common_pb2 as _common_pb2
from google.protobuf.internal import containers as _containers
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from collections.abc import Iterable as _Iterable, Mapping as _Mapping
from typing import ClassVar as _ClassVar, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class AgentEvent(_message.Message):
    __slots__ = ("sequence", "event", "data", "parts")
    SEQUENCE_FIELD_NUMBER: _ClassVar[int]
    EVENT_FIELD_NUMBER: _ClassVar[int]
    DATA_FIELD_NUMBER: _ClassVar[int]
    PARTS_FIELD_NUMBER: _ClassVar[int]
    sequence: int
    event: str
    data: str
    parts: int
    def __init__(self, sequence: _Optional[int] = ..., event: _Optional[str] = ..., data: _Optional[str] = ..., parts: _Optional[int] = ...) -> None: ...

class Invocation(_message.Message):
    __slots__ = ("invocation_id", "thread_id", "status", "result", "error_code", "error_message", "owner_instance_id", "owner_available", "events", "last_sequence", "result_parts")
    INVOCATION_ID_FIELD_NUMBER: _ClassVar[int]
    THREAD_ID_FIELD_NUMBER: _ClassVar[int]
    STATUS_FIELD_NUMBER: _ClassVar[int]
    RESULT_FIELD_NUMBER: _ClassVar[int]
    ERROR_CODE_FIELD_NUMBER: _ClassVar[int]
    ERROR_MESSAGE_FIELD_NUMBER: _ClassVar[int]
    OWNER_INSTANCE_ID_FIELD_NUMBER: _ClassVar[int]
    OWNER_AVAILABLE_FIELD_NUMBER: _ClassVar[int]
    EVENTS_FIELD_NUMBER: _ClassVar[int]
    LAST_SEQUENCE_FIELD_NUMBER: _ClassVar[int]
    RESULT_PARTS_FIELD_NUMBER: _ClassVar[int]
    invocation_id: str
    thread_id: str
    status: str
    result: str
    error_code: str
    error_message: str
    owner_instance_id: str
    owner_available: bool
    events: _containers.RepeatedCompositeFieldContainer[AgentEvent]
    last_sequence: int
    result_parts: int
    def __init__(self, invocation_id: _Optional[str] = ..., thread_id: _Optional[str] = ..., status: _Optional[str] = ..., result: _Optional[str] = ..., error_code: _Optional[str] = ..., error_message: _Optional[str] = ..., owner_instance_id: _Optional[str] = ..., owner_available: bool = ..., events: _Optional[_Iterable[_Union[AgentEvent, _Mapping]]] = ..., last_sequence: _Optional[int] = ..., result_parts: _Optional[int] = ...) -> None: ...

class SubmitRequest(_message.Message):
    __slots__ = ("context", "invocation_id", "thread_id", "prompt", "mode", "deadline_seconds", "output_format")
    CONTEXT_FIELD_NUMBER: _ClassVar[int]
    INVOCATION_ID_FIELD_NUMBER: _ClassVar[int]
    THREAD_ID_FIELD_NUMBER: _ClassVar[int]
    PROMPT_FIELD_NUMBER: _ClassVar[int]
    MODE_FIELD_NUMBER: _ClassVar[int]
    DEADLINE_SECONDS_FIELD_NUMBER: _ClassVar[int]
    OUTPUT_FORMAT_FIELD_NUMBER: _ClassVar[int]
    context: _common_pb2.CallContext
    invocation_id: str
    thread_id: str
    prompt: str
    mode: str
    deadline_seconds: int
    output_format: int
    def __init__(self, context: _Optional[_Union[_common_pb2.CallContext, _Mapping]] = ..., invocation_id: _Optional[str] = ..., thread_id: _Optional[str] = ..., prompt: _Optional[str] = ..., mode: _Optional[str] = ..., deadline_seconds: _Optional[int] = ..., output_format: _Optional[int] = ...) -> None: ...

class SubmitResponse(_message.Message):
    __slots__ = ("error", "invocation")
    ERROR_FIELD_NUMBER: _ClassVar[int]
    INVOCATION_FIELD_NUMBER: _ClassVar[int]
    error: _common_pb2.CallError
    invocation: Invocation
    def __init__(self, error: _Optional[_Union[_common_pb2.CallError, _Mapping]] = ..., invocation: _Optional[_Union[Invocation, _Mapping]] = ...) -> None: ...

class StatusRequest(_message.Message):
    __slots__ = ("context", "invocation_id", "after_sequence", "output_format")
    CONTEXT_FIELD_NUMBER: _ClassVar[int]
    INVOCATION_ID_FIELD_NUMBER: _ClassVar[int]
    AFTER_SEQUENCE_FIELD_NUMBER: _ClassVar[int]
    OUTPUT_FORMAT_FIELD_NUMBER: _ClassVar[int]
    context: _common_pb2.CallContext
    invocation_id: str
    after_sequence: int
    output_format: int
    def __init__(self, context: _Optional[_Union[_common_pb2.CallContext, _Mapping]] = ..., invocation_id: _Optional[str] = ..., after_sequence: _Optional[int] = ..., output_format: _Optional[int] = ...) -> None: ...

class StatusResponse(_message.Message):
    __slots__ = ("error", "invocation")
    ERROR_FIELD_NUMBER: _ClassVar[int]
    INVOCATION_FIELD_NUMBER: _ClassVar[int]
    error: _common_pb2.CallError
    invocation: Invocation
    def __init__(self, error: _Optional[_Union[_common_pb2.CallError, _Mapping]] = ..., invocation: _Optional[_Union[Invocation, _Mapping]] = ...) -> None: ...

class CancelRequest(_message.Message):
    __slots__ = ("context", "invocation_id", "output_format")
    CONTEXT_FIELD_NUMBER: _ClassVar[int]
    INVOCATION_ID_FIELD_NUMBER: _ClassVar[int]
    OUTPUT_FORMAT_FIELD_NUMBER: _ClassVar[int]
    context: _common_pb2.CallContext
    invocation_id: str
    output_format: int
    def __init__(self, context: _Optional[_Union[_common_pb2.CallContext, _Mapping]] = ..., invocation_id: _Optional[str] = ..., output_format: _Optional[int] = ...) -> None: ...

class CancelResponse(_message.Message):
    __slots__ = ("error", "invocation")
    ERROR_FIELD_NUMBER: _ClassVar[int]
    INVOCATION_FIELD_NUMBER: _ClassVar[int]
    error: _common_pb2.CallError
    invocation: Invocation
    def __init__(self, error: _Optional[_Union[_common_pb2.CallError, _Mapping]] = ..., invocation: _Optional[_Union[Invocation, _Mapping]] = ...) -> None: ...

class EventRequest(_message.Message):
    __slots__ = ("context", "invocation_id", "sequence", "part")
    CONTEXT_FIELD_NUMBER: _ClassVar[int]
    INVOCATION_ID_FIELD_NUMBER: _ClassVar[int]
    SEQUENCE_FIELD_NUMBER: _ClassVar[int]
    PART_FIELD_NUMBER: _ClassVar[int]
    context: _common_pb2.CallContext
    invocation_id: str
    sequence: int
    part: int
    def __init__(self, context: _Optional[_Union[_common_pb2.CallContext, _Mapping]] = ..., invocation_id: _Optional[str] = ..., sequence: _Optional[int] = ..., part: _Optional[int] = ...) -> None: ...

class EventResponse(_message.Message):
    __slots__ = ("error", "data")
    ERROR_FIELD_NUMBER: _ClassVar[int]
    DATA_FIELD_NUMBER: _ClassVar[int]
    error: _common_pb2.CallError
    data: bytes
    def __init__(self, error: _Optional[_Union[_common_pb2.CallError, _Mapping]] = ..., data: _Optional[bytes] = ...) -> None: ...
