from naas_abi_core.services.event.adapters.event_stream_codec import (
    decode_events,
    event_frames,
)
from naas_abi_core.services.event.EventPort import StoredEvent


def _event(seq: int, size: int) -> StoredEvent:
    return StoredEvent(
        id=f"urn:e{seq}",
        event_type="urn:Type:A",
        seq=seq,
        timestamp="2026-01-01T00:00:00",
        payload=b"x" * size,
    )


def test_events_cross_the_wire_in_bounded_frames():
    events = [_event(seq, 1_000) for seq in range(1, 3_001)]

    frames = list(event_frames(iter(events), frame_bytes=64 * 1024))

    assert len(frames) > 1 and all(len(frame) < 2 * 64 * 1024 for frame in frames)
    assert [event for frame in frames for event in decode_events(frame)] == events


def test_an_event_larger_than_a_frame_closes_the_batch_it_joins():
    events = [_event(1, 10), _event(2, 200_000), _event(3, 10)]

    frames = list(event_frames(iter(events), frame_bytes=64 * 1024))

    assert [len(decode_events(frame)) for frame in frames] == [2, 1]
    assert [event for frame in frames for event in decode_events(frame)] == events


def test_no_events_no_frames():
    assert list(event_frames(iter(()))) == []
