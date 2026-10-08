from naas_abi_proto.common.v1 import common_pb2 as _common_pb2
from google.protobuf.internal import containers as _containers
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from collections.abc import Iterable as _Iterable, Mapping as _Mapping
from typing import ClassVar as _ClassVar, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class KVLockTimeoutDetail(_message.Message):
    __slots__ = ("key", "attempts", "timeout_seconds")
    KEY_FIELD_NUMBER: _ClassVar[int]
    ATTEMPTS_FIELD_NUMBER: _ClassVar[int]
    TIMEOUT_SECONDS_FIELD_NUMBER: _ClassVar[int]
    key: str
    attempts: int
    timeout_seconds: float
    def __init__(self, key: _Optional[str] = ..., attempts: _Optional[int] = ..., timeout_seconds: _Optional[float] = ...) -> None: ...

class GetRequest(_message.Message):
    __slots__ = ("context", "key")
    CONTEXT_FIELD_NUMBER: _ClassVar[int]
    KEY_FIELD_NUMBER: _ClassVar[int]
    context: _common_pb2.CallContext
    key: str
    def __init__(self, context: _Optional[_Union[_common_pb2.CallContext, _Mapping]] = ..., key: _Optional[str] = ...) -> None: ...

class GetResponse(_message.Message):
    __slots__ = ("value", "error", "lock_timeout_detail")
    VALUE_FIELD_NUMBER: _ClassVar[int]
    ERROR_FIELD_NUMBER: _ClassVar[int]
    LOCK_TIMEOUT_DETAIL_FIELD_NUMBER: _ClassVar[int]
    value: bytes
    error: _common_pb2.CallError
    lock_timeout_detail: KVLockTimeoutDetail
    def __init__(self, value: _Optional[bytes] = ..., error: _Optional[_Union[_common_pb2.CallError, _Mapping]] = ..., lock_timeout_detail: _Optional[_Union[KVLockTimeoutDetail, _Mapping]] = ...) -> None: ...

class SetRequest(_message.Message):
    __slots__ = ("context", "key", "value", "ttl")
    CONTEXT_FIELD_NUMBER: _ClassVar[int]
    KEY_FIELD_NUMBER: _ClassVar[int]
    VALUE_FIELD_NUMBER: _ClassVar[int]
    TTL_FIELD_NUMBER: _ClassVar[int]
    context: _common_pb2.CallContext
    key: str
    value: bytes
    ttl: int
    def __init__(self, context: _Optional[_Union[_common_pb2.CallContext, _Mapping]] = ..., key: _Optional[str] = ..., value: _Optional[bytes] = ..., ttl: _Optional[int] = ...) -> None: ...

class SetResponse(_message.Message):
    __slots__ = ("error", "lock_timeout_detail")
    ERROR_FIELD_NUMBER: _ClassVar[int]
    LOCK_TIMEOUT_DETAIL_FIELD_NUMBER: _ClassVar[int]
    error: _common_pb2.CallError
    lock_timeout_detail: KVLockTimeoutDetail
    def __init__(self, error: _Optional[_Union[_common_pb2.CallError, _Mapping]] = ..., lock_timeout_detail: _Optional[_Union[KVLockTimeoutDetail, _Mapping]] = ...) -> None: ...

class SetIfNotExistsRequest(_message.Message):
    __slots__ = ("context", "key", "value", "ttl")
    CONTEXT_FIELD_NUMBER: _ClassVar[int]
    KEY_FIELD_NUMBER: _ClassVar[int]
    VALUE_FIELD_NUMBER: _ClassVar[int]
    TTL_FIELD_NUMBER: _ClassVar[int]
    context: _common_pb2.CallContext
    key: str
    value: bytes
    ttl: int
    def __init__(self, context: _Optional[_Union[_common_pb2.CallContext, _Mapping]] = ..., key: _Optional[str] = ..., value: _Optional[bytes] = ..., ttl: _Optional[int] = ...) -> None: ...

class SetIfNotExistsResponse(_message.Message):
    __slots__ = ("ok_value", "error", "lock_timeout_detail")
    OK_VALUE_FIELD_NUMBER: _ClassVar[int]
    ERROR_FIELD_NUMBER: _ClassVar[int]
    LOCK_TIMEOUT_DETAIL_FIELD_NUMBER: _ClassVar[int]
    ok_value: bool
    error: _common_pb2.CallError
    lock_timeout_detail: KVLockTimeoutDetail
    def __init__(self, ok_value: bool = ..., error: _Optional[_Union[_common_pb2.CallError, _Mapping]] = ..., lock_timeout_detail: _Optional[_Union[KVLockTimeoutDetail, _Mapping]] = ...) -> None: ...

class DeleteRequest(_message.Message):
    __slots__ = ("context", "key")
    CONTEXT_FIELD_NUMBER: _ClassVar[int]
    KEY_FIELD_NUMBER: _ClassVar[int]
    context: _common_pb2.CallContext
    key: str
    def __init__(self, context: _Optional[_Union[_common_pb2.CallContext, _Mapping]] = ..., key: _Optional[str] = ...) -> None: ...

class DeleteResponse(_message.Message):
    __slots__ = ("error", "lock_timeout_detail")
    ERROR_FIELD_NUMBER: _ClassVar[int]
    LOCK_TIMEOUT_DETAIL_FIELD_NUMBER: _ClassVar[int]
    error: _common_pb2.CallError
    lock_timeout_detail: KVLockTimeoutDetail
    def __init__(self, error: _Optional[_Union[_common_pb2.CallError, _Mapping]] = ..., lock_timeout_detail: _Optional[_Union[KVLockTimeoutDetail, _Mapping]] = ...) -> None: ...

class DeleteIfValueMatchesRequest(_message.Message):
    __slots__ = ("context", "key", "value")
    CONTEXT_FIELD_NUMBER: _ClassVar[int]
    KEY_FIELD_NUMBER: _ClassVar[int]
    VALUE_FIELD_NUMBER: _ClassVar[int]
    context: _common_pb2.CallContext
    key: str
    value: bytes
    def __init__(self, context: _Optional[_Union[_common_pb2.CallContext, _Mapping]] = ..., key: _Optional[str] = ..., value: _Optional[bytes] = ...) -> None: ...

class DeleteIfValueMatchesResponse(_message.Message):
    __slots__ = ("ok_value", "error", "lock_timeout_detail")
    OK_VALUE_FIELD_NUMBER: _ClassVar[int]
    ERROR_FIELD_NUMBER: _ClassVar[int]
    LOCK_TIMEOUT_DETAIL_FIELD_NUMBER: _ClassVar[int]
    ok_value: bool
    error: _common_pb2.CallError
    lock_timeout_detail: KVLockTimeoutDetail
    def __init__(self, ok_value: bool = ..., error: _Optional[_Union[_common_pb2.CallError, _Mapping]] = ..., lock_timeout_detail: _Optional[_Union[KVLockTimeoutDetail, _Mapping]] = ...) -> None: ...

class ExistsRequest(_message.Message):
    __slots__ = ("context", "key")
    CONTEXT_FIELD_NUMBER: _ClassVar[int]
    KEY_FIELD_NUMBER: _ClassVar[int]
    context: _common_pb2.CallContext
    key: str
    def __init__(self, context: _Optional[_Union[_common_pb2.CallContext, _Mapping]] = ..., key: _Optional[str] = ...) -> None: ...

class ExistsResponse(_message.Message):
    __slots__ = ("ok_value", "error", "lock_timeout_detail")
    OK_VALUE_FIELD_NUMBER: _ClassVar[int]
    ERROR_FIELD_NUMBER: _ClassVar[int]
    LOCK_TIMEOUT_DETAIL_FIELD_NUMBER: _ClassVar[int]
    ok_value: bool
    error: _common_pb2.CallError
    lock_timeout_detail: KVLockTimeoutDetail
    def __init__(self, ok_value: bool = ..., error: _Optional[_Union[_common_pb2.CallError, _Mapping]] = ..., lock_timeout_detail: _Optional[_Union[KVLockTimeoutDetail, _Mapping]] = ...) -> None: ...

class ListKeysRequest(_message.Message):
    __slots__ = ("context", "prefix", "limit", "after")
    CONTEXT_FIELD_NUMBER: _ClassVar[int]
    PREFIX_FIELD_NUMBER: _ClassVar[int]
    LIMIT_FIELD_NUMBER: _ClassVar[int]
    AFTER_FIELD_NUMBER: _ClassVar[int]
    context: _common_pb2.CallContext
    prefix: str
    limit: int
    after: str
    def __init__(self, context: _Optional[_Union[_common_pb2.CallContext, _Mapping]] = ..., prefix: _Optional[str] = ..., limit: _Optional[int] = ..., after: _Optional[str] = ...) -> None: ...

class ListKeysResponse(_message.Message):
    __slots__ = ("error", "keys", "next_after", "lock_timeout_detail")
    ERROR_FIELD_NUMBER: _ClassVar[int]
    KEYS_FIELD_NUMBER: _ClassVar[int]
    NEXT_AFTER_FIELD_NUMBER: _ClassVar[int]
    LOCK_TIMEOUT_DETAIL_FIELD_NUMBER: _ClassVar[int]
    error: _common_pb2.CallError
    keys: _containers.RepeatedScalarFieldContainer[str]
    next_after: str
    lock_timeout_detail: KVLockTimeoutDetail
    def __init__(self, error: _Optional[_Union[_common_pb2.CallError, _Mapping]] = ..., keys: _Optional[_Iterable[str]] = ..., next_after: _Optional[str] = ..., lock_timeout_detail: _Optional[_Union[KVLockTimeoutDetail, _Mapping]] = ...) -> None: ...

class GetTtlRequest(_message.Message):
    __slots__ = ("context", "key")
    CONTEXT_FIELD_NUMBER: _ClassVar[int]
    KEY_FIELD_NUMBER: _ClassVar[int]
    context: _common_pb2.CallContext
    key: str
    def __init__(self, context: _Optional[_Union[_common_pb2.CallContext, _Mapping]] = ..., key: _Optional[str] = ...) -> None: ...

class GetTtlResponse(_message.Message):
    __slots__ = ("error", "seconds", "lock_timeout_detail")
    ERROR_FIELD_NUMBER: _ClassVar[int]
    SECONDS_FIELD_NUMBER: _ClassVar[int]
    LOCK_TIMEOUT_DETAIL_FIELD_NUMBER: _ClassVar[int]
    error: _common_pb2.CallError
    seconds: int
    lock_timeout_detail: KVLockTimeoutDetail
    def __init__(self, error: _Optional[_Union[_common_pb2.CallError, _Mapping]] = ..., seconds: _Optional[int] = ..., lock_timeout_detail: _Optional[_Union[KVLockTimeoutDetail, _Mapping]] = ...) -> None: ...
