"""Unit tests for EventPrimaryAdapterNATS's auth/dispatch/error-mapping.

None of these need a real NATS server: each handler is invoked directly
against a minimal fake ``Request`` that records whatever gets passed to
``respond``, matching the "test the handler logic directly" option called
out for this adapter.
"""

import asyncio

import pytest

from naas_abi_core.engine.nats_auth import issue_service_token
from naas_abi_core.proto.event.v1 import event_pb2
from naas_abi_core.services.event.adapters.primary.event__primary_adapter__NATS import (
    AUTH_HEADER,
    EventPrimaryAdapterNATS,
)
from naas_abi_core.services.event.EventPort import (
    EventNotFoundError,
    IEventAdapter,
    InvalidEventError,
    StoredEvent,
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
        subject: str = "abi.svc.event.v1.append",
    ) -> None:
        self.data = data
        self.headers = headers
        self.subject = subject
        self.responses: list[bytes] = []

    async def respond(
        self, data: bytes = b"", headers: dict[str, str] | None = None
    ) -> None:
        self.responses.append(data)


class _StubAdapter(IEventAdapter):
    """Minimal in-memory IEventAdapter for driving the handlers."""

    def __init__(self) -> None:
        self.events: list[StoredEvent] = []
        self.cursors: dict[tuple[str, str], int] = {}

    def append(
        self, event_id: str, event_type: str, timestamp: str, payload: bytes
    ) -> StoredEvent:
        stored = StoredEvent(
            id=event_id,
            event_type=event_type,
            seq=len(self.events) + 1,
            timestamp=timestamp,
            payload=payload,
        )
        self.events.append(stored)
        return stored

    def query(
        self,
        event_type: str | None = None,
        since_seq: int | None = None,
        until_seq: int | None = None,
        since_timestamp: str | None = None,
        until_timestamp: str | None = None,
        json_filter: dict | None = None,
        limit: int | None = None,
        newest_first: bool = False,
        search: str | None = None,
    ) -> list[StoredEvent]:
        rows = [e for e in self.events if event_type is None or e.event_type == event_type]
        if since_seq is not None:
            rows = [e for e in rows if e.seq > since_seq]
        if until_seq is not None:
            rows = [e for e in rows if e.seq <= until_seq]
        rows = sorted(rows, key=lambda e: e.seq, reverse=newest_first)
        if limit is not None:
            rows = rows[:limit]
        return rows

    def max_seq(self, event_type: str | None = None) -> int:
        rows = [e for e in self.events if event_type is None or e.event_type == event_type]
        return max((e.seq for e in rows), default=0)

    def get_cursor(self, consumer_id: str, event_type: str) -> int:
        return self.cursors.get((consumer_id, event_type), 0)

    def set_cursor(self, consumer_id: str, event_type: str, last_seq: int) -> None:
        self.cursors[(consumer_id, event_type)] = last_seq

    def query_for_consumer(
        self,
        consumer_id: str,
        event_type: str,
        limit: int | None = None,
        json_filter: dict | None = None,
    ) -> list[StoredEvent]:
        cursor = self.get_cursor(consumer_id, event_type)
        rows = self.query(event_type=event_type, since_seq=cursor, limit=limit)
        if rows:
            self.set_cursor(consumer_id, event_type, rows[-1].seq)
        return rows


def _valid_token() -> str:
    return issue_service_token("api", SECRET)


def _append_request(
    event_id: str = "evt-1", event_type: str = "t", timestamp: str = "2020-01-01T00:00:00Z"
) -> bytes:
    return event_pb2.AppendRequest(
        event_id=event_id, event_type=event_type, timestamp=timestamp, payload=b"x"
    ).SerializeToString()


# ---------------------------------------------------------------------------
# Auth.
# ---------------------------------------------------------------------------


def test_missing_token_returns_unauthenticated():
    adapter = EventPrimaryAdapterNATS(_StubAdapter(), SECRET)
    request = _FakeRequest(data=_append_request(), headers=None)

    asyncio.run(adapter._handle_append(request))

    response = event_pb2.AppendResponse()
    response.ParseFromString(request.responses[0])
    assert response.HasField("error")
    assert response.error.code == "UNAUTHENTICATED"
    assert response.error.retryable is False


def test_empty_token_header_returns_unauthenticated():
    adapter = EventPrimaryAdapterNATS(_StubAdapter(), SECRET)
    request = _FakeRequest(data=_append_request(), headers={AUTH_HEADER: ""})

    asyncio.run(adapter._handle_append(request))

    response = event_pb2.AppendResponse()
    response.ParseFromString(request.responses[0])
    assert response.error.code == "UNAUTHENTICATED"


def test_malformed_token_returns_unauthenticated():
    adapter = EventPrimaryAdapterNATS(_StubAdapter(), SECRET)
    request = _FakeRequest(data=_append_request(), headers={AUTH_HEADER: "not-a-jwt"})

    asyncio.run(adapter._handle_append(request))

    response = event_pb2.AppendResponse()
    response.ParseFromString(request.responses[0])
    assert response.error.code == "UNAUTHENTICATED"


def test_token_signed_with_wrong_secret_returns_unauthenticated():
    adapter = EventPrimaryAdapterNATS(_StubAdapter(), SECRET)
    wrong_secret_token = issue_service_token("api", "a-different-secret")
    request = _FakeRequest(
        data=_append_request(), headers={AUTH_HEADER: wrong_secret_token}
    )

    asyncio.run(adapter._handle_append(request))

    response = event_pb2.AppendResponse()
    response.ParseFromString(request.responses[0])
    assert response.error.code == "UNAUTHENTICATED"


# ---------------------------------------------------------------------------
# Happy path -- one success test per IEventAdapter method.
# ---------------------------------------------------------------------


def test_successful_append_returns_stored_event_with_no_error():
    adapter = EventPrimaryAdapterNATS(_StubAdapter(), SECRET)
    request = _FakeRequest(
        data=_append_request("evt-1", "t", "2020-01-01T00:00:00Z"),
        headers={AUTH_HEADER: _valid_token()},
    )

    asyncio.run(adapter._handle_append(request))

    response = event_pb2.AppendResponse()
    response.ParseFromString(request.responses[0])
    assert not response.HasField("error")
    assert response.event.id == "evt-1"
    assert response.event.event_type == "t"
    assert response.event.seq == 1
    assert response.event.timestamp == "2020-01-01T00:00:00Z"
    assert response.event.payload == b"x"


def test_successful_query_round_trips_events():
    stub = _StubAdapter()
    stub.append("evt-1", "t", "2020-01-01T00:00:00Z", b"x")
    stub.append("evt-2", "t", "2020-01-02T00:00:00Z", b"y")
    adapter = EventPrimaryAdapterNATS(stub, SECRET)
    request = _FakeRequest(
        data=event_pb2.QueryRequest(event_type="t").SerializeToString(),
        headers={AUTH_HEADER: _valid_token()},
        subject="abi.svc.event.v1.query",
    )

    asyncio.run(adapter._handle_query(request))

    response = event_pb2.QueryResponse()
    response.ParseFromString(request.responses[0])
    assert not response.HasField("error")
    assert [e.id for e in response.events.events] == ["evt-1", "evt-2"]


def test_query_with_unset_optional_fields_passes_none_through():
    stub = _StubAdapter()
    stub.append("evt-1", "t", "2020-01-01T00:00:00Z", b"x")
    adapter = EventPrimaryAdapterNATS(stub, SECRET)
    request = _FakeRequest(
        data=event_pb2.QueryRequest().SerializeToString(),
        headers={AUTH_HEADER: _valid_token()},
        subject="abi.svc.event.v1.query",
    )

    asyncio.run(adapter._handle_query(request))

    response = event_pb2.QueryResponse()
    response.ParseFromString(request.responses[0])
    assert not response.HasField("error")
    assert [e.id for e in response.events.events] == ["evt-1"]


def test_successful_max_seq_returns_seq_with_no_error():
    stub = _StubAdapter()
    stub.append("evt-1", "t", "2020-01-01T00:00:00Z", b"x")
    stub.append("evt-2", "t", "2020-01-02T00:00:00Z", b"y")
    adapter = EventPrimaryAdapterNATS(stub, SECRET)
    request = _FakeRequest(
        data=event_pb2.MaxSeqRequest(event_type="t").SerializeToString(),
        headers={AUTH_HEADER: _valid_token()},
        subject="abi.svc.event.v1.max_seq",
    )

    asyncio.run(adapter._handle_max_seq(request))

    response = event_pb2.MaxSeqResponse()
    response.ParseFromString(request.responses[0])
    assert not response.HasField("error")
    assert response.seq == 2


def test_successful_get_cursor_returns_zero_when_unset():
    adapter = EventPrimaryAdapterNATS(_StubAdapter(), SECRET)
    request = _FakeRequest(
        data=event_pb2.GetCursorRequest(
            consumer_id="c1", event_type="t"
        ).SerializeToString(),
        headers={AUTH_HEADER: _valid_token()},
        subject="abi.svc.event.v1.get_cursor",
    )

    asyncio.run(adapter._handle_get_cursor(request))

    response = event_pb2.GetCursorResponse()
    response.ParseFromString(request.responses[0])
    assert not response.HasField("error")
    assert response.last_seq == 0


def test_successful_set_cursor_returns_empty_response_with_no_error():
    stub = _StubAdapter()
    adapter = EventPrimaryAdapterNATS(stub, SECRET)
    request = _FakeRequest(
        data=event_pb2.SetCursorRequest(
            consumer_id="c1", event_type="t", last_seq=5
        ).SerializeToString(),
        headers={AUTH_HEADER: _valid_token()},
        subject="abi.svc.event.v1.set_cursor",
    )

    asyncio.run(adapter._handle_set_cursor(request))

    response = event_pb2.SetCursorResponse()
    response.ParseFromString(request.responses[0])
    assert not response.HasField("error")
    assert stub.get_cursor("c1", "t") == 5


def test_successful_query_for_consumer_returns_events_and_advances_cursor():
    stub = _StubAdapter()
    stub.append("evt-1", "t", "2020-01-01T00:00:00Z", b"x")
    stub.append("evt-2", "t", "2020-01-02T00:00:00Z", b"y")
    adapter = EventPrimaryAdapterNATS(stub, SECRET)
    request = _FakeRequest(
        data=event_pb2.QueryForConsumerRequest(
            consumer_id="c1", event_type="t"
        ).SerializeToString(),
        headers={AUTH_HEADER: _valid_token()},
        subject="abi.svc.event.v1.query_for_consumer",
    )

    asyncio.run(adapter._handle_query_for_consumer(request))

    response = event_pb2.QueryForConsumerResponse()
    response.ParseFromString(request.responses[0])
    assert not response.HasField("error")
    assert [e.id for e in response.events.events] == ["evt-1", "evt-2"]
    assert stub.get_cursor("c1", "t") == 2


# ---------------------------------------------------------------------------
# Error mapping.
# ---------------------------------------------------------------------


def test_event_not_found_maps_to_call_error():
    class _NotFoundAdapter(_StubAdapter):
        def get_cursor(self, consumer_id: str, event_type: str) -> int:
            raise EventNotFoundError(f"{consumer_id}/{event_type} not found")

    adapter = EventPrimaryAdapterNATS(_NotFoundAdapter(), SECRET)
    request = _FakeRequest(
        data=event_pb2.GetCursorRequest(
            consumer_id="c1", event_type="t"
        ).SerializeToString(),
        headers={AUTH_HEADER: _valid_token()},
        subject="abi.svc.event.v1.get_cursor",
    )

    asyncio.run(adapter._handle_get_cursor(request))

    response = event_pb2.GetCursorResponse()
    response.ParseFromString(request.responses[0])
    assert response.error.code == "EVENT_NOT_FOUND"
    assert response.error.retryable is False


def test_invalid_event_maps_to_call_error():
    class _InvalidAdapter(_StubAdapter):
        def append(
            self, event_id: str, event_type: str, timestamp: str, payload: bytes
        ) -> StoredEvent:
            raise InvalidEventError("not a LogProcess instance")

    adapter = EventPrimaryAdapterNATS(_InvalidAdapter(), SECRET)
    request = _FakeRequest(
        data=_append_request(), headers={AUTH_HEADER: _valid_token()}
    )

    asyncio.run(adapter._handle_append(request))

    response = event_pb2.AppendResponse()
    response.ParseFromString(request.responses[0])
    assert response.error.code == "INVALID_EVENT"
    assert response.error.retryable is False


def test_unexpected_exception_maps_to_internal_and_does_not_leak_message():
    class _BoomAdapter(_StubAdapter):
        def append(
            self, event_id: str, event_type: str, timestamp: str, payload: bytes
        ) -> StoredEvent:
            raise RuntimeError("some sensitive internal detail")

    adapter = EventPrimaryAdapterNATS(_BoomAdapter(), SECRET)
    request = _FakeRequest(
        data=_append_request(), headers={AUTH_HEADER: _valid_token()}
    )

    asyncio.run(adapter._handle_append(request))

    response = event_pb2.AppendResponse()
    response.ParseFromString(request.responses[0])
    assert response.error.code == "INTERNAL"
    assert response.error.retryable is True
    assert "sensitive internal detail" not in response.error.message


# ---------------------------------------------------------------------------
# Lifecycle no-ops.
# ---------------------------------------------------------------------------


def test_stop_without_start_is_a_noop():
    adapter = EventPrimaryAdapterNATS(_StubAdapter(), SECRET)
    asyncio.run(adapter.stop())  # must not raise


@pytest.mark.parametrize(
    "method_name",
    ["publish", "subscribe", "iter_query", "iter_query_for_consumer", "seek_consumer_to_end"],
)
def test_stub_adapter_domain_only_methods_are_not_wired_to_any_endpoint(method_name):
    # Defence-in-depth check on the test double itself: the primary adapter
    # never registers an endpoint for anything outside IEventAdapter's six
    # methods (see the module docstring) -- those live on IEventService,
    # composed above this port, not on it.
    adapter = EventPrimaryAdapterNATS(_StubAdapter(), SECRET)
    assert not hasattr(adapter, f"_handle_{method_name}")
