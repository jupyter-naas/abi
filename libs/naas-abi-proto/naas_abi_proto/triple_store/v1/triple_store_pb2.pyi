from naas_abi_proto.common.v1 import common_pb2 as _common_pb2
from google.protobuf.internal import containers as _containers
from google.protobuf.internal import enum_type_wrapper as _enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from collections.abc import Iterable as _Iterable, Mapping as _Mapping
from typing import ClassVar as _ClassVar, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class OntologyEventType(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    ONTOLOGY_EVENT_TYPE_UNSPECIFIED: _ClassVar[OntologyEventType]
    ONTOLOGY_EVENT_TYPE_INSERT: _ClassVar[OntologyEventType]
    ONTOLOGY_EVENT_TYPE_DELETE: _ClassVar[OntologyEventType]
ONTOLOGY_EVENT_TYPE_UNSPECIFIED: OntologyEventType
ONTOLOGY_EVENT_TYPE_INSERT: OntologyEventType
ONTOLOGY_EVENT_TYPE_DELETE: OntologyEventType

class TripleStoreRequestErrorDetail(_message.Message):
    __slots__ = ("operation", "status_code", "response_body", "endpoint", "attempts")
    OPERATION_FIELD_NUMBER: _ClassVar[int]
    STATUS_CODE_FIELD_NUMBER: _ClassVar[int]
    RESPONSE_BODY_FIELD_NUMBER: _ClassVar[int]
    ENDPOINT_FIELD_NUMBER: _ClassVar[int]
    ATTEMPTS_FIELD_NUMBER: _ClassVar[int]
    operation: str
    status_code: int
    response_body: str
    endpoint: str
    attempts: int
    def __init__(self, operation: _Optional[str] = ..., status_code: _Optional[int] = ..., response_body: _Optional[str] = ..., endpoint: _Optional[str] = ..., attempts: _Optional[int] = ...) -> None: ...

class TriplePattern(_message.Message):
    __slots__ = ("subject", "predicate", "object")
    SUBJECT_FIELD_NUMBER: _ClassVar[int]
    PREDICATE_FIELD_NUMBER: _ClassVar[int]
    OBJECT_FIELD_NUMBER: _ClassVar[int]
    subject: str
    predicate: str
    object: str
    def __init__(self, subject: _Optional[str] = ..., predicate: _Optional[str] = ..., object: _Optional[str] = ...) -> None: ...

class InsertRequest(_message.Message):
    __slots__ = ("context", "triples_nt", "graph_name")
    CONTEXT_FIELD_NUMBER: _ClassVar[int]
    TRIPLES_NT_FIELD_NUMBER: _ClassVar[int]
    GRAPH_NAME_FIELD_NUMBER: _ClassVar[int]
    context: _common_pb2.CallContext
    triples_nt: bytes
    graph_name: str
    def __init__(self, context: _Optional[_Union[_common_pb2.CallContext, _Mapping]] = ..., triples_nt: _Optional[bytes] = ..., graph_name: _Optional[str] = ...) -> None: ...

class InsertResponse(_message.Message):
    __slots__ = ("error", "error_detail")
    ERROR_FIELD_NUMBER: _ClassVar[int]
    ERROR_DETAIL_FIELD_NUMBER: _ClassVar[int]
    error: _common_pb2.CallError
    error_detail: TripleStoreRequestErrorDetail
    def __init__(self, error: _Optional[_Union[_common_pb2.CallError, _Mapping]] = ..., error_detail: _Optional[_Union[TripleStoreRequestErrorDetail, _Mapping]] = ...) -> None: ...

class RemoveRequest(_message.Message):
    __slots__ = ("context", "triples_nt", "graph_name")
    CONTEXT_FIELD_NUMBER: _ClassVar[int]
    TRIPLES_NT_FIELD_NUMBER: _ClassVar[int]
    GRAPH_NAME_FIELD_NUMBER: _ClassVar[int]
    context: _common_pb2.CallContext
    triples_nt: bytes
    graph_name: str
    def __init__(self, context: _Optional[_Union[_common_pb2.CallContext, _Mapping]] = ..., triples_nt: _Optional[bytes] = ..., graph_name: _Optional[str] = ...) -> None: ...

class RemoveResponse(_message.Message):
    __slots__ = ("error", "error_detail")
    ERROR_FIELD_NUMBER: _ClassVar[int]
    ERROR_DETAIL_FIELD_NUMBER: _ClassVar[int]
    error: _common_pb2.CallError
    error_detail: TripleStoreRequestErrorDetail
    def __init__(self, error: _Optional[_Union[_common_pb2.CallError, _Mapping]] = ..., error_detail: _Optional[_Union[TripleStoreRequestErrorDetail, _Mapping]] = ...) -> None: ...

class GetRequest(_message.Message):
    __slots__ = ("context",)
    CONTEXT_FIELD_NUMBER: _ClassVar[int]
    context: _common_pb2.CallContext
    def __init__(self, context: _Optional[_Union[_common_pb2.CallContext, _Mapping]] = ...) -> None: ...

class GetResponse(_message.Message):
    __slots__ = ("triples_nt", "error", "error_detail")
    TRIPLES_NT_FIELD_NUMBER: _ClassVar[int]
    ERROR_FIELD_NUMBER: _ClassVar[int]
    ERROR_DETAIL_FIELD_NUMBER: _ClassVar[int]
    triples_nt: bytes
    error: _common_pb2.CallError
    error_detail: TripleStoreRequestErrorDetail
    def __init__(self, triples_nt: _Optional[bytes] = ..., error: _Optional[_Union[_common_pb2.CallError, _Mapping]] = ..., error_detail: _Optional[_Union[TripleStoreRequestErrorDetail, _Mapping]] = ...) -> None: ...

class HandleViewEventRequest(_message.Message):
    __slots__ = ("context", "view", "event", "triple")
    CONTEXT_FIELD_NUMBER: _ClassVar[int]
    VIEW_FIELD_NUMBER: _ClassVar[int]
    EVENT_FIELD_NUMBER: _ClassVar[int]
    TRIPLE_FIELD_NUMBER: _ClassVar[int]
    context: _common_pb2.CallContext
    view: TriplePattern
    event: OntologyEventType
    triple: TriplePattern
    def __init__(self, context: _Optional[_Union[_common_pb2.CallContext, _Mapping]] = ..., view: _Optional[_Union[TriplePattern, _Mapping]] = ..., event: _Optional[_Union[OntologyEventType, str]] = ..., triple: _Optional[_Union[TriplePattern, _Mapping]] = ...) -> None: ...

class HandleViewEventResponse(_message.Message):
    __slots__ = ("error", "error_detail")
    ERROR_FIELD_NUMBER: _ClassVar[int]
    ERROR_DETAIL_FIELD_NUMBER: _ClassVar[int]
    error: _common_pb2.CallError
    error_detail: TripleStoreRequestErrorDetail
    def __init__(self, error: _Optional[_Union[_common_pb2.CallError, _Mapping]] = ..., error_detail: _Optional[_Union[TripleStoreRequestErrorDetail, _Mapping]] = ...) -> None: ...

class QueryRequest(_message.Message):
    __slots__ = ("context", "query")
    CONTEXT_FIELD_NUMBER: _ClassVar[int]
    QUERY_FIELD_NUMBER: _ClassVar[int]
    context: _common_pb2.CallContext
    query: str
    def __init__(self, context: _Optional[_Union[_common_pb2.CallContext, _Mapping]] = ..., query: _Optional[str] = ...) -> None: ...

class QueryResponse(_message.Message):
    __slots__ = ("success", "error", "error_detail")
    SUCCESS_FIELD_NUMBER: _ClassVar[int]
    ERROR_FIELD_NUMBER: _ClassVar[int]
    ERROR_DETAIL_FIELD_NUMBER: _ClassVar[int]
    success: QueryResult
    error: _common_pb2.CallError
    error_detail: TripleStoreRequestErrorDetail
    def __init__(self, success: _Optional[_Union[QueryResult, _Mapping]] = ..., error: _Optional[_Union[_common_pb2.CallError, _Mapping]] = ..., error_detail: _Optional[_Union[TripleStoreRequestErrorDetail, _Mapping]] = ...) -> None: ...

class QueryViewRequest(_message.Message):
    __slots__ = ("context", "view", "query")
    CONTEXT_FIELD_NUMBER: _ClassVar[int]
    VIEW_FIELD_NUMBER: _ClassVar[int]
    QUERY_FIELD_NUMBER: _ClassVar[int]
    context: _common_pb2.CallContext
    view: str
    query: str
    def __init__(self, context: _Optional[_Union[_common_pb2.CallContext, _Mapping]] = ..., view: _Optional[str] = ..., query: _Optional[str] = ...) -> None: ...

class QueryViewResponse(_message.Message):
    __slots__ = ("success", "error", "error_detail")
    SUCCESS_FIELD_NUMBER: _ClassVar[int]
    ERROR_FIELD_NUMBER: _ClassVar[int]
    ERROR_DETAIL_FIELD_NUMBER: _ClassVar[int]
    success: QueryResult
    error: _common_pb2.CallError
    error_detail: TripleStoreRequestErrorDetail
    def __init__(self, success: _Optional[_Union[QueryResult, _Mapping]] = ..., error: _Optional[_Union[_common_pb2.CallError, _Mapping]] = ..., error_detail: _Optional[_Union[TripleStoreRequestErrorDetail, _Mapping]] = ...) -> None: ...

class QueryResult(_message.Message):
    __slots__ = ("result_type", "select", "ask_answer", "construct_triples_nt")
    RESULT_TYPE_FIELD_NUMBER: _ClassVar[int]
    SELECT_FIELD_NUMBER: _ClassVar[int]
    ASK_ANSWER_FIELD_NUMBER: _ClassVar[int]
    CONSTRUCT_TRIPLES_NT_FIELD_NUMBER: _ClassVar[int]
    result_type: str
    select: SelectResult
    ask_answer: bool
    construct_triples_nt: bytes
    def __init__(self, result_type: _Optional[str] = ..., select: _Optional[_Union[SelectResult, _Mapping]] = ..., ask_answer: bool = ..., construct_triples_nt: _Optional[bytes] = ...) -> None: ...

class SelectResult(_message.Message):
    __slots__ = ("vars", "rows")
    VARS_FIELD_NUMBER: _ClassVar[int]
    ROWS_FIELD_NUMBER: _ClassVar[int]
    vars: _containers.RepeatedScalarFieldContainer[str]
    rows: _containers.RepeatedCompositeFieldContainer[Row]
    def __init__(self, vars: _Optional[_Iterable[str]] = ..., rows: _Optional[_Iterable[_Union[Row, _Mapping]]] = ...) -> None: ...

class Row(_message.Message):
    __slots__ = ("bindings",)
    class BindingsEntry(_message.Message):
        __slots__ = ("key", "value")
        KEY_FIELD_NUMBER: _ClassVar[int]
        VALUE_FIELD_NUMBER: _ClassVar[int]
        key: str
        value: str
        def __init__(self, key: _Optional[str] = ..., value: _Optional[str] = ...) -> None: ...
    BINDINGS_FIELD_NUMBER: _ClassVar[int]
    bindings: _containers.ScalarMap[str, str]
    def __init__(self, bindings: _Optional[_Mapping[str, str]] = ...) -> None: ...

class GetSubjectGraphRequest(_message.Message):
    __slots__ = ("context", "subject", "graph_name")
    CONTEXT_FIELD_NUMBER: _ClassVar[int]
    SUBJECT_FIELD_NUMBER: _ClassVar[int]
    GRAPH_NAME_FIELD_NUMBER: _ClassVar[int]
    context: _common_pb2.CallContext
    subject: str
    graph_name: str
    def __init__(self, context: _Optional[_Union[_common_pb2.CallContext, _Mapping]] = ..., subject: _Optional[str] = ..., graph_name: _Optional[str] = ...) -> None: ...

class GetSubjectGraphResponse(_message.Message):
    __slots__ = ("triples_nt", "error", "error_detail")
    TRIPLES_NT_FIELD_NUMBER: _ClassVar[int]
    ERROR_FIELD_NUMBER: _ClassVar[int]
    ERROR_DETAIL_FIELD_NUMBER: _ClassVar[int]
    triples_nt: bytes
    error: _common_pb2.CallError
    error_detail: TripleStoreRequestErrorDetail
    def __init__(self, triples_nt: _Optional[bytes] = ..., error: _Optional[_Union[_common_pb2.CallError, _Mapping]] = ..., error_detail: _Optional[_Union[TripleStoreRequestErrorDetail, _Mapping]] = ...) -> None: ...

class CreateGraphRequest(_message.Message):
    __slots__ = ("context", "graph_name")
    CONTEXT_FIELD_NUMBER: _ClassVar[int]
    GRAPH_NAME_FIELD_NUMBER: _ClassVar[int]
    context: _common_pb2.CallContext
    graph_name: str
    def __init__(self, context: _Optional[_Union[_common_pb2.CallContext, _Mapping]] = ..., graph_name: _Optional[str] = ...) -> None: ...

class CreateGraphResponse(_message.Message):
    __slots__ = ("error", "error_detail")
    ERROR_FIELD_NUMBER: _ClassVar[int]
    ERROR_DETAIL_FIELD_NUMBER: _ClassVar[int]
    error: _common_pb2.CallError
    error_detail: TripleStoreRequestErrorDetail
    def __init__(self, error: _Optional[_Union[_common_pb2.CallError, _Mapping]] = ..., error_detail: _Optional[_Union[TripleStoreRequestErrorDetail, _Mapping]] = ...) -> None: ...

class ClearGraphRequest(_message.Message):
    __slots__ = ("context", "graph_name")
    CONTEXT_FIELD_NUMBER: _ClassVar[int]
    GRAPH_NAME_FIELD_NUMBER: _ClassVar[int]
    context: _common_pb2.CallContext
    graph_name: str
    def __init__(self, context: _Optional[_Union[_common_pb2.CallContext, _Mapping]] = ..., graph_name: _Optional[str] = ...) -> None: ...

class ClearGraphResponse(_message.Message):
    __slots__ = ("error", "error_detail")
    ERROR_FIELD_NUMBER: _ClassVar[int]
    ERROR_DETAIL_FIELD_NUMBER: _ClassVar[int]
    error: _common_pb2.CallError
    error_detail: TripleStoreRequestErrorDetail
    def __init__(self, error: _Optional[_Union[_common_pb2.CallError, _Mapping]] = ..., error_detail: _Optional[_Union[TripleStoreRequestErrorDetail, _Mapping]] = ...) -> None: ...

class DropGraphRequest(_message.Message):
    __slots__ = ("context", "graph_name")
    CONTEXT_FIELD_NUMBER: _ClassVar[int]
    GRAPH_NAME_FIELD_NUMBER: _ClassVar[int]
    context: _common_pb2.CallContext
    graph_name: str
    def __init__(self, context: _Optional[_Union[_common_pb2.CallContext, _Mapping]] = ..., graph_name: _Optional[str] = ...) -> None: ...

class DropGraphResponse(_message.Message):
    __slots__ = ("error", "error_detail")
    ERROR_FIELD_NUMBER: _ClassVar[int]
    ERROR_DETAIL_FIELD_NUMBER: _ClassVar[int]
    error: _common_pb2.CallError
    error_detail: TripleStoreRequestErrorDetail
    def __init__(self, error: _Optional[_Union[_common_pb2.CallError, _Mapping]] = ..., error_detail: _Optional[_Union[TripleStoreRequestErrorDetail, _Mapping]] = ...) -> None: ...

class ListGraphsRequest(_message.Message):
    __slots__ = ("context",)
    CONTEXT_FIELD_NUMBER: _ClassVar[int]
    context: _common_pb2.CallContext
    def __init__(self, context: _Optional[_Union[_common_pb2.CallContext, _Mapping]] = ...) -> None: ...

class ListGraphsResponse(_message.Message):
    __slots__ = ("graph_names", "error", "error_detail")
    GRAPH_NAMES_FIELD_NUMBER: _ClassVar[int]
    ERROR_FIELD_NUMBER: _ClassVar[int]
    ERROR_DETAIL_FIELD_NUMBER: _ClassVar[int]
    graph_names: GraphNames
    error: _common_pb2.CallError
    error_detail: TripleStoreRequestErrorDetail
    def __init__(self, graph_names: _Optional[_Union[GraphNames, _Mapping]] = ..., error: _Optional[_Union[_common_pb2.CallError, _Mapping]] = ..., error_detail: _Optional[_Union[TripleStoreRequestErrorDetail, _Mapping]] = ...) -> None: ...

class GraphNames(_message.Message):
    __slots__ = ("graph_names",)
    GRAPH_NAMES_FIELD_NUMBER: _ClassVar[int]
    graph_names: _containers.RepeatedScalarFieldContainer[str]
    def __init__(self, graph_names: _Optional[_Iterable[str]] = ...) -> None: ...
