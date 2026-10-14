from naas_abi_proto.common.v1 import common_pb2 as _common_pb2
from google.protobuf.internal import containers as _containers
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from collections.abc import Iterable as _Iterable, Mapping as _Mapping
from typing import ClassVar as _ClassVar, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class VectorData(_message.Message):
    __slots__ = ("values",)
    VALUES_FIELD_NUMBER: _ClassVar[int]
    values: _containers.RepeatedScalarFieldContainer[float]
    def __init__(self, values: _Optional[_Iterable[float]] = ...) -> None: ...

class VectorDocument(_message.Message):
    __slots__ = ("id", "vector", "metadata", "payload")
    ID_FIELD_NUMBER: _ClassVar[int]
    VECTOR_FIELD_NUMBER: _ClassVar[int]
    METADATA_FIELD_NUMBER: _ClassVar[int]
    PAYLOAD_FIELD_NUMBER: _ClassVar[int]
    id: str
    vector: VectorData
    metadata: bytes
    payload: bytes
    def __init__(self, id: _Optional[str] = ..., vector: _Optional[_Union[VectorData, _Mapping]] = ..., metadata: _Optional[bytes] = ..., payload: _Optional[bytes] = ...) -> None: ...

class SearchResult(_message.Message):
    __slots__ = ("id", "score", "vector", "metadata", "payload")
    ID_FIELD_NUMBER: _ClassVar[int]
    SCORE_FIELD_NUMBER: _ClassVar[int]
    VECTOR_FIELD_NUMBER: _ClassVar[int]
    METADATA_FIELD_NUMBER: _ClassVar[int]
    PAYLOAD_FIELD_NUMBER: _ClassVar[int]
    id: str
    score: float
    vector: VectorData
    metadata: bytes
    payload: bytes
    def __init__(self, id: _Optional[str] = ..., score: _Optional[float] = ..., vector: _Optional[_Union[VectorData, _Mapping]] = ..., metadata: _Optional[bytes] = ..., payload: _Optional[bytes] = ...) -> None: ...

class InitializeRequest(_message.Message):
    __slots__ = ("context",)
    CONTEXT_FIELD_NUMBER: _ClassVar[int]
    context: _common_pb2.CallContext
    def __init__(self, context: _Optional[_Union[_common_pb2.CallContext, _Mapping]] = ...) -> None: ...

class InitializeResponse(_message.Message):
    __slots__ = ("error",)
    ERROR_FIELD_NUMBER: _ClassVar[int]
    error: _common_pb2.CallError
    def __init__(self, error: _Optional[_Union[_common_pb2.CallError, _Mapping]] = ...) -> None: ...

class CreateCollectionRequest(_message.Message):
    __slots__ = ("context", "collection_name", "dimension", "distance_metric")
    CONTEXT_FIELD_NUMBER: _ClassVar[int]
    COLLECTION_NAME_FIELD_NUMBER: _ClassVar[int]
    DIMENSION_FIELD_NUMBER: _ClassVar[int]
    DISTANCE_METRIC_FIELD_NUMBER: _ClassVar[int]
    context: _common_pb2.CallContext
    collection_name: str
    dimension: int
    distance_metric: str
    def __init__(self, context: _Optional[_Union[_common_pb2.CallContext, _Mapping]] = ..., collection_name: _Optional[str] = ..., dimension: _Optional[int] = ..., distance_metric: _Optional[str] = ...) -> None: ...

class CreateCollectionResponse(_message.Message):
    __slots__ = ("error",)
    ERROR_FIELD_NUMBER: _ClassVar[int]
    error: _common_pb2.CallError
    def __init__(self, error: _Optional[_Union[_common_pb2.CallError, _Mapping]] = ...) -> None: ...

class DeleteCollectionRequest(_message.Message):
    __slots__ = ("context", "collection_name")
    CONTEXT_FIELD_NUMBER: _ClassVar[int]
    COLLECTION_NAME_FIELD_NUMBER: _ClassVar[int]
    context: _common_pb2.CallContext
    collection_name: str
    def __init__(self, context: _Optional[_Union[_common_pb2.CallContext, _Mapping]] = ..., collection_name: _Optional[str] = ...) -> None: ...

class DeleteCollectionResponse(_message.Message):
    __slots__ = ("error",)
    ERROR_FIELD_NUMBER: _ClassVar[int]
    error: _common_pb2.CallError
    def __init__(self, error: _Optional[_Union[_common_pb2.CallError, _Mapping]] = ...) -> None: ...

class ListCollectionsRequest(_message.Message):
    __slots__ = ("context",)
    CONTEXT_FIELD_NUMBER: _ClassVar[int]
    context: _common_pb2.CallContext
    def __init__(self, context: _Optional[_Union[_common_pb2.CallContext, _Mapping]] = ...) -> None: ...

class CollectionNames(_message.Message):
    __slots__ = ("names",)
    NAMES_FIELD_NUMBER: _ClassVar[int]
    names: _containers.RepeatedScalarFieldContainer[str]
    def __init__(self, names: _Optional[_Iterable[str]] = ...) -> None: ...

class ListCollectionsResponse(_message.Message):
    __slots__ = ("collections", "error")
    COLLECTIONS_FIELD_NUMBER: _ClassVar[int]
    ERROR_FIELD_NUMBER: _ClassVar[int]
    collections: CollectionNames
    error: _common_pb2.CallError
    def __init__(self, collections: _Optional[_Union[CollectionNames, _Mapping]] = ..., error: _Optional[_Union[_common_pb2.CallError, _Mapping]] = ...) -> None: ...

class StoreVectorsRequest(_message.Message):
    __slots__ = ("context", "collection_name", "documents")
    CONTEXT_FIELD_NUMBER: _ClassVar[int]
    COLLECTION_NAME_FIELD_NUMBER: _ClassVar[int]
    DOCUMENTS_FIELD_NUMBER: _ClassVar[int]
    context: _common_pb2.CallContext
    collection_name: str
    documents: _containers.RepeatedCompositeFieldContainer[VectorDocument]
    def __init__(self, context: _Optional[_Union[_common_pb2.CallContext, _Mapping]] = ..., collection_name: _Optional[str] = ..., documents: _Optional[_Iterable[_Union[VectorDocument, _Mapping]]] = ...) -> None: ...

class StoreVectorsResponse(_message.Message):
    __slots__ = ("error",)
    ERROR_FIELD_NUMBER: _ClassVar[int]
    error: _common_pb2.CallError
    def __init__(self, error: _Optional[_Union[_common_pb2.CallError, _Mapping]] = ...) -> None: ...

class SearchRequest(_message.Message):
    __slots__ = ("context", "collection_name", "query_vector", "k", "filter", "include_vectors", "include_metadata")
    CONTEXT_FIELD_NUMBER: _ClassVar[int]
    COLLECTION_NAME_FIELD_NUMBER: _ClassVar[int]
    QUERY_VECTOR_FIELD_NUMBER: _ClassVar[int]
    K_FIELD_NUMBER: _ClassVar[int]
    FILTER_FIELD_NUMBER: _ClassVar[int]
    INCLUDE_VECTORS_FIELD_NUMBER: _ClassVar[int]
    INCLUDE_METADATA_FIELD_NUMBER: _ClassVar[int]
    context: _common_pb2.CallContext
    collection_name: str
    query_vector: _containers.RepeatedScalarFieldContainer[float]
    k: int
    filter: bytes
    include_vectors: bool
    include_metadata: bool
    def __init__(self, context: _Optional[_Union[_common_pb2.CallContext, _Mapping]] = ..., collection_name: _Optional[str] = ..., query_vector: _Optional[_Iterable[float]] = ..., k: _Optional[int] = ..., filter: _Optional[bytes] = ..., include_vectors: bool = ..., include_metadata: bool = ...) -> None: ...

class SearchResultList(_message.Message):
    __slots__ = ("results",)
    RESULTS_FIELD_NUMBER: _ClassVar[int]
    results: _containers.RepeatedCompositeFieldContainer[SearchResult]
    def __init__(self, results: _Optional[_Iterable[_Union[SearchResult, _Mapping]]] = ...) -> None: ...

class SearchResponse(_message.Message):
    __slots__ = ("results", "error")
    RESULTS_FIELD_NUMBER: _ClassVar[int]
    ERROR_FIELD_NUMBER: _ClassVar[int]
    results: SearchResultList
    error: _common_pb2.CallError
    def __init__(self, results: _Optional[_Union[SearchResultList, _Mapping]] = ..., error: _Optional[_Union[_common_pb2.CallError, _Mapping]] = ...) -> None: ...

class GetVectorRequest(_message.Message):
    __slots__ = ("context", "collection_name", "vector_id", "include_vector")
    CONTEXT_FIELD_NUMBER: _ClassVar[int]
    COLLECTION_NAME_FIELD_NUMBER: _ClassVar[int]
    VECTOR_ID_FIELD_NUMBER: _ClassVar[int]
    INCLUDE_VECTOR_FIELD_NUMBER: _ClassVar[int]
    context: _common_pb2.CallContext
    collection_name: str
    vector_id: str
    include_vector: bool
    def __init__(self, context: _Optional[_Union[_common_pb2.CallContext, _Mapping]] = ..., collection_name: _Optional[str] = ..., vector_id: _Optional[str] = ..., include_vector: bool = ...) -> None: ...

class VectorDocumentOrNone(_message.Message):
    __slots__ = ("document",)
    DOCUMENT_FIELD_NUMBER: _ClassVar[int]
    document: VectorDocument
    def __init__(self, document: _Optional[_Union[VectorDocument, _Mapping]] = ...) -> None: ...

class GetVectorResponse(_message.Message):
    __slots__ = ("found", "error")
    FOUND_FIELD_NUMBER: _ClassVar[int]
    ERROR_FIELD_NUMBER: _ClassVar[int]
    found: VectorDocumentOrNone
    error: _common_pb2.CallError
    def __init__(self, found: _Optional[_Union[VectorDocumentOrNone, _Mapping]] = ..., error: _Optional[_Union[_common_pb2.CallError, _Mapping]] = ...) -> None: ...

class UpdateVectorRequest(_message.Message):
    __slots__ = ("context", "collection_name", "vector_id", "vector", "metadata", "payload")
    CONTEXT_FIELD_NUMBER: _ClassVar[int]
    COLLECTION_NAME_FIELD_NUMBER: _ClassVar[int]
    VECTOR_ID_FIELD_NUMBER: _ClassVar[int]
    VECTOR_FIELD_NUMBER: _ClassVar[int]
    METADATA_FIELD_NUMBER: _ClassVar[int]
    PAYLOAD_FIELD_NUMBER: _ClassVar[int]
    context: _common_pb2.CallContext
    collection_name: str
    vector_id: str
    vector: VectorData
    metadata: bytes
    payload: bytes
    def __init__(self, context: _Optional[_Union[_common_pb2.CallContext, _Mapping]] = ..., collection_name: _Optional[str] = ..., vector_id: _Optional[str] = ..., vector: _Optional[_Union[VectorData, _Mapping]] = ..., metadata: _Optional[bytes] = ..., payload: _Optional[bytes] = ...) -> None: ...

class UpdateVectorResponse(_message.Message):
    __slots__ = ("error",)
    ERROR_FIELD_NUMBER: _ClassVar[int]
    error: _common_pb2.CallError
    def __init__(self, error: _Optional[_Union[_common_pb2.CallError, _Mapping]] = ...) -> None: ...

class DeleteVectorsRequest(_message.Message):
    __slots__ = ("context", "collection_name", "vector_ids")
    CONTEXT_FIELD_NUMBER: _ClassVar[int]
    COLLECTION_NAME_FIELD_NUMBER: _ClassVar[int]
    VECTOR_IDS_FIELD_NUMBER: _ClassVar[int]
    context: _common_pb2.CallContext
    collection_name: str
    vector_ids: _containers.RepeatedScalarFieldContainer[str]
    def __init__(self, context: _Optional[_Union[_common_pb2.CallContext, _Mapping]] = ..., collection_name: _Optional[str] = ..., vector_ids: _Optional[_Iterable[str]] = ...) -> None: ...

class DeleteVectorsResponse(_message.Message):
    __slots__ = ("error",)
    ERROR_FIELD_NUMBER: _ClassVar[int]
    error: _common_pb2.CallError
    def __init__(self, error: _Optional[_Union[_common_pb2.CallError, _Mapping]] = ...) -> None: ...

class CountVectorsRequest(_message.Message):
    __slots__ = ("context", "collection_name")
    CONTEXT_FIELD_NUMBER: _ClassVar[int]
    COLLECTION_NAME_FIELD_NUMBER: _ClassVar[int]
    context: _common_pb2.CallContext
    collection_name: str
    def __init__(self, context: _Optional[_Union[_common_pb2.CallContext, _Mapping]] = ..., collection_name: _Optional[str] = ...) -> None: ...

class CountVectorsResponse(_message.Message):
    __slots__ = ("count", "error")
    COUNT_FIELD_NUMBER: _ClassVar[int]
    ERROR_FIELD_NUMBER: _ClassVar[int]
    count: int
    error: _common_pb2.CallError
    def __init__(self, count: _Optional[int] = ..., error: _Optional[_Union[_common_pb2.CallError, _Mapping]] = ...) -> None: ...

class ListVectorsRequest(_message.Message):
    __slots__ = ("context", "collection_name", "limit", "cursor", "include_vectors")
    CONTEXT_FIELD_NUMBER: _ClassVar[int]
    COLLECTION_NAME_FIELD_NUMBER: _ClassVar[int]
    LIMIT_FIELD_NUMBER: _ClassVar[int]
    CURSOR_FIELD_NUMBER: _ClassVar[int]
    INCLUDE_VECTORS_FIELD_NUMBER: _ClassVar[int]
    context: _common_pb2.CallContext
    collection_name: str
    limit: int
    cursor: str
    include_vectors: bool
    def __init__(self, context: _Optional[_Union[_common_pb2.CallContext, _Mapping]] = ..., collection_name: _Optional[str] = ..., limit: _Optional[int] = ..., cursor: _Optional[str] = ..., include_vectors: bool = ...) -> None: ...

class VectorPage(_message.Message):
    __slots__ = ("documents", "next_cursor")
    DOCUMENTS_FIELD_NUMBER: _ClassVar[int]
    NEXT_CURSOR_FIELD_NUMBER: _ClassVar[int]
    documents: _containers.RepeatedCompositeFieldContainer[VectorDocument]
    next_cursor: str
    def __init__(self, documents: _Optional[_Iterable[_Union[VectorDocument, _Mapping]]] = ..., next_cursor: _Optional[str] = ...) -> None: ...

class ListVectorsResponse(_message.Message):
    __slots__ = ("page", "error")
    PAGE_FIELD_NUMBER: _ClassVar[int]
    ERROR_FIELD_NUMBER: _ClassVar[int]
    page: VectorPage
    error: _common_pb2.CallError
    def __init__(self, page: _Optional[_Union[VectorPage, _Mapping]] = ..., error: _Optional[_Union[_common_pb2.CallError, _Mapping]] = ...) -> None: ...

class GetCollectionInfoRequest(_message.Message):
    __slots__ = ("context", "collection_name")
    CONTEXT_FIELD_NUMBER: _ClassVar[int]
    COLLECTION_NAME_FIELD_NUMBER: _ClassVar[int]
    context: _common_pb2.CallContext
    collection_name: str
    def __init__(self, context: _Optional[_Union[_common_pb2.CallContext, _Mapping]] = ..., collection_name: _Optional[str] = ...) -> None: ...

class CollectionInfo(_message.Message):
    __slots__ = ("name", "dimension", "distance_metric", "size")
    NAME_FIELD_NUMBER: _ClassVar[int]
    DIMENSION_FIELD_NUMBER: _ClassVar[int]
    DISTANCE_METRIC_FIELD_NUMBER: _ClassVar[int]
    SIZE_FIELD_NUMBER: _ClassVar[int]
    name: str
    dimension: int
    distance_metric: str
    size: int
    def __init__(self, name: _Optional[str] = ..., dimension: _Optional[int] = ..., distance_metric: _Optional[str] = ..., size: _Optional[int] = ...) -> None: ...

class GetCollectionInfoResponse(_message.Message):
    __slots__ = ("info", "error")
    INFO_FIELD_NUMBER: _ClassVar[int]
    ERROR_FIELD_NUMBER: _ClassVar[int]
    info: CollectionInfo
    error: _common_pb2.CallError
    def __init__(self, info: _Optional[_Union[CollectionInfo, _Mapping]] = ..., error: _Optional[_Union[_common_pb2.CallError, _Mapping]] = ...) -> None: ...

class CloseRequest(_message.Message):
    __slots__ = ("context",)
    CONTEXT_FIELD_NUMBER: _ClassVar[int]
    context: _common_pb2.CallContext
    def __init__(self, context: _Optional[_Union[_common_pb2.CallContext, _Mapping]] = ...) -> None: ...

class CloseResponse(_message.Message):
    __slots__ = ("error",)
    ERROR_FIELD_NUMBER: _ClassVar[int]
    error: _common_pb2.CallError
    def __init__(self, error: _Optional[_Union[_common_pb2.CallError, _Mapping]] = ...) -> None: ...
