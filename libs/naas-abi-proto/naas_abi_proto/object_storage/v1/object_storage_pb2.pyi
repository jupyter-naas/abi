import datetime

from naas_abi_proto.common.v1 import common_pb2 as _common_pb2
from google.protobuf import timestamp_pb2 as _timestamp_pb2
from google.protobuf.internal import containers as _containers
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from collections.abc import Iterable as _Iterable, Mapping as _Mapping
from typing import ClassVar as _ClassVar, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class ObjectMetaData(_message.Message):
    __slots__ = ("file_path", "file_name", "file_size_bytes", "created_time", "modified_time", "accessed_time", "permissions", "mime_type", "encoding")
    FILE_PATH_FIELD_NUMBER: _ClassVar[int]
    FILE_NAME_FIELD_NUMBER: _ClassVar[int]
    FILE_SIZE_BYTES_FIELD_NUMBER: _ClassVar[int]
    CREATED_TIME_FIELD_NUMBER: _ClassVar[int]
    MODIFIED_TIME_FIELD_NUMBER: _ClassVar[int]
    ACCESSED_TIME_FIELD_NUMBER: _ClassVar[int]
    PERMISSIONS_FIELD_NUMBER: _ClassVar[int]
    MIME_TYPE_FIELD_NUMBER: _ClassVar[int]
    ENCODING_FIELD_NUMBER: _ClassVar[int]
    file_path: str
    file_name: str
    file_size_bytes: int
    created_time: _timestamp_pb2.Timestamp
    modified_time: _timestamp_pb2.Timestamp
    accessed_time: _timestamp_pb2.Timestamp
    permissions: str
    mime_type: str
    encoding: str
    def __init__(self, file_path: _Optional[str] = ..., file_name: _Optional[str] = ..., file_size_bytes: _Optional[int] = ..., created_time: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., modified_time: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., accessed_time: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., permissions: _Optional[str] = ..., mime_type: _Optional[str] = ..., encoding: _Optional[str] = ...) -> None: ...

class GetObjectRequest(_message.Message):
    __slots__ = ("context", "prefix", "key")
    CONTEXT_FIELD_NUMBER: _ClassVar[int]
    PREFIX_FIELD_NUMBER: _ClassVar[int]
    KEY_FIELD_NUMBER: _ClassVar[int]
    context: _common_pb2.CallContext
    prefix: str
    key: str
    def __init__(self, context: _Optional[_Union[_common_pb2.CallContext, _Mapping]] = ..., prefix: _Optional[str] = ..., key: _Optional[str] = ...) -> None: ...

class GetObjectResponse(_message.Message):
    __slots__ = ("content", "error")
    CONTENT_FIELD_NUMBER: _ClassVar[int]
    ERROR_FIELD_NUMBER: _ClassVar[int]
    content: bytes
    error: _common_pb2.CallError
    def __init__(self, content: _Optional[bytes] = ..., error: _Optional[_Union[_common_pb2.CallError, _Mapping]] = ...) -> None: ...

class PutObjectRequest(_message.Message):
    __slots__ = ("context", "prefix", "key", "content")
    CONTEXT_FIELD_NUMBER: _ClassVar[int]
    PREFIX_FIELD_NUMBER: _ClassVar[int]
    KEY_FIELD_NUMBER: _ClassVar[int]
    CONTENT_FIELD_NUMBER: _ClassVar[int]
    context: _common_pb2.CallContext
    prefix: str
    key: str
    content: bytes
    def __init__(self, context: _Optional[_Union[_common_pb2.CallContext, _Mapping]] = ..., prefix: _Optional[str] = ..., key: _Optional[str] = ..., content: _Optional[bytes] = ...) -> None: ...

class PutObjectResponse(_message.Message):
    __slots__ = ("error",)
    ERROR_FIELD_NUMBER: _ClassVar[int]
    error: _common_pb2.CallError
    def __init__(self, error: _Optional[_Union[_common_pb2.CallError, _Mapping]] = ...) -> None: ...

class DeleteObjectRequest(_message.Message):
    __slots__ = ("context", "prefix", "key")
    CONTEXT_FIELD_NUMBER: _ClassVar[int]
    PREFIX_FIELD_NUMBER: _ClassVar[int]
    KEY_FIELD_NUMBER: _ClassVar[int]
    context: _common_pb2.CallContext
    prefix: str
    key: str
    def __init__(self, context: _Optional[_Union[_common_pb2.CallContext, _Mapping]] = ..., prefix: _Optional[str] = ..., key: _Optional[str] = ...) -> None: ...

class DeleteObjectResponse(_message.Message):
    __slots__ = ("error",)
    ERROR_FIELD_NUMBER: _ClassVar[int]
    error: _common_pb2.CallError
    def __init__(self, error: _Optional[_Union[_common_pb2.CallError, _Mapping]] = ...) -> None: ...

class ListObjectsRequest(_message.Message):
    __slots__ = ("context", "prefix")
    CONTEXT_FIELD_NUMBER: _ClassVar[int]
    PREFIX_FIELD_NUMBER: _ClassVar[int]
    context: _common_pb2.CallContext
    prefix: str
    def __init__(self, context: _Optional[_Union[_common_pb2.CallContext, _Mapping]] = ..., prefix: _Optional[str] = ...) -> None: ...

class ListObjectsResponse(_message.Message):
    __slots__ = ("keys", "error")
    KEYS_FIELD_NUMBER: _ClassVar[int]
    ERROR_FIELD_NUMBER: _ClassVar[int]
    keys: Keys
    error: _common_pb2.CallError
    def __init__(self, keys: _Optional[_Union[Keys, _Mapping]] = ..., error: _Optional[_Union[_common_pb2.CallError, _Mapping]] = ...) -> None: ...

class ListObjectsRecursiveRequest(_message.Message):
    __slots__ = ("context", "prefix")
    CONTEXT_FIELD_NUMBER: _ClassVar[int]
    PREFIX_FIELD_NUMBER: _ClassVar[int]
    context: _common_pb2.CallContext
    prefix: str
    def __init__(self, context: _Optional[_Union[_common_pb2.CallContext, _Mapping]] = ..., prefix: _Optional[str] = ...) -> None: ...

class ListObjectsRecursiveResponse(_message.Message):
    __slots__ = ("keys", "error")
    KEYS_FIELD_NUMBER: _ClassVar[int]
    ERROR_FIELD_NUMBER: _ClassVar[int]
    keys: Keys
    error: _common_pb2.CallError
    def __init__(self, keys: _Optional[_Union[Keys, _Mapping]] = ..., error: _Optional[_Union[_common_pb2.CallError, _Mapping]] = ...) -> None: ...

class Keys(_message.Message):
    __slots__ = ("keys",)
    KEYS_FIELD_NUMBER: _ClassVar[int]
    keys: _containers.RepeatedScalarFieldContainer[str]
    def __init__(self, keys: _Optional[_Iterable[str]] = ...) -> None: ...

class GetObjectMetadataRequest(_message.Message):
    __slots__ = ("context", "prefix", "key")
    CONTEXT_FIELD_NUMBER: _ClassVar[int]
    PREFIX_FIELD_NUMBER: _ClassVar[int]
    KEY_FIELD_NUMBER: _ClassVar[int]
    context: _common_pb2.CallContext
    prefix: str
    key: str
    def __init__(self, context: _Optional[_Union[_common_pb2.CallContext, _Mapping]] = ..., prefix: _Optional[str] = ..., key: _Optional[str] = ...) -> None: ...

class GetObjectMetadataResponse(_message.Message):
    __slots__ = ("metadata", "error")
    METADATA_FIELD_NUMBER: _ClassVar[int]
    ERROR_FIELD_NUMBER: _ClassVar[int]
    metadata: ObjectMetaData
    error: _common_pb2.CallError
    def __init__(self, metadata: _Optional[_Union[ObjectMetaData, _Mapping]] = ..., error: _Optional[_Union[_common_pb2.CallError, _Mapping]] = ...) -> None: ...
