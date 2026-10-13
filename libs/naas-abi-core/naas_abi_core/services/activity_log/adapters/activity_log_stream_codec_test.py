from datetime import UTC, datetime

from naas_abi_core.services.activity_log.ActivityLogPort import ActivityEvent
from naas_abi_core.services.activity_log.adapters.activity_log_stream_codec import (
    activity_frames,
    decode_events,
)


def _event(seq: int, pad: int = 0) -> ActivityEvent:
    return ActivityEvent(
        actor_id="user:1",
        event_type="http.request",
        timestamp=datetime(2026, 10, 4, 12, 30, tzinfo=UTC),
        correlation_id=f"req-{seq}" if seq % 2 else None,
        attributes={"seq": seq, "nested": {"a": [1, 2]}, "pad": "p" * pad},
        seq=seq,
    )


def test_events_cross_the_wire_in_bounded_frames():
    events = [_event(seq, pad=500) for seq in range(1, 2_001)]

    frames = list(activity_frames(iter(events), frame_bytes=64 * 1024))

    assert len(frames) > 1 and all(len(frame) < 2 * 64 * 1024 for frame in frames)
    assert [event for frame in frames for event in decode_events(frame)] == events


def test_no_events_no_frames():
    assert list(activity_frames(iter(()))) == []
