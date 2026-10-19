from naas_abi_proto.common.v1 import common_pb2 as _common_pb2
from google.protobuf.internal import containers as _containers
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from collections.abc import Iterable as _Iterable, Mapping as _Mapping
from typing import ClassVar as _ClassVar, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class Header(_message.Message):
    __slots__ = ("name", "value")
    NAME_FIELD_NUMBER: _ClassVar[int]
    VALUE_FIELD_NUMBER: _ClassVar[int]
    name: str
    value: str
    def __init__(self, name: _Optional[str] = ..., value: _Optional[str] = ...) -> None: ...

class HttpRequest(_message.Message):
    __slots__ = ("context", "app", "method", "path", "query", "headers", "body", "root_path", "user_id", "principal_id", "principal_kind", "principal_name", "body_follows", "body_inbox", "max_body_bytes")
    CONTEXT_FIELD_NUMBER: _ClassVar[int]
    APP_FIELD_NUMBER: _ClassVar[int]
    METHOD_FIELD_NUMBER: _ClassVar[int]
    PATH_FIELD_NUMBER: _ClassVar[int]
    QUERY_FIELD_NUMBER: _ClassVar[int]
    HEADERS_FIELD_NUMBER: _ClassVar[int]
    BODY_FIELD_NUMBER: _ClassVar[int]
    ROOT_PATH_FIELD_NUMBER: _ClassVar[int]
    USER_ID_FIELD_NUMBER: _ClassVar[int]
    PRINCIPAL_ID_FIELD_NUMBER: _ClassVar[int]
    PRINCIPAL_KIND_FIELD_NUMBER: _ClassVar[int]
    PRINCIPAL_NAME_FIELD_NUMBER: _ClassVar[int]
    BODY_FOLLOWS_FIELD_NUMBER: _ClassVar[int]
    BODY_INBOX_FIELD_NUMBER: _ClassVar[int]
    MAX_BODY_BYTES_FIELD_NUMBER: _ClassVar[int]
    context: _common_pb2.CallContext
    app: str
    method: str
    path: str
    query: str
    headers: _containers.RepeatedCompositeFieldContainer[Header]
    body: bytes
    root_path: str
    user_id: str
    principal_id: str
    principal_kind: str
    principal_name: str
    body_follows: bool
    body_inbox: str
    max_body_bytes: int
    def __init__(self, context: _Optional[_Union[_common_pb2.CallContext, _Mapping]] = ..., app: _Optional[str] = ..., method: _Optional[str] = ..., path: _Optional[str] = ..., query: _Optional[str] = ..., headers: _Optional[_Iterable[_Union[Header, _Mapping]]] = ..., body: _Optional[bytes] = ..., root_path: _Optional[str] = ..., user_id: _Optional[str] = ..., principal_id: _Optional[str] = ..., principal_kind: _Optional[str] = ..., principal_name: _Optional[str] = ..., body_follows: bool = ..., body_inbox: _Optional[str] = ..., max_body_bytes: _Optional[int] = ...) -> None: ...

class HttpResponse(_message.Message):
    __slots__ = ("error", "status", "headers", "body", "body_follows", "body_inbox")
    ERROR_FIELD_NUMBER: _ClassVar[int]
    STATUS_FIELD_NUMBER: _ClassVar[int]
    HEADERS_FIELD_NUMBER: _ClassVar[int]
    BODY_FIELD_NUMBER: _ClassVar[int]
    BODY_FOLLOWS_FIELD_NUMBER: _ClassVar[int]
    BODY_INBOX_FIELD_NUMBER: _ClassVar[int]
    error: _common_pb2.CallError
    status: int
    headers: _containers.RepeatedCompositeFieldContainer[Header]
    body: bytes
    body_follows: bool
    body_inbox: str
    def __init__(self, error: _Optional[_Union[_common_pb2.CallError, _Mapping]] = ..., status: _Optional[int] = ..., headers: _Optional[_Iterable[_Union[Header, _Mapping]]] = ..., body: _Optional[bytes] = ..., body_follows: bool = ..., body_inbox: _Optional[str] = ...) -> None: ...

class BodyPull(_message.Message):
    __slots__ = ("sequence", "cancel")
    SEQUENCE_FIELD_NUMBER: _ClassVar[int]
    CANCEL_FIELD_NUMBER: _ClassVar[int]
    sequence: int
    cancel: bool
    def __init__(self, sequence: _Optional[int] = ..., cancel: bool = ...) -> None: ...

class BodyChunk(_message.Message):
    __slots__ = ("error", "sequence", "data", "last")
    ERROR_FIELD_NUMBER: _ClassVar[int]
    SEQUENCE_FIELD_NUMBER: _ClassVar[int]
    DATA_FIELD_NUMBER: _ClassVar[int]
    LAST_FIELD_NUMBER: _ClassVar[int]
    error: _common_pb2.CallError
    sequence: int
    data: bytes
    last: bool
    def __init__(self, error: _Optional[_Union[_common_pb2.CallError, _Mapping]] = ..., sequence: _Optional[int] = ..., data: _Optional[bytes] = ..., last: bool = ...) -> None: ...
