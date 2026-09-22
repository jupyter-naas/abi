from naas_abi_proto.common.v1 import common_pb2 as _common_pb2
from google.protobuf.internal import containers as _containers
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from collections.abc import Iterable as _Iterable, Mapping as _Mapping
from typing import ClassVar as _ClassVar, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class Value(_message.Message):
    __slots__ = ("null_value", "string_value", "int_value", "float_value", "bool_value", "bytes_value", "datetime_value", "list_value", "object_value")
    NULL_VALUE_FIELD_NUMBER: _ClassVar[int]
    STRING_VALUE_FIELD_NUMBER: _ClassVar[int]
    INT_VALUE_FIELD_NUMBER: _ClassVar[int]
    FLOAT_VALUE_FIELD_NUMBER: _ClassVar[int]
    BOOL_VALUE_FIELD_NUMBER: _ClassVar[int]
    BYTES_VALUE_FIELD_NUMBER: _ClassVar[int]
    DATETIME_VALUE_FIELD_NUMBER: _ClassVar[int]
    LIST_VALUE_FIELD_NUMBER: _ClassVar[int]
    OBJECT_VALUE_FIELD_NUMBER: _ClassVar[int]
    null_value: bool
    string_value: str
    int_value: int
    float_value: float
    bool_value: bool
    bytes_value: bytes
    datetime_value: str
    list_value: Values
    object_value: Data
    def __init__(self, null_value: bool = ..., string_value: _Optional[str] = ..., int_value: _Optional[int] = ..., float_value: _Optional[float] = ..., bool_value: bool = ..., bytes_value: _Optional[bytes] = ..., datetime_value: _Optional[str] = ..., list_value: _Optional[_Union[Values, _Mapping]] = ..., object_value: _Optional[_Union[Data, _Mapping]] = ...) -> None: ...

class Values(_message.Message):
    __slots__ = ("items",)
    ITEMS_FIELD_NUMBER: _ClassVar[int]
    items: _containers.RepeatedCompositeFieldContainer[Value]
    def __init__(self, items: _Optional[_Iterable[_Union[Value, _Mapping]]] = ...) -> None: ...

class Data(_message.Message):
    __slots__ = ("fields",)
    class FieldsEntry(_message.Message):
        __slots__ = ("key", "value")
        KEY_FIELD_NUMBER: _ClassVar[int]
        VALUE_FIELD_NUMBER: _ClassVar[int]
        key: str
        value: Value
        def __init__(self, key: _Optional[str] = ..., value: _Optional[_Union[Value, _Mapping]] = ...) -> None: ...
    FIELDS_FIELD_NUMBER: _ClassVar[int]
    fields: _containers.MessageMap[str, Value]
    def __init__(self, fields: _Optional[_Mapping[str, Value]] = ...) -> None: ...

class FieldSpec(_message.Message):
    __slots__ = ("name", "type", "indexed", "unique")
    NAME_FIELD_NUMBER: _ClassVar[int]
    TYPE_FIELD_NUMBER: _ClassVar[int]
    INDEXED_FIELD_NUMBER: _ClassVar[int]
    UNIQUE_FIELD_NUMBER: _ClassVar[int]
    name: str
    type: str
    indexed: bool
    unique: bool
    def __init__(self, name: _Optional[str] = ..., type: _Optional[str] = ..., indexed: bool = ..., unique: bool = ...) -> None: ...

class UniqueGroup(_message.Message):
    __slots__ = ("fields",)
    FIELDS_FIELD_NUMBER: _ClassVar[int]
    fields: _containers.RepeatedScalarFieldContainer[str]
    def __init__(self, fields: _Optional[_Iterable[str]] = ...) -> None: ...

class CollectionSpec(_message.Message):
    __slots__ = ("name", "fields", "unique_together")
    NAME_FIELD_NUMBER: _ClassVar[int]
    FIELDS_FIELD_NUMBER: _ClassVar[int]
    UNIQUE_TOGETHER_FIELD_NUMBER: _ClassVar[int]
    name: str
    fields: _containers.RepeatedCompositeFieldContainer[FieldSpec]
    unique_together: _containers.RepeatedCompositeFieldContainer[UniqueGroup]
    def __init__(self, name: _Optional[str] = ..., fields: _Optional[_Iterable[_Union[FieldSpec, _Mapping]]] = ..., unique_together: _Optional[_Iterable[_Union[UniqueGroup, _Mapping]]] = ...) -> None: ...

class Document(_message.Message):
    __slots__ = ("id", "data", "created_at", "updated_at", "version")
    ID_FIELD_NUMBER: _ClassVar[int]
    DATA_FIELD_NUMBER: _ClassVar[int]
    CREATED_AT_FIELD_NUMBER: _ClassVar[int]
    UPDATED_AT_FIELD_NUMBER: _ClassVar[int]
    VERSION_FIELD_NUMBER: _ClassVar[int]
    id: str
    data: Data
    created_at: str
    updated_at: str
    version: int
    def __init__(self, id: _Optional[str] = ..., data: _Optional[_Union[Data, _Mapping]] = ..., created_at: _Optional[str] = ..., updated_at: _Optional[str] = ..., version: _Optional[int] = ...) -> None: ...

class Predicate(_message.Message):
    __slots__ = ("field", "operator", "value")
    FIELD_FIELD_NUMBER: _ClassVar[int]
    OPERATOR_FIELD_NUMBER: _ClassVar[int]
    VALUE_FIELD_NUMBER: _ClassVar[int]
    field: str
    operator: str
    value: Value
    def __init__(self, field: _Optional[str] = ..., operator: _Optional[str] = ..., value: _Optional[_Union[Value, _Mapping]] = ...) -> None: ...

class OrderBy(_message.Message):
    __slots__ = ("field", "direction")
    FIELD_FIELD_NUMBER: _ClassVar[int]
    DIRECTION_FIELD_NUMBER: _ClassVar[int]
    field: str
    direction: str
    def __init__(self, field: _Optional[str] = ..., direction: _Optional[str] = ...) -> None: ...

class EnsureCollectionRequest(_message.Message):
    __slots__ = ("context", "namespace", "spec")
    CONTEXT_FIELD_NUMBER: _ClassVar[int]
    NAMESPACE_FIELD_NUMBER: _ClassVar[int]
    SPEC_FIELD_NUMBER: _ClassVar[int]
    context: _common_pb2.CallContext
    namespace: str
    spec: CollectionSpec
    def __init__(self, context: _Optional[_Union[_common_pb2.CallContext, _Mapping]] = ..., namespace: _Optional[str] = ..., spec: _Optional[_Union[CollectionSpec, _Mapping]] = ...) -> None: ...

class EnsureCollectionResponse(_message.Message):
    __slots__ = ("error",)
    ERROR_FIELD_NUMBER: _ClassVar[int]
    error: _common_pb2.CallError
    def __init__(self, error: _Optional[_Union[_common_pb2.CallError, _Mapping]] = ...) -> None: ...

class DropCollectionRequest(_message.Message):
    __slots__ = ("context", "namespace", "collection")
    CONTEXT_FIELD_NUMBER: _ClassVar[int]
    NAMESPACE_FIELD_NUMBER: _ClassVar[int]
    COLLECTION_FIELD_NUMBER: _ClassVar[int]
    context: _common_pb2.CallContext
    namespace: str
    collection: str
    def __init__(self, context: _Optional[_Union[_common_pb2.CallContext, _Mapping]] = ..., namespace: _Optional[str] = ..., collection: _Optional[str] = ...) -> None: ...

class DropCollectionResponse(_message.Message):
    __slots__ = ("error",)
    ERROR_FIELD_NUMBER: _ClassVar[int]
    error: _common_pb2.CallError
    def __init__(self, error: _Optional[_Union[_common_pb2.CallError, _Mapping]] = ...) -> None: ...

class CollectionsRequest(_message.Message):
    __slots__ = ("context", "namespace")
    CONTEXT_FIELD_NUMBER: _ClassVar[int]
    NAMESPACE_FIELD_NUMBER: _ClassVar[int]
    context: _common_pb2.CallContext
    namespace: str
    def __init__(self, context: _Optional[_Union[_common_pb2.CallContext, _Mapping]] = ..., namespace: _Optional[str] = ...) -> None: ...

class CollectionsResponse(_message.Message):
    __slots__ = ("error", "collections")
    ERROR_FIELD_NUMBER: _ClassVar[int]
    COLLECTIONS_FIELD_NUMBER: _ClassVar[int]
    error: _common_pb2.CallError
    collections: _containers.RepeatedScalarFieldContainer[str]
    def __init__(self, error: _Optional[_Union[_common_pb2.CallError, _Mapping]] = ..., collections: _Optional[_Iterable[str]] = ...) -> None: ...

class PutRequest(_message.Message):
    __slots__ = ("context", "namespace", "collection", "id", "data", "if_version")
    CONTEXT_FIELD_NUMBER: _ClassVar[int]
    NAMESPACE_FIELD_NUMBER: _ClassVar[int]
    COLLECTION_FIELD_NUMBER: _ClassVar[int]
    ID_FIELD_NUMBER: _ClassVar[int]
    DATA_FIELD_NUMBER: _ClassVar[int]
    IF_VERSION_FIELD_NUMBER: _ClassVar[int]
    context: _common_pb2.CallContext
    namespace: str
    collection: str
    id: str
    data: Data
    if_version: int
    def __init__(self, context: _Optional[_Union[_common_pb2.CallContext, _Mapping]] = ..., namespace: _Optional[str] = ..., collection: _Optional[str] = ..., id: _Optional[str] = ..., data: _Optional[_Union[Data, _Mapping]] = ..., if_version: _Optional[int] = ...) -> None: ...

class PutResponse(_message.Message):
    __slots__ = ("error", "document")
    ERROR_FIELD_NUMBER: _ClassVar[int]
    DOCUMENT_FIELD_NUMBER: _ClassVar[int]
    error: _common_pb2.CallError
    document: Document
    def __init__(self, error: _Optional[_Union[_common_pb2.CallError, _Mapping]] = ..., document: _Optional[_Union[Document, _Mapping]] = ...) -> None: ...

class GetRequest(_message.Message):
    __slots__ = ("context", "namespace", "collection", "id")
    CONTEXT_FIELD_NUMBER: _ClassVar[int]
    NAMESPACE_FIELD_NUMBER: _ClassVar[int]
    COLLECTION_FIELD_NUMBER: _ClassVar[int]
    ID_FIELD_NUMBER: _ClassVar[int]
    context: _common_pb2.CallContext
    namespace: str
    collection: str
    id: str
    def __init__(self, context: _Optional[_Union[_common_pb2.CallContext, _Mapping]] = ..., namespace: _Optional[str] = ..., collection: _Optional[str] = ..., id: _Optional[str] = ...) -> None: ...

class GetResponse(_message.Message):
    __slots__ = ("error", "document")
    ERROR_FIELD_NUMBER: _ClassVar[int]
    DOCUMENT_FIELD_NUMBER: _ClassVar[int]
    error: _common_pb2.CallError
    document: Document
    def __init__(self, error: _Optional[_Union[_common_pb2.CallError, _Mapping]] = ..., document: _Optional[_Union[Document, _Mapping]] = ...) -> None: ...

class DeleteRequest(_message.Message):
    __slots__ = ("context", "namespace", "collection", "id", "if_version")
    CONTEXT_FIELD_NUMBER: _ClassVar[int]
    NAMESPACE_FIELD_NUMBER: _ClassVar[int]
    COLLECTION_FIELD_NUMBER: _ClassVar[int]
    ID_FIELD_NUMBER: _ClassVar[int]
    IF_VERSION_FIELD_NUMBER: _ClassVar[int]
    context: _common_pb2.CallContext
    namespace: str
    collection: str
    id: str
    if_version: int
    def __init__(self, context: _Optional[_Union[_common_pb2.CallContext, _Mapping]] = ..., namespace: _Optional[str] = ..., collection: _Optional[str] = ..., id: _Optional[str] = ..., if_version: _Optional[int] = ...) -> None: ...

class DeleteResponse(_message.Message):
    __slots__ = ("error",)
    ERROR_FIELD_NUMBER: _ClassVar[int]
    error: _common_pb2.CallError
    def __init__(self, error: _Optional[_Union[_common_pb2.CallError, _Mapping]] = ...) -> None: ...

class FindRequest(_message.Message):
    __slots__ = ("context", "namespace", "collection", "where", "order_by", "limit", "cursor")
    CONTEXT_FIELD_NUMBER: _ClassVar[int]
    NAMESPACE_FIELD_NUMBER: _ClassVar[int]
    COLLECTION_FIELD_NUMBER: _ClassVar[int]
    WHERE_FIELD_NUMBER: _ClassVar[int]
    ORDER_BY_FIELD_NUMBER: _ClassVar[int]
    LIMIT_FIELD_NUMBER: _ClassVar[int]
    CURSOR_FIELD_NUMBER: _ClassVar[int]
    context: _common_pb2.CallContext
    namespace: str
    collection: str
    where: _containers.RepeatedCompositeFieldContainer[Predicate]
    order_by: OrderBy
    limit: int
    cursor: str
    def __init__(self, context: _Optional[_Union[_common_pb2.CallContext, _Mapping]] = ..., namespace: _Optional[str] = ..., collection: _Optional[str] = ..., where: _Optional[_Iterable[_Union[Predicate, _Mapping]]] = ..., order_by: _Optional[_Union[OrderBy, _Mapping]] = ..., limit: _Optional[int] = ..., cursor: _Optional[str] = ...) -> None: ...

class FindResponse(_message.Message):
    __slots__ = ("error", "items", "cursor")
    ERROR_FIELD_NUMBER: _ClassVar[int]
    ITEMS_FIELD_NUMBER: _ClassVar[int]
    CURSOR_FIELD_NUMBER: _ClassVar[int]
    error: _common_pb2.CallError
    items: _containers.RepeatedCompositeFieldContainer[Document]
    cursor: str
    def __init__(self, error: _Optional[_Union[_common_pb2.CallError, _Mapping]] = ..., items: _Optional[_Iterable[_Union[Document, _Mapping]]] = ..., cursor: _Optional[str] = ...) -> None: ...

class CountRequest(_message.Message):
    __slots__ = ("context", "namespace", "collection", "where")
    CONTEXT_FIELD_NUMBER: _ClassVar[int]
    NAMESPACE_FIELD_NUMBER: _ClassVar[int]
    COLLECTION_FIELD_NUMBER: _ClassVar[int]
    WHERE_FIELD_NUMBER: _ClassVar[int]
    context: _common_pb2.CallContext
    namespace: str
    collection: str
    where: _containers.RepeatedCompositeFieldContainer[Predicate]
    def __init__(self, context: _Optional[_Union[_common_pb2.CallContext, _Mapping]] = ..., namespace: _Optional[str] = ..., collection: _Optional[str] = ..., where: _Optional[_Iterable[_Union[Predicate, _Mapping]]] = ...) -> None: ...

class CountResponse(_message.Message):
    __slots__ = ("error", "count")
    ERROR_FIELD_NUMBER: _ClassVar[int]
    COUNT_FIELD_NUMBER: _ClassVar[int]
    error: _common_pb2.CallError
    count: int
    def __init__(self, error: _Optional[_Union[_common_pb2.CallError, _Mapping]] = ..., count: _Optional[int] = ...) -> None: ...
