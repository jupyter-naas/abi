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
