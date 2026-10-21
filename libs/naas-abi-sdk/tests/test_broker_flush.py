"""flush_to_broker waits for the broker, and keeps nats-py from hiding a timeout."""

import asyncio

import pytest

from naas_abi_sdk.broker_flush import flush_to_broker


class _Client:
    """What nats-py's client does around a flush: its ``_flush_pending``
    swallows ``CancelledError``."""

    def __init__(self, pending_hangs: bool = False) -> None:
        self.pending_hangs = pending_hangs
        self.calls: list[str] = []

    async def _flush_pending(self, force_flush: bool = False) -> None:
        self.calls.append("pending")
        try:
            if self.pending_hangs:
                await asyncio.sleep(3600)
        except asyncio.CancelledError:
            pass

    async def flush(self, timeout: float = 10) -> None:
        self.calls.append("ping")


class _Plain:
    """A client with no ``_flush_pending``: a fake, or another nats-py."""

    def __init__(self) -> None:
        self.calls: list[str] = []

    async def flush(self, timeout: float = 10) -> None:
        self.calls.append("ping")


def test_writes_the_buffer_before_it_pings():
    nc = _Client()
    asyncio.run(flush_to_broker(nc))
    assert nc.calls == ["pending", "ping"]


def test_a_client_without_the_private_flush_gets_the_public_one():
    nc = _Plain()
    asyncio.run(flush_to_broker(nc))
    assert nc.calls == ["ping"]


def test_a_flush_that_hangs_times_out_instead_of_returning():
    nc = _Client(pending_hangs=True)
    with pytest.raises(asyncio.TimeoutError):
        asyncio.run(flush_to_broker(nc, timeout=0.05))
    # It stopped there: the ping would only tell nothing about the buffer.
    assert nc.calls == ["pending"]


def test_a_cancelled_caller_is_cancelled():
    async def scenario() -> None:
        nc = _Client(pending_hangs=True)
        task = asyncio.ensure_future(flush_to_broker(nc, timeout=30))
        await asyncio.sleep(0.05)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert nc.calls == ["pending"]

    asyncio.run(scenario())
