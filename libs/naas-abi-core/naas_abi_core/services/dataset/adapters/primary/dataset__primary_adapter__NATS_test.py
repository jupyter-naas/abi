"""Unit tests for DatasetPrimaryAdapterNATS's auth/dispatch/error-mapping.

None of these need a real NATS server: each handler is invoked directly
against a minimal fake ``Request`` that records whatever gets passed to
``respond``, matching the "test the handler logic directly" option used by
``object_storage__primary_adapter__NATS_test.py``.
"""

import asyncio

# ``list`` is a port method name, so it shadows the builtin for annotations
# evaluated in _StubAdapter's class body below (methods after ``list``);
# use ``builtins.list`` there -- same workaround as DatasetPort.py/DatasetService.py.
import builtins
from datetime import UTC, datetime
from typing import Any

from naas_abi_core.engine.nats_auth import issue_service_token
from naas_abi_core.proto.dataset.v1 import dataset_pb2
from naas_abi_core.services.dataset.adapters.primary.dataset__primary_adapter__NATS import (
    AUTH_HEADER,
    DatasetPrimaryAdapterNATS,
)
from naas_abi_core.services.dataset.DatasetPort import (
    DatasetAlreadyExistsError,
    DatasetInfo,
    DatasetNotFoundError,
    DatasetSchemaError,
    DatasetSnapshotConflictError,
    DatasetSnapshotInfo,
    DatasetSnapshotNotFoundError,
    DatasetSpec,
    IDatasetPort,
    QueryResult,
    WriteMode,
)

SECRET = "test-shared-secret"


class _FakeRequest:
    """Stands in for nats.micro.request.Request: same ``.data``/``.headers``
    surface, and ``respond`` just records the payload instead of publishing
    it anywhere."""

    def __init__(
        self,
        data: bytes,
        headers: dict[str, str] | None = None,
        subject: str = "abi.svc.dataset.v1.describe",
    ) -> None:
        self.data = data
        self.headers = headers
        self.subject = subject
        self.responses: list[bytes] = []

    async def respond(
        self, data: bytes = b"", headers: dict[str, str] | None = None
    ) -> None:
        self.responses.append(data)


class _StubAdapter(IDatasetPort):
    """Minimal in-memory IDatasetPort for driving the handlers."""

    def __init__(self) -> None:
        self.datasets: dict[tuple[str, str], DatasetInfo] = {}
        self._counter = 0

    def _next_snapshot_id(self) -> int:
        self._counter += 1
        return self._counter

    def create(self, spec: DatasetSpec) -> DatasetInfo:
        key = (spec.namespace, spec.name)
        if key in self.datasets:
            raise DatasetAlreadyExistsError(spec.name, spec.namespace)
        info = DatasetInfo(
            name=spec.name,
            namespace=spec.namespace,
            columns=spec.columns,
            partitions=spec.partitions,
            primary_key=spec.primary_key,
            snapshot_id=self._next_snapshot_id(),
            location=f"mem://{spec.namespace}/{spec.name}",
        )
        self.datasets[key] = info
        return info

    def describe(self, name: str, *, namespace: str = "default") -> DatasetInfo:
        key = (namespace, name)
        if key not in self.datasets:
            raise DatasetNotFoundError(name, namespace)
        return self.datasets[key]

    def list(self, *, namespace: str | None = None) -> list[DatasetInfo]:
        return [
            info
            for (ns, _name), info in self.datasets.items()
            if namespace is None or ns == namespace
        ]

    def write(
        self,
        name: str,
        rows: builtins.list[dict[str, Any]],
        *,
        namespace: str = "default",
        mode: WriteMode = "append",
        snapshot_id: int | None = None,
    ) -> DatasetInfo:
        key = (namespace, name)
        if key not in self.datasets:
            raise DatasetNotFoundError(name, namespace)
        current = self.datasets[key]
        if snapshot_id is not None and snapshot_id != current.snapshot_id:
            raise DatasetSnapshotConflictError(snapshot_id, current.snapshot_id)
        updated = current.model_copy(update={"snapshot_id": self._next_snapshot_id()})
        self.datasets[key] = updated
        return updated

    def query(
        self, sql: str, *, namespace: str = "default", snapshot_id: int | None = None
    ) -> QueryResult:
        return QueryResult(columns=["answer"], rows=[{"answer": 42}])

    def flush(self, name: str, *, namespace: str = "default") -> QueryResult:
        return QueryResult(columns=[], rows=[])

    def inlined_row_count(self, name: str, *, namespace: str = "default") -> int:
        return 7

    def compact(self, name: str, *, namespace: str = "default") -> QueryResult:
        return QueryResult(columns=[], rows=[])

    def list_snapshots(self) -> builtins.list[DatasetSnapshotInfo]:
        return [
            DatasetSnapshotInfo(snapshot_id=info.snapshot_id, created_at=datetime.now(UTC))
            for info in self.datasets.values()
        ]

    def drop(self, name: str, *, namespace: str = "default") -> None:
        key = (namespace, name)
        if key not in self.datasets:
            raise DatasetNotFoundError(name, namespace)
        del self.datasets[key]


def _valid_token() -> str:
    return issue_service_token("api", SECRET)


def _describe_request(name: str = "n", namespace: str = "default") -> bytes:
    return dataset_pb2.DescribeRequest(
        name=name, namespace=namespace
    ).SerializeToString()


# ---------------------------------------------------------------------------
# Auth.
# ---------------------------------------------------------------------------


def test_missing_token_returns_unauthenticated():
    adapter = DatasetPrimaryAdapterNATS(_StubAdapter(), SECRET)
    request = _FakeRequest(data=_describe_request(), headers=None)

    asyncio.run(adapter._handle_describe(request))

    response = dataset_pb2.DescribeResponse()
    response.ParseFromString(request.responses[0])
    assert response.HasField("error")
    assert response.error.error.code == "UNAUTHENTICATED"
    assert response.error.error.retryable is False


def test_empty_token_header_returns_unauthenticated():
    adapter = DatasetPrimaryAdapterNATS(_StubAdapter(), SECRET)
    request = _FakeRequest(data=_describe_request(), headers={AUTH_HEADER: ""})

    asyncio.run(adapter._handle_describe(request))

    response = dataset_pb2.DescribeResponse()
    response.ParseFromString(request.responses[0])
    assert response.error.error.code == "UNAUTHENTICATED"


def test_malformed_token_returns_unauthenticated():
    adapter = DatasetPrimaryAdapterNATS(_StubAdapter(), SECRET)
    request = _FakeRequest(data=_describe_request(), headers={AUTH_HEADER: "not-a-jwt"})

    asyncio.run(adapter._handle_describe(request))

    response = dataset_pb2.DescribeResponse()
    response.ParseFromString(request.responses[0])
    assert response.error.error.code == "UNAUTHENTICATED"


def test_token_signed_with_wrong_secret_returns_unauthenticated():
    adapter = DatasetPrimaryAdapterNATS(_StubAdapter(), SECRET)
    wrong_secret_token = issue_service_token("api", "a-different-secret")
    request = _FakeRequest(
        data=_describe_request(), headers={AUTH_HEADER: wrong_secret_token}
    )

    asyncio.run(adapter._handle_describe(request))

    response = dataset_pb2.DescribeResponse()
    response.ParseFromString(request.responses[0])
    assert response.error.error.code == "UNAUTHENTICATED"


# ---------------------------------------------------------------------------
# Happy path + business error mapping.
# ---------------------------------------------------------------------


def test_successful_create_returns_info_with_no_error():
    adapter = DatasetPrimaryAdapterNATS(_StubAdapter(), SECRET)
    spec = dataset_pb2.DatasetSpec(
        name="events",
        namespace="acme",
        columns=[dataset_pb2.ColumnSpec(name="id", type=dataset_pb2.COLUMN_TYPE_STRING)],
    )
    request = _FakeRequest(
        data=dataset_pb2.CreateRequest(spec=spec).SerializeToString(),
        headers={AUTH_HEADER: _valid_token()},
        subject="abi.svc.dataset.v1.create",
    )

    asyncio.run(adapter._handle_create(request))

    response = dataset_pb2.CreateResponse()
    response.ParseFromString(request.responses[0])
    assert not response.HasField("error")
    assert response.info.name == "events"
    assert response.info.namespace == "acme"
    assert response.info.columns[0].name == "id"
    assert response.info.columns[0].type == dataset_pb2.COLUMN_TYPE_STRING


def test_dataset_not_found_maps_to_call_error_with_detail():
    adapter = DatasetPrimaryAdapterNATS(_StubAdapter(), SECRET)
    request = _FakeRequest(
        data=_describe_request("missing", "acme"),
        headers={AUTH_HEADER: _valid_token()},
    )

    asyncio.run(adapter._handle_describe(request))

    response = dataset_pb2.DescribeResponse()
    response.ParseFromString(request.responses[0])
    assert response.error.error.code == "DATASET_NOT_FOUND"
    assert response.error.error.retryable is False
    assert response.error.WhichOneof("detail") == "not_found"
    assert response.error.not_found.name == "missing"
    assert response.error.not_found.namespace == "acme"


def test_dataset_already_exists_maps_to_call_error_with_detail():
    stub = _StubAdapter()
    stub.create(DatasetSpec(name="events", namespace="acme", columns=()))
    adapter = DatasetPrimaryAdapterNATS(stub, SECRET)
    request = _FakeRequest(
        data=dataset_pb2.CreateRequest(
            spec=dataset_pb2.DatasetSpec(name="events", namespace="acme")
        ).SerializeToString(),
        headers={AUTH_HEADER: _valid_token()},
        subject="abi.svc.dataset.v1.create",
    )

    asyncio.run(adapter._handle_create(request))

    response = dataset_pb2.CreateResponse()
    response.ParseFromString(request.responses[0])
    assert response.error.error.code == "DATASET_ALREADY_EXISTS"
    assert response.error.error.retryable is False
    assert response.error.WhichOneof("detail") == "already_exists"
    assert response.error.already_exists.name == "events"
    assert response.error.already_exists.namespace == "acme"


def test_dataset_schema_error_maps_to_call_error_without_detail():
    class _SchemaErrorAdapter(_StubAdapter):
        def write(self, name, rows, *, namespace="default", mode="append", snapshot_id=None):
            raise DatasetSchemaError("rows are not valid JSON")

    adapter = DatasetPrimaryAdapterNATS(_SchemaErrorAdapter(), SECRET)
    request = _FakeRequest(
        data=dataset_pb2.WriteRequest(name="events", namespace="acme").SerializeToString(),
        headers={AUTH_HEADER: _valid_token()},
        subject="abi.svc.dataset.v1.write",
    )

    asyncio.run(adapter._handle_write(request))

    response = dataset_pb2.WriteResponse()
    response.ParseFromString(request.responses[0])
    assert response.error.error.code == "DATASET_SCHEMA_ERROR"
    assert response.error.error.retryable is False
    assert response.error.WhichOneof("detail") is None


def test_dataset_snapshot_not_found_maps_to_call_error_with_detail():
    class _SnapshotMissingAdapter(_StubAdapter):
        def query(self, sql, *, namespace="default", snapshot_id=None):
            raise DatasetSnapshotNotFoundError(99)

    adapter = DatasetPrimaryAdapterNATS(_SnapshotMissingAdapter(), SECRET)
    request = _FakeRequest(
        data=dataset_pb2.QueryRequest(sql="SELECT 1", namespace="acme").SerializeToString(),
        headers={AUTH_HEADER: _valid_token()},
        subject="abi.svc.dataset.v1.query",
    )

    asyncio.run(adapter._handle_query(request))

    response = dataset_pb2.QueryResponse()
    response.ParseFromString(request.responses[0])
    assert response.error.error.code == "DATASET_SNAPSHOT_NOT_FOUND"
    assert response.error.error.retryable is False
    assert response.error.WhichOneof("detail") == "snapshot_not_found"
    assert response.error.snapshot_not_found.snapshot_id == 99


def test_dataset_snapshot_conflict_maps_to_call_error_with_detail():
    stub = _StubAdapter()
    stub.create(DatasetSpec(name="events", namespace="acme", columns=()))
    adapter = DatasetPrimaryAdapterNATS(stub, SECRET)
    request = _FakeRequest(
        data=dataset_pb2.WriteRequest(
            name="events", namespace="acme", snapshot_id=999
        ).SerializeToString(),
        headers={AUTH_HEADER: _valid_token()},
        subject="abi.svc.dataset.v1.write",
    )

    asyncio.run(adapter._handle_write(request))

    response = dataset_pb2.WriteResponse()
    response.ParseFromString(request.responses[0])
    assert response.error.error.code == "DATASET_SNAPSHOT_CONFLICT"
    assert response.error.error.retryable is False
    assert response.error.WhichOneof("detail") == "snapshot_conflict"
    assert response.error.snapshot_conflict.expected_snapshot_id == 999
    assert response.error.snapshot_conflict.current_snapshot_id == 1


def test_unexpected_exception_maps_to_internal_and_does_not_leak_message():
    class _BoomAdapter(_StubAdapter):
        def describe(self, name, *, namespace="default"):
            raise RuntimeError("some sensitive internal detail")

    adapter = DatasetPrimaryAdapterNATS(_BoomAdapter(), SECRET)
    request = _FakeRequest(
        data=_describe_request(), headers={AUTH_HEADER: _valid_token()}
    )

    asyncio.run(adapter._handle_describe(request))

    response = dataset_pb2.DescribeResponse()
    response.ParseFromString(request.responses[0])
    assert response.error.error.code == "INTERNAL"
    assert response.error.error.retryable is True
    assert response.error.WhichOneof("detail") is None
    assert "sensitive internal detail" not in response.error.error.message


# ---------------------------------------------------------------------------
# Round trips (also exercises the Struct-based row encoding).
# ---------------------------------------------------------------------


def test_list_round_trips_datasets():
    stub = _StubAdapter()
    stub.create(DatasetSpec(name="a", namespace="acme", columns=()))
    stub.create(DatasetSpec(name="b", namespace="acme", columns=()))
    adapter = DatasetPrimaryAdapterNATS(stub, SECRET)
    request = _FakeRequest(
        data=dataset_pb2.ListRequest(namespace="acme").SerializeToString(),
        headers={AUTH_HEADER: _valid_token()},
        subject="abi.svc.dataset.v1.list",
    )

    asyncio.run(adapter._handle_list(request))

    response = dataset_pb2.ListResponse()
    response.ParseFromString(request.responses[0])
    assert not response.HasField("error")
    assert sorted(item.name for item in response.datasets.items) == ["a", "b"]


def test_query_round_trips_rows_via_struct():
    adapter = DatasetPrimaryAdapterNATS(_StubAdapter(), SECRET)
    request = _FakeRequest(
        data=dataset_pb2.QueryRequest(
            sql="SELECT 42 AS answer", namespace="acme"
        ).SerializeToString(),
        headers={AUTH_HEADER: _valid_token()},
        subject="abi.svc.dataset.v1.query",
    )

    asyncio.run(adapter._handle_query(request))

    response = dataset_pb2.QueryResponse()
    response.ParseFromString(request.responses[0])
    assert not response.HasField("error")
    assert list(response.query_result.columns) == ["answer"]
    assert len(response.query_result.rows) == 1
    assert response.query_result.rows[0]["answer"] == 42


# ---------------------------------------------------------------------------
# Lifecycle no-ops.
# ---------------------------------------------------------------------


def test_stop_without_start_is_a_noop():
    adapter = DatasetPrimaryAdapterNATS(_StubAdapter(), SECRET)
    asyncio.run(adapter.stop())  # must not raise
