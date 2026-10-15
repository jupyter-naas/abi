"""Stored events on the wire, and the frames of a streamed ``query``
(docs/adr/20261003_nats-streamed-results.md).

Shared by the NATS primary and client; no new protobuf messages: each frame
is a ``StoredEvents`` batch of about ``FRAME_BYTES``.
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator

from naas_abi_core.proto.event.v1 import event_pb2
from naas_abi_core.services.event.EventPort import StoredEvent

FRAME_BYTES = 256 * 1024


def event_to_pb(event: StoredEvent) -> event_pb2.StoredEvent:
    return event_pb2.StoredEvent(
        id=event.id,
        event_type=event.event_type,
        seq=event.seq,
        timestamp=event.timestamp,
        payload=event.payload,
    )


def pb_to_event(pb: event_pb2.StoredEvent) -> StoredEvent:
    return StoredEvent(
        id=pb.id,
        event_type=pb.event_type,
        seq=pb.seq,
        timestamp=pb.timestamp,
        payload=pb.payload,
    )


def event_frames(
    events: Iterable[StoredEvent], frame_bytes: int = FRAME_BYTES
) -> Iterator[bytes]:
    """``events`` in ``StoredEvents`` batches, each closed once it reaches
    ``frame_bytes``: an event larger than that closes the batch it joins."""
    batch, size = event_pb2.StoredEvents(), 0
    for event in events:
        pb = batch.events.add()
        pb.CopyFrom(event_to_pb(event))
        size += pb.ByteSize()
        if size >= frame_bytes:
            yield batch.SerializeToString()
            batch, size = event_pb2.StoredEvents(), 0
    if batch.events:
        yield batch.SerializeToString()


def decode_events(frame: bytes) -> list[StoredEvent]:
    return [pb_to_event(pb) for pb in event_pb2.StoredEvents.FromString(frame).events]
