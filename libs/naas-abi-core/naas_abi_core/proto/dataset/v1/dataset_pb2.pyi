import datetime

from naas_abi_core.proto.common.v1 import common_pb2 as _common_pb2
from google.protobuf import timestamp_pb2 as _timestamp_pb2
from google.protobuf import struct_pb2 as _struct_pb2
from google.protobuf.internal import containers as _containers
from google.protobuf.internal import enum_type_wrapper as _enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from collections.abc import Iterable as _Iterable, Mapping as _Mapping
from typing import ClassVar as _ClassVar, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class ColumnType(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    COLUMN_TYPE_UNSPECIFIED: _ClassVar[ColumnType]
    COLUMN_TYPE_STRING: _ClassVar[ColumnType]
    COLUMN_TYPE_INTEGER: _ClassVar[ColumnType]
    COLUMN_TYPE_BIGINT: _ClassVar[ColumnType]
    COLUMN_TYPE_DOUBLE: _ClassVar[ColumnType]
    COLUMN_TYPE_BOOLEAN: _ClassVar[ColumnType]
    COLUMN_TYPE_DATE: _ClassVar[ColumnType]
    COLUMN_TYPE_TIMESTAMP: _ClassVar[ColumnType]
    COLUMN_TYPE_JSON: _ClassVar[ColumnType]

class PartitionTransform(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    PARTITION_TRANSFORM_UNSPECIFIED: _ClassVar[PartitionTransform]
    PARTITION_TRANSFORM_IDENTITY: _ClassVar[PartitionTransform]
    PARTITION_TRANSFORM_YEAR: _ClassVar[PartitionTransform]
    PARTITION_TRANSFORM_MONTH: _ClassVar[PartitionTransform]
    PARTITION_TRANSFORM_DAY: _ClassVar[PartitionTransform]

class WriteMode(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    WRITE_MODE_UNSPECIFIED: _ClassVar[WriteMode]
    WRITE_MODE_APPEND: _ClassVar[WriteMode]
    WRITE_MODE_REPLACE: _ClassVar[WriteMode]
    WRITE_MODE_UPSERT: _ClassVar[WriteMode]
COLUMN_TYPE_UNSPECIFIED: ColumnType
COLUMN_TYPE_STRING: ColumnType
COLUMN_TYPE_INTEGER: ColumnType
COLUMN_TYPE_BIGINT: ColumnType
COLUMN_TYPE_DOUBLE: ColumnType
COLUMN_TYPE_BOOLEAN: ColumnType
COLUMN_TYPE_DATE: ColumnType
COLUMN_TYPE_TIMESTAMP: ColumnType
COLUMN_TYPE_JSON: ColumnType
PARTITION_TRANSFORM_UNSPECIFIED: PartitionTransform
PARTITION_TRANSFORM_IDENTITY: PartitionTransform
PARTITION_TRANSFORM_YEAR: PartitionTransform
PARTITION_TRANSFORM_MONTH: PartitionTransform
PARTITION_TRANSFORM_DAY: PartitionTransform
WRITE_MODE_UNSPECIFIED: WriteMode
WRITE_MODE_APPEND: WriteMode
WRITE_MODE_REPLACE: WriteMode
WRITE_MODE_UPSERT: WriteMode

class ColumnSpec(_message.Message):
    __slots__ = ("name", "type")
    NAME_FIELD_NUMBER: _ClassVar[int]
    TYPE_FIELD_NUMBER: _ClassVar[int]
    name: str
    type: ColumnType
    def __init__(self, name: _Optional[str] = ..., type: _Optional[_Union[ColumnType, str]] = ...) -> None: ...

class PartitionSpec(_message.Message):
    __slots__ = ("column", "transform")
    COLUMN_FIELD_NUMBER: _ClassVar[int]
    TRANSFORM_FIELD_NUMBER: _ClassVar[int]
    column: str
    transform: PartitionTransform
    def __init__(self, column: _Optional[str] = ..., transform: _Optional[_Union[PartitionTransform, str]] = ...) -> None: ...

class DatasetSpec(_message.Message):
    __slots__ = ("name", "namespace", "columns", "partitions", "primary_key")
    NAME_FIELD_NUMBER: _ClassVar[int]
    NAMESPACE_FIELD_NUMBER: _ClassVar[int]
    COLUMNS_FIELD_NUMBER: _ClassVar[int]
    PARTITIONS_FIELD_NUMBER: _ClassVar[int]
    PRIMARY_KEY_FIELD_NUMBER: _ClassVar[int]
    name: str
    namespace: str
    columns: _containers.RepeatedCompositeFieldContainer[ColumnSpec]
    partitions: _containers.RepeatedCompositeFieldContainer[PartitionSpec]
    primary_key: _containers.RepeatedScalarFieldContainer[str]
    def __init__(self, name: _Optional[str] = ..., namespace: _Optional[str] = ..., columns: _Optional[_Iterable[_Union[ColumnSpec, _Mapping]]] = ..., partitions: _Optional[_Iterable[_Union[PartitionSpec, _Mapping]]] = ..., primary_key: _Optional[_Iterable[str]] = ...) -> None: ...

class DatasetInfo(_message.Message):
    __slots__ = ("name", "namespace", "columns", "partitions", "primary_key", "snapshot_id", "location")
    NAME_FIELD_NUMBER: _ClassVar[int]
    NAMESPACE_FIELD_NUMBER: _ClassVar[int]
    COLUMNS_FIELD_NUMBER: _ClassVar[int]
    PARTITIONS_FIELD_NUMBER: _ClassVar[int]
    PRIMARY_KEY_FIELD_NUMBER: _ClassVar[int]
    SNAPSHOT_ID_FIELD_NUMBER: _ClassVar[int]
    LOCATION_FIELD_NUMBER: _ClassVar[int]
    name: str
    namespace: str
    columns: _containers.RepeatedCompositeFieldContainer[ColumnSpec]
    partitions: _containers.RepeatedCompositeFieldContainer[PartitionSpec]
    primary_key: _containers.RepeatedScalarFieldContainer[str]
    snapshot_id: int
    location: str
    def __init__(self, name: _Optional[str] = ..., namespace: _Optional[str] = ..., columns: _Optional[_Iterable[_Union[ColumnSpec, _Mapping]]] = ..., partitions: _Optional[_Iterable[_Union[PartitionSpec, _Mapping]]] = ..., primary_key: _Optional[_Iterable[str]] = ..., snapshot_id: _Optional[int] = ..., location: _Optional[str] = ...) -> None: ...

class DatasetInfoList(_message.Message):
    __slots__ = ("items",)
    ITEMS_FIELD_NUMBER: _ClassVar[int]
    items: _containers.RepeatedCompositeFieldContainer[DatasetInfo]
    def __init__(self, items: _Optional[_Iterable[_Union[DatasetInfo, _Mapping]]] = ...) -> None: ...

class DatasetSnapshotInfo(_message.Message):
    __slots__ = ("snapshot_id", "created_at")
    SNAPSHOT_ID_FIELD_NUMBER: _ClassVar[int]
    CREATED_AT_FIELD_NUMBER: _ClassVar[int]
    snapshot_id: int
    created_at: _timestamp_pb2.Timestamp
    def __init__(self, snapshot_id: _Optional[int] = ..., created_at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ...) -> None: ...

class DatasetSnapshotInfoList(_message.Message):
    __slots__ = ("items",)
    ITEMS_FIELD_NUMBER: _ClassVar[int]
    items: _containers.RepeatedCompositeFieldContainer[DatasetSnapshotInfo]
    def __init__(self, items: _Optional[_Iterable[_Union[DatasetSnapshotInfo, _Mapping]]] = ...) -> None: ...

class QueryResult(_message.Message):
    __slots__ = ("columns", "rows")
    COLUMNS_FIELD_NUMBER: _ClassVar[int]
    ROWS_FIELD_NUMBER: _ClassVar[int]
    columns: _containers.RepeatedScalarFieldContainer[str]
    rows: _containers.RepeatedCompositeFieldContainer[_struct_pb2.Struct]
    def __init__(self, columns: _Optional[_Iterable[str]] = ..., rows: _Optional[_Iterable[_Union[_struct_pb2.Struct, _Mapping]]] = ...) -> None: ...

class DatasetNotFoundDetail(_message.Message):
    __slots__ = ("name", "namespace")
    NAME_FIELD_NUMBER: _ClassVar[int]
    NAMESPACE_FIELD_NUMBER: _ClassVar[int]
    name: str
    namespace: str
    def __init__(self, name: _Optional[str] = ..., namespace: _Optional[str] = ...) -> None: ...

class DatasetAlreadyExistsDetail(_message.Message):
    __slots__ = ("name", "namespace")
    NAME_FIELD_NUMBER: _ClassVar[int]
    NAMESPACE_FIELD_NUMBER: _ClassVar[int]
    name: str
    namespace: str
    def __init__(self, name: _Optional[str] = ..., namespace: _Optional[str] = ...) -> None: ...

class DatasetSnapshotNotFoundDetail(_message.Message):
    __slots__ = ("snapshot_id",)
    SNAPSHOT_ID_FIELD_NUMBER: _ClassVar[int]
    snapshot_id: int
    def __init__(self, snapshot_id: _Optional[int] = ...) -> None: ...

class DatasetSnapshotConflictDetail(_message.Message):
    __slots__ = ("expected_snapshot_id", "current_snapshot_id")
    EXPECTED_SNAPSHOT_ID_FIELD_NUMBER: _ClassVar[int]
    CURRENT_SNAPSHOT_ID_FIELD_NUMBER: _ClassVar[int]
    expected_snapshot_id: int
    current_snapshot_id: int
    def __init__(self, expected_snapshot_id: _Optional[int] = ..., current_snapshot_id: _Optional[int] = ...) -> None: ...

class DatasetError(_message.Message):
    __slots__ = ("error", "not_found", "already_exists", "snapshot_not_found", "snapshot_conflict")
    ERROR_FIELD_NUMBER: _ClassVar[int]
    NOT_FOUND_FIELD_NUMBER: _ClassVar[int]
    ALREADY_EXISTS_FIELD_NUMBER: _ClassVar[int]
    SNAPSHOT_NOT_FOUND_FIELD_NUMBER: _ClassVar[int]
    SNAPSHOT_CONFLICT_FIELD_NUMBER: _ClassVar[int]
    error: _common_pb2.CallError
    not_found: DatasetNotFoundDetail
    already_exists: DatasetAlreadyExistsDetail
    snapshot_not_found: DatasetSnapshotNotFoundDetail
    snapshot_conflict: DatasetSnapshotConflictDetail
    def __init__(self, error: _Optional[_Union[_common_pb2.CallError, _Mapping]] = ..., not_found: _Optional[_Union[DatasetNotFoundDetail, _Mapping]] = ..., already_exists: _Optional[_Union[DatasetAlreadyExistsDetail, _Mapping]] = ..., snapshot_not_found: _Optional[_Union[DatasetSnapshotNotFoundDetail, _Mapping]] = ..., snapshot_conflict: _Optional[_Union[DatasetSnapshotConflictDetail, _Mapping]] = ...) -> None: ...

class CreateRequest(_message.Message):
    __slots__ = ("context", "spec")
    CONTEXT_FIELD_NUMBER: _ClassVar[int]
    SPEC_FIELD_NUMBER: _ClassVar[int]
    context: _common_pb2.CallContext
    spec: DatasetSpec
    def __init__(self, context: _Optional[_Union[_common_pb2.CallContext, _Mapping]] = ..., spec: _Optional[_Union[DatasetSpec, _Mapping]] = ...) -> None: ...

class CreateResponse(_message.Message):
    __slots__ = ("info", "error")
    INFO_FIELD_NUMBER: _ClassVar[int]
    ERROR_FIELD_NUMBER: _ClassVar[int]
    info: DatasetInfo
    error: DatasetError
    def __init__(self, info: _Optional[_Union[DatasetInfo, _Mapping]] = ..., error: _Optional[_Union[DatasetError, _Mapping]] = ...) -> None: ...

class DescribeRequest(_message.Message):
    __slots__ = ("context", "name", "namespace")
    CONTEXT_FIELD_NUMBER: _ClassVar[int]
    NAME_FIELD_NUMBER: _ClassVar[int]
    NAMESPACE_FIELD_NUMBER: _ClassVar[int]
    context: _common_pb2.CallContext
    name: str
    namespace: str
    def __init__(self, context: _Optional[_Union[_common_pb2.CallContext, _Mapping]] = ..., name: _Optional[str] = ..., namespace: _Optional[str] = ...) -> None: ...

class DescribeResponse(_message.Message):
    __slots__ = ("info", "error")
    INFO_FIELD_NUMBER: _ClassVar[int]
    ERROR_FIELD_NUMBER: _ClassVar[int]
    info: DatasetInfo
    error: DatasetError
    def __init__(self, info: _Optional[_Union[DatasetInfo, _Mapping]] = ..., error: _Optional[_Union[DatasetError, _Mapping]] = ...) -> None: ...

class ListRequest(_message.Message):
    __slots__ = ("context", "namespace")
    CONTEXT_FIELD_NUMBER: _ClassVar[int]
    NAMESPACE_FIELD_NUMBER: _ClassVar[int]
    context: _common_pb2.CallContext
    namespace: str
    def __init__(self, context: _Optional[_Union[_common_pb2.CallContext, _Mapping]] = ..., namespace: _Optional[str] = ...) -> None: ...

class ListResponse(_message.Message):
    __slots__ = ("datasets", "error")
    DATASETS_FIELD_NUMBER: _ClassVar[int]
    ERROR_FIELD_NUMBER: _ClassVar[int]
    datasets: DatasetInfoList
    error: DatasetError
    def __init__(self, datasets: _Optional[_Union[DatasetInfoList, _Mapping]] = ..., error: _Optional[_Union[DatasetError, _Mapping]] = ...) -> None: ...

class WriteRequest(_message.Message):
    __slots__ = ("context", "name", "rows", "namespace", "mode", "snapshot_id")
    CONTEXT_FIELD_NUMBER: _ClassVar[int]
    NAME_FIELD_NUMBER: _ClassVar[int]
    ROWS_FIELD_NUMBER: _ClassVar[int]
    NAMESPACE_FIELD_NUMBER: _ClassVar[int]
    MODE_FIELD_NUMBER: _ClassVar[int]
    SNAPSHOT_ID_FIELD_NUMBER: _ClassVar[int]
    context: _common_pb2.CallContext
    name: str
    rows: _containers.RepeatedCompositeFieldContainer[_struct_pb2.Struct]
    namespace: str
    mode: WriteMode
    snapshot_id: int
    def __init__(self, context: _Optional[_Union[_common_pb2.CallContext, _Mapping]] = ..., name: _Optional[str] = ..., rows: _Optional[_Iterable[_Union[_struct_pb2.Struct, _Mapping]]] = ..., namespace: _Optional[str] = ..., mode: _Optional[_Union[WriteMode, str]] = ..., snapshot_id: _Optional[int] = ...) -> None: ...

class WriteResponse(_message.Message):
    __slots__ = ("info", "error")
    INFO_FIELD_NUMBER: _ClassVar[int]
    ERROR_FIELD_NUMBER: _ClassVar[int]
    info: DatasetInfo
    error: DatasetError
    def __init__(self, info: _Optional[_Union[DatasetInfo, _Mapping]] = ..., error: _Optional[_Union[DatasetError, _Mapping]] = ...) -> None: ...

class QueryRequest(_message.Message):
    __slots__ = ("context", "sql", "namespace", "snapshot_id")
    CONTEXT_FIELD_NUMBER: _ClassVar[int]
    SQL_FIELD_NUMBER: _ClassVar[int]
    NAMESPACE_FIELD_NUMBER: _ClassVar[int]
    SNAPSHOT_ID_FIELD_NUMBER: _ClassVar[int]
    context: _common_pb2.CallContext
    sql: str
    namespace: str
    snapshot_id: int
    def __init__(self, context: _Optional[_Union[_common_pb2.CallContext, _Mapping]] = ..., sql: _Optional[str] = ..., namespace: _Optional[str] = ..., snapshot_id: _Optional[int] = ...) -> None: ...

class QueryResponse(_message.Message):
    __slots__ = ("query_result", "error")
    QUERY_RESULT_FIELD_NUMBER: _ClassVar[int]
    ERROR_FIELD_NUMBER: _ClassVar[int]
    query_result: QueryResult
    error: DatasetError
    def __init__(self, query_result: _Optional[_Union[QueryResult, _Mapping]] = ..., error: _Optional[_Union[DatasetError, _Mapping]] = ...) -> None: ...

class FlushRequest(_message.Message):
    __slots__ = ("context", "name", "namespace")
    CONTEXT_FIELD_NUMBER: _ClassVar[int]
    NAME_FIELD_NUMBER: _ClassVar[int]
    NAMESPACE_FIELD_NUMBER: _ClassVar[int]
    context: _common_pb2.CallContext
    name: str
    namespace: str
    def __init__(self, context: _Optional[_Union[_common_pb2.CallContext, _Mapping]] = ..., name: _Optional[str] = ..., namespace: _Optional[str] = ...) -> None: ...

class FlushResponse(_message.Message):
    __slots__ = ("query_result", "error")
    QUERY_RESULT_FIELD_NUMBER: _ClassVar[int]
    ERROR_FIELD_NUMBER: _ClassVar[int]
    query_result: QueryResult
    error: DatasetError
    def __init__(self, query_result: _Optional[_Union[QueryResult, _Mapping]] = ..., error: _Optional[_Union[DatasetError, _Mapping]] = ...) -> None: ...

class InlinedRowCountRequest(_message.Message):
    __slots__ = ("context", "name", "namespace")
    CONTEXT_FIELD_NUMBER: _ClassVar[int]
    NAME_FIELD_NUMBER: _ClassVar[int]
    NAMESPACE_FIELD_NUMBER: _ClassVar[int]
    context: _common_pb2.CallContext
    name: str
    namespace: str
    def __init__(self, context: _Optional[_Union[_common_pb2.CallContext, _Mapping]] = ..., name: _Optional[str] = ..., namespace: _Optional[str] = ...) -> None: ...

class InlinedRowCountResponse(_message.Message):
    __slots__ = ("count", "error")
    COUNT_FIELD_NUMBER: _ClassVar[int]
    ERROR_FIELD_NUMBER: _ClassVar[int]
    count: int
    error: DatasetError
    def __init__(self, count: _Optional[int] = ..., error: _Optional[_Union[DatasetError, _Mapping]] = ...) -> None: ...

class CompactRequest(_message.Message):
    __slots__ = ("context", "name", "namespace")
    CONTEXT_FIELD_NUMBER: _ClassVar[int]
    NAME_FIELD_NUMBER: _ClassVar[int]
    NAMESPACE_FIELD_NUMBER: _ClassVar[int]
    context: _common_pb2.CallContext
    name: str
    namespace: str
    def __init__(self, context: _Optional[_Union[_common_pb2.CallContext, _Mapping]] = ..., name: _Optional[str] = ..., namespace: _Optional[str] = ...) -> None: ...

class CompactResponse(_message.Message):
    __slots__ = ("query_result", "error")
    QUERY_RESULT_FIELD_NUMBER: _ClassVar[int]
    ERROR_FIELD_NUMBER: _ClassVar[int]
    query_result: QueryResult
    error: DatasetError
    def __init__(self, query_result: _Optional[_Union[QueryResult, _Mapping]] = ..., error: _Optional[_Union[DatasetError, _Mapping]] = ...) -> None: ...

class ListSnapshotsRequest(_message.Message):
    __slots__ = ("context",)
    CONTEXT_FIELD_NUMBER: _ClassVar[int]
    context: _common_pb2.CallContext
    def __init__(self, context: _Optional[_Union[_common_pb2.CallContext, _Mapping]] = ...) -> None: ...

class ListSnapshotsResponse(_message.Message):
    __slots__ = ("snapshots", "error")
    SNAPSHOTS_FIELD_NUMBER: _ClassVar[int]
    ERROR_FIELD_NUMBER: _ClassVar[int]
    snapshots: DatasetSnapshotInfoList
    error: DatasetError
    def __init__(self, snapshots: _Optional[_Union[DatasetSnapshotInfoList, _Mapping]] = ..., error: _Optional[_Union[DatasetError, _Mapping]] = ...) -> None: ...

class DropRequest(_message.Message):
    __slots__ = ("context", "name", "namespace")
    CONTEXT_FIELD_NUMBER: _ClassVar[int]
    NAME_FIELD_NUMBER: _ClassVar[int]
    NAMESPACE_FIELD_NUMBER: _ClassVar[int]
    context: _common_pb2.CallContext
    name: str
    namespace: str
    def __init__(self, context: _Optional[_Union[_common_pb2.CallContext, _Mapping]] = ..., name: _Optional[str] = ..., namespace: _Optional[str] = ...) -> None: ...

class DropResponse(_message.Message):
    __slots__ = ("error",)
    ERROR_FIELD_NUMBER: _ClassVar[int]
    error: DatasetError
    def __init__(self, error: _Optional[_Union[DatasetError, _Mapping]] = ...) -> None: ...
