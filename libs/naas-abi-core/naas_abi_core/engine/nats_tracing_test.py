import asyncio
from types import SimpleNamespace as NS

import pytest

pytest.importorskip("opentelemetry.sdk")

from naas_abi_core.engine import nats_tracing
from naas_abi_core.engine.nats_rpc import respond_protobuf
from naas_abi_core.proto.common.v1 import common_pb2
from naas_abi_sdk import telemetry
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
    InMemorySpanExporter,
)
from opentelemetry.trace import SpanKind, StatusCode


@pytest.fixture
def spans(monkeypatch):
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    monkeypatch.setattr(telemetry, "_tracer", lambda: provider.get_tracer("test"))
    return exporter


class FakeService:
    def __init__(self):
        self.endpoints = {}
        self.stopped = False

    async def add_endpoint(self, *, name, subject, handler, **kwargs):
        self.endpoints[subject] = handler

    async def stop(self):
        self.stopped = True


def test_endpoints_of_a_traced_service_run_in_server_spans(monkeypatch, spans):
    fake = FakeService()

    async def add_service(nc, **config):
        return fake

    monkeypatch.setattr(nats_tracing.nats.micro, "add_service", add_service)
    handled = []

    async def handler(request):
        handled.append(request.subject)

    async def scenario():
        service = await nats_tracing.add_traced_service(
            object(), name="document", version="1.0.0"
        )
        await service.add_endpoint(
            name="get", subject="abi.svc.document.v1.get", handler=handler
        )
        headers = {}
        with telemetry.client_span("abi.svc.document.v1.get", headers):
            pass
        await fake.endpoints["abi.svc.document.v1.get"](
            NS(subject="abi.svc.document.v1.get", headers=headers)
        )
        await service.stop()

    asyncio.run(scenario())

    client, server = spans.get_finished_spans()
    assert handled == ["abi.svc.document.v1.get"]
    assert server.kind is SpanKind.SERVER and server.name == "document/get"
    assert server.context.trace_id == client.context.trace_id
    assert fake.stopped


class _Request:
    def __init__(self):
        self.replies = []

    async def respond(self, data=b"", headers=None):
        self.replies.append((data, headers))


def _response(error=None):
    from naas_abi_proto.keyvalue.v1 import keyvalue_pb2

    return (
        keyvalue_pb2.GetResponse(error=error)
        if error
        else keyvalue_pb2.GetResponse(value=b"v")
    )


def test_error_replies_carry_their_code_in_a_header_and_fail_the_span(spans):
    from naas_abi_proto.keyvalue.v1 import keyvalue_pb2

    request = _Request()

    async def scenario():
        with telemetry.server_span("abi.svc.keyvalue.v1.get", {}):
            await respond_protobuf(
                request,
                _response(common_pb2.CallError(code="NOT_FOUND", message="missing")),
                keyvalue_pb2.GetResponse,
            )

    asyncio.run(scenario())

    (_, headers) = request.replies[0]
    assert headers == {"Abi-Error-Code": "NOT_FOUND"}
    (span,) = spans.get_finished_spans()
    assert span.status.status_code is StatusCode.ERROR


def test_successful_replies_have_no_error_header():
    from naas_abi_proto.keyvalue.v1 import keyvalue_pb2

    request = _Request()
    asyncio.run(respond_protobuf(request, _response(), keyvalue_pb2.GetResponse))

    assert request.replies[0][1] is None


# --- calls side by side ------------------------------------------------------------------


async def _until(predicate, timeout=2.0):
    deadline = asyncio.get_running_loop().time() + timeout
    while not predicate():
        assert asyncio.get_running_loop().time() < deadline, "timed out"
        await asyncio.sleep(0.005)


class _Calls:
    """An endpoint callback whose calls wait until released."""

    def __init__(self):
        self.started = []
        self.running = 0
        self.peak = 0
        self.release = asyncio.Event()

    async def __call__(self, msg):
        self.started.append(msg)
        self.running += 1
        self.peak = max(self.peak, self.running)
        try:
            await self.release.wait()
        finally:
            self.running -= 1


def test_calls_to_one_endpoint_run_side_by_side():
    async def scenario():
        requests = nats_tracing.ConcurrentRequests(limit=4)
        calls = _Calls()
        receive = requests.callback(calls)
        for msg in range(3):
            await receive(msg)  # returns at once: the next message can come
        await _until(lambda: len(calls.started) == 3)
        assert requests.in_flight == 3
        calls.release.set()
        await _until(lambda: requests.in_flight == 0)
        return calls

    calls = asyncio.run(scenario())

    assert calls.peak == 3


def test_beyond_the_limit_a_call_waits_for_a_free_slot():
    async def scenario():
        requests = nats_tracing.ConcurrentRequests(limit=2)
        calls = _Calls()
        receive = requests.callback(calls)
        await receive(0)
        await receive(1)
        third = asyncio.create_task(receive(2))
        await asyncio.sleep(0.05)
        assert not third.done()  # the subscription holds its next messages
        assert calls.started == [0, 1]
        # Counted while it waits, so a drain waits for it too.
        assert requests.in_flight == 3
        calls.release.set()
        await third
        await _until(lambda: requests.in_flight == 0)
        return calls

    calls = asyncio.run(scenario())

    assert calls.started == [0, 1, 2]
    assert calls.peak == 2


def test_cancel_stops_the_calls_still_running():
    async def scenario():
        requests = nats_tracing.ConcurrentRequests(limit=4)
        calls = _Calls()
        receive = requests.callback(calls)
        await receive(0)
        await receive(1)
        await _until(lambda: calls.running == 2)
        await requests.cancel()
        return requests, calls

    requests, calls = asyncio.run(scenario())

    assert calls.running == 0
    assert requests.in_flight == 0


def test_a_call_that_fails_frees_its_slot():
    async def scenario():
        requests = nats_tracing.ConcurrentRequests(limit=1)
        answered = []

        async def handle(msg):
            if msg == "broken":
                raise ConnectionError("the reply could not be sent")
            answered.append(msg)

        receive = requests.callback(handle)
        await receive("broken")
        await receive("next")
        await _until(lambda: requests.in_flight == 0)
        return answered

    assert asyncio.run(scenario()) == ["next"]


class _Client:
    def __init__(self):
        self.subscriptions = []
        self.flushed = False

    async def subscribe(self, subject, queue="", cb=None, **kwargs):
        self.subscriptions.append((subject, queue, cb))
        return NS(subject=subject)

    async def flush(self):
        self.flushed = True


def test_only_endpoint_subscriptions_run_their_calls_side_by_side():
    async def endpoint(msg):
        pass

    async def verb(msg):
        pass

    async def scenario():
        nc = _Client()
        client = nats_tracing.ConcurrentRequests(limit=4).client(nc)
        await client.subscribe(
            subject="abi.svc.document.v1.get", queue="q", cb=endpoint
        )
        await client.subscribe("$SRV.PING", cb=verb)  # nats.micro's own verbs
        await client.flush()
        return nc

    nc = asyncio.run(scenario())

    (_, queue, endpoint_cb), (_, _, verb_cb) = nc.subscriptions
    assert queue == "q" and endpoint_cb is not endpoint
    assert verb_cb is verb
    assert nc.flushed
