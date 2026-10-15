import asyncio
import json
from collections import deque

import pytest
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.adapters.secondary.nats_micro import (
    NatsMicroServiceMonitor,
)
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.contracts import (
    MicroServiceMonitorContract,
    UnavailableMicroServiceMonitorContract,
)
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.port import SourceUnavailable
from nats.errors import TimeoutError as NATSTimeoutError


def _stats(name, instance, requests, subject_op="get"):
    return {
        "type": "io.nats.micro.v1.stats_response",
        "name": name,
        "id": instance,
        "version": "1.0.0",
        "started": "2026-10-02T08:00:00.000Z",
        "metadata": {},
        "endpoints": [
            {
                "name": subject_op,
                "subject": f"abi.svc.{name}.v1.{subject_op}",
                "queue_group": "q",
                "num_requests": requests,
                "num_errors": 0,
                "last_error": "",
                "processing_time": 3_000_000 * requests,
                "average_processing_time": 3_000_000 if requests else 0,
                "data": None,
            }
        ],
    }


class _Msg:
    def __init__(self, data):
        self.data = data


class _Sub:
    def __init__(self):
        self.queue = deque()
        self.unsubscribed = False

    async def next_msg(self, timeout):
        if self.queue:
            return self.queue.popleft()
        await asyncio.sleep(0)
        raise NATSTimeoutError

    async def unsubscribe(self):
        self.unsubscribed = True


class FakeNats:
    def __init__(self, replies):
        self.replies, self.sub, self.published = replies, None, []

    def new_inbox(self):
        return "_INBOX.test"

    async def subscribe(self, subject):
        self.sub = _Sub()
        return self.sub

    async def publish(self, subject, payload=b"", reply=""):
        self.published.append((subject, reply))
        for reply_body in self.replies:
            self.sub.queue.append(_Msg(json.dumps(reply_body).encode()))


@pytest.fixture
def monitor(request):
    if request.cls is not None and "Unavailable" in request.cls.__name__:

        async def refuse():
            raise OSError("connection refused")

        return NatsMicroServiceMonitor(refuse)
    nc = FakeNats(
        [_stats("document", "d1", 3), _stats("document", "d2", 2), _stats("keyvalue", "k1", 0)]
    )

    async def connect():
        return nc

    return NatsMicroServiceMonitor(connect, idle_seconds=0.01)


class TestNatsMicroServiceMonitor(MicroServiceMonitorContract):
    pass


class TestUnavailableNats(UnavailableMicroServiceMonitorContract):
    pass


def test_processing_time_is_reported_in_milliseconds(monitor):
    instances = asyncio.run(monitor.list_instances())

    endpoint = next(i for i in instances if i.instance_id == "d1").endpoints[0]
    assert endpoint.average_ms == 3.0


def test_ignores_replies_that_are_not_stats_and_unsubscribes():
    nc = FakeNats([_stats("document", "d1", 1), {"type": "other"}, "not json"])

    async def connect():
        return nc

    instances = asyncio.run(NatsMicroServiceMonitor(connect, idle_seconds=0.01).list_instances())

    assert [i.instance_id for i in instances] == ["d1"]
    assert nc.published == [("$SRV.STATS", "_INBOX.test")]
    assert nc.sub.unsubscribed


def test_a_hanging_connection_is_unavailable_within_the_budget():
    import time

    async def hang():
        await asyncio.sleep(30)

    started = time.monotonic()
    with pytest.raises(SourceUnavailable):
        asyncio.run(NatsMicroServiceMonitor(hang, connect_timeout_seconds=0.05).list_instances())
    assert time.monotonic() - started < 2
