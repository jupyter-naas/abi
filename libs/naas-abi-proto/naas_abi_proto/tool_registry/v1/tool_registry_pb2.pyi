from naas_abi_proto.common.v1 import common_pb2 as _common_pb2
from google.protobuf.internal import containers as _containers
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from collections.abc import Iterable as _Iterable, Mapping as _Mapping
from typing import ClassVar as _ClassVar, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class ConfigRequirement(_message.Message):
    __slots__ = ("key", "description", "secret", "required")
    KEY_FIELD_NUMBER: _ClassVar[int]
    DESCRIPTION_FIELD_NUMBER: _ClassVar[int]
    SECRET_FIELD_NUMBER: _ClassVar[int]
    REQUIRED_FIELD_NUMBER: _ClassVar[int]
    key: str
    description: str
    secret: bool
    required: bool
    def __init__(self, key: _Optional[str] = ..., description: _Optional[str] = ..., secret: bool = ..., required: bool = ...) -> None: ...

class ToolRequirements(_message.Message):
    __slots__ = ("config", "requires_workspace")
    CONFIG_FIELD_NUMBER: _ClassVar[int]
    REQUIRES_WORKSPACE_FIELD_NUMBER: _ClassVar[int]
    config: _containers.RepeatedCompositeFieldContainer[ConfigRequirement]
    requires_workspace: bool
    def __init__(self, config: _Optional[_Iterable[_Union[ConfigRequirement, _Mapping]]] = ..., requires_workspace: bool = ...) -> None: ...

class ToolDefinition(_message.Message):
    __slots__ = ("id", "namespace", "name", "version", "module", "description", "input_schema_json", "output_schema_json", "tags", "requirements", "required_scopes", "remote")
    ID_FIELD_NUMBER: _ClassVar[int]
    NAMESPACE_FIELD_NUMBER: _ClassVar[int]
    NAME_FIELD_NUMBER: _ClassVar[int]
    VERSION_FIELD_NUMBER: _ClassVar[int]
    MODULE_FIELD_NUMBER: _ClassVar[int]
    DESCRIPTION_FIELD_NUMBER: _ClassVar[int]
    INPUT_SCHEMA_JSON_FIELD_NUMBER: _ClassVar[int]
    OUTPUT_SCHEMA_JSON_FIELD_NUMBER: _ClassVar[int]
    TAGS_FIELD_NUMBER: _ClassVar[int]
    REQUIREMENTS_FIELD_NUMBER: _ClassVar[int]
    REQUIRED_SCOPES_FIELD_NUMBER: _ClassVar[int]
    REMOTE_FIELD_NUMBER: _ClassVar[int]
    id: str
    namespace: str
    name: str
    version: str
    module: str
    description: str
    input_schema_json: bytes
    output_schema_json: bytes
    tags: _containers.RepeatedScalarFieldContainer[str]
    requirements: ToolRequirements
    required_scopes: _containers.RepeatedScalarFieldContainer[str]
    remote: bool
    def __init__(self, id: _Optional[str] = ..., namespace: _Optional[str] = ..., name: _Optional[str] = ..., version: _Optional[str] = ..., module: _Optional[str] = ..., description: _Optional[str] = ..., input_schema_json: _Optional[bytes] = ..., output_schema_json: _Optional[bytes] = ..., tags: _Optional[_Iterable[str]] = ..., requirements: _Optional[_Union[ToolRequirements, _Mapping]] = ..., required_scopes: _Optional[_Iterable[str]] = ..., remote: bool = ...) -> None: ...

class ToolAvailability(_message.Message):
    __slots__ = ("available", "missing_config")
    AVAILABLE_FIELD_NUMBER: _ClassVar[int]
    MISSING_CONFIG_FIELD_NUMBER: _ClassVar[int]
    available: bool
    missing_config: _containers.RepeatedScalarFieldContainer[str]
    def __init__(self, available: bool = ..., missing_config: _Optional[_Iterable[str]] = ...) -> None: ...

class ToolEntry(_message.Message):
    __slots__ = ("definition", "availability")
    DEFINITION_FIELD_NUMBER: _ClassVar[int]
    AVAILABILITY_FIELD_NUMBER: _ClassVar[int]
    definition: ToolDefinition
    availability: ToolAvailability
    def __init__(self, definition: _Optional[_Union[ToolDefinition, _Mapping]] = ..., availability: _Optional[_Union[ToolAvailability, _Mapping]] = ...) -> None: ...

class ToolMatch(_message.Message):
    __slots__ = ("tool", "score")
    TOOL_FIELD_NUMBER: _ClassVar[int]
    SCORE_FIELD_NUMBER: _ClassVar[int]
    tool: ToolEntry
    score: float
    def __init__(self, tool: _Optional[_Union[ToolEntry, _Mapping]] = ..., score: _Optional[float] = ...) -> None: ...

class ToolFilter(_message.Message):
    __slots__ = ("modules", "tags", "available_only")
    MODULES_FIELD_NUMBER: _ClassVar[int]
    TAGS_FIELD_NUMBER: _ClassVar[int]
    AVAILABLE_ONLY_FIELD_NUMBER: _ClassVar[int]
    modules: _containers.RepeatedScalarFieldContainer[str]
    tags: _containers.RepeatedScalarFieldContainer[str]
    available_only: bool
    def __init__(self, modules: _Optional[_Iterable[str]] = ..., tags: _Optional[_Iterable[str]] = ..., available_only: bool = ...) -> None: ...

class ListToolsRequest(_message.Message):
    __slots__ = ("context", "filter", "limit", "after")
    CONTEXT_FIELD_NUMBER: _ClassVar[int]
    FILTER_FIELD_NUMBER: _ClassVar[int]
    LIMIT_FIELD_NUMBER: _ClassVar[int]
    AFTER_FIELD_NUMBER: _ClassVar[int]
    context: _common_pb2.CallContext
    filter: ToolFilter
    limit: int
    after: str
    def __init__(self, context: _Optional[_Union[_common_pb2.CallContext, _Mapping]] = ..., filter: _Optional[_Union[ToolFilter, _Mapping]] = ..., limit: _Optional[int] = ..., after: _Optional[str] = ...) -> None: ...

class ListToolsResponse(_message.Message):
    __slots__ = ("tools", "next_after", "error")
    TOOLS_FIELD_NUMBER: _ClassVar[int]
    NEXT_AFTER_FIELD_NUMBER: _ClassVar[int]
    ERROR_FIELD_NUMBER: _ClassVar[int]
    tools: _containers.RepeatedCompositeFieldContainer[ToolEntry]
    next_after: str
    error: _common_pb2.CallError
    def __init__(self, tools: _Optional[_Iterable[_Union[ToolEntry, _Mapping]]] = ..., next_after: _Optional[str] = ..., error: _Optional[_Union[_common_pb2.CallError, _Mapping]] = ...) -> None: ...

class GetToolRequest(_message.Message):
    __slots__ = ("context", "ref")
    CONTEXT_FIELD_NUMBER: _ClassVar[int]
    REF_FIELD_NUMBER: _ClassVar[int]
    context: _common_pb2.CallContext
    ref: str
    def __init__(self, context: _Optional[_Union[_common_pb2.CallContext, _Mapping]] = ..., ref: _Optional[str] = ...) -> None: ...

class GetToolResponse(_message.Message):
    __slots__ = ("tool", "error")
    TOOL_FIELD_NUMBER: _ClassVar[int]
    ERROR_FIELD_NUMBER: _ClassVar[int]
    tool: ToolEntry
    error: _common_pb2.CallError
    def __init__(self, tool: _Optional[_Union[ToolEntry, _Mapping]] = ..., error: _Optional[_Union[_common_pb2.CallError, _Mapping]] = ...) -> None: ...

class SearchToolsRequest(_message.Message):
    __slots__ = ("context", "query", "limit", "min_score", "filter")
    CONTEXT_FIELD_NUMBER: _ClassVar[int]
    QUERY_FIELD_NUMBER: _ClassVar[int]
    LIMIT_FIELD_NUMBER: _ClassVar[int]
    MIN_SCORE_FIELD_NUMBER: _ClassVar[int]
    FILTER_FIELD_NUMBER: _ClassVar[int]
    context: _common_pb2.CallContext
    query: str
    limit: int
    min_score: float
    filter: ToolFilter
    def __init__(self, context: _Optional[_Union[_common_pb2.CallContext, _Mapping]] = ..., query: _Optional[str] = ..., limit: _Optional[int] = ..., min_score: _Optional[float] = ..., filter: _Optional[_Union[ToolFilter, _Mapping]] = ...) -> None: ...

class SearchToolsResponse(_message.Message):
    __slots__ = ("matches", "truncated", "error")
    MATCHES_FIELD_NUMBER: _ClassVar[int]
    TRUNCATED_FIELD_NUMBER: _ClassVar[int]
    ERROR_FIELD_NUMBER: _ClassVar[int]
    matches: _containers.RepeatedCompositeFieldContainer[ToolMatch]
    truncated: bool
    error: _common_pb2.CallError
    def __init__(self, matches: _Optional[_Iterable[_Union[ToolMatch, _Mapping]]] = ..., truncated: bool = ..., error: _Optional[_Union[_common_pb2.CallError, _Mapping]] = ...) -> None: ...

class InvokeToolRequest(_message.Message):
    __slots__ = ("context", "tool", "version", "arguments_json", "config_json", "secret_refs", "call_id")
    class SecretRefsEntry(_message.Message):
        __slots__ = ("key", "value")
        KEY_FIELD_NUMBER: _ClassVar[int]
        VALUE_FIELD_NUMBER: _ClassVar[int]
        key: str
        value: str
        def __init__(self, key: _Optional[str] = ..., value: _Optional[str] = ...) -> None: ...
    CONTEXT_FIELD_NUMBER: _ClassVar[int]
    TOOL_FIELD_NUMBER: _ClassVar[int]
    VERSION_FIELD_NUMBER: _ClassVar[int]
    ARGUMENTS_JSON_FIELD_NUMBER: _ClassVar[int]
    CONFIG_JSON_FIELD_NUMBER: _ClassVar[int]
    SECRET_REFS_FIELD_NUMBER: _ClassVar[int]
    CALL_ID_FIELD_NUMBER: _ClassVar[int]
    context: _common_pb2.CallContext
    tool: str
    version: str
    arguments_json: bytes
    config_json: bytes
    secret_refs: _containers.ScalarMap[str, str]
    call_id: str
    def __init__(self, context: _Optional[_Union[_common_pb2.CallContext, _Mapping]] = ..., tool: _Optional[str] = ..., version: _Optional[str] = ..., arguments_json: _Optional[bytes] = ..., config_json: _Optional[bytes] = ..., secret_refs: _Optional[_Mapping[str, str]] = ..., call_id: _Optional[str] = ...) -> None: ...

class InvokeToolResponse(_message.Message):
    __slots__ = ("result_json", "error")
    RESULT_JSON_FIELD_NUMBER: _ClassVar[int]
    ERROR_FIELD_NUMBER: _ClassVar[int]
    result_json: bytes
    error: _common_pb2.CallError
    def __init__(self, result_json: _Optional[bytes] = ..., error: _Optional[_Union[_common_pb2.CallError, _Mapping]] = ...) -> None: ...

class CancelToolRequest(_message.Message):
    __slots__ = ("context", "call_id")
    CONTEXT_FIELD_NUMBER: _ClassVar[int]
    CALL_ID_FIELD_NUMBER: _ClassVar[int]
    context: _common_pb2.CallContext
    call_id: str
    def __init__(self, context: _Optional[_Union[_common_pb2.CallContext, _Mapping]] = ..., call_id: _Optional[str] = ...) -> None: ...

class CancelToolResponse(_message.Message):
    __slots__ = ("cancelled", "error")
    CANCELLED_FIELD_NUMBER: _ClassVar[int]
    ERROR_FIELD_NUMBER: _ClassVar[int]
    cancelled: bool
    error: _common_pb2.CallError
    def __init__(self, cancelled: bool = ..., error: _Optional[_Union[_common_pb2.CallError, _Mapping]] = ...) -> None: ...
