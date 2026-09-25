from naas_abi_proto.common.v1 import common_pb2 as _common_pb2
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from collections.abc import Mapping as _Mapping
from typing import ClassVar as _ClassVar, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class OpenRequest(_message.Message):
    __slots__ = ("context", "operation", "metadata", "chunk_bytes")
    CONTEXT_FIELD_NUMBER: _ClassVar[int]
    OPERATION_FIELD_NUMBER: _ClassVar[int]
    METADATA_FIELD_NUMBER: _ClassVar[int]
    CHUNK_BYTES_FIELD_NUMBER: _ClassVar[int]
    context: _common_pb2.CallContext
    operation: str
    metadata: bytes
    chunk_bytes: int
    def __init__(self, context: _Optional[_Union[_common_pb2.CallContext, _Mapping]] = ..., operation: _Optional[str] = ..., metadata: _Optional[bytes] = ..., chunk_bytes: _Optional[int] = ...) -> None: ...

class OpenResponse(_message.Message):
    __slots__ = ("id", "chunk_bytes", "error")
    ID_FIELD_NUMBER: _ClassVar[int]
    CHUNK_BYTES_FIELD_NUMBER: _ClassVar[int]
    ERROR_FIELD_NUMBER: _ClassVar[int]
    id: str
    chunk_bytes: int
    error: _common_pb2.CallError
    def __init__(self, id: _Optional[str] = ..., chunk_bytes: _Optional[int] = ..., error: _Optional[_Union[_common_pb2.CallError, _Mapping]] = ...) -> None: ...

class WriteRequest(_message.Message):
    __slots__ = ("context", "id", "sequence", "data")
    CONTEXT_FIELD_NUMBER: _ClassVar[int]
    ID_FIELD_NUMBER: _ClassVar[int]
    SEQUENCE_FIELD_NUMBER: _ClassVar[int]
    DATA_FIELD_NUMBER: _ClassVar[int]
    context: _common_pb2.CallContext
    id: str
    sequence: int
    data: bytes
    def __init__(self, context: _Optional[_Union[_common_pb2.CallContext, _Mapping]] = ..., id: _Optional[str] = ..., sequence: _Optional[int] = ..., data: _Optional[bytes] = ...) -> None: ...

class WriteResponse(_message.Message):
    __slots__ = ("error",)
    ERROR_FIELD_NUMBER: _ClassVar[int]
    error: _common_pb2.CallError
    def __init__(self, error: _Optional[_Union[_common_pb2.CallError, _Mapping]] = ...) -> None: ...

class StartRequest(_message.Message):
    __slots__ = ("context", "id")
    CONTEXT_FIELD_NUMBER: _ClassVar[int]
    ID_FIELD_NUMBER: _ClassVar[int]
    context: _common_pb2.CallContext
    id: str
    def __init__(self, context: _Optional[_Union[_common_pb2.CallContext, _Mapping]] = ..., id: _Optional[str] = ...) -> None: ...

class StartResponse(_message.Message):
    __slots__ = ("error",)
    ERROR_FIELD_NUMBER: _ClassVar[int]
    error: _common_pb2.CallError
    def __init__(self, error: _Optional[_Union[_common_pb2.CallError, _Mapping]] = ...) -> None: ...

class ReadRequest(_message.Message):
    __slots__ = ("context", "id", "sequence")
    CONTEXT_FIELD_NUMBER: _ClassVar[int]
    ID_FIELD_NUMBER: _ClassVar[int]
    SEQUENCE_FIELD_NUMBER: _ClassVar[int]
    context: _common_pb2.CallContext
    id: str
    sequence: int
    def __init__(self, context: _Optional[_Union[_common_pb2.CallContext, _Mapping]] = ..., id: _Optional[str] = ..., sequence: _Optional[int] = ...) -> None: ...

class ReadResponse(_message.Message):
    __slots__ = ("data", "sequence", "frame_end", "pending", "done", "error")
    DATA_FIELD_NUMBER: _ClassVar[int]
    SEQUENCE_FIELD_NUMBER: _ClassVar[int]
    FRAME_END_FIELD_NUMBER: _ClassVar[int]
    PENDING_FIELD_NUMBER: _ClassVar[int]
    DONE_FIELD_NUMBER: _ClassVar[int]
    ERROR_FIELD_NUMBER: _ClassVar[int]
    data: bytes
    sequence: int
    frame_end: bool
    pending: bool
    done: bool
    error: _common_pb2.CallError
    def __init__(self, data: _Optional[bytes] = ..., sequence: _Optional[int] = ..., frame_end: bool = ..., pending: bool = ..., done: bool = ..., error: _Optional[_Union[_common_pb2.CallError, _Mapping]] = ...) -> None: ...

class CloseRequest(_message.Message):
    __slots__ = ("context", "id")
    CONTEXT_FIELD_NUMBER: _ClassVar[int]
    ID_FIELD_NUMBER: _ClassVar[int]
    context: _common_pb2.CallContext
    id: str
    def __init__(self, context: _Optional[_Union[_common_pb2.CallContext, _Mapping]] = ..., id: _Optional[str] = ...) -> None: ...

class CloseResponse(_message.Message):
    __slots__ = ("error",)
    ERROR_FIELD_NUMBER: _ClassVar[int]
    error: _common_pb2.CallError
    def __init__(self, error: _Optional[_Union[_common_pb2.CallError, _Mapping]] = ...) -> None: ...
