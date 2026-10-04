"""Activity events on the wire, and the frames of a streamed ``query``
(docs/adr/20261003_nats-streamed-results.md).

Shared by the NATS primary and client; no new protobuf messages: each frame
is an ``ActivityEvents`` batch of about ``FRAME_BYTES``.
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator
from datetime import UTC

from google.protobuf import json_format
from naas_abi_core.proto.activity_log.v1 import activity_log_pb2
from naas_abi_core.services.activity_log.ActivityLogPort import ActivityEvent

FRAME_BYTES = 256 * 1024


def event_to_pb(event: ActivityEvent) -> activity_log_pb2.ActivityEvent:
    pb = activity_log_pb2.ActivityEvent(
        actor_id=event.actor_id,
        event_type=event.event_type,
    )
    pb.timestamp.FromDatetime(event.timestamp)
    if event.correlation_id is not None:
        pb.correlation_id = event.correlation_id
    pb.attributes.update(event.attributes)
    if event.seq is not None:
        pb.seq = event.seq
    return pb


def pb_to_event(pb: activity_log_pb2.ActivityEvent) -> ActivityEvent:
    return ActivityEvent(
        actor_id=pb.actor_id,
        event_type=pb.event_type,
        timestamp=pb.timestamp.ToDatetime(tzinfo=UTC),
        correlation_id=pb.correlation_id if pb.HasField("correlation_id") else None,
        attributes=json_format.MessageToDict(pb.attributes),
        seq=pb.seq if pb.HasField("seq") else None,
    )


def activity_frames(
    events: Iterable[ActivityEvent], frame_bytes: int = FRAME_BYTES
) -> Iterator[bytes]:
    """``events`` in ``ActivityEvents`` batches, each closed once it reaches
    ``frame_bytes``: an event larger than that closes the batch it joins."""
    batch, size = activity_log_pb2.ActivityEvents(), 0
    for event in events:
        pb = batch.events.add()
        pb.CopyFrom(event_to_pb(event))
        size += pb.ByteSize()
        if size >= frame_bytes:
            yield batch.SerializeToString()
            batch, size = activity_log_pb2.ActivityEvents(), 0
    if batch.events:
        yield batch.SerializeToString()


def decode_events(frame: bytes) -> list[ActivityEvent]:
    return [
        pb_to_event(pb)
        for pb in activity_log_pb2.ActivityEvents.FromString(frame).events
    ]
