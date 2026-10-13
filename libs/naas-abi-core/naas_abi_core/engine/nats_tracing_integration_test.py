"""Trace context across a real broker: core client -> traced kernel service."""

import asyncio
import shutil
import socket
import subprocess
import time
from unittest.mock import Mock

import pytest

pytest.importorskip("opentelemetry.sdk")

import nats
from naas_abi_core.engine import nats_tracing
from naas_abi_core.services.keyvalue.adapters.primary.keyvalue__primary_adapter__NATS import (
    KeyValuePrimaryAdapterNATS,
)
from naas_abi_core.services.keyvalue.adapters.secondary.KeyValueSecondaryAdapterNATSClient import (
    KeyValueSecondaryAdapterNATSClient,
)
from naas_abi_core.services.keyvalue.KeyValuePorts import (
    IKeyValueAdapter,
    KVNotFoundError,
)
from naas_abi_sdk import telemetry
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
    InMemorySpanExporter,
)
from opentelemetry.trace import SpanKind, StatusCode

SECRET = "tracing-integration-secret-32-bytes!"
pytestmark = pytest.mark.integration


@pytest.fixture
def broker(tmp_path):
    binary = shutil.which("nats-server")
    if binary is None:
        pytest.skip("nats-server is not installed")
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    process = subprocess.Popen(
        [binary, "-a", "127.0.0.1", "-p", str(port)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            try:
                with socket.create_connection(("127.0.0.1", port), timeout=0.1):
                    break
            except OSError:
                time.sleep(0.01)
        yield f"nats://127.0.0.1:{port}"
    finally:
        process.terminate()
        process.wait(timeout=5)


def test_a_kernel_call_is_one_trace_from_caller_to_service(broker, monkeypatch):
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    tracer = provider.get_tracer("test")
    monkeypatch.setattr(telemetry, "_tracer", lambda: tracer)
    reply_headers = []

    async def scenario():
        nc = await nats.connect(broker)
        backend = Mock(spec=IKeyValueAdapter)

        def get(key):
            if key != "present":
                raise KVNotFoundError(key)
            return b"v"

        backend.get.side_effect = get
        primary = KeyValuePrimaryAdapterNATS(backend, SECRET)
        client = KeyValueSecondaryAdapterNATSClient(broker, SECRET, "test")

        async def record(msg):
            if msg.headers:
                reply_headers.append(dict(msg.headers))

        tap = await nc.subscribe("_INBOX.>", cb=record)
        try:
            await primary.start(nc)
            await nc.flush()
            with tracer.start_as_current_span("chat request"):
                assert await asyncio.to_thread(client.get, "present") == b"v"
                with pytest.raises(KVNotFoundError):
                    await asyncio.to_thread(client.get, "missing")
        finally:
            # The tap gets its copy of a reply after the client does. The round
            # trip queues every copy, and drain hands the queued ones to the
            # callback before unsubscribing (unsubscribe would drop them).
            await nc.flush()
            await tap.drain()
            await asyncio.to_thread(client.close)
            await primary.stop()
            await nc.close()

    asyncio.run(scenario())

    spans = {
        (s.kind, s.attributes.get("abi.error_code")): s
        for s in exporter.get_finished_spans()
    }
    root = next(s for s in exporter.get_finished_spans() if s.name == "chat request")
    ok_client = spans[(SpanKind.CLIENT, None)]
    ok_server = spans[(SpanKind.SERVER, None)]
    failed_client = spans[(SpanKind.CLIENT, "KV_NOT_FOUND")]
    failed_server = spans[(SpanKind.SERVER, "KV_NOT_FOUND")]

    assert {s.context.trace_id for s in spans.values()} == {root.context.trace_id}
    assert ok_client.parent.span_id == root.context.span_id
    assert ok_server.parent.span_id == ok_client.context.span_id
    assert ok_server.name == "keyvalue/get"
    assert failed_server.parent.span_id == failed_client.context.span_id
    assert failed_server.status.status_code is StatusCode.ERROR
    assert failed_client.status.status_code is StatusCode.ERROR
    assert {"Abi-Error-Code": "KV_NOT_FOUND"} in reply_headers


def test_a_chunked_upload_is_one_span_with_its_totals(broker, monkeypatch, tmp_path):
    from naas_abi_core.services.object_storage.adapters.primary.object_storage__primary_adapter__NATS import (
        ObjectStoragePrimaryAdapterNATS,
    )
    from naas_abi_core.services.object_storage.adapters.secondary.ObjectStorageSecondaryAdapterFS import (
        ObjectStorageSecondaryAdapterFS,
    )
    from naas_abi_core.services.object_storage.adapters.secondary.ObjectStorageSecondaryAdapterNATSClient import (
        ObjectStorageSecondaryAdapterNATSClient,
    )
    from naas_abi_core.services.object_storage.ObjectStorageService import (
        ObjectStorageService,
    )

    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    tracer = provider.get_tracer("test")
    monkeypatch.setattr(telemetry, "_tracer", lambda: tracer)
    content = b"z" * 300_000

    async def scenario():
        nc = await nats.connect(broker)
        owner = ObjectStorageService(ObjectStorageSecondaryAdapterFS(str(tmp_path)))
        primary = ObjectStoragePrimaryAdapterNATS(owner, SECRET)
        client = ObjectStorageSecondaryAdapterNATSClient(broker, SECRET, "test")
        try:
            await primary.start(nc)
            await nc.flush()
            await asyncio.to_thread(client.put_object, "drive", "big.bin", content)
            assert (
                await asyncio.to_thread(client.get_object, "drive", "big.bin")
                == content
            )
        finally:
            await asyncio.to_thread(client.close)
            await primary.stop()
            await nc.close()

    asyncio.run(scenario())

    clients = [s for s in exporter.get_finished_spans() if s.kind is SpanKind.CLIENT]
    assert [s.name for s in clients] == [
        "object_storage/transfer.put",
        "object_storage/transfer.get",
    ]
    put, get = clients
    assert put.attributes["abi.transfer.bytes_sent"] >= 300_000
    assert put.attributes["abi.transfer.messages"] >= 5
    assert get.attributes["abi.transfer.bytes_received"] >= 300_000


def test_a_remote_model_call_is_one_trace_through_the_engine(broker, monkeypatch):
    """SDK model proxy -> transfer -> engine session span -> model span."""
    from langchain_core.language_models.fake_chat_models import FakeListChatModel
    from naas_abi_core.engine.nats_auth import issue_service_token
    from naas_abi_core.models.Model import ChatModel
    from naas_abi_core.services.model_registry.adapters.primary.model_registry_nats import (
        ModelRegistryNATS,
    )
    from naas_abi_core.services.model_registry.ModelRegistryService import (
        ModelRegistryService,
    )
    from naas_abi_sdk import ABIClient
    from naas_abi_sdk.services.model_registry import (
        ModelRegistryService as RemoteRegistry,
    )
    from naas_abi_sdk.transport import RPCError

    class BrokenModel(FakeListChatModel):
        async def _agenerate(self, *args, **kwargs):
            raise RuntimeError("private provider details")

    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    tracer = provider.get_tracer("test")
    monkeypatch.setattr(telemetry, "_tracer", lambda: tracer)

    async def scenario():
        owner = ModelRegistryService()
        owner.register(
            "chat",
            ChatModel(
                model_id="fake",
                provider="test",
                model=FakeListChatModel(responses=["answer"]),
            ),
        )
        owner.register(
            "broken",
            ChatModel(
                model_id="broken", provider="test", model=BrokenModel(responses=[""])
            ),
        )
        nc = await nats.connect(broker)
        primary = ModelRegistryNATS(owner, SECRET)
        try:
            await primary.start(nc)
            token = issue_service_token("module", SECRET)
            async with ABIClient(broker, token) as client:
                registry = RemoteRegistry(client.model_registry)
                chat = (await registry.get_chat_model("chat")).model
                broken = (await registry.get_chat_model("broken")).model
                with tracer.start_as_current_span("agent turn"):
                    assert (await chat.ainvoke("hello")).content == "answer"
                    with pytest.raises(RPCError) as failure:
                        await broken.ainvoke("hello")
            # The caller still only sees the sanitized error.
            assert failure.value.code == "MODEL_ERROR"
            assert "private" not in str(failure.value)
        finally:
            await primary.stop()
            await nc.close()

    asyncio.run(scenario())

    finished = exporter.get_finished_spans()
    root = next(s for s in finished if s.name == "agent turn")
    turn = [s for s in finished if s.context.trace_id == root.context.trace_id]
    clients = {s.context.span_id: s for s in turn if s.kind is SpanKind.CLIENT}
    servers = {s.name: s for s in turn if s.kind is SpanKind.SERVER}
    models = {s.name: s for s in turn if s.name.startswith("model ")}
    assert [s.name for s in clients.values()] == ["model_registry/transfer.chat"] * 2
    assert all(s.parent.span_id == root.context.span_id for s in clients.values())
    assert set(models) == {"model chat chat", "model chat broken"}
    (served,) = set(servers)
    assert served == "model_registry/transfer.chat"
    sessions = [s for s in turn if s.kind is SpanKind.SERVER]
    assert len(sessions) == 2
    assert all(s.parent.span_id in clients for s in sessions)
    ok, failed = sorted(sessions, key=lambda s: s.status.status_code.value)
    assert ok.status.status_code is StatusCode.UNSET
    assert ok.attributes["abi.caller"] == "module"
    assert ok.attributes["abi.transfer.end"] == "closed"
    assert models["model chat chat"].parent.span_id == ok.context.span_id
    assert models["model chat broken"].parent.span_id == failed.context.span_id
    assert models["model chat chat"].attributes["abi.model.provider"] == "test"
    # The real cause is on the engine span, in the caller's trace.
    assert failed.status.status_code is StatusCode.ERROR
    assert failed.attributes["abi.error_code"] == "MODEL_ERROR"
    assert [e.attributes["exception.message"] for e in failed.events] == [
        "private provider details"
    ]
    failed_client = clients[failed.parent.span_id]
    assert failed_client.status.status_code is StatusCode.ERROR


# --- calls side by side, over a real broker ------------------------------------------------


async def _slow_service(url, *, max_concurrency, seconds=0.5, fail=False):
    """A traced service whose one endpoint takes ``seconds`` and records its peak."""
    nc = await nats.connect(url)
    state = {"running": 0, "peak": 0, "started": 0}

    async def handler(request):
        state["started"] += 1
        state["running"] += 1
        state["peak"] = max(state["peak"], state["running"])
        try:
            await asyncio.sleep(seconds)
            if fail:
                raise RuntimeError("the handler failed")
            await request.respond(b"ok")
        finally:
            state["running"] -= 1

    service = await nats_tracing.add_traced_service(
        nc, name="slow", version="1.0.0", max_concurrency=max_concurrency
    )
    await service.add_endpoint(name="wait", subject="test.slow.wait", handler=handler)
    return nc, service, state


def test_an_endpoint_answers_its_calls_side_by_side(broker):
    async def scenario():
        nc, service, state = await _slow_service(broker, max_concurrency=8)
        client = await nats.connect(broker)
        try:
            start = time.monotonic()
            replies = await asyncio.gather(
                *(client.request("test.slow.wait", b"", timeout=5) for _ in range(4))
            )
            elapsed = time.monotonic() - start
            (stats,) = service.stats().endpoints
        finally:
            await service.stop()
            await client.close()
            await nc.close()
        return replies, elapsed, stats, state

    replies, elapsed, stats, state = asyncio.run(scenario())

    assert [reply.data for reply in replies] == [b"ok"] * 4
    assert elapsed < 1.5  # one call at a time would take 2 s
    assert state["peak"] == 4
    # nats.micro's own statistics still cover the whole call.
    assert stats.num_requests == 4
    assert stats.average_processing_time >= 0.5e9


def test_a_service_runs_at_most_max_concurrency_calls_at_once(broker):
    async def scenario():
        nc, service, state = await _slow_service(broker, max_concurrency=2, seconds=0.2)
        client = await nats.connect(broker)
        try:
            replies = await asyncio.gather(
                *(client.request("test.slow.wait", b"", timeout=5) for _ in range(6))
            )
        finally:
            await service.stop()
            await client.close()
            await nc.close()
        return replies, state

    replies, state = asyncio.run(scenario())

    assert [reply.data for reply in replies] == [b"ok"] * 6
    assert state["peak"] == 2


def test_a_handler_that_raises_is_still_answered_with_a_500(broker):
    async def scenario():
        nc, service, _ = await _slow_service(
            broker, max_concurrency=8, seconds=0, fail=True
        )
        client = await nats.connect(broker)
        try:
            reply = await client.request("test.slow.wait", b"", timeout=5)
            (stats,) = service.stats().endpoints
        finally:
            await service.stop()
            await client.close()
            await nc.close()
        return reply, stats

    reply, stats = asyncio.run(scenario())

    assert reply.headers["Nats-Service-Error-Code"] == "500"
    assert stats.num_errors == 1


def test_a_drain_answers_the_calls_already_received(broker):
    async def scenario():
        nc, service, state = await _slow_service(broker, max_concurrency=8)
        client = await nats.connect(broker)
        try:
            calls = [
                asyncio.create_task(client.request("test.slow.wait", b"", timeout=5))
                for _ in range(3)
            ]
            deadline = time.monotonic() + 5
            while state["started"] < 3:
                assert time.monotonic() < deadline, "the calls did not start"
                await asyncio.sleep(0.01)
            await service.stop_accepting()
            await asyncio.wait_for(service.requests_finished(), timeout=5)
            replies = await asyncio.gather(*calls)
        finally:
            await service.stop()
            await client.close()
            await nc.close()
        return replies

    replies = asyncio.run(scenario())

    assert [reply.data for reply in replies] == [b"ok"] * 3


def test_a_kernel_service_runs_its_synchronous_calls_on_parallel_threads(broker):
    async def scenario():
        nc = await nats.connect(broker)
        backend = Mock(spec=IKeyValueAdapter)

        def get(key):
            time.sleep(0.5)  # a backend round trip, on a dispatcher thread
            return b"v"

        backend.get.side_effect = get
        primary = KeyValuePrimaryAdapterNATS(backend, SECRET)
        client = KeyValueSecondaryAdapterNATSClient(broker, SECRET, "test")
        try:
            await primary.start(nc)
            await nc.flush()
            start = time.monotonic()
            values = await asyncio.gather(
                *(asyncio.to_thread(client.get, "present") for _ in range(4))
            )
            elapsed = time.monotonic() - start
        finally:
            await asyncio.to_thread(client.close)
            await primary.stop()
            await nc.close()
        return values, elapsed

    values, elapsed = asyncio.run(scenario())

    assert values == [b"v"] * 4
    assert elapsed < 1.5  # one call at a time would take 2 s
