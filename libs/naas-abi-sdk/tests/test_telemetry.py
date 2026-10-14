import pytest

pytest.importorskip("opentelemetry.sdk")

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
    InMemorySpanExporter,
)
from opentelemetry.trace import SpanKind, StatusCode

from naas_abi_sdk import telemetry


@pytest.fixture
def spans(monkeypatch):
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    monkeypatch.setattr(telemetry, "_tracer", lambda: provider.get_tracer("test"))
    return exporter


def test_describe_subject_names_service_and_method():
    assert telemetry.describe_subject("abi.svc.document.v1.get") == ("document", "get")
    assert telemetry.describe_subject("abi.svc.cache.v1.tier.0.get") == ("cache", "get")
    assert telemetry.describe_subject("abi.discovery.zen.v1.list_modules") == (
        "discovery",
        "list_modules",
    )
    assert telemetry.describe_subject("abi.agent.zen.i.h.v1.submit") == (
        "agent",
        "submit",
    )
    assert telemetry.describe_subject("other") == ("nats", "other")


def test_a_client_span_injects_the_trace_into_headers(spans):
    headers = {"Nats-Auth-Token": "t"}

    with telemetry.client_span("abi.svc.document.v1.get", headers):
        pass

    (span,) = spans.get_finished_spans()
    assert span.name == "document/get" and span.kind is SpanKind.CLIENT
    assert span.attributes["rpc.system"] == "nats"
    assert span.attributes["messaging.destination.name"] == "abi.svc.document.v1.get"
    trace_id = format(span.context.trace_id, "032x")
    assert headers["traceparent"].split("-")[1] == trace_id
    assert headers["Nats-Auth-Token"] == "t"


def test_a_server_span_continues_the_callers_trace(spans):
    headers: dict[str, str] = {}
    with telemetry.client_span("abi.svc.document.v1.get", headers):
        pass
    with telemetry.server_span("abi.svc.document.v1.get", headers):
        telemetry.record_error("NOT_FOUND", "missing")

    client, server = spans.get_finished_spans()
    assert server.kind is SpanKind.SERVER
    assert server.context.trace_id == client.context.trace_id
    assert server.parent.span_id == client.context.span_id
    assert server.status.status_code is StatusCode.ERROR
    assert server.attributes["abi.error_code"] == "NOT_FOUND"


def test_a_failing_block_marks_its_span_and_reraises(spans):
    with pytest.raises(ValueError), telemetry.client_span("abi.svc.kv.v1.get", {}):
        raise ValueError("boom")

    (span,) = spans.get_finished_spans()
    assert span.status.status_code is StatusCode.ERROR


def test_without_a_configured_provider_nothing_is_injected():
    headers: dict[str, str] = {}
    trace.get_tracer_provider()  # the default no-op provider in this process

    with telemetry.client_span("abi.svc.kv.v1.get", headers):
        telemetry.record_error("X")

    assert "traceparent" not in headers


def test_configure_from_env_only_with_an_endpoint(monkeypatch):
    monkeypatch.delenv("OTEL_EXPORTER_OTLP_ENDPOINT", raising=False)
    monkeypatch.delenv("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT", raising=False)
    assert telemetry.configure_from_env("acme.module") is False


def test_internal_spans_nest_under_the_current_one(spans):
    with (
        telemetry.server_span("abi.agent.zen.i.h.v1.submit", {}),
        telemetry.internal_span(
            "agent Researcher run", {"abi.agent.name": "Researcher"}
        ),
    ):
        pass

    child, parent = spans.get_finished_spans()
    assert child.name == "agent Researcher run" and child.kind is SpanKind.INTERNAL
    assert child.parent.span_id == parent.context.span_id
    assert child.attributes["abi.agent.name"] == "Researcher"


def test_calls_record_their_request_and_reply_sizes(spans):
    with telemetry.client_span("abi.svc.keyvalue.v1.get", {}, size=12):
        telemetry.record_reply(345)

    (span,) = spans.get_finished_spans()
    assert span.attributes["messaging.message.body.size"] == 12
    assert span.attributes["abi.reply.body.size"] == 345


def test_a_transfer_is_one_span_with_totals_not_one_per_chunk(spans):
    headers = []
    with telemetry.transfer_span("abi.svc.object_storage.v1.transfer", "put") as stats:
        for size in (100, 64, 64):
            chunk_headers: dict[str, str] = {}
            with telemetry.client_span(
                "abi.svc.object_storage.v1.transfer.x.write",
                chunk_headers,
                size=size,
                transfer=stats,
            ):
                telemetry.record_reply(8, transfer=stats)
            headers.append(chunk_headers)

    (span,) = spans.get_finished_spans()
    assert span.name == "object_storage/transfer.put" and span.kind is SpanKind.CLIENT
    assert span.attributes["abi.transfer.messages"] == 3
    assert span.attributes["abi.transfer.bytes_sent"] == 228
    assert span.attributes["abi.transfer.bytes_received"] == 24
    assert stats.messages == 3
    # Chunks still carry the trace (the transfer span) to the owner.
    trace_id = format(span.context.trace_id, "032x")
    assert all(h["traceparent"].split("-")[1] == trace_id for h in headers)


def test_after_a_transfer_calls_get_their_own_spans_again(spans):
    with (
        telemetry.transfer_span(
            "abi.svc.object_storage.v1.transfer", "get"
        ) as transfer,
        telemetry.client_span(
            "abi.svc.object_storage.v1.transfer.x.read", {}, transfer=transfer
        ),
    ):
        pass
    with telemetry.client_span("abi.svc.keyvalue.v1.get", {}):
        pass

    assert [s.name for s in spans.get_finished_spans()] == [
        "object_storage/transfer.get",
        "keyvalue/get",
    ]


def test_a_transfer_driven_from_several_tasks_still_ends_cleanly(spans):
    """Model streams run the transfer inside an async generator that callers
    (LangChain) advance from different tasks, i.e. different contexts."""
    import asyncio

    async def stream():
        with telemetry.transfer_span(
            "abi.svc.model_registry.v1.transfer", "chat"
        ) as transfer:
            for size in (10, 20):
                headers: dict[str, str] = {}
                with telemetry.client_span(
                    "abi.svc.model_registry.v1.transfer.x.read",
                    headers,
                    size=size,
                    transfer=transfer,
                ):
                    telemetry.record_reply(5, transfer=transfer)
                yield headers

    async def main():
        frames = stream()
        first = await asyncio.create_task(frames.__anext__())
        second = await asyncio.create_task(frames.__anext__())
        with pytest.raises(StopAsyncIteration):
            await asyncio.create_task(frames.__anext__())
        return first, second

    first, second = asyncio.run(main())

    (span,) = spans.get_finished_spans()
    assert span.name == "model_registry/transfer.chat"
    assert span.attributes["abi.transfer.bytes_sent"] == 30
    assert span.attributes["abi.transfer.bytes_received"] == 10
    trace_id = format(span.context.trace_id, "032x")
    assert (
        first["traceparent"].split("-")[1]
        == trace_id
        == second["traceparent"].split("-")[1]
    )


def test_current_trace_id_is_empty_outside_a_span_and_hex_inside(spans):
    assert telemetry.current_trace_id() == ""
    with telemetry.internal_span("work") as span:
        assert telemetry.current_trace_id() == format(
            span.get_span_context().trace_id, "032x"
        )


def test_a_served_transfer_continues_the_callers_transfer_span(spans):
    headers: dict[str, str] = {}
    with telemetry.transfer_span("abi.svc.model_registry.v1.transfer", "chat") as t:
        t.inject(headers)
    served = telemetry.serve_transfer(
        "abi.svc.model_registry.v1.transfer",
        "chat",
        headers,
        attributes={"abi.caller": "api"},
    )
    with served.activate(), telemetry.internal_span("model chat gpt"):
        pass
    served.messages, served.bytes_received, served.bytes_sent = 5, 100, 40
    served.end("closed")
    served.end("expired")  # a session ends once, whoever notices last

    client, child, server = spans.get_finished_spans()
    assert server.name == "model_registry/transfer.chat"
    assert server.kind is SpanKind.SERVER
    assert server.context.trace_id == client.context.trace_id
    assert server.parent.span_id == client.context.span_id
    assert child.parent.span_id == server.context.span_id
    assert server.attributes["rpc.service"] == "model_registry"
    assert server.attributes["abi.transfer.operation"] == "chat"
    assert server.attributes["abi.caller"] == "api"
    assert server.attributes["abi.transfer.end"] == "closed"
    assert server.attributes["abi.transfer.cancelled"] is False
    assert server.attributes["abi.transfer.messages"] == 5
    assert server.attributes["abi.transfer.bytes_received"] == 100
    assert server.attributes["abi.transfer.bytes_sent"] == 40
    assert server.status.status_code is StatusCode.UNSET


def test_a_served_transfer_keeps_the_real_failure_engine_side(spans):
    served = telemetry.serve_transfer("abi.svc.x.v1.transfer", "get", {})
    with served.activate():
        pass
    served.fail(RuntimeError("private details"), "INTERNAL", "Streaming failed")
    served.end("closed")
    served.fail(RuntimeError("after the end"), "INTERNAL")

    (span,) = spans.get_finished_spans()
    assert span.status.status_code is StatusCode.ERROR
    assert span.attributes["abi.error_code"] == "INTERNAL"
    (event,) = span.events
    assert event.name == "exception"
    assert event.attributes["exception.message"] == "private details"


def test_a_served_transfer_is_inert_without_opentelemetry(monkeypatch):
    monkeypatch.setattr(telemetry, "_api", lambda: None)
    served = telemetry.serve_transfer("abi.svc.x.v1.transfer", "get", None)
    with served.activate():
        pass
    served.fail(RuntimeError("x"), "INTERNAL")
    served.end("expired", cancelled=True)
    assert served.span is None


SECRET = "sk-or-v1-0123456789abcdef0123456789abcdef"


def _assert_scrubbed(span):
    assert span.status.status_code is StatusCode.ERROR
    assert SECRET not in (span.status.description or "")
    (event,) = [e for e in span.events if e.name == "exception"]
    assert SECRET not in event.attributes["exception.message"]
    assert SECRET not in event.attributes["exception.stacktrace"]
    assert "[REDACTED]" in event.attributes["exception.message"]
    assert "[REDACTED]" in event.attributes["exception.stacktrace"]
    return event


@pytest.mark.parametrize(
    "opened",
    [
        lambda: telemetry.client_span("abi.svc.kv.v1.get", {}),
        lambda: telemetry.server_span("abi.svc.kv.v1.get", {}),
        lambda: telemetry.internal_span("model chat m"),
    ],
)
def test_failures_escaping_a_span_are_recorded_without_secrets(spans, opened):
    with pytest.raises(PermissionError), opened():
        raise PermissionError(f"401 Unauthorized: invalid key {SECRET}")

    (span,) = spans.get_finished_spans()
    event = _assert_scrubbed(span)
    assert event.attributes["exception.type"] == "PermissionError"
    assert span.status.description.startswith("PermissionError: 401 Unauthorized")


def test_transfers_record_failures_without_secrets(spans):
    with (
        pytest.raises(RuntimeError),
        telemetry.transfer_span("abi.svc.x.v1.transfer", "get"),
    ):
        raise RuntimeError(f"Authorization: Bearer {SECRET}")
    served = telemetry.serve_transfer("abi.svc.x.v1.transfer", "get", {})
    served.fail(RuntimeError(f"api_key={SECRET}"), "INTERNAL", f"failed {SECRET}")
    served.end("closed")

    for span in spans.get_finished_spans():
        _assert_scrubbed(span)


def test_error_codes_and_messages_are_scrubbed(spans):
    with telemetry.server_span("abi.svc.kv.v1.get", {}):
        telemetry.record_error("UNAUTHENTICATED", f"bad token {SECRET}")

    (span,) = spans.get_finished_spans()
    assert span.status.description == "UNAUTHENTICATED: bad token [REDACTED]"
