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
