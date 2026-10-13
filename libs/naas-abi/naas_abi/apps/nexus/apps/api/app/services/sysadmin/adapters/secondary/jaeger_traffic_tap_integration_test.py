"""The span tap against a real Jaeger v2 (skipped without the `jaeger` binary)."""

import asyncio
import contextlib
import shutil
import socket
import subprocess
import time

import pytest
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.adapters.secondary.jaeger_traffic_tap import (
    JaegerSpanTap,
)

pytestmark = pytest.mark.integration

CONFIG = """
service:
  extensions: [jaeger_storage, jaeger_query]
  pipelines:
    traces:
      receivers: [otlp]
      processors: [batch]
      exporters: [jaeger_storage_exporter]
  telemetry:
    metrics:
      level: none
extensions:
  jaeger_query:
    storage:
      traces: memstore
    http:
      endpoint: 127.0.0.1:{query}
    grpc:
      endpoint: 127.0.0.1:{grpc}
  jaeger_storage:
    backends:
      memstore:
        memory:
          max_traces: 1000
receivers:
  otlp:
    protocols:
      http:
        endpoint: 127.0.0.1:{otlp}
processors:
  batch:
    timeout: 100ms
exporters:
  jaeger_storage_exporter:
    trace_storage: memstore
"""


def _port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


@contextlib.contextmanager
def run_jaeger(directory):
    """A memstore Jaeger v2: yields (query url, OTLP HTTP url); skips without the binary."""
    binary = shutil.which("jaeger")
    if binary is None:
        pytest.skip("jaeger is not installed")
    query, grpc, otlp = _port(), _port(), _port()
    config = directory / "jaeger.yaml"
    config.write_text(CONFIG.format(query=query, grpc=grpc, otlp=otlp))
    process = subprocess.Popen(
        [binary, "--config", str(config)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        env={"OTEL_TRACES_EXPORTER": "none", "PATH": "/usr/bin:/bin"},
    )
    try:
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            try:
                with socket.create_connection(("127.0.0.1", query), timeout=0.2):
                    break
            except OSError:
                time.sleep(0.1)
        yield f"http://127.0.0.1:{query}", f"http://127.0.0.1:{otlp}"
    finally:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:  # Jaeger drains slowly on SIGTERM
            process.kill()
            process.wait(timeout=5)


@pytest.fixture
def jaeger(tmp_path):
    with run_jaeger(tmp_path) as urls:
        yield urls


def test_calls_and_transfers_recorded_by_abi_show_up_as_traffic(jaeger, monkeypatch):
    from naas_abi_sdk import telemetry
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import SimpleSpanProcessor

    query_url, otlp_url = jaeger
    provider = TracerProvider(resource=Resource.create({"service.name": "itest-engine"}))
    provider.add_span_processor(
        SimpleSpanProcessor(OTLPSpanExporter(endpoint=f"{otlp_url}/v1/traces"))
    )
    monkeypatch.setattr(telemetry, "_tracer", lambda: provider.get_tracer("itest"))

    with telemetry.client_span("abi.svc.document.v1.get", {}, size=12):
        telemetry.record_reply(340)
    with telemetry.transfer_span("abi.svc.object_storage.v1.transfer", "put") as transfer:
        for _ in range(3):
            with telemetry.client_span(
                "abi.svc.object_storage.v1.transfer.x.write", {}, size=1000, transfer=transfer
            ):
                telemetry.record_reply(8, transfer=transfer)
    provider.force_flush()

    seen = []

    async def scenario():
        tap = JaegerSpanTap(query_url, poll_seconds=0.2)
        await tap.start(seen.append)
        deadline = asyncio.get_running_loop().time() + 10
        while len(seen) < 2 and asyncio.get_running_loop().time() < deadline:
            await asyncio.sleep(0.2)
        await tap.stop()

    asyncio.run(scenario())

    by_method = {(e.service, e.method): e for e in seen}
    get = by_method[("document", "get")]
    assert (get.caller, get.request_bytes, get.reply_bytes, get.status) == (
        "itest-engine",
        12,
        340,
        "ok",
    )
    put = by_method[("object_storage", "transfer.put")]
    assert (put.kind, put.request_bytes, put.reply_bytes) == ("transfer", 3000, 24)
    assert len(seen) == 2  # the transfer's chunks are not rows of their own
