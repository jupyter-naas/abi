"""NATS RPC primary adapter for the dataset kernel domain.

Exposes a real ``IDatasetPort`` as a NATS micro-service (see
``naas_abi_core/proto/dataset/v1/dataset.proto`` for the wire contract and
``naas_abi_core/proto/README.md`` for why it lives there). This is the
server side; the matching client is ``DatasetSecondaryAdapterNATSClient``.

Stage 1 auth model (see ``naas_abi_core.engine.nats_auth``): one shared
secret, one claim -- which known first-party process holds the token. Every
incoming request must carry a valid token in the ``Nats-Auth-Token`` header
(``AUTH_HEADER``, imported from ``dataset_nats_contract`` below -- that's a
neutral module neither adapter owns, so this file and the client's don't
depend on each other; see that module's docstring for why).

``IDatasetPort`` has no streaming/callback members, so this is a full 1:1
mapping -- one endpoint per port method, no exclusions.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import Any, TypeVar

import nats
import nats.micro
from google.protobuf import json_format
from google.protobuf.message import DecodeError, Message
from naas_abi_core import logger
from naas_abi_core.engine.nats_auth import (
    InvalidServiceTokenError,
    verify_service_token,
)
from naas_abi_core.engine.nats_rpc import respond_protobuf
from naas_abi_core.proto.common.v1 import common_pb2
from naas_abi_core.proto.dataset.v1 import dataset_pb2
from naas_abi_core.services.dataset.adapters.dataset_nats_contract import (
    AUTH_HEADER,
    SERVICE_NAME,
    SERVICE_VERSION,
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
from naas_abi_core.services.dataset.DatasetService import DatasetService
from nats.micro.request import Request
from nats.micro.service import Service

__all__ = [
    "AUTH_HEADER",
    "SERVICE_NAME",
    "SERVICE_VERSION",
    "SUBJECT_PREFIX",
    "DatasetPrimaryAdapterNATS",
]

_RequestT = TypeVar("_RequestT", bound=Message)
_ResponseT = TypeVar("_ResponseT", bound=Message)

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


def _pb_to_dataset_spec(pb: dataset_pb2.DatasetSpec) -> DatasetSpec:
    return DatasetSpec(
        name=pb.name,
        namespace=pb.namespace,
        columns=tuple(_pb_to_column_spec(column) for column in pb.columns),
        partitions=tuple(
            _pb_to_partition_spec(partition) for partition in pb.partitions
        ),
        primary_key=tuple(pb.primary_key),
    )


def _dataset_info_to_pb(info: DatasetInfo) -> dataset_pb2.DatasetInfo:
    return dataset_pb2.DatasetInfo(
        name=info.name,
        namespace=info.namespace,
        columns=[_column_spec_to_pb(column) for column in info.columns],
        partitions=[_partition_spec_to_pb(partition) for partition in info.partitions],
        primary_key=list(info.primary_key),
        snapshot_id=info.snapshot_id,
        location=info.location,
    )


def _dataset_snapshot_info_to_pb(
    snapshot: DatasetSnapshotInfo,
) -> dataset_pb2.DatasetSnapshotInfo:
    pb = dataset_pb2.DatasetSnapshotInfo(snapshot_id=snapshot.snapshot_id)
    pb.created_at.FromDatetime(snapshot.created_at)
    return pb


def _struct_to_row(pb: Any) -> dict[str, Any]:
    """Decode one ``google.protobuf.Struct`` row back into a plain dict.

    ``pb`` is typed ``Any``, not ``struct_pb2.Struct``, deliberately: mypy
    cannot resolve well-known-type attributes (``Struct``, ``Timestamp``, ...)
    from ``google.protobuf`` in this project's environment when referenced as
    a bare annotation outside a generated ``_pb2.pyi`` (see the ``[tool.mypy]``
    override comment on ``naas_abi_core.proto.*`` in ``pyproject.toml`` for
    the same upstream quirk). Encoding the other direction needs no such
    helper: protobuf message constructors accept a plain dict anywhere a
    ``Struct``-typed field is expected (see ``_query_result_to_pb`` below), so
    there is no ``_row_to_struct`` counterpart to this function.
    """
    return json_format.MessageToDict(pb)


def _query_result_to_pb(result: QueryResult) -> dataset_pb2.QueryResult:
    return dataset_pb2.QueryResult(columns=result.columns, rows=result.rows)


class DatasetPrimaryAdapterNATS:
    """Serves datasets over NATS RPC (request/reply).

    Wraps a real adapter *or* the domain service and registers one NATS
    micro-service endpoint per ``IDatasetPort`` method. Each endpoint
    authenticates the caller via ``Nats-Auth-Token`` before doing anything
    else, then decodes the Protobuf request, calls straight through to the
    wrapped object, and encodes a Protobuf response. Errors -- auth
    failures, known domain exceptions, anything unexpected -- are always
    reported as a normal response carrying a populated ``DatasetError``,
    never as a crashed handler or a raw NATS-level error.

    Accepts either an ``IDatasetPort`` (a bare secondary adapter, e.g. in
    tests) or a ``DatasetService`` (the real engine-loaded domain service) --
    deliberately, not for convenience: wrapping the raw adapter instead of
    the domain service would silently skip any behaviour ``DatasetService``
    layers on top of the port (event publishing, derived checks) for every
    remote caller, which would only diverge from in-process behaviour, not
    match it. ``EngineNATSLoader`` always passes the domain service.
    """

    def __init__(
        self,
        adapter: IDatasetPort | DatasetService,
        jwt_secret: str,
    ) -> None:
        self._adapter = adapter
        self._jwt_secret = jwt_secret
        self._service: Service | None = None

    async def start(self, nc: nats.NATS) -> None:
        """Register the ``dataset`` NATS service on ``nc``.

        ``nc`` must already be connected -- this adapter never manages the
        connection lifecycle itself, only the service/endpoints layered on
        top of it. Calling this more than once is a no-op.
        """
        if self._service is not None:
            return

        service = await nats.micro.add_service(
            nc,
            name=SERVICE_NAME,
            version=SERVICE_VERSION,
            description="ABI kernel dataset domain, exposed over NATS RPC (v1).",
        )
        await service.add_endpoint(
            name="create",
            subject=f"{SUBJECT_PREFIX}.create",
            handler=self._handle_create,
        )
        await service.add_endpoint(
            name="describe",
            subject=f"{SUBJECT_PREFIX}.describe",
            handler=self._handle_describe,
        )
        await service.add_endpoint(
            name="list",
            subject=f"{SUBJECT_PREFIX}.list",
            handler=self._handle_list,
        )
        await service.add_endpoint(
            name="write",
            subject=f"{SUBJECT_PREFIX}.write",
            handler=self._handle_write,
        )
        await service.add_endpoint(
            name="query",
            subject=f"{SUBJECT_PREFIX}.query",
            handler=self._handle_query,
        )
        await service.add_endpoint(
            name="flush",
            subject=f"{SUBJECT_PREFIX}.flush",
            handler=self._handle_flush,
        )
        await service.add_endpoint(
            name="inlined_row_count",
            subject=f"{SUBJECT_PREFIX}.inlined_row_count",
            handler=self._handle_inlined_row_count,
        )
        await service.add_endpoint(
            name="compact",
            subject=f"{SUBJECT_PREFIX}.compact",
            handler=self._handle_compact,
        )
        await service.add_endpoint(
            name="list_snapshots",
            subject=f"{SUBJECT_PREFIX}.list_snapshots",
            handler=self._handle_list_snapshots,
        )
        await service.add_endpoint(
            name="drop",
            subject=f"{SUBJECT_PREFIX}.drop",
            handler=self._handle_drop,
        )
        self._service = service

    async def stop(self) -> None:
        """Deregister the service, draining its subscriptions."""
        service = self._service
        self._service = None
        if service is not None:
            await service.stop()

    # ------------------------------------------------------------------
    # Shared request handling: auth, decode, dispatch, encode.
    # ------------------------------------------------------------------

    async def _handle(
        self,
        request: Request,
        request_cls: type[_RequestT],
        response_cls: Callable[..., _ResponseT],
        call: Callable[[_RequestT], _ResponseT],
    ) -> None:
        if not self._is_authenticated(request):
            await self._respond_error(
                request,
                response_cls,
                self._error(
                    "UNAUTHENTICATED", "missing or invalid auth token", retryable=False
                ),
            )
            return

        parsed_request = request_cls()
        try:
            parsed_request.ParseFromString(request.data)
        except DecodeError:
            await self._respond_error(
                request,
                response_cls,
                self._error(
                    "INVALID_ARGUMENT", "invalid protobuf request", retryable=False
                ),
            )
            return

        try:
            # The adapter port is synchronous and may block for seconds (network
            # round trips, slow backends). Every primary shares ONE event loop and
            # ONE connection (nats_runtime), so run the call on a worker thread:
            # inline it would stall every other endpoint of every service in the
            # process, plus nats-py's own PING/PONG handling.
            response = await asyncio.to_thread(call, parsed_request)
        except DatasetNotFoundError as exc:
            await self._respond_error(
                request,
                response_cls,
                self._error(
                    "DATASET_NOT_FOUND",
                    str(exc),
                    retryable=False,
                    not_found=dataset_pb2.DatasetNotFoundDetail(
                        name=exc.name, namespace=exc.namespace
                    ),
                ),
            )
            return
        except DatasetAlreadyExistsError as exc:
            await self._respond_error(
                request,
                response_cls,
                self._error(
                    "DATASET_ALREADY_EXISTS",
                    str(exc),
                    retryable=False,
                    already_exists=dataset_pb2.DatasetAlreadyExistsDetail(
                        name=exc.name, namespace=exc.namespace
                    ),
                ),
            )
            return
        except DatasetSnapshotNotFoundError as exc:
            await self._respond_error(
                request,
                response_cls,
                self._error(
                    "DATASET_SNAPSHOT_NOT_FOUND",
                    str(exc),
                    retryable=False,
                    snapshot_not_found=dataset_pb2.DatasetSnapshotNotFoundDetail(
                        snapshot_id=exc.snapshot_id
                    ),
                ),
            )
            return
        except DatasetSnapshotConflictError as exc:
            await self._respond_error(
                request,
                response_cls,
                self._error(
                    "DATASET_SNAPSHOT_CONFLICT",
                    str(exc),
                    retryable=False,
                    snapshot_conflict=dataset_pb2.DatasetSnapshotConflictDetail(
                        expected_snapshot_id=exc.expected_snapshot_id,
                        current_snapshot_id=exc.current_snapshot_id,
                    ),
                ),
            )
            return
        except DatasetSchemaError as exc:
            await self._respond_error(
                request,
                response_cls,
                self._error("DATASET_SCHEMA_ERROR", str(exc), retryable=False),
            )
            return
        except Exception:  # noqa: BLE001 - a handler must never crash the service
            logger.opt(exception=True).error(
                f"DatasetPrimaryAdapterNATS: unexpected error handling {request.subject!r}"
            )
            await self._respond_error(
                request,
                response_cls,
                self._error("INTERNAL", "internal error", retryable=True),
            )
            return

        await respond_protobuf(request, response, response_cls)

    def _is_authenticated(self, request: Request) -> bool:
        headers = request.headers or {}
        token = headers.get(AUTH_HEADER)
        if not token:
            return False
        try:
            verify_service_token(token, self._jwt_secret)
        except InvalidServiceTokenError:
            return False
        return True

    @staticmethod
    def _error(
        code: str,
        message: str,
        *,
        retryable: bool,
        not_found: dataset_pb2.DatasetNotFoundDetail | None = None,
        already_exists: dataset_pb2.DatasetAlreadyExistsDetail | None = None,
        snapshot_not_found: dataset_pb2.DatasetSnapshotNotFoundDetail | None = None,
        snapshot_conflict: dataset_pb2.DatasetSnapshotConflictDetail | None = None,
    ) -> dataset_pb2.DatasetError:
        # At most one of these is ever non-None at a given call site (each
        # exception maps to exactly one detail arm) -- passing all four
        # straight through lets protobuf's constructor set only the one that
        # matters and leave the ``detail`` oneof's other arms unset.
        return dataset_pb2.DatasetError(
            error=common_pb2.CallError(code=code, message=message, retryable=retryable),
            not_found=not_found,
            already_exists=already_exists,
            snapshot_not_found=snapshot_not_found,
            snapshot_conflict=snapshot_conflict,
        )

    @staticmethod
    async def _respond_error(
        request: Request,
        response_cls: Callable[..., Message],
        dataset_error: dataset_pb2.DatasetError,
    ) -> None:
        response = response_cls(error=dataset_error)
        await respond_protobuf(request, response, response_cls)

    # ------------------------------------------------------------------
    # Endpoint handlers -- one per IDatasetPort method.
    # ------------------------------------------------------------------

    async def _handle_create(self, request: Request) -> None:
        await self._handle(
            request,
            dataset_pb2.CreateRequest,
            dataset_pb2.CreateResponse,
            self._call_create,
        )

    def _call_create(
        self, req: dataset_pb2.CreateRequest
    ) -> dataset_pb2.CreateResponse:
        info = self._adapter.create(_pb_to_dataset_spec(req.spec))
        return dataset_pb2.CreateResponse(info=_dataset_info_to_pb(info))

    async def _handle_describe(self, request: Request) -> None:
        await self._handle(
            request,
            dataset_pb2.DescribeRequest,
            dataset_pb2.DescribeResponse,
            self._call_describe,
        )

    def _call_describe(
        self, req: dataset_pb2.DescribeRequest
    ) -> dataset_pb2.DescribeResponse:
        info = self._adapter.describe(req.name, namespace=req.namespace)
        return dataset_pb2.DescribeResponse(info=_dataset_info_to_pb(info))

    async def _handle_list(self, request: Request) -> None:
        await self._handle(
            request, dataset_pb2.ListRequest, dataset_pb2.ListResponse, self._call_list
        )

    def _call_list(self, req: dataset_pb2.ListRequest) -> dataset_pb2.ListResponse:
        namespace = req.namespace if req.HasField("namespace") else None
        infos = self._adapter.list(namespace=namespace)
        return dataset_pb2.ListResponse(
            datasets=dataset_pb2.DatasetInfoList(
                items=[_dataset_info_to_pb(info) for info in infos]
            )
        )

    async def _handle_write(self, request: Request) -> None:
        await self._handle(
            request,
            dataset_pb2.WriteRequest,
            dataset_pb2.WriteResponse,
            self._call_write,
        )

    def _call_write(self, req: dataset_pb2.WriteRequest) -> dataset_pb2.WriteResponse:
        snapshot_id = req.snapshot_id if req.HasField("snapshot_id") else None
        # A wire request that leaves ``mode`` unset decodes as the proto3
        # zero value (WRITE_MODE_UNSPECIFIED), not one of our three named
        # modes -- fall back to IDatasetPort.write's own default ("append")
        # so an unset mode behaves identically over NATS and in-process,
        # rather than a KeyError surfacing as an opaque INTERNAL error.
        mode = _PB_TO_WRITE_MODE.get(req.mode, "append")
        info = self._adapter.write(
            req.name,
            [_struct_to_row(row) for row in req.rows],
            namespace=req.namespace,
            mode=mode,
            snapshot_id=snapshot_id,
        )
        return dataset_pb2.WriteResponse(info=_dataset_info_to_pb(info))

    async def _handle_query(self, request: Request) -> None:
        await self._handle(
            request,
            dataset_pb2.QueryRequest,
            dataset_pb2.QueryResponse,
            self._call_query,
        )

    def _call_query(self, req: dataset_pb2.QueryRequest) -> dataset_pb2.QueryResponse:
        snapshot_id = req.snapshot_id if req.HasField("snapshot_id") else None
        result = self._adapter.query(
            req.sql, namespace=req.namespace, snapshot_id=snapshot_id
        )
        return dataset_pb2.QueryResponse(query_result=_query_result_to_pb(result))

    async def _handle_flush(self, request: Request) -> None:
        await self._handle(
            request,
            dataset_pb2.FlushRequest,
            dataset_pb2.FlushResponse,
            self._call_flush,
        )

    def _call_flush(self, req: dataset_pb2.FlushRequest) -> dataset_pb2.FlushResponse:
        result = self._adapter.flush(req.name, namespace=req.namespace)
        return dataset_pb2.FlushResponse(query_result=_query_result_to_pb(result))

    async def _handle_inlined_row_count(self, request: Request) -> None:
        await self._handle(
            request,
            dataset_pb2.InlinedRowCountRequest,
            dataset_pb2.InlinedRowCountResponse,
            self._call_inlined_row_count,
        )

    def _call_inlined_row_count(
        self, req: dataset_pb2.InlinedRowCountRequest
    ) -> dataset_pb2.InlinedRowCountResponse:
        count = self._adapter.inlined_row_count(req.name, namespace=req.namespace)
        return dataset_pb2.InlinedRowCountResponse(count=count)

    async def _handle_compact(self, request: Request) -> None:
        await self._handle(
            request,
            dataset_pb2.CompactRequest,
            dataset_pb2.CompactResponse,
            self._call_compact,
        )

    def _call_compact(
        self, req: dataset_pb2.CompactRequest
    ) -> dataset_pb2.CompactResponse:
        result = self._adapter.compact(req.name, namespace=req.namespace)
        return dataset_pb2.CompactResponse(query_result=_query_result_to_pb(result))

    async def _handle_list_snapshots(self, request: Request) -> None:
        await self._handle(
            request,
            dataset_pb2.ListSnapshotsRequest,
            dataset_pb2.ListSnapshotsResponse,
            self._call_list_snapshots,
        )

    def _call_list_snapshots(
        self, req: dataset_pb2.ListSnapshotsRequest
    ) -> dataset_pb2.ListSnapshotsResponse:
        snapshots = self._adapter.list_snapshots()
        return dataset_pb2.ListSnapshotsResponse(
            snapshots=dataset_pb2.DatasetSnapshotInfoList(
                items=[_dataset_snapshot_info_to_pb(snapshot) for snapshot in snapshots]
            )
        )

    async def _handle_drop(self, request: Request) -> None:
        await self._handle(
            request, dataset_pb2.DropRequest, dataset_pb2.DropResponse, self._call_drop
        )

    def _call_drop(self, req: dataset_pb2.DropRequest) -> dataset_pb2.DropResponse:
        self._adapter.drop(req.name, namespace=req.namespace)
        return dataset_pb2.DropResponse()
