from naas_abi_proto.common.v1 import common_pb2 as _common_pb2
from google.protobuf.internal import containers as _containers
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from collections.abc import Iterable as _Iterable, Mapping as _Mapping
from typing import ClassVar as _ClassVar, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class ModelRef(_message.Message):
    __slots__ = ("canonical_id", "provider", "kind", "model_id")
    CANONICAL_ID_FIELD_NUMBER: _ClassVar[int]
    PROVIDER_FIELD_NUMBER: _ClassVar[int]
    KIND_FIELD_NUMBER: _ClassVar[int]
    MODEL_ID_FIELD_NUMBER: _ClassVar[int]
    canonical_id: str
    provider: str
    kind: str
    model_id: str
    def __init__(self, canonical_id: _Optional[str] = ..., provider: _Optional[str] = ..., kind: _Optional[str] = ..., model_id: _Optional[str] = ...) -> None: ...

class ModelDescriptor(_message.Message):
    __slots__ = ("ref", "model_id", "name", "description", "metadata_json")
    REF_FIELD_NUMBER: _ClassVar[int]
    MODEL_ID_FIELD_NUMBER: _ClassVar[int]
    NAME_FIELD_NUMBER: _ClassVar[int]
    DESCRIPTION_FIELD_NUMBER: _ClassVar[int]
    METADATA_JSON_FIELD_NUMBER: _ClassVar[int]
    ref: ModelRef
    model_id: str
    name: str
    description: str
    metadata_json: bytes
    def __init__(self, ref: _Optional[_Union[ModelRef, _Mapping]] = ..., model_id: _Optional[str] = ..., name: _Optional[str] = ..., description: _Optional[str] = ..., metadata_json: _Optional[bytes] = ...) -> None: ...

class ChatMessage(_message.Message):
    __slots__ = ("type", "data_json")
    TYPE_FIELD_NUMBER: _ClassVar[int]
    DATA_JSON_FIELD_NUMBER: _ClassVar[int]
    type: str
    data_json: bytes
    def __init__(self, type: _Optional[str] = ..., data_json: _Optional[bytes] = ...) -> None: ...

class ListModelsRequest(_message.Message):
    __slots__ = ("context",)
    CONTEXT_FIELD_NUMBER: _ClassVar[int]
    context: _common_pb2.CallContext
    def __init__(self, context: _Optional[_Union[_common_pb2.CallContext, _Mapping]] = ...) -> None: ...

class ListModelsResponse(_message.Message):
    __slots__ = ("models", "default_chat_model_id", "default_embedding_model_id", "error")
    MODELS_FIELD_NUMBER: _ClassVar[int]
    DEFAULT_CHAT_MODEL_ID_FIELD_NUMBER: _ClassVar[int]
    DEFAULT_EMBEDDING_MODEL_ID_FIELD_NUMBER: _ClassVar[int]
    ERROR_FIELD_NUMBER: _ClassVar[int]
    models: _containers.RepeatedCompositeFieldContainer[ModelDescriptor]
    default_chat_model_id: str
    default_embedding_model_id: str
    error: _common_pb2.CallError
    def __init__(self, models: _Optional[_Iterable[_Union[ModelDescriptor, _Mapping]]] = ..., default_chat_model_id: _Optional[str] = ..., default_embedding_model_id: _Optional[str] = ..., error: _Optional[_Union[_common_pb2.CallError, _Mapping]] = ...) -> None: ...

class ResolveRequest(_message.Message):
    __slots__ = ("context", "ref")
    CONTEXT_FIELD_NUMBER: _ClassVar[int]
    REF_FIELD_NUMBER: _ClassVar[int]
    context: _common_pb2.CallContext
    ref: ModelRef
    def __init__(self, context: _Optional[_Union[_common_pb2.CallContext, _Mapping]] = ..., ref: _Optional[_Union[ModelRef, _Mapping]] = ...) -> None: ...

class ResolveResponse(_message.Message):
    __slots__ = ("model", "error")
    MODEL_FIELD_NUMBER: _ClassVar[int]
    ERROR_FIELD_NUMBER: _ClassVar[int]
    model: ModelDescriptor
    error: _common_pb2.CallError
    def __init__(self, model: _Optional[_Union[ModelDescriptor, _Mapping]] = ..., error: _Optional[_Union[_common_pb2.CallError, _Mapping]] = ...) -> None: ...

class ChatRequest(_message.Message):
    __slots__ = ("context", "ref", "messages", "stop", "options_json", "tools_json", "tool_options_json")
    CONTEXT_FIELD_NUMBER: _ClassVar[int]
    REF_FIELD_NUMBER: _ClassVar[int]
    MESSAGES_FIELD_NUMBER: _ClassVar[int]
    STOP_FIELD_NUMBER: _ClassVar[int]
    OPTIONS_JSON_FIELD_NUMBER: _ClassVar[int]
    TOOLS_JSON_FIELD_NUMBER: _ClassVar[int]
    TOOL_OPTIONS_JSON_FIELD_NUMBER: _ClassVar[int]
    context: _common_pb2.CallContext
    ref: ModelRef
    messages: _containers.RepeatedCompositeFieldContainer[ChatMessage]
    stop: _containers.RepeatedScalarFieldContainer[str]
    options_json: bytes
    tools_json: _containers.RepeatedScalarFieldContainer[bytes]
    tool_options_json: bytes
    def __init__(self, context: _Optional[_Union[_common_pb2.CallContext, _Mapping]] = ..., ref: _Optional[_Union[ModelRef, _Mapping]] = ..., messages: _Optional[_Iterable[_Union[ChatMessage, _Mapping]]] = ..., stop: _Optional[_Iterable[str]] = ..., options_json: _Optional[bytes] = ..., tools_json: _Optional[_Iterable[bytes]] = ..., tool_options_json: _Optional[bytes] = ...) -> None: ...

class ChatResponse(_message.Message):
    __slots__ = ("message", "error")
    MESSAGE_FIELD_NUMBER: _ClassVar[int]
    ERROR_FIELD_NUMBER: _ClassVar[int]
    message: ChatMessage
    error: _common_pb2.CallError
    def __init__(self, message: _Optional[_Union[ChatMessage, _Mapping]] = ..., error: _Optional[_Union[_common_pb2.CallError, _Mapping]] = ...) -> None: ...

class StreamOpenRequest(_message.Message):
    __slots__ = ("context", "chat")
    CONTEXT_FIELD_NUMBER: _ClassVar[int]
    CHAT_FIELD_NUMBER: _ClassVar[int]
    context: _common_pb2.CallContext
    chat: ChatRequest
    def __init__(self, context: _Optional[_Union[_common_pb2.CallContext, _Mapping]] = ..., chat: _Optional[_Union[ChatRequest, _Mapping]] = ...) -> None: ...

class StreamOpenResponse(_message.Message):
    __slots__ = ("stream_id", "error")
    STREAM_ID_FIELD_NUMBER: _ClassVar[int]
    ERROR_FIELD_NUMBER: _ClassVar[int]
    stream_id: str
    error: _common_pb2.CallError
    def __init__(self, stream_id: _Optional[str] = ..., error: _Optional[_Union[_common_pb2.CallError, _Mapping]] = ...) -> None: ...

class StreamNextRequest(_message.Message):
    __slots__ = ("context", "stream_id", "sequence")
    CONTEXT_FIELD_NUMBER: _ClassVar[int]
    STREAM_ID_FIELD_NUMBER: _ClassVar[int]
    SEQUENCE_FIELD_NUMBER: _ClassVar[int]
    context: _common_pb2.CallContext
    stream_id: str
    sequence: int
    def __init__(self, context: _Optional[_Union[_common_pb2.CallContext, _Mapping]] = ..., stream_id: _Optional[str] = ..., sequence: _Optional[int] = ...) -> None: ...

class StreamNextResponse(_message.Message):
    __slots__ = ("chunk", "done", "sequence", "error")
    CHUNK_FIELD_NUMBER: _ClassVar[int]
    DONE_FIELD_NUMBER: _ClassVar[int]
    SEQUENCE_FIELD_NUMBER: _ClassVar[int]
    ERROR_FIELD_NUMBER: _ClassVar[int]
    chunk: ChatMessage
    done: bool
    sequence: int
    error: _common_pb2.CallError
    def __init__(self, chunk: _Optional[_Union[ChatMessage, _Mapping]] = ..., done: bool = ..., sequence: _Optional[int] = ..., error: _Optional[_Union[_common_pb2.CallError, _Mapping]] = ...) -> None: ...

class StreamCloseRequest(_message.Message):
    __slots__ = ("context", "stream_id")
    CONTEXT_FIELD_NUMBER: _ClassVar[int]
    STREAM_ID_FIELD_NUMBER: _ClassVar[int]
    context: _common_pb2.CallContext
    stream_id: str
    def __init__(self, context: _Optional[_Union[_common_pb2.CallContext, _Mapping]] = ..., stream_id: _Optional[str] = ...) -> None: ...

class StreamCloseResponse(_message.Message):
    __slots__ = ("error",)
    ERROR_FIELD_NUMBER: _ClassVar[int]
    error: _common_pb2.CallError
    def __init__(self, error: _Optional[_Union[_common_pb2.CallError, _Mapping]] = ...) -> None: ...

class EmbedRequest(_message.Message):
    __slots__ = ("context", "ref", "texts", "query")
    CONTEXT_FIELD_NUMBER: _ClassVar[int]
    REF_FIELD_NUMBER: _ClassVar[int]
    TEXTS_FIELD_NUMBER: _ClassVar[int]
    QUERY_FIELD_NUMBER: _ClassVar[int]
    context: _common_pb2.CallContext
    ref: ModelRef
    texts: _containers.RepeatedScalarFieldContainer[str]
    query: bool
    def __init__(self, context: _Optional[_Union[_common_pb2.CallContext, _Mapping]] = ..., ref: _Optional[_Union[ModelRef, _Mapping]] = ..., texts: _Optional[_Iterable[str]] = ..., query: bool = ...) -> None: ...

class Vector(_message.Message):
    __slots__ = ("values",)
    VALUES_FIELD_NUMBER: _ClassVar[int]
    values: _containers.RepeatedScalarFieldContainer[float]
    def __init__(self, values: _Optional[_Iterable[float]] = ...) -> None: ...

class EmbedResponse(_message.Message):
    __slots__ = ("vectors", "error")
    VECTORS_FIELD_NUMBER: _ClassVar[int]
    ERROR_FIELD_NUMBER: _ClassVar[int]
    vectors: _containers.RepeatedCompositeFieldContainer[Vector]
    error: _common_pb2.CallError
    def __init__(self, vectors: _Optional[_Iterable[_Union[Vector, _Mapping]]] = ..., error: _Optional[_Union[_common_pb2.CallError, _Mapping]] = ...) -> None: ...
