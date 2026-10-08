import asyncio
from types import SimpleNamespace as NS

import pytest
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.adapters.secondary.bus_resources import (
    REDACTED,
    BusResources,
    payload_kind,
    payload_summary,
    stream_kind,
)
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.port import SourceUnavailable
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.resources import (
    InvalidResource,
    ResourceNotFound,
)


class FakeJSM:
    """One stream ``S`` holding sequences 1..10 with 2..8 deleted."""

    def __init__(self, error=None):
        self.error = error
        self.gets = 0
        self.messages = {
            seq: NS(
                seq=seq, subject=f"s.{seq}", data=b"v", headers={"Authorization": "x"}, time=None
            )
            for seq in (1, 9, 10)
        }

    async def stream_info(self, name):
        if self.error:
            raise self.error
        from nats.js.errors import NotFoundError

        if name != "S":
            raise NotFoundError()
        return NS(
            config=NS(name="S", subjects=["s.>"]),
            state=NS(first_seq=1, last_seq=10, bytes=3, messages=3, consumer_count=0),
        )

    async def get_msg(self, stream, seq):
        from nats.js.errors import NotFoundError

        self.gets += 1
        if seq not in self.messages:
            raise NotFoundError()
        return self.messages[seq]


def _bus(jsm):
    async def connect():
        return NS(jsm=lambda timeout: jsm)

    return BusResources(connect)


def test_unreachable_nats_is_named():
    async def connect():
        raise OSError("connection refused")

    with pytest.raises(SourceUnavailable, match="NATS unreachable"):
        asyncio.run(BusResources(connect).list(""))


def test_jetstream_disabled_is_named():
    from nats.errors import NoRespondersError

    with pytest.raises(SourceUnavailable, match="JetStream is not enabled"):
        asyncio.run(_bus(FakeJSM(error=NoRespondersError())).stat("S"))


def test_pages_skip_deleted_sequences_newest_first():
    jsm = FakeJSM()
    bus = _bus(jsm)

    first = asyncio.run(bus.list("S", limit=2))
    second = asyncio.run(bus.list("S", cursor=first.next_cursor, limit=2))

    assert [e.id for e in first.entries] == ["S/10", "S/9"]
    assert [e.id for e in second.entries] == ["S/1"]
    assert second.next_cursor is None
    assert first.entries[0].attributes["header:Authorization"] == REDACTED


def test_a_page_scans_a_bounded_number_of_sequences():
    jsm = FakeJSM()
    page = asyncio.run(_bus(jsm).list("S", cursor="8", limit=1))

    # Sequences 8..1: seven misses then sequence 1, within 8 scans for 1 entry.
    assert [e.id for e in page.entries] == ["S/1"]
    assert jsm.gets <= 8


@pytest.mark.parametrize("bad", ["x", "-1"])
def test_bad_cursors_are_refused(bad):
    with pytest.raises(InvalidResource):
        asyncio.run(_bus(FakeJSM()).list("S", cursor=bad))


@pytest.mark.parametrize("resource_id", ["NOPE", "NOPE/1", "S/0", "S/x", "S/5"])
def test_unknown_streams_and_messages_are_not_found(resource_id):
    with pytest.raises(ResourceNotFound):
        asyncio.run(_bus(FakeJSM()).stat(resource_id))


def test_stream_kinds_follow_their_names():
    assert [stream_kind(n) for n in ("KV_x", "ABI_JOBS_zen", "naas-abi-events", "other")] == [
        "kv",
        "jobs",
        "bus",
        "other",
    ]


def test_payloads_are_summarized_by_kind():
    assert payload_kind(b'{"a": 1}') == "json"
    assert payload_kind(b"hello") == "text"
    assert payload_kind(b"\xff\xfe") == "binary"
    assert payload_summary(b'{"a": 1, "b": 2}') == "{a, b}"
    assert payload_summary(b"[1, 2, 3]") == "[3 items]"
    assert payload_summary(b"  hello\n  world ") == "hello world"
    assert payload_summary(b"\xff\x00") == "binary · 2 bytes"
    assert payload_summary(b"") == "empty"
    assert len(payload_summary(b"x" * 500)) == 96


def test_reading_a_message_adds_a_message_view_without_credentials():
    from datetime import UTC, datetime

    jsm = FakeJSM()
    jsm.messages[10].time = datetime(2026, 10, 2, 12, 0, tzinfo=UTC)
    bus = _bus(jsm)

    detail = asyncio.run(bus.read("S/10"))

    assert detail.view == {
        "type": "message",
        "subject": "s.10",
        "headers": {"Authorization": REDACTED},
        "sequence": 10,
        "published_at": "2026-10-02T12:00:00+00:00",
    }
    assert detail.entry.attributes["summary"] == "v"
    assert detail.entry.modified == "2026-10-02T12:00:00+00:00"


def test_streams_carry_their_last_activity_and_subjects():
    from datetime import UTC, datetime

    class Listing(FakeJSM):
        async def streams_info(self, offset=0):
            return [await self.stream_info("S")]

    jsm = Listing()
    jsm.messages[10].time = datetime(2026, 10, 2, 12, 0, tzinfo=UTC)

    (stream,) = asyncio.run(_bus(jsm).list("")).entries

    assert stream.modified == "2026-10-02T12:00:00+00:00"
    assert (stream.attributes["summary"], stream.attributes["last_seq"]) == ("s.>", "10")
    assert "read_only" not in stream.attributes
