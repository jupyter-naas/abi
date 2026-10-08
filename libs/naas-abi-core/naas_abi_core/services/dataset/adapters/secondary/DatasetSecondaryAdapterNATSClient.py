"""NATS RPC client adapter for the dataset kernel domain.

Implements ``IDatasetPort`` by calling out to a remote
``DatasetPrimaryAdapterNATS`` over NATS request/reply -- see
``naas_abi_core/proto/dataset/v1/dataset.proto`` for the wire contract and
``naas_abi_core/proto/README.md`` for why it lives there.

Shared connection, token, timeout, and reply handling live in
``naas_abi_core.engine.nats_rpc.NatsRPCClient``. Calls are never replayed
by the transport after failure; a timeout may hide a completed operation.

Stage 1 auth model (see ``naas_abi_core.engine.nats_auth``): a JWT asserting
``service_identity`` is issued once and attached on the ``Nats-Auth-Token``
header of every request, reissued only when it is close to expiry rather
than on every call. ``DatasetPrimaryAdapterNATS`` must read the token from
that exact header -- both sides read ``AUTH_HEADER`` from
``dataset_nats_contract``, a neutral module neither adapter owns, so this
file never has to import from the primary adapter's module (or vice versa)
just to agree on a header name.

``IDatasetPort`` has no streaming/callback members, so every method here has
a matching NATS subject -- no exclusions.
"""

from __future__ import annotations

# ``list`` is a port method name, so it shadows the builtin for annotations
# evaluated in this class body below (methods after ``list``); use
# ``builtins.list`` there -- same workaround as DatasetPort.py/DatasetService.py.
import builtins
from datetime import UTC
from typing import Any

from google.protobuf import json_format
from naas_abi_core.engine.nats_rpc import NatsRPCClient
from naas_abi_core.proto.dataset.v1 import dataset_pb2
from naas_abi_core.services.dataset.adapters.dataset_nats_contract import (
    AUTH_HEADER,
    SUBJECT_PREFIX,
)
from naas_abi_core.services.dataset.DatasetPort import (
    ColumnSpec,
    ColumnType,
    DatasetAlreadyExistsError,
    DatasetInfo,
    DatasetNotFoundError,
    DatasetSchemaError,
    DatasetSnapshotConflictError,
    DatasetSnapshotInfo,
    DatasetSnapshotNotFoundError,
    DatasetSpec,
    IDatasetPort,
    PartitionSpec,
    PartitionTransform,
    QueryResult,
    WriteMode,
)

_COLUMN_TYPE_TO_PB: dict[ColumnType, dataset_pb2.ColumnType] = {
    "string": dataset_pb2.COLUMN_TYPE_STRING,
    "integer": dataset_pb2.COLUMN_TYPE_INTEGER,
    "bigint": dataset_pb2.COLUMN_TYPE_BIGINT,
    "double": dataset_pb2.COLUMN_TYPE_DOUBLE,
    "boolean": dataset_pb2.COLUMN_TYPE_BOOLEAN,
    "date": dataset_pb2.COLUMN_TYPE_DATE,
    "timestamp": dataset_pb2.COLUMN_TYPE_TIMESTAMP,
    "json": dataset_pb2.COLUMN_TYPE_JSON,
}
_PB_TO_COLUMN_TYPE: dict[dataset_pb2.ColumnType, ColumnType] = {
    v: k for k, v in _COLUMN_TYPE_TO_PB.items()
}

_PARTITION_TRANSFORM_TO_PB: dict[PartitionTransform, dataset_pb2.PartitionTransform] = {
    "identity": dataset_pb2.PARTITION_TRANSFORM_IDENTITY,
    "year": dataset_pb2.PARTITION_TRANSFORM_YEAR,
    "month": dataset_pb2.PARTITION_TRANSFORM_MONTH,
    "day": dataset_pb2.PARTITION_TRANSFORM_DAY,
}
_PB_TO_PARTITION_TRANSFORM: dict[dataset_pb2.PartitionTransform, PartitionTransform] = {
    v: k for k, v in _PARTITION_TRANSFORM_TO_PB.items()
}

_WRITE_MODE_TO_PB: dict[WriteMode, dataset_pb2.WriteMode] = {
    "append": dataset_pb2.WRITE_MODE_APPEND,
    "replace": dataset_pb2.WRITE_MODE_REPLACE,
    "upsert": dataset_pb2.WRITE_MODE_UPSERT,
}
_PB_TO_WRITE_MODE: dict[dataset_pb2.WriteMode, WriteMode] = {
    v: k for k, v in _WRITE_MODE_TO_PB.items()
}


def _column_spec_to_pb(column: ColumnSpec) -> dataset_pb2.ColumnSpec:
    return dataset_pb2.ColumnSpec(
        name=column.name, type=_COLUMN_TYPE_TO_PB[column.type]
    )


def _pb_to_column_spec(pb: dataset_pb2.ColumnSpec) -> ColumnSpec:
    return ColumnSpec(name=pb.name, type=_PB_TO_COLUMN_TYPE[pb.type])


def _partition_spec_to_pb(partition: PartitionSpec) -> dataset_pb2.PartitionSpec:
    return dataset_pb2.PartitionSpec(
        column=partition.column,
        transform=_PARTITION_TRANSFORM_TO_PB[partition.transform],
    )


def _pb_to_partition_spec(pb: dataset_pb2.PartitionSpec) -> PartitionSpec:
    return PartitionSpec(
        column=pb.column, transform=_PB_TO_PARTITION_TRANSFORM[pb.transform]
    )


def _dataset_spec_to_pb(spec: DatasetSpec) -> dataset_pb2.DatasetSpec:
    return dataset_pb2.DatasetSpec(
        name=spec.name,
        namespace=spec.namespace,
        columns=[_column_spec_to_pb(column) for column in spec.columns],
        partitions=[_partition_spec_to_pb(partition) for partition in spec.partitions],
        primary_key=list(spec.primary_key),
    )


def _pb_to_dataset_info(pb: dataset_pb2.DatasetInfo) -> DatasetInfo:
    return DatasetInfo(
        name=pb.name,
        namespace=pb.namespace,
        columns=tuple(_pb_to_column_spec(column) for column in pb.columns),
        partitions=tuple(
            _pb_to_partition_spec(partition) for partition in pb.partitions
        ),
        primary_key=tuple(pb.primary_key),
        snapshot_id=pb.snapshot_id,
        location=pb.location,
    )


def _pb_to_dataset_snapshot_info(
    pb: dataset_pb2.DatasetSnapshotInfo,
) -> DatasetSnapshotInfo:
    return DatasetSnapshotInfo(
        snapshot_id=pb.snapshot_id, created_at=pb.created_at.ToDatetime(tzinfo=UTC)
    )


def _struct_to_row(pb: Any) -> dict[str, Any]:
    """Decode one ``google.protobuf.Struct`` row back into a plain dict.

    ``pb`` is typed ``Any``, not ``struct_pb2.Struct``, deliberately: mypy
    cannot resolve well-known-type attributes (``Struct``, ``Timestamp``, ...)
    from ``google.protobuf`` in this project's environment when referenced as
    a bare annotation outside a generated ``_pb2.pyi`` (see the ``[tool.mypy]``
    override comment on ``naas_abi_core.proto.*`` in ``pyproject.toml`` for
    the same upstream quirk). Encoding the other direction needs no such
    helper: protobuf message constructors accept a plain dict anywhere a
    ``Struct``-typed field is expected (see ``write()`` below), so there is
    no ``_row_to_struct`` counterpart to this function.
    """
    return json_format.MessageToDict(pb)


def _pb_to_query_result(pb: dataset_pb2.QueryResult) -> QueryResult:
    return QueryResult(
        columns=list(pb.columns), rows=[_struct_to_row(row) for row in pb.rows]
    )


def _raise_for_error(error: dataset_pb2.DatasetError) -> None:
    """Raise the exception matching ``error``.

    Must stay exactly symmetric with how ``DatasetPrimaryAdapterNATS``
    encodes errors -- the generic adapter contract test asserts on the real
    exception types, not on the wire code.
    """
    code = error.error.code
    message = error.error.message
    detail_case = error.WhichOneof("detail")
    if code == "DATASET_NOT_FOUND" and detail_case == "not_found":
        raise DatasetNotFoundError(error.not_found.name, error.not_found.namespace)
    if code == "DATASET_ALREADY_EXISTS" and detail_case == "already_exists":
        raise DatasetAlreadyExistsError(
            error.already_exists.name, error.already_exists.namespace
        )
    if code == "DATASET_SNAPSHOT_NOT_FOUND" and detail_case == "snapshot_not_found":
        raise DatasetSnapshotNotFoundError(error.snapshot_not_found.snapshot_id)
    if code == "DATASET_SNAPSHOT_CONFLICT" and detail_case == "snapshot_conflict":
        raise DatasetSnapshotConflictError(
            error.snapshot_conflict.expected_snapshot_id,
            error.snapshot_conflict.current_snapshot_id,
        )
    if code == "DATASET_SCHEMA_ERROR":
        raise DatasetSchemaError(message)
    raise RuntimeError(f"dataset NATS RPC failed ({code}): {message}")


class DatasetSecondaryAdapterNATSClient(NatsRPCClient, IDatasetPort):
    """Calls a remote ``DatasetPrimaryAdapterNATS`` over NATS RPC."""

    def __init__(
        self,
        nats_url: str,
        jwt_secret: str,
        service_identity: str,
        timeout_seconds: float = 10.0,
    ) -> None:
        super().__init__(
            nats_url,
            jwt_secret,
            service_identity,
            timeout_seconds,
            auth_header=AUTH_HEADER,
        )

    # ------------------------------------------------------------------
    # IDatasetPort.
    # ------------------------------------------------------------------

    def create(self, spec: DatasetSpec) -> DatasetInfo:
        request = dataset_pb2.CreateRequest(
            context=self._context(), spec=_dataset_spec_to_pb(spec)
        )
        response = self._call(
            f"{SUBJECT_PREFIX}.create", request, dataset_pb2.CreateResponse
        )
        if response.HasField("error"):
            _raise_for_error(response.error)
        return _pb_to_dataset_info(response.info)

    def describe(self, name: str, *, namespace: str = "default") -> DatasetInfo:
        request = dataset_pb2.DescribeRequest(
            context=self._context(), name=name, namespace=namespace
        )
        response = self._call(
            f"{SUBJECT_PREFIX}.describe", request, dataset_pb2.DescribeResponse
        )
        if response.HasField("error"):
            _raise_for_error(response.error)
        return _pb_to_dataset_info(response.info)

    def list(self, *, namespace: str | None = None) -> list[DatasetInfo]:
        request = dataset_pb2.ListRequest(context=self._context())
        if namespace is not None:
            request.namespace = namespace
        response = self._call(
            f"{SUBJECT_PREFIX}.list", request, dataset_pb2.ListResponse
        )
        if response.HasField("error"):
            _raise_for_error(response.error)
        return [_pb_to_dataset_info(info) for info in response.datasets.items]

    def write(
        self,
        name: str,
        rows: builtins.list[dict[str, Any]],
        *,
        namespace: str = "default",
        mode: WriteMode = "append",
        snapshot_id: int | None = None,
    ) -> DatasetInfo:
        request = dataset_pb2.WriteRequest(
            context=self._context(),
            name=name,
            rows=rows,
            namespace=namespace,
            mode=_WRITE_MODE_TO_PB[mode],
        )
        if snapshot_id is not None:
            request.snapshot_id = snapshot_id
        response = self._call(
            f"{SUBJECT_PREFIX}.write", request, dataset_pb2.WriteResponse
        )
        if response.HasField("error"):
            _raise_for_error(response.error)
        return _pb_to_dataset_info(response.info)

    def query(
        self,
        sql: str,
        *,
        namespace: str = "default",
        snapshot_id: int | None = None,
    ) -> QueryResult:
        request = dataset_pb2.QueryRequest(
            context=self._context(), sql=sql, namespace=namespace
        )
        if snapshot_id is not None:
            request.snapshot_id = snapshot_id
        response = self._call(
            f"{SUBJECT_PREFIX}.query", request, dataset_pb2.QueryResponse
        )
        if response.HasField("error"):
            _raise_for_error(response.error)
        return _pb_to_query_result(response.query_result)

    def flush(self, name: str, *, namespace: str = "default") -> QueryResult:
        request = dataset_pb2.FlushRequest(
            context=self._context(), name=name, namespace=namespace
        )
        response = self._call(
            f"{SUBJECT_PREFIX}.flush", request, dataset_pb2.FlushResponse
        )
        if response.HasField("error"):
            _raise_for_error(response.error)
        return _pb_to_query_result(response.query_result)

    def inlined_row_count(self, name: str, *, namespace: str = "default") -> int:
        request = dataset_pb2.InlinedRowCountRequest(
            context=self._context(), name=name, namespace=namespace
        )
        response = self._call(
            f"{SUBJECT_PREFIX}.inlined_row_count",
            request,
            dataset_pb2.InlinedRowCountResponse,
        )
        if response.HasField("error"):
            _raise_for_error(response.error)
        return response.count

    def compact(self, name: str, *, namespace: str = "default") -> QueryResult:
        request = dataset_pb2.CompactRequest(
            context=self._context(), name=name, namespace=namespace
        )
        response = self._call(
            f"{SUBJECT_PREFIX}.compact", request, dataset_pb2.CompactResponse
        )
        if response.HasField("error"):
            _raise_for_error(response.error)
        return _pb_to_query_result(response.query_result)

    def list_snapshots(self) -> builtins.list[DatasetSnapshotInfo]:
        request = dataset_pb2.ListSnapshotsRequest(context=self._context())
        response = self._call(
            f"{SUBJECT_PREFIX}.list_snapshots",
            request,
            dataset_pb2.ListSnapshotsResponse,
        )
        if response.HasField("error"):
            _raise_for_error(response.error)
        return [
            _pb_to_dataset_snapshot_info(snapshot)
            for snapshot in response.snapshots.items
        ]

    def drop(self, name: str, *, namespace: str = "default") -> None:
        request = dataset_pb2.DropRequest(
            context=self._context(), name=name, namespace=namespace
        )
        response = self._call(
            f"{SUBJECT_PREFIX}.drop", request, dataset_pb2.DropResponse
        )
        if response.HasField("error"):
            _raise_for_error(response.error)
