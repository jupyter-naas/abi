from naas_abi_proto.common.v1 import common_pb2 as _common_pb2
from google.protobuf.internal import enum_type_wrapper as _enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from collections.abc import Mapping as _Mapping
from typing import ClassVar as _ClassVar, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class DataType(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    DATA_TYPE_UNSPECIFIED: _ClassVar[DataType]
    DATA_TYPE_TEXT: _ClassVar[DataType]
    DATA_TYPE_JSON: _ClassVar[DataType]
    DATA_TYPE_BINARY: _ClassVar[DataType]
    DATA_TYPE_PICKLE: _ClassVar[DataType]
DATA_TYPE_UNSPECIFIED: DataType
DATA_TYPE_TEXT: DataType
DATA_TYPE_JSON: DataType
DATA_TYPE_BINARY: DataType
DATA_TYPE_PICKLE: DataType

class CachedData(_message.Message):
    __slots__ = ("key", "data", "data_type", "created_at")
    KEY_FIELD_NUMBER: _ClassVar[int]
    DATA_FIELD_NUMBER: _ClassVar[int]
    DATA_TYPE_FIELD_NUMBER: _ClassVar[int]
    CREATED_AT_FIELD_NUMBER: _ClassVar[int]
    key: str
    data: str
    data_type: DataType
    created_at: str
    def __init__(self, key: _Optional[str] = ..., data: _Optional[str] = ..., data_type: _Optional[_Union[DataType, str]] = ..., created_at: _Optional[str] = ...) -> None: ...

class GetRequest(_message.Message):
    __slots__ = ("context", "key")
    CONTEXT_FIELD_NUMBER: _ClassVar[int]
    KEY_FIELD_NUMBER: _ClassVar[int]
    context: _common_pb2.CallContext
    key: str
    def __init__(self, context: _Optional[_Union[_common_pb2.CallContext, _Mapping]] = ..., key: _Optional[str] = ...) -> None: ...

class GetResponse(_message.Message):
    __slots__ = ("value", "error")
    VALUE_FIELD_NUMBER: _ClassVar[int]
    ERROR_FIELD_NUMBER: _ClassVar[int]
    value: CachedData
    error: _common_pb2.CallError
    def __init__(self, value: _Optional[_Union[CachedData, _Mapping]] = ..., error: _Optional[_Union[_common_pb2.CallError, _Mapping]] = ...) -> None: ...

class SetRequest(_message.Message):
    __slots__ = ("context", "key", "value")
    CONTEXT_FIELD_NUMBER: _ClassVar[int]
    KEY_FIELD_NUMBER: _ClassVar[int]
    VALUE_FIELD_NUMBER: _ClassVar[int]
    context: _common_pb2.CallContext
    key: str
    value: CachedData
    def __init__(self, context: _Optional[_Union[_common_pb2.CallContext, _Mapping]] = ..., key: _Optional[str] = ..., value: _Optional[_Union[CachedData, _Mapping]] = ...) -> None: ...

class SetResponse(_message.Message):
    __slots__ = ("error",)
    ERROR_FIELD_NUMBER: _ClassVar[int]
    error: _common_pb2.CallError
    def __init__(self, error: _Optional[_Union[_common_pb2.CallError, _Mapping]] = ...) -> None: ...

class SetIfAbsentRequest(_message.Message):
    __slots__ = ("context", "key", "value")
    CONTEXT_FIELD_NUMBER: _ClassVar[int]
    KEY_FIELD_NUMBER: _ClassVar[int]
    VALUE_FIELD_NUMBER: _ClassVar[int]
    context: _common_pb2.CallContext
    key: str
    value: CachedData
    def __init__(self, context: _Optional[_Union[_common_pb2.CallContext, _Mapping]] = ..., key: _Optional[str] = ..., value: _Optional[_Union[CachedData, _Mapping]] = ...) -> None: ...

class SetIfAbsentResponse(_message.Message):
    __slots__ = ("value", "error")
    VALUE_FIELD_NUMBER: _ClassVar[int]
    ERROR_FIELD_NUMBER: _ClassVar[int]
    value: bool
    error: _common_pb2.CallError
    def __init__(self, value: bool = ..., error: _Optional[_Union[_common_pb2.CallError, _Mapping]] = ...) -> None: ...

class DeleteRequest(_message.Message):
    __slots__ = ("context", "key")
    CONTEXT_FIELD_NUMBER: _ClassVar[int]
    KEY_FIELD_NUMBER: _ClassVar[int]
    context: _common_pb2.CallContext
    key: str
    def __init__(self, context: _Optional[_Union[_common_pb2.CallContext, _Mapping]] = ..., key: _Optional[str] = ...) -> None: ...

class DeleteResponse(_message.Message):
    __slots__ = ("error",)
    ERROR_FIELD_NUMBER: _ClassVar[int]
    error: _common_pb2.CallError
    def __init__(self, error: _Optional[_Union[_common_pb2.CallError, _Mapping]] = ...) -> None: ...

class ExistsRequest(_message.Message):
    __slots__ = ("context", "key")
    CONTEXT_FIELD_NUMBER: _ClassVar[int]
    KEY_FIELD_NUMBER: _ClassVar[int]
    context: _common_pb2.CallContext
    key: str
    def __init__(self, context: _Optional[_Union[_common_pb2.CallContext, _Mapping]] = ..., key: _Optional[str] = ...) -> None: ...

class ExistsResponse(_message.Message):
    __slots__ = ("value", "error")
    VALUE_FIELD_NUMBER: _ClassVar[int]
    ERROR_FIELD_NUMBER: _ClassVar[int]
    value: bool
    error: _common_pb2.CallError
    def __init__(self, value: bool = ..., error: _Optional[_Union[_common_pb2.CallError, _Mapping]] = ...) -> None: ...
