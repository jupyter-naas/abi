import asyncio
import base64
import json
from types import SimpleNamespace as NS

import pytest
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.adapters.secondary.nats_traffic_tap import (
    TAP_SUBJECTS,
    NatsTrafficTap,
)
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.port import SourceUnavailable


def _token(sub):
    claims = base64.urlsafe_b64encode(json.dumps({"sub": sub}).encode()).decode().rstrip("=")
    return f"h.{claims}.s"


class FakeNats:
    def __init__(self):
        self.subs = {}

    async def subscribe(self, subject, cb=None):
        self.subs[subject] = cb
        return NS(unsubscribe=self._unsubscribe(subject))

    def _unsubscribe(self, subject):
        async def unsubscribe():
            self.subs.pop(subject, None)

        return unsubscribe

    async def deliver(self, pattern, subject, data=b"", reply="", headers=None):
        await self.subs[pattern](NS(subject=subject, data=data, reply=reply, headers=headers))


class Clock:
    def __init__(self):
        self.now = 100.0

    def __call__(self):
        return self.now


def _tap(nc, clock, **kwargs):
    async def connect():
        return nc

    return NatsTrafficTap(connect, clock=clock, monotonic=clock, **kwargs)


def test_pairs_a_request_with_its_reply():
    nc, clock, seen = FakeNats(), Clock(), []

    async def scenario():
        tap = _tap(nc, clock)
        await tap.start(seen.append)
        headers = {
            "Nats-Auth-Token": _token("api"),
            "traceparent": "00-" + "a" * 32 + "-" + "b" * 16 + "-01",
        }
        await nc.deliver(
            "abi.svc.*.v1.*", "abi.svc.document.v1.get", b"12345", "_INBOX.x.1", headers
        )
        clock.now += 0.004
        await nc.deliver("_INBOX.>", "_INBOX.x.1", b"1234567890")
        await tap.stop()

    asyncio.run(scenario())

    (event,) = seen
    assert (event.kind, event.service, event.method, event.caller) == (
        "service",
        "document",
        "get",
        "api",
    )
    assert (event.request_bytes, event.reply_bytes, event.status) == (5, 10, "ok")
    assert event.latency_ms == pytest.approx(4.0)
    assert event.trace_id == "a" * 32
    assert "Nats-Auth-Token" not in repr(event) and _token("api") not in repr(event)


def test_error_codes_come_from_reply_headers():
    nc, clock, seen = FakeNats(), Clock(), []

    async def scenario():
        tap = _tap(nc, clock)
        await tap.start(seen.append)
        await nc.deliver("abi.svc.*.v1.*", "abi.svc.kv.v1.get", b"", "_INBOX.x.2")
        await nc.deliver("_INBOX.>", "_INBOX.x.2", b"", headers={"Abi-Error-Code": "NOT_FOUND"})
        await nc.deliver("abi.svc.*.v1.*", "abi.svc.kv.v1.put", b"", "_INBOX.x.3")
        await nc.deliver("_INBOX.>", "_INBOX.x.3", b"", headers={"Nats-Service-Error-Code": "500"})
        await tap.stop()

    asyncio.run(scenario())

    assert [(e.status, e.error_code) for e in seen] == [("error", "NOT_FOUND"), ("error", "500")]


def test_publishes_are_reported_at_once_and_unknown_replies_ignored():
    nc, clock, seen = FakeNats(), Clock(), []

    async def scenario():
        tap = _tap(nc, clock)
        await tap.start(seen.append)
        await nc.deliver("evt.>", "evt.abc.e-1", b"{}")
        await nc.deliver("_INBOX.>", "_INBOX.someone-else.9", b"big transfer chunk")
        await tap.stop()

    asyncio.run(scenario())

    assert [(e.kind, e.status, e.reply_bytes) for e in seen] == [("event", "published", None)]


def test_unanswered_requests_are_reported_after_the_reply_timeout():
    nc, clock, seen = FakeNats(), Clock(), []

    async def scenario():
        tap = _tap(nc, clock, reply_timeout_seconds=5, sweep_seconds=0.01)
        await tap.start(seen.append)
        await nc.deliver(
            "abi.discovery.*.v1.*", "abi.discovery.zen.v1.list_modules", b"", "_INBOX.x.4"
        )
        clock.now += 6
        await asyncio.sleep(0.05)
        await tap.stop()

    asyncio.run(scenario())

    assert [(e.kind, e.status) for e in seen] == [("discovery", "no_reply")]


def test_pending_requests_are_bounded():
    nc, clock, seen = FakeNats(), Clock(), []

    async def scenario():
        tap = _tap(nc, clock, max_pending=2)
        await tap.start(seen.append)
        for i in range(3):
            await nc.deliver("abi.svc.*.v1.*", "abi.svc.kv.v1.get", b"", f"_INBOX.x.{i}")
        await tap.stop()

    asyncio.run(scenario())

    assert [e.status for e in seen] == ["no_reply"]


def test_subscribes_to_abi_subjects_and_replies_and_cleans_up():
    nc, clock = FakeNats(), Clock()

    async def scenario():
        tap = _tap(nc, clock)
        await tap.start(lambda e: None)
        subscribed = set(nc.subs)
        await tap.stop()
        return subscribed

    subscribed = asyncio.run(scenario())

    assert subscribed == {*TAP_SUBJECTS, "_INBOX.>"}
    assert not any("transfer" in s for s in subscribed)
    assert nc.subs == {}


def test_unreachable_nats_is_unavailable():
    async def refuse():
        raise OSError("connection refused")

    with pytest.raises(SourceUnavailable):
        asyncio.run(NatsTrafficTap(refuse).start(lambda e: None))
