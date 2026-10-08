import asyncio
import base64
import json

import pytest
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.traffic import (
    TrafficEvent,
    TrafficHub,
    caller_from_token,
    classify,
    trace_id_from_traceparent,
)


@pytest.mark.parametrize(
    ("subject", "expected"),
    [
        ("abi.svc.document.v1.get", ("service", "document", "get")),
        ("abi.svc.model_registry.v1.chat", ("model", "model_registry", "chat")),
        ("abi.svc.cache.v1.tier.0.get", ("service", "cache", "get")),
        ("abi.discovery.zen.v1.list_modules", ("discovery", "zen", "list_modules")),
        ("abi.agent.zen.inst-1.abc123.v1.submit", ("agent", "zen/inst-1", "submit")),
        ("abi.jobs.zen.trigger.mh.jh", ("job", "zen", "trigger")),
        ("abi.jobs.zen.schedule.mh.jh.0", ("job", "zen", "schedule")),
        ("evt.0123abcd.http://ontology.naas.ai/abi/x", ("event", "0123abcd", "publish")),
        ("something.else", ("other", "", "")),
    ],
)
def test_classify_names_the_service_and_method(subject, expected):
    assert classify(subject) == expected


def _token(claims):
    def part(value):
        return base64.urlsafe_b64encode(json.dumps(value).encode()).decode().rstrip("=")

    return f"{part({'alg': 'HS256'})}.{part(claims)}.signature"


def test_caller_is_the_token_subject_never_the_token():
    assert caller_from_token(_token({"sub": "api", "exp": 1})) == "api"
    assert caller_from_token("not-a-jwt") == ""
    assert caller_from_token(None) == ""
    assert caller_from_token(_token({"exp": 1})) == ""


def test_trace_id_from_w3c_traceparent():
    header = "00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01"
    assert trace_id_from_traceparent(header) == "4bf92f3577b34da6a3ce929d0e0e4736"
    assert trace_id_from_traceparent("garbage") == ""
    assert trace_id_from_traceparent(None) == ""


def _event(i=0):
    return TrafficEvent(
        at=float(i),
        kind="service",
        subject="abi.svc.document.v1.get",
        service="document",
        method="get",
        caller="api",
        request_bytes=10,
        reply_bytes=20,
        latency_ms=1.0,
        status="ok",
    )


class FakeTap:
    def __init__(self):
        self.emit = None
        self.starts = 0
        self.stops = 0

    async def start(self, emit):
        self.starts += 1
        self.emit = emit

    async def stop(self):
        self.stops += 1
        self.emit = None


def test_the_tap_runs_only_while_someone_watches_and_fans_out():
    tap = FakeTap()
    hub = TrafficHub(lambda: tap)

    async def scenario():
        async with hub.subscribe() as first, hub.subscribe() as second:
            assert tap.starts == 1
            tap.emit(_event(1))
            assert (await first.get()).at == 1.0
            assert (await second.get()).at == 1.0
        assert tap.stops == 1
        async with hub.subscribe():
            assert tap.starts == 2

    asyncio.run(scenario())


def test_a_slow_viewer_drops_old_events_instead_of_blocking():
    tap = FakeTap()
    hub = TrafficHub(lambda: tap, max_queue=2)

    async def scenario():
        async with hub.subscribe() as viewer:
            for i in range(5):
                tap.emit(_event(i))
            return [(await viewer.get()).at, (await viewer.get()).at], viewer.dropped

    kept, dropped = asyncio.run(scenario())
    assert kept == [3.0, 4.0] and dropped == 3


def test_drain_returns_what_is_queued_without_waiting():
    tap = FakeTap()
    hub = TrafficHub(lambda: tap)

    async def scenario():
        async with hub.subscribe() as viewer:
            for i in range(3):
                tap.emit(_event(i))
            first = await viewer.get()
            return [first.at] + [e.at for e in viewer.drain(10)], viewer.drain(10)

    batch, empty = asyncio.run(scenario())
    assert batch == [0.0, 1.0, 2.0] and empty == []


def test_a_tap_that_fails_to_start_is_retried_by_the_next_viewer():
    from naas_abi.apps.nexus.apps.api.app.services.sysadmin.port import SourceUnavailable

    attempts = []

    class Flaky(FakeTap):
        async def start(self, emit):
            attempts.append(1)
            if len(attempts) == 1:
                raise SourceUnavailable("nats", "connection refused")
            await super().start(emit)

    hub = TrafficHub(Flaky)

    async def scenario():
        with pytest.raises(SourceUnavailable):
            async with hub.subscribe():
                pass
        async with hub.subscribe() as viewer:
            return viewer

    asyncio.run(scenario())
    assert len(attempts) == 2


def test_the_hub_reports_which_source_is_live():
    tap = FakeTap()
    tap.source = "traces"
    tap.skipped = {}
    hub = TrafficHub(lambda: tap)

    async def scenario():
        assert hub.source is None
        async with hub.subscribe():
            return hub.source, hub.skipped

    assert asyncio.run(scenario()) == ("traces", {})
