import asyncio
import threading

import pytest
from naas_abi_core.engine.nats_transfer import (
    TransferError,
    TransferHost,
    stream_thread,
)
from naas_abi_proto.transfer.v1 import transfer_pb2 as pb


async def empty_handler(*args):
    if False:
        yield b""


def test_sequences_caller_capacity_and_upload_budgets():
    async def scenario():
        host = TransferHost(
            "test",
            "secret",
            empty_handler,
            operations=("put",),
            max_sessions=2,
            max_upload_bytes=5,
            max_buffered_upload_bytes=6,
        )

        async def open():
            return (
                await host._execute("open", pb.OpenRequest(operation="put"), "a")
            ).id

        one, two = await open(), await open()
        assert host.sessions[one].source is None
        with pytest.raises(TransferError, match="capacity"):
            await open()
        with pytest.raises(TransferError, match="another caller"):
            await host._execute("write", pb.WriteRequest(id=one), "b")
        await host._execute("write", pb.WriteRequest(id=one, data=b"1234"), "a")
        with pytest.raises(TransferError, match="sequence"):
            await host._execute("write", pb.WriteRequest(id=one, data=b"1"), "a")
        with pytest.raises(TransferError, match="total upload"):
            await host._execute(
                "write", pb.WriteRequest(id=one, sequence=1, data=b"12"), "a"
            )
        with pytest.raises(TransferError, match="budget"):
            await host._execute("write", pb.WriteRequest(id=two, data=b"123"), "a")
        await host._close(one)
        assert host.buffered_upload_bytes == 0
        await host._execute("write", pb.WriteRequest(id=two, data=b"123"), "a")
        await host.stop()
        assert host.buffered_upload_bytes == 0

    asyncio.run(scenario())


def test_stuck_backend_does_not_block_expiry_or_stop_and_keeps_file_open():
    async def scenario():
        entered, release = threading.Event(), threading.Event()
        source = None

        def blocked_read(file):
            entered.set()
            release.wait(5)
            assert not file.closed
            return file.read()

        async def handler(operation, metadata, file):
            nonlocal source
            source = file
            yield await stream_thread(blocked_read, file)

        host = TransferHost(
            "test",
            "secret",
            handler,
            operations=("put",),
            idle_seconds=0.03,
            close_timeout_seconds=0.01,
        )
        one = await host._execute("open", pb.OpenRequest(operation="put"), "a")
        await host._execute("write", pb.WriteRequest(id=one.id, data=b"data"), "a")
        await host._execute("start", pb.StartRequest(id=one.id), "a")
        await asyncio.to_thread(entered.wait, 1)
        host.reaper = asyncio.create_task(host._expire())
        try:
            await asyncio.sleep(0.08)
            assert one.id not in host.sessions
            assert host.retiring and source is not None and not source.closed
            two = await host._execute("open", pb.OpenRequest(operation="put"), "a")
            await asyncio.sleep(0.08)
            assert two.id not in host.sessions
            await asyncio.wait_for(host.stop(), 0.2)
            assert not source.closed
        finally:
            release.set()
            await asyncio.gather(*host.retiring)
        assert source.closed
        assert host.buffered_upload_bytes == 0

    asyncio.run(scenario())


def test_transfer_errors_are_logged_but_sanitized(monkeypatch):
    from unittest.mock import Mock

    from naas_abi_core.engine import nats_transfer

    log = Mock()
    monkeypatch.setattr(nats_transfer, "logger", log)
    host = TransferHost("test", "secret", empty_handler, operations=("get",))
    error = RuntimeError("private backend details")
    assert host._error(error) == ("INTERNAL", "Streaming operation failed")
    log.opt.assert_called_once_with(exception=error)


def test_producer_failure_is_logged_without_a_followup_read(monkeypatch):
    from unittest.mock import Mock

    from naas_abi_core.engine import nats_transfer

    log = Mock()
    monkeypatch.setattr(nats_transfer, "logger", log)

    async def broken(*args):
        raise OSError("private path")
        yield b""

    async def scenario():
        host = TransferHost("test", "secret", broken, operations=("get",))
        opened = await host._execute("open", pb.OpenRequest(operation="get"), "a")
        await host._execute("start", pb.StartRequest(id=opened.id), "a")
        session = host.sessions[opened.id]
        await session.task
        assert session.error.code == "INTERNAL"
        assert "private" not in str(session.error)
        log.opt.assert_called_once()
        await host.stop()

    asyncio.run(scenario())


SECRET = "transfer-unit-test-secret-at-least-32-bytes"
PREFIX = "abi.svc.object_storage.v1.transfer"


@pytest.fixture
def spans(monkeypatch):
    pytest.importorskip("opentelemetry.sdk")
    from naas_abi_sdk import telemetry
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import SimpleSpanProcessor
    from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
        InMemorySpanExporter,
    )

    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    monkeypatch.setattr(telemetry, "_tracer", lambda: provider.get_tracer("test"))
    return exporter


class _Caller:
    """Drives a host through ``_handle`` like the SDK does: one header set
    (token and trace) on every chunk request."""

    def __init__(self, host, headers):
        self.host, self.headers, self.calls = host, headers, 0
        host.packet_bytes = 1024 * 1024  # what start(nc) sets from the broker

    async def __call__(self, operation, request):
        from types import SimpleNamespace
        from unittest.mock import AsyncMock

        from naas_abi_core.engine.nats_transfer import OPERATIONS

        msg = SimpleNamespace(
            data=request.SerializeToString(),
            headers=self.headers,
            reply="inbox",
            respond=AsyncMock(),
            _client=SimpleNamespace(max_payload=1024 * 1024, publish=AsyncMock()),
        )
        await self.host._handle(operation, msg)
        self.calls += 1
        return OPERATIONS[operation][1].FromString(
            msg._client.publish.call_args.args[1]
        )

    async def run(self, operation, upload=b""):
        """open, write, start, read until done or failed, close."""
        opened = await self("open", pb.OpenRequest(operation=operation))
        if upload:
            await self("write", pb.WriteRequest(id=opened.id, data=upload))
        await self("start", pb.StartRequest(id=opened.id))
        data, sequence = b"", 0
        while True:
            read = await self("read", pb.ReadRequest(id=opened.id, sequence=sequence))
            if read.HasField("error") or read.done:
                break
            if read.pending:
                await asyncio.sleep(0.005)
                continue
            data += read.data
            sequence += 1
        await self("close", pb.CloseRequest(id=opened.id))
        return data, read.error


def _headers(caller="api"):
    from naas_abi_core.engine.nats_auth import issue_service_token

    return {"Nats-Auth-Token": issue_service_token(caller, SECRET)}


def test_a_session_span_continues_the_caller_and_parents_the_handler(spans):
    from naas_abi_sdk import telemetry
    from opentelemetry.trace import SpanKind, StatusCode

    def backend_read():
        # Synchronous backend code in a worker thread still nests.
        with telemetry.internal_span("backend read"):
            return b"payload"

    async def handler(operation, metadata, source):
        with telemetry.internal_span("handler"):
            yield await stream_thread(backend_read)

    async def scenario():
        host = TransferHost(PREFIX, SECRET, handler, operations=("get",))
        caller = _Caller(host, _headers())
        with telemetry.transfer_span(PREFIX, "get") as trace:
            trace.inject(caller.headers)
            result = await caller.run("get")
        await host.stop()
        return result, caller.calls

    (data, error), calls = asyncio.run(scenario())

    assert data == b"payload" and not error.code
    finished = spans.get_finished_spans()
    named = {s.name: s for s in finished if s.kind is SpanKind.INTERNAL}
    (client,) = [s for s in finished if s.kind is SpanKind.CLIENT]
    (server,) = [s for s in finished if s.kind is SpanKind.SERVER]
    assert server.name == client.name == "object_storage/transfer.get"
    assert server.context.trace_id == client.context.trace_id
    assert server.parent.span_id == client.context.span_id
    assert named["handler"].parent.span_id == server.context.span_id
    assert named["backend read"].parent.span_id == named["handler"].context.span_id
    assert server.attributes["rpc.system"] == "nats"
    assert server.attributes["rpc.service"] == "object_storage"
    assert server.attributes["abi.transfer.operation"] == "get"
    assert server.attributes["abi.caller"] == "api"
    assert server.attributes["abi.transfer.end"] == "closed"
    assert server.attributes["abi.transfer.cancelled"] is False
    assert server.attributes["abi.transfer.messages"] == calls
    assert server.attributes["abi.transfer.bytes_sent"] == len(b"payload")
    assert server.status.status_code is StatusCode.UNSET


def test_a_failing_handler_fails_the_session_span_not_the_reply(spans, monkeypatch):
    from unittest.mock import Mock

    from naas_abi_core.engine import nats_transfer
    from opentelemetry.trace import SpanKind, StatusCode

    monkeypatch.setattr(nats_transfer, "logger", Mock())

    async def broken(operation, metadata, source):
        raise RuntimeError("private backend details")
        yield b""

    async def scenario():
        host = TransferHost(PREFIX, SECRET, broken, operations=("put",))
        result = await _Caller(host, _headers()).run("put", upload=b"data")
        await host.stop()
        return result

    _, error = asyncio.run(scenario())

    # The caller's reply is sanitized exactly as before.
    assert (error.code, error.message) == ("INTERNAL", "Streaming operation failed")
    (server,) = [s for s in spans.get_finished_spans() if s.kind is SpanKind.SERVER]
    assert server.status.status_code is StatusCode.ERROR
    assert server.attributes["abi.error_code"] == "INTERNAL"
    assert server.attributes["abi.transfer.bytes_received"] == 4
    assert server.attributes["abi.transfer.end"] == "closed"
    (event,) = server.events
    assert event.attributes["exception.type"] == "RuntimeError"
    assert event.attributes["exception.message"] == "private backend details"


def test_close_expiry_and_stop_end_each_session_span_once(spans, caplog):
    from opentelemetry.trace import SpanKind, StatusCode

    started = asyncio.Event()

    async def endless(operation, metadata, source):
        started.set()
        await asyncio.Event().wait()
        yield b""

    async def scenario():
        host = TransferHost(
            PREFIX, SECRET, endless, operations=("get",), idle_seconds=0.03
        )

        async def open():
            return (
                await host._execute("open", pb.OpenRequest(operation="get"), "a")
            ).id

        idle, running = await open(), await open()
        await host._execute("start", pb.StartRequest(id=running), "a")
        await started.wait()
        await host._execute("close", pb.CloseRequest(id=running), "a")
        host.reaper = asyncio.create_task(host._expire())
        await asyncio.sleep(0.1)
        assert idle not in host.sessions
        stopped = await open()
        await host.stop()
        # Late duplicates of a finished session change nothing.
        for key in (idle, running, stopped):
            await host._execute("close", pb.CloseRequest(id=key), "a")
            host._begin_close(key, "closed")

    asyncio.run(scenario())

    servers = [s for s in spans.get_finished_spans() if s.kind is SpanKind.SERVER]
    assert sorted(
        (s.attributes["abi.transfer.end"], s.attributes["abi.transfer.cancelled"])
        for s in servers
    ) == [("closed", True), ("expired", False), ("stopped", False)]
    assert all(s.status.status_code is StatusCode.UNSET for s in servers)
    assert "ended span" not in caplog.text


def test_transfers_are_untraced_without_opentelemetry(monkeypatch):
    from naas_abi_sdk import telemetry

    monkeypatch.setattr(telemetry, "_api", lambda: None)

    async def handler(operation, metadata, source):
        yield b"payload"

    async def scenario():
        host = TransferHost(PREFIX, SECRET, handler, operations=("get",))
        result = await _Caller(host, _headers()).run("get")
        await host.stop()
        return result

    data, error = asyncio.run(scenario())
    assert data == b"payload" and not error.code


# --- thread_frames: a stream produced on one dedicated thread


def test_thread_frames_keep_the_producer_on_one_thread_and_stop_when_abandoned():
    from naas_abi_core.engine.nats_transfer import thread_frames

    threads, emitted, finished = set(), [], threading.Event()

    def produce(emit):
        try:
            for n in range(100):
                threads.add(threading.get_ident())
                if not emit(str(n).encode()):
                    return
                emitted.append(n)
        finally:
            finished.set()  # the backend's context manager exits on its thread

    async def scenario():
        frames = thread_frames(produce, max_queued=2)
        received = [await frames.__anext__() for _ in range(3)]
        await frames.aclose()
        return received

    assert asyncio.run(scenario()) == [b"0", b"1", b"2"]
    assert finished.wait(2)
    assert len(threads) == 1 and threading.get_ident() not in threads
    assert len(emitted) < 10  # back-pressure: it stopped soon after the reader left


def test_thread_frames_raise_the_producers_error_after_its_frames():
    from naas_abi_core.engine.nats_transfer import thread_frames

    def produce(emit):
        emit(b"first")
        raise TransferError("REQUEST_ERROR", "backend aborted")

    async def scenario():
        received = []
        with pytest.raises(TransferError, match="backend aborted"):
            async for frame in thread_frames(produce):
                received.append(frame)
        return received

    assert asyncio.run(scenario()) == [b"first"]
