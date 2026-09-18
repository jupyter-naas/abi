import datetime

from naas_abi_core.proto.common.v1 import common_pb2 as _common_pb2
from google.protobuf import timestamp_pb2 as _timestamp_pb2
from google.protobuf import struct_pb2 as _struct_pb2
from google.protobuf.internal import containers as _containers
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from collections.abc import Iterable as _Iterable, Mapping as _Mapping
from typing import ClassVar as _ClassVar, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class ActivityEvent(_message.Message):
    __slots__ = ("actor_id", "event_type", "timestamp", "correlation_id", "attributes")
    ACTOR_ID_FIELD_NUMBER: _ClassVar[int]
    EVENT_TYPE_FIELD_NUMBER: _ClassVar[int]
    TIMESTAMP_FIELD_NUMBER: _ClassVar[int]
    CORRELATION_ID_FIELD_NUMBER: _ClassVar[int]
    ATTRIBUTES_FIELD_NUMBER: _ClassVar[int]
    actor_id: str
    event_type: str
    timestamp: _timestamp_pb2.Timestamp
    correlation_id: str
    attributes: _struct_pb2.Struct
    def __init__(self, actor_id: _Optional[str] = ..., event_type: _Optional[str] = ..., timestamp: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., correlation_id: _Optional[str] = ..., attributes: _Optional[_Union[_struct_pb2.Struct, _Mapping]] = ...) -> None: ...

class ActivityLogQueryFilter(_message.Message):
    __slots__ = ("event_type", "since", "until", "limit")
    EVENT_TYPE_FIELD_NUMBER: _ClassVar[int]
    SINCE_FIELD_NUMBER: _ClassVar[int]
    UNTIL_FIELD_NUMBER: _ClassVar[int]
    LIMIT_FIELD_NUMBER: _ClassVar[int]
    event_type: str
    since: _timestamp_pb2.Timestamp
    until: _timestamp_pb2.Timestamp
    limit: int
    def __init__(self, event_type: _Optional[str] = ..., since: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., until: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., limit: _Optional[int] = ...) -> None: ...

class RecordRequest(_message.Message):
    __slots__ = ("context", "event")
    CONTEXT_FIELD_NUMBER: _ClassVar[int]
    EVENT_FIELD_NUMBER: _ClassVar[int]
    context: _common_pb2.CallContext
    event: ActivityEvent
    def __init__(self, context: _Optional[_Union[_common_pb2.CallContext, _Mapping]] = ..., event: _Optional[_Union[ActivityEvent, _Mapping]] = ...) -> None: ...

class RecordResponse(_message.Message):
    __slots__ = ("error",)
    ERROR_FIELD_NUMBER: _ClassVar[int]
    error: _common_pb2.CallError
    def __init__(self, error: _Optional[_Union[_common_pb2.CallError, _Mapping]] = ...) -> None: ...

class QueryRequest(_message.Message):
    __slots__ = ("context", "actor_id", "filter")
    CONTEXT_FIELD_NUMBER: _ClassVar[int]
    ACTOR_ID_FIELD_NUMBER: _ClassVar[int]
    FILTER_FIELD_NUMBER: _ClassVar[int]
    context: _common_pb2.CallContext
    actor_id: str
    filter: ActivityLogQueryFilter
    def __init__(self, context: _Optional[_Union[_common_pb2.CallContext, _Mapping]] = ..., actor_id: _Optional[str] = ..., filter: _Optional[_Union[ActivityLogQueryFilter, _Mapping]] = ...) -> None: ...

class QueryResponse(_message.Message):
    __slots__ = ("events", "error")
    EVENTS_FIELD_NUMBER: _ClassVar[int]
    ERROR_FIELD_NUMBER: _ClassVar[int]
    events: ActivityEvents
    error: _common_pb2.CallError
    def __init__(self, events: _Optional[_Union[ActivityEvents, _Mapping]] = ..., error: _Optional[_Union[_common_pb2.CallError, _Mapping]] = ...) -> None: ...

class ActivityEvents(_message.Message):
    __slots__ = ("events",)
    EVENTS_FIELD_NUMBER: _ClassVar[int]
    events: _containers.RepeatedCompositeFieldContainer[ActivityEvent]
    def __init__(self, events: _Optional[_Iterable[_Union[ActivityEvent, _Mapping]]] = ...) -> None: ...

class ListActorsRequest(_message.Message):
    __slots__ = ("context",)
    CONTEXT_FIELD_NUMBER: _ClassVar[int]
    context: _common_pb2.CallContext
    def __init__(self, context: _Optional[_Union[_common_pb2.CallContext, _Mapping]] = ...) -> None: ...

class ListActorsResponse(_message.Message):
    __slots__ = ("actors", "error")
    ACTORS_FIELD_NUMBER: _ClassVar[int]
    ERROR_FIELD_NUMBER: _ClassVar[int]
    actors: Actors
    error: _common_pb2.CallError
    def __init__(self, actors: _Optional[_Union[Actors, _Mapping]] = ..., error: _Optional[_Union[_common_pb2.CallError, _Mapping]] = ...) -> None: ...

class Actors(_message.Message):
    __slots__ = ("actors",)
    ACTORS_FIELD_NUMBER: _ClassVar[int]
    actors: _containers.RepeatedScalarFieldContainer[str]
    def __init__(self, actors: _Optional[_Iterable[str]] = ...) -> None: ...

class ShutdownRequest(_message.Message):
    __slots__ = ("context",)
    CONTEXT_FIELD_NUMBER: _ClassVar[int]
    context: _common_pb2.CallContext
    def __init__(self, context: _Optional[_Union[_common_pb2.CallContext, _Mapping]] = ...) -> None: ...

class ShutdownResponse(_message.Message):
    __slots__ = ("error",)
    ERROR_FIELD_NUMBER: _ClassVar[int]
    error: _common_pb2.CallError
    def __init__(self, error: _Optional[_Union[_common_pb2.CallError, _Mapping]] = ...) -> None: ...
