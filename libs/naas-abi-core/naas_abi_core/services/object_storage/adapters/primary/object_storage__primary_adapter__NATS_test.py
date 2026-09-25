"""Unit tests for ObjectStoragePrimaryAdapterNATS's auth/dispatch/error-mapping.

None of these need a real NATS server: each handler is invoked directly
against a minimal fake ``Request`` that records whatever gets passed to
``respond``, matching the "test the handler logic directly" option called
out for this adapter.
"""

import asyncio
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from queue import Queue
from typing import BinaryIO

from naas_abi_core.engine.nats_auth import issue_service_token
from naas_abi_core.proto.object_storage.v1 import object_storage_pb2
from naas_abi_core.services.object_storage.adapters.primary.object_storage__primary_adapter__NATS import (
    AUTH_HEADER,
    ObjectStoragePrimaryAdapterNATS,
)
from naas_abi_core.services.object_storage.ObjectStoragePort import (
    Exceptions,
    IObjectStorageAdapter,
    ObjectMetaData,
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
        subject: str = "abi.svc.object_storage.v1.get_object",
    ) -> None:
        self.data = data
        self.headers = headers
        self.subject = subject
        self.responses: list[bytes] = []

    async def respond(
        self, data: bytes = b"", headers: dict[str, str] | None = None
    ) -> None:
        self.responses.append(data)


class _StubAdapter(IObjectStorageAdapter):
    """Minimal in-memory IObjectStorageAdapter for driving the handlers."""

    def __init__(self) -> None:
        self.objects: dict[tuple[str, str], bytes] = {}

    def get_object(self, prefix: str, key: str) -> bytes:
        try:
            return self.objects[(prefix, key)]
        except KeyError:
            raise Exceptions.ObjectNotFound(f"{prefix}/{key} not found") from None

    @contextmanager
    def get_object_stream(self, prefix: str, key: str) -> Iterator[BinaryIO]:
        raise NotImplementedError
        yield  # pragma: no cover - unreachable

    def put_object(self, prefix: str, key: str, content: bytes) -> None:
        self.objects[(prefix, key)] = content

    def put_object_stream(self, prefix: str, key: str, stream: BinaryIO) -> None:
        raise NotImplementedError

    def delete_object(self, prefix: str, key: str) -> None:
        try:
            del self.objects[(prefix, key)]
        except KeyError:
            raise Exceptions.ObjectNotFound(f"{prefix}/{key} not found") from None

    def list_objects(self, prefix: str, queue: Queue | None = None) -> list[str]:
        return [k for (p, k) in self.objects if p == prefix]

    def list_objects_recursive(
        self, prefix: str, queue: Queue | None = None
    ) -> list[str]:
        return self.list_objects(prefix, queue)

    def get_object_metadata(self, prefix: str, key: str) -> ObjectMetaData:
        raise NotImplementedError


def _valid_token() -> str:
    return issue_service_token("api", SECRET)


def _get_object_request(prefix: str = "p", key: str = "k") -> bytes:
    return object_storage_pb2.GetObjectRequest(
        prefix=prefix, key=key
    ).SerializeToString()


# ---------------------------------------------------------------------------
# Auth.
# ---------------------------------------------------------------------------


def test_missing_token_returns_unauthenticated():
    adapter = ObjectStoragePrimaryAdapterNATS(_StubAdapter(), SECRET)
    request = _FakeRequest(data=_get_object_request(), headers=None)

    asyncio.run(adapter._handle_get_object(request))

    response = object_storage_pb2.GetObjectResponse()
    response.ParseFromString(request.responses[0])
    assert response.HasField("error")
    assert response.error.code == "UNAUTHENTICATED"
    assert response.error.retryable is False


def test_empty_token_header_returns_unauthenticated():
    adapter = ObjectStoragePrimaryAdapterNATS(_StubAdapter(), SECRET)
    request = _FakeRequest(data=_get_object_request(), headers={AUTH_HEADER: ""})

    asyncio.run(adapter._handle_get_object(request))

    response = object_storage_pb2.GetObjectResponse()
    response.ParseFromString(request.responses[0])
    assert response.error.code == "UNAUTHENTICATED"


def test_malformed_token_returns_unauthenticated():
    adapter = ObjectStoragePrimaryAdapterNATS(_StubAdapter(), SECRET)
    request = _FakeRequest(
        data=_get_object_request(), headers={AUTH_HEADER: "not-a-jwt"}
    )

    asyncio.run(adapter._handle_get_object(request))

    response = object_storage_pb2.GetObjectResponse()
    response.ParseFromString(request.responses[0])
    assert response.error.code == "UNAUTHENTICATED"


def test_token_signed_with_wrong_secret_returns_unauthenticated():
    adapter = ObjectStoragePrimaryAdapterNATS(_StubAdapter(), SECRET)
    wrong_secret_token = issue_service_token("api", "a-different-secret")
    request = _FakeRequest(
        data=_get_object_request(), headers={AUTH_HEADER: wrong_secret_token}
    )

    asyncio.run(adapter._handle_get_object(request))

    response = object_storage_pb2.GetObjectResponse()
    response.ParseFromString(request.responses[0])
    assert response.error.code == "UNAUTHENTICATED"


# ---------------------------------------------------------------------------
# Happy path + business error mapping.
# ---------------------------------------------------------------------


def test_successful_get_object_returns_content_with_no_error():
    stub = _StubAdapter()
    stub.put_object("p", "k", b"hello")
    adapter = ObjectStoragePrimaryAdapterNATS(stub, SECRET)
    request = _FakeRequest(
        data=_get_object_request("p", "k"), headers={AUTH_HEADER: _valid_token()}
    )

    asyncio.run(adapter._handle_get_object(request))

    response = object_storage_pb2.GetObjectResponse()
    response.ParseFromString(request.responses[0])
    assert not response.HasField("error")
    assert response.content == b"hello"


def test_object_not_found_maps_to_call_error():
    adapter = ObjectStoragePrimaryAdapterNATS(_StubAdapter(), SECRET)
    request = _FakeRequest(
        data=_get_object_request("missing", "k"),
        headers={AUTH_HEADER: _valid_token()},
    )

    asyncio.run(adapter._handle_get_object(request))

    response = object_storage_pb2.GetObjectResponse()
    response.ParseFromString(request.responses[0])
    assert response.error.code == "OBJECT_NOT_FOUND"
    assert response.error.retryable is False


def test_object_already_exists_maps_to_call_error():
    class _ExistsAdapter(_StubAdapter):
        def put_object(self, prefix: str, key: str, content: bytes) -> None:
            raise Exceptions.ObjectAlreadyExists(f"{prefix}/{key} already exists")

    adapter = ObjectStoragePrimaryAdapterNATS(_ExistsAdapter(), SECRET)
    request = _FakeRequest(
        data=object_storage_pb2.PutObjectRequest(
            prefix="p", key="k", content=b"x"
        ).SerializeToString(),
        headers={AUTH_HEADER: _valid_token()},
        subject="abi.svc.object_storage.v1.put_object",
    )

    asyncio.run(adapter._handle_put_object(request))

    response = object_storage_pb2.PutObjectResponse()
    response.ParseFromString(request.responses[0])
    assert response.error.code == "OBJECT_ALREADY_EXISTS"
    assert response.error.retryable is False


def test_unexpected_exception_maps_to_internal_and_does_not_leak_message():
    class _BoomAdapter(_StubAdapter):
        def get_object(self, prefix: str, key: str) -> bytes:
            raise RuntimeError("some sensitive internal detail")

    adapter = ObjectStoragePrimaryAdapterNATS(_BoomAdapter(), SECRET)
    request = _FakeRequest(
        data=_get_object_request(), headers={AUTH_HEADER: _valid_token()}
    )

    asyncio.run(adapter._handle_get_object(request))

    response = object_storage_pb2.GetObjectResponse()
    response.ParseFromString(request.responses[0])
    assert response.error.code == "INTERNAL"
    assert response.error.retryable is True
    assert "sensitive internal detail" not in response.error.message


def test_list_objects_round_trips_keys():
    stub = _StubAdapter()
    stub.put_object("p", "a", b"1")
    stub.put_object("p", "b", b"2")
    adapter = ObjectStoragePrimaryAdapterNATS(stub, SECRET)
    request = _FakeRequest(
        data=object_storage_pb2.ListObjectsRequest(prefix="p").SerializeToString(),
        headers={AUTH_HEADER: _valid_token()},
        subject="abi.svc.object_storage.v1.list_objects",
    )

    asyncio.run(adapter._handle_list_objects(request))

    response = object_storage_pb2.ListObjectsResponse()
    response.ParseFromString(request.responses[0])
    assert not response.HasField("error")
    assert sorted(response.keys.keys) == ["a", "b"]


# ---------------------------------------------------------------------------
# Lifecycle no-ops.
# ---------------------------------------------------------------------


def test_stop_without_start_is_a_noop():
    adapter = ObjectStoragePrimaryAdapterNATS(_StubAdapter(), SECRET)
    asyncio.run(adapter.stop())  # must not raise


def test_streaming_methods_are_exposed_via_transfer_contract():
    adapter = ObjectStoragePrimaryAdapterNATS(_StubAdapter(), SECRET)
    assert adapter._transfer.operations == {"get", "put"}
    assert adapter._transfer.handler == adapter._transfer_frames


def test_domain_call_runs_off_the_event_loop_so_the_loop_stays_responsive():
    """The adapter port is synchronous and may block for seconds (S3 round
    trip, a slow Fuseki query on the triple_store twin of this class, ...).
    All primaries share ONE event loop (``nats_runtime``) and ONE connection,
    so running the call inline would freeze every other endpoint of every
    service in the process, plus nats-py's own PING/PONG handling.

    Scenario: a handler whose domain call parks on a threading.Event. If the
    call ran on the loop thread, the coroutine below that releases it could
    never be scheduled and the call would time out; with the call on a
    worker thread the loop keeps turning, releases it, and the reply is the
    real content.
    """
    entered = threading.Event()
    release = threading.Event()
    call_threads: list[threading.Thread] = []

    class _SlowAdapter(_StubAdapter):
        def get_object(self, prefix: str, key: str) -> bytes:
            call_threads.append(threading.current_thread())
            entered.set()
            if not release.wait(timeout=2.0):
                raise TimeoutError("event loop never got to release the call")
            return b"slow-but-served"

    adapter = ObjectStoragePrimaryAdapterNATS(_SlowAdapter(), SECRET)
    request = _FakeRequest(
        data=_get_object_request("p", "k"), headers={AUTH_HEADER: _valid_token()}
    )

    async def scenario() -> threading.Thread:
        loop_thread = threading.current_thread()
        handler = asyncio.create_task(adapter._handle_get_object(request))
        # Only runs if the loop is free while the domain call is in flight.
        for _ in range(500):
            if entered.is_set():
                break
            await asyncio.sleep(0.01)
        release.set()
        await asyncio.wait_for(handler, timeout=5.0)
        return loop_thread

    loop_thread = asyncio.run(scenario())

    response = object_storage_pb2.GetObjectResponse()
    response.ParseFromString(request.responses[0])
    assert not response.HasField("error"), response.error
    assert response.content == b"slow-but-served"
    assert call_threads and call_threads[0] is not loop_thread
