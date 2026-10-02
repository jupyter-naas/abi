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
            await tap.unsubscribe()
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
