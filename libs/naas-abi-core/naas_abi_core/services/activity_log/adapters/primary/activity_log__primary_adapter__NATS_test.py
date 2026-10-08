"""Unit tests for ActivityLogPrimaryAdapterNATS's auth/dispatch/error-mapping.

None of these need a real NATS server: each handler is invoked directly
against a minimal fake ``Request`` that records whatever gets passed to
``respond``, matching the "test the handler logic directly" option called
out for this adapter.
"""

import asyncio
from datetime import UTC, datetime

from naas_abi_core.engine.nats_auth import issue_service_token
from naas_abi_core.proto.activity_log.v1 import activity_log_pb2
from naas_abi_core.services.activity_log.ActivityLogPort import (
    ActivityEvent,
    ActivityLogQuery,
    IActivityLogAdapter,
)
from naas_abi_core.services.activity_log.adapters.primary.activity_log__primary_adapter__NATS import (
    AUTH_HEADER,
    ActivityLogPrimaryAdapterNATS,
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
        subject: str = "abi.svc.activity_log.v1.record",
    ) -> None:
        self.data = data
        self.headers = headers
        self.subject = subject
        self.responses: list[bytes] = []

    async def respond(
        self, data: bytes = b"", headers: dict[str, str] | None = None
    ) -> None:
        self.responses.append(data)


class _StubAdapter(IActivityLogAdapter):
    """Minimal in-memory IActivityLogAdapter for driving the handlers."""

    def __init__(self) -> None:
        self.events: dict[str, list[ActivityEvent]] = {}
        self.shutdown_called = False

    def record(self, event: ActivityEvent) -> None:
        self.events.setdefault(event.actor_id, []).append(event)

    def query(
        self, actor_id: str, query: ActivityLogQuery | None = None
    ) -> list[ActivityEvent]:
        events = self.events.get(actor_id, [])
        if query is not None and query.event_type is not None:
            events = [e for e in events if e.event_type == query.event_type]
        if query is not None and query.limit is not None:
            events = events[: query.limit]
        return events

    def list_actors(self) -> list[str]:
        return list(self.events.keys())

    def shutdown(self) -> None:
        self.shutdown_called = True


def _valid_token() -> str:
    return issue_service_token("api", SECRET)


def _record_request(actor_id: str = "user:1", event_type: str = "http.request") -> bytes:
    event = activity_log_pb2.ActivityEvent(actor_id=actor_id, event_type=event_type)
    event.timestamp.FromDatetime(datetime.now(UTC))
    return activity_log_pb2.RecordRequest(event=event).SerializeToString()


# ---------------------------------------------------------------------------
# Auth.
# ---------------------------------------------------------------------------


def test_missing_token_returns_unauthenticated():
    adapter = ActivityLogPrimaryAdapterNATS(_StubAdapter(), SECRET)
    request = _FakeRequest(data=_record_request(), headers=None)

    asyncio.run(adapter._handle_record(request))

    response = activity_log_pb2.RecordResponse()
    response.ParseFromString(request.responses[0])
    assert response.HasField("error")
    assert response.error.code == "UNAUTHENTICATED"
    assert response.error.retryable is False


def test_empty_token_header_returns_unauthenticated():
    adapter = ActivityLogPrimaryAdapterNATS(_StubAdapter(), SECRET)
    request = _FakeRequest(data=_record_request(), headers={AUTH_HEADER: ""})

    asyncio.run(adapter._handle_record(request))

    response = activity_log_pb2.RecordResponse()
    response.ParseFromString(request.responses[0])
    assert response.error.code == "UNAUTHENTICATED"


def test_malformed_token_returns_unauthenticated():
    adapter = ActivityLogPrimaryAdapterNATS(_StubAdapter(), SECRET)
    request = _FakeRequest(data=_record_request(), headers={AUTH_HEADER: "not-a-jwt"})

    asyncio.run(adapter._handle_record(request))

    response = activity_log_pb2.RecordResponse()
    response.ParseFromString(request.responses[0])
    assert response.error.code == "UNAUTHENTICATED"


def test_token_signed_with_wrong_secret_returns_unauthenticated():
    adapter = ActivityLogPrimaryAdapterNATS(_StubAdapter(), SECRET)
    wrong_secret_token = issue_service_token("api", "a-different-secret")
    request = _FakeRequest(
        data=_record_request(), headers={AUTH_HEADER: wrong_secret_token}
    )

    asyncio.run(adapter._handle_record(request))

    response = activity_log_pb2.RecordResponse()
    response.ParseFromString(request.responses[0])
    assert response.error.code == "UNAUTHENTICATED"


# ---------------------------------------------------------------------------
# Happy path.
# ---------------------------------------------------------------------


def test_successful_record_returns_no_error():
    stub = _StubAdapter()
    adapter = ActivityLogPrimaryAdapterNATS(stub, SECRET)
    request = _FakeRequest(
        data=_record_request("user:1", "http.request"),
        headers={AUTH_HEADER: _valid_token()},
    )

    asyncio.run(adapter._handle_record(request))

    response = activity_log_pb2.RecordResponse()
    response.ParseFromString(request.responses[0])
    assert not response.HasField("error")
    assert len(stub.events["user:1"]) == 1
    assert stub.events["user:1"][0].event_type == "http.request"


def test_record_round_trips_attributes_and_correlation_id():
    stub = _StubAdapter()
    adapter = ActivityLogPrimaryAdapterNATS(stub, SECRET)
    event = activity_log_pb2.ActivityEvent(actor_id="user:1", event_type="x")
    event.timestamp.FromDatetime(datetime.now(UTC))
    event.correlation_id = "req-1"
    event.attributes.update({"method": "GET", "status": 200})
    request = _FakeRequest(
        data=activity_log_pb2.RecordRequest(event=event).SerializeToString(),
        headers={AUTH_HEADER: _valid_token()},
    )

    asyncio.run(adapter._handle_record(request))

    stored = stub.events["user:1"][0]
    assert stored.correlation_id == "req-1"
    assert stored.attributes == {"method": "GET", "status": 200}


def test_query_round_trips_events():
    stub = _StubAdapter()
    stub.record(ActivityEvent(actor_id="user:1", event_type="http.request"))
    stub.record(ActivityEvent(actor_id="user:1", event_type="http.request"))
    adapter = ActivityLogPrimaryAdapterNATS(stub, SECRET)
    request = _FakeRequest(
        data=activity_log_pb2.QueryRequest(actor_id="user:1").SerializeToString(),
        headers={AUTH_HEADER: _valid_token()},
        subject="abi.svc.activity_log.v1.query",
    )

    asyncio.run(adapter._handle_query(request))

    response = activity_log_pb2.QueryResponse()
    response.ParseFromString(request.responses[0])
    assert not response.HasField("error")
    assert len(response.events.events) == 2


def test_query_with_filter_applies_it():
    stub = _StubAdapter()
    stub.record(ActivityEvent(actor_id="user:1", event_type="http.request"))
    stub.record(ActivityEvent(actor_id="user:1", event_type="triple_store.insert"))
    adapter = ActivityLogPrimaryAdapterNATS(stub, SECRET)
    query_filter = activity_log_pb2.ActivityLogQueryFilter(event_type="http.request")
    request = _FakeRequest(
        data=activity_log_pb2.QueryRequest(
            actor_id="user:1", filter=query_filter
        ).SerializeToString(),
        headers={AUTH_HEADER: _valid_token()},
        subject="abi.svc.activity_log.v1.query",
    )

    asyncio.run(adapter._handle_query(request))

    response = activity_log_pb2.QueryResponse()
    response.ParseFromString(request.responses[0])
    assert len(response.events.events) == 1
    assert response.events.events[0].event_type == "http.request"


def test_query_unknown_actor_returns_empty_events():
    adapter = ActivityLogPrimaryAdapterNATS(_StubAdapter(), SECRET)
    request = _FakeRequest(
        data=activity_log_pb2.QueryRequest(actor_id="missing").SerializeToString(),
        headers={AUTH_HEADER: _valid_token()},
        subject="abi.svc.activity_log.v1.query",
    )

    asyncio.run(adapter._handle_query(request))

    response = activity_log_pb2.QueryResponse()
    response.ParseFromString(request.responses[0])
    assert not response.HasField("error")
    assert len(response.events.events) == 0


def test_list_actors_round_trips():
    stub = _StubAdapter()
    stub.record(ActivityEvent(actor_id="user:1", event_type="x"))
    stub.record(ActivityEvent(actor_id="user:2", event_type="x"))
    adapter = ActivityLogPrimaryAdapterNATS(stub, SECRET)
    request = _FakeRequest(
        data=activity_log_pb2.ListActorsRequest().SerializeToString(),
        headers={AUTH_HEADER: _valid_token()},
        subject="abi.svc.activity_log.v1.list_actors",
    )

    asyncio.run(adapter._handle_list_actors(request))

    response = activity_log_pb2.ListActorsResponse()
    response.ParseFromString(request.responses[0])
    assert not response.HasField("error")
    assert sorted(response.actors.actors) == ["user:1", "user:2"]


def test_shutdown_calls_through_to_adapter():
    stub = _StubAdapter()
    adapter = ActivityLogPrimaryAdapterNATS(stub, SECRET)
    request = _FakeRequest(
        data=activity_log_pb2.ShutdownRequest().SerializeToString(),
        headers={AUTH_HEADER: _valid_token()},
        subject="abi.svc.activity_log.v1.shutdown",
    )

    asyncio.run(adapter._handle_shutdown(request))

    response = activity_log_pb2.ShutdownResponse()
    response.ParseFromString(request.responses[0])
    assert not response.HasField("error")
    assert stub.shutdown_called is True


# ---------------------------------------------------------------------------
# Unexpected errors map to INTERNAL and never leak the raw message.
# ---------------------------------------------------------------------------


def test_unexpected_exception_maps_to_internal_and_does_not_leak_message():
    class _BoomAdapter(_StubAdapter):
        def query(
            self, actor_id: str, query: ActivityLogQuery | None = None
        ) -> list[ActivityEvent]:
            raise RuntimeError("some sensitive internal detail")

    adapter = ActivityLogPrimaryAdapterNATS(_BoomAdapter(), SECRET)
    request = _FakeRequest(
        data=activity_log_pb2.QueryRequest(actor_id="user:1").SerializeToString(),
        headers={AUTH_HEADER: _valid_token()},
        subject="abi.svc.activity_log.v1.query",
    )

    asyncio.run(adapter._handle_query(request))

    response = activity_log_pb2.QueryResponse()
    response.ParseFromString(request.responses[0])
    assert response.error.code == "INTERNAL"
    assert response.error.retryable is True
    assert "sensitive internal detail" not in response.error.message


# ---------------------------------------------------------------------------
# Lifecycle no-ops.
# ---------------------------------------------------------------------------


def test_stop_without_start_is_a_noop():
    adapter = ActivityLogPrimaryAdapterNATS(_StubAdapter(), SECRET)
    asyncio.run(adapter.stop())  # must not raise
