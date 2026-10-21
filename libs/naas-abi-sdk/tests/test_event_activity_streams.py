"""SDK activity log and event facades: paging fields and streamed queries."""

import asyncio
import json
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from naas_abi_proto.activity_log.v1 import activity_log_pb2 as activity
from naas_abi_proto.event.v1 import event_pb2 as events

from naas_abi_sdk.services import FACTORIES, service_proxy
from naas_abi_sdk.services.models import ActivityLogQuery


class StreamOwner:
    """The owner side of one transfer stream: frames read in order."""

    def __init__(self, frames, *, no_responders=False):
        self.frames, self.no_responders = list(frames), no_responders
        self.opened, self.closed, self.read = [], [], 0

    async def connect(self):
        return SimpleNamespace(max_payload=1024 * 1024)

    async def call(self, subject, request, response_type, transfer=None):
        operation = subject.rsplit(".", 1)[1]
        if operation == "open":
            if self.no_responders:
                from nats.errors import NoRespondersError

                raise NoRespondersError()
            self.opened.append((subject, request.operation, request.metadata))
            return response_type(id=f"{'a' * 32}:s", chunk_bytes=request.chunk_bytes)
        if operation == "start":
            return response_type()
        if operation == "close":
            self.closed.append(request.id)
            return response_type()
        if self.read >= len(self.frames):
            return response_type(done=True, sequence=request.sequence)
        self.read += 1
        return response_type(
            data=self.frames[self.read - 1], frame_end=True, sequence=request.sequence
        )


def _activity(seq: int) -> activity.ActivityEvent:
    pb = activity.ActivityEvent(actor_id="user:1", event_type="http.request", seq=seq)
    pb.timestamp.FromDatetime(datetime(2026, 10, 4, tzinfo=timezone.utc))
    pb.attributes.update({"seq": seq})
    return pb


def test_activity_log_query_pages_with_seq_cursors():
    client = AsyncMock()
    client.query.return_value = activity.QueryResponse(
        events=activity.ActivityEvents(events=[_activity(7)])
    )
    service = FACTORIES["activity_log"](client)

    (event,) = asyncio.run(
        service.query(
            "user:1", ActivityLogQuery(newest_first=True, before_seq=10, limit=5)
        )
    )

    assert event.seq == 7 and event.attributes == {"seq": 7}
    sent = client.query.call_args.args[0].filter
    assert (sent.newest_first, sent.before_seq, sent.limit) == (True, 10, 5)


def test_activity_log_query_stream_pins_the_snapshot_and_reads_frames():
    first = activity.ActivityEvents(events=[_activity(1), _activity(2)])
    second = activity.ActivityEvents(events=[_activity(3)])
    owner = StreamOwner([first.SerializeToString(), second.SerializeToString()])
    client = SimpleNamespace(
        _transport=owner,
        query=AsyncMock(
            return_value=activity.QueryResponse(
                events=activity.ActivityEvents(events=[_activity(3)])
            )
        ),
    )
    service = FACTORIES["activity_log"](client)

    async def scenario():
        async with service.query_stream(
            "user:1", ActivityLogQuery(event_type="http.request")
        ) as stream:
            return [event async for event in stream]

    streamed = asyncio.run(scenario())

    assert [event.seq for event in streamed] == [1, 2, 3]
    ((subject, operation, metadata),) = owner.opened
    assert subject == "abi.svc.activity_log.v1.transfer.open" and operation == "query"
    request = activity.QueryRequest.FromString(metadata)
    assert request.actor_id == "user:1"
    assert request.filter.event_type == "http.request"
    assert request.filter.before_seq == 4  # pinned above the newest event, seq 3
    assert owner.closed


def test_activity_log_query_stream_of_an_unknown_actor_opens_nothing():
    owner = StreamOwner([])
    client = SimpleNamespace(
        _transport=owner, query=AsyncMock(return_value=activity.QueryResponse())
    )
    service = FACTORIES["activity_log"](client)

    async def scenario():
        async with service.query_stream("user:nobody") as stream:
            return [event async for event in stream]

    assert asyncio.run(scenario()) == [] and owner.opened == []


def _stored(seq: int) -> events.StoredEvent:
    return events.StoredEvent(
        id=f"urn:e{seq}",
        event_type="urn:Type:A",
        seq=seq,
        timestamp="2026-10-04T00:00:00",
        payload=json.dumps({"n": seq}).encode(),
    )


def test_event_query_stream_pins_max_seq_and_restores_payloads():
    frame = events.StoredEvents(events=[_stored(1), _stored(2)]).SerializeToString()
    owner = StreamOwner([frame])
    client = SimpleNamespace(
        _transport=owner, max_seq=AsyncMock(return_value=events.MaxSeqResponse(seq=9))
    )
    service = service_proxy("event", client, bus=None)

    async def scenario():
        async with service.query_stream(
            "urn:Type:A", until_seq=50, newest_first=True, filter={"n": [1, 2]}
        ) as stream:
            return [item async for item in stream]

    assert asyncio.run(scenario()) == [{"n": 1}, {"n": 2}]
    ((subject, operation, metadata),) = owner.opened
    assert subject == "abi.svc.event.v1.transfer.open" and operation == "query"
    request = events.QueryRequest.FromString(metadata)
    assert (request.event_type, request.until_seq, request.newest_first) == (
        "urn:Type:A",
        9,
        True,
    )
    assert dict(request.json_filter) == {"n": [1, 2]}


def test_event_query_stream_needs_an_engine_that_streams():
    owner = StreamOwner([], no_responders=True)
    client = SimpleNamespace(
        _transport=owner, max_seq=AsyncMock(return_value=events.MaxSeqResponse(seq=1))
    )
    service = service_proxy("event", client, bus=None)

    async def scenario():
        async with service.query_stream() as stream:
            return [item async for item in stream]

    with pytest.raises(Exception, match="UNAVAILABLE"):
        asyncio.run(scenario())
