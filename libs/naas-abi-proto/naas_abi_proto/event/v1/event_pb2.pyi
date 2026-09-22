from naas_abi_proto.common.v1 import common_pb2 as _common_pb2
from google.protobuf import struct_pb2 as _struct_pb2
from google.protobuf.internal import containers as _containers
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from collections.abc import Iterable as _Iterable, Mapping as _Mapping
from typing import ClassVar as _ClassVar, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class StoredEvent(_message.Message):
    __slots__ = ("id", "event_type", "seq", "timestamp", "payload")
    ID_FIELD_NUMBER: _ClassVar[int]
    EVENT_TYPE_FIELD_NUMBER: _ClassVar[int]
    SEQ_FIELD_NUMBER: _ClassVar[int]
    TIMESTAMP_FIELD_NUMBER: _ClassVar[int]
    PAYLOAD_FIELD_NUMBER: _ClassVar[int]
    id: str
    event_type: str
    seq: int
    timestamp: str
    payload: bytes
    def __init__(self, id: _Optional[str] = ..., event_type: _Optional[str] = ..., seq: _Optional[int] = ..., timestamp: _Optional[str] = ..., payload: _Optional[bytes] = ...) -> None: ...

class StoredEvents(_message.Message):
    __slots__ = ("events",)
    EVENTS_FIELD_NUMBER: _ClassVar[int]
    events: _containers.RepeatedCompositeFieldContainer[StoredEvent]
    def __init__(self, events: _Optional[_Iterable[_Union[StoredEvent, _Mapping]]] = ...) -> None: ...

class AppendRequest(_message.Message):
    __slots__ = ("context", "event_id", "event_type", "timestamp", "payload")
    CONTEXT_FIELD_NUMBER: _ClassVar[int]
    EVENT_ID_FIELD_NUMBER: _ClassVar[int]
    EVENT_TYPE_FIELD_NUMBER: _ClassVar[int]
    TIMESTAMP_FIELD_NUMBER: _ClassVar[int]
    PAYLOAD_FIELD_NUMBER: _ClassVar[int]
    context: _common_pb2.CallContext
    event_id: str
    event_type: str
    timestamp: str
    payload: bytes
    def __init__(self, context: _Optional[_Union[_common_pb2.CallContext, _Mapping]] = ..., event_id: _Optional[str] = ..., event_type: _Optional[str] = ..., timestamp: _Optional[str] = ..., payload: _Optional[bytes] = ...) -> None: ...

class AppendResponse(_message.Message):
    __slots__ = ("event", "error")
    EVENT_FIELD_NUMBER: _ClassVar[int]
    ERROR_FIELD_NUMBER: _ClassVar[int]
    event: StoredEvent
    error: _common_pb2.CallError
    def __init__(self, event: _Optional[_Union[StoredEvent, _Mapping]] = ..., error: _Optional[_Union[_common_pb2.CallError, _Mapping]] = ...) -> None: ...

class QueryRequest(_message.Message):
    __slots__ = ("context", "event_type", "since_seq", "until_seq", "since_timestamp", "until_timestamp", "json_filter", "limit", "newest_first", "search")
    CONTEXT_FIELD_NUMBER: _ClassVar[int]
    EVENT_TYPE_FIELD_NUMBER: _ClassVar[int]
    SINCE_SEQ_FIELD_NUMBER: _ClassVar[int]
    UNTIL_SEQ_FIELD_NUMBER: _ClassVar[int]
    SINCE_TIMESTAMP_FIELD_NUMBER: _ClassVar[int]
    UNTIL_TIMESTAMP_FIELD_NUMBER: _ClassVar[int]
    JSON_FILTER_FIELD_NUMBER: _ClassVar[int]
    LIMIT_FIELD_NUMBER: _ClassVar[int]
    NEWEST_FIRST_FIELD_NUMBER: _ClassVar[int]
    SEARCH_FIELD_NUMBER: _ClassVar[int]
    context: _common_pb2.CallContext
    event_type: str
    since_seq: int
    until_seq: int
    since_timestamp: str
    until_timestamp: str
    json_filter: _struct_pb2.Struct
    limit: int
    newest_first: bool
    search: str
    def __init__(self, context: _Optional[_Union[_common_pb2.CallContext, _Mapping]] = ..., event_type: _Optional[str] = ..., since_seq: _Optional[int] = ..., until_seq: _Optional[int] = ..., since_timestamp: _Optional[str] = ..., until_timestamp: _Optional[str] = ..., json_filter: _Optional[_Union[_struct_pb2.Struct, _Mapping]] = ..., limit: _Optional[int] = ..., newest_first: bool = ..., search: _Optional[str] = ...) -> None: ...

class QueryResponse(_message.Message):
    __slots__ = ("events", "error")
    EVENTS_FIELD_NUMBER: _ClassVar[int]
    ERROR_FIELD_NUMBER: _ClassVar[int]
    events: StoredEvents
    error: _common_pb2.CallError
    def __init__(self, events: _Optional[_Union[StoredEvents, _Mapping]] = ..., error: _Optional[_Union[_common_pb2.CallError, _Mapping]] = ...) -> None: ...

class MaxSeqRequest(_message.Message):
    __slots__ = ("context", "event_type")
    CONTEXT_FIELD_NUMBER: _ClassVar[int]
    EVENT_TYPE_FIELD_NUMBER: _ClassVar[int]
    context: _common_pb2.CallContext
    event_type: str
    def __init__(self, context: _Optional[_Union[_common_pb2.CallContext, _Mapping]] = ..., event_type: _Optional[str] = ...) -> None: ...

class MaxSeqResponse(_message.Message):
    __slots__ = ("seq", "error")
    SEQ_FIELD_NUMBER: _ClassVar[int]
    ERROR_FIELD_NUMBER: _ClassVar[int]
    seq: int
    error: _common_pb2.CallError
    def __init__(self, seq: _Optional[int] = ..., error: _Optional[_Union[_common_pb2.CallError, _Mapping]] = ...) -> None: ...

class GetCursorRequest(_message.Message):
    __slots__ = ("context", "consumer_id", "event_type")
    CONTEXT_FIELD_NUMBER: _ClassVar[int]
    CONSUMER_ID_FIELD_NUMBER: _ClassVar[int]
    EVENT_TYPE_FIELD_NUMBER: _ClassVar[int]
    context: _common_pb2.CallContext
    consumer_id: str
    event_type: str
    def __init__(self, context: _Optional[_Union[_common_pb2.CallContext, _Mapping]] = ..., consumer_id: _Optional[str] = ..., event_type: _Optional[str] = ...) -> None: ...

class GetCursorResponse(_message.Message):
    __slots__ = ("last_seq", "error")
    LAST_SEQ_FIELD_NUMBER: _ClassVar[int]
    ERROR_FIELD_NUMBER: _ClassVar[int]
    last_seq: int
    error: _common_pb2.CallError
    def __init__(self, last_seq: _Optional[int] = ..., error: _Optional[_Union[_common_pb2.CallError, _Mapping]] = ...) -> None: ...

class SetCursorRequest(_message.Message):
    __slots__ = ("context", "consumer_id", "event_type", "last_seq")
    CONTEXT_FIELD_NUMBER: _ClassVar[int]
    CONSUMER_ID_FIELD_NUMBER: _ClassVar[int]
    EVENT_TYPE_FIELD_NUMBER: _ClassVar[int]
    LAST_SEQ_FIELD_NUMBER: _ClassVar[int]
    context: _common_pb2.CallContext
    consumer_id: str
    event_type: str
    last_seq: int
    def __init__(self, context: _Optional[_Union[_common_pb2.CallContext, _Mapping]] = ..., consumer_id: _Optional[str] = ..., event_type: _Optional[str] = ..., last_seq: _Optional[int] = ...) -> None: ...

class SetCursorResponse(_message.Message):
    __slots__ = ("error",)
    ERROR_FIELD_NUMBER: _ClassVar[int]
    error: _common_pb2.CallError
    def __init__(self, error: _Optional[_Union[_common_pb2.CallError, _Mapping]] = ...) -> None: ...

class QueryForConsumerRequest(_message.Message):
    __slots__ = ("context", "consumer_id", "event_type", "limit", "json_filter")
    CONTEXT_FIELD_NUMBER: _ClassVar[int]
    CONSUMER_ID_FIELD_NUMBER: _ClassVar[int]
    EVENT_TYPE_FIELD_NUMBER: _ClassVar[int]
    LIMIT_FIELD_NUMBER: _ClassVar[int]
    JSON_FILTER_FIELD_NUMBER: _ClassVar[int]
    context: _common_pb2.CallContext
    consumer_id: str
    event_type: str
    limit: int
    json_filter: _struct_pb2.Struct
    def __init__(self, context: _Optional[_Union[_common_pb2.CallContext, _Mapping]] = ..., consumer_id: _Optional[str] = ..., event_type: _Optional[str] = ..., limit: _Optional[int] = ..., json_filter: _Optional[_Union[_struct_pb2.Struct, _Mapping]] = ...) -> None: ...

class QueryForConsumerResponse(_message.Message):
    __slots__ = ("events", "error")
    EVENTS_FIELD_NUMBER: _ClassVar[int]
    ERROR_FIELD_NUMBER: _ClassVar[int]
    events: StoredEvents
    error: _common_pb2.CallError
    def __init__(self, events: _Optional[_Union[StoredEvents, _Mapping]] = ..., error: _Optional[_Union[_common_pb2.CallError, _Mapping]] = ...) -> None: ...
