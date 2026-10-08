"""A subscription's messages run side by side, a bounded number at once."""

import asyncio

import pytest

from naas_abi_sdk.concurrency import DEFAULT_LIMIT, ConcurrentCalls


async def _until(predicate, timeout=2.0):
    deadline = asyncio.get_running_loop().time() + timeout
    while not predicate():
        assert asyncio.get_running_loop().time() < deadline, "timed out"
        await asyncio.sleep(0.005)


class _Calls:
    """A subscription callback whose calls wait until released."""

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


def test_64_calls_run_at_once_by_default():
    assert DEFAULT_LIMIT == 64
    assert ConcurrentCalls().limit == 64


def test_a_limit_below_one_is_refused():
    with pytest.raises(ValueError):
        ConcurrentCalls(0)


def test_calls_run_side_by_side():
    async def scenario():
        calls = ConcurrentCalls(4)
        handler = _Calls()
        receive = calls.callback(handler)
        for msg in range(3):
            await receive(msg)  # returns at once: the next message can come
        await _until(lambda: len(handler.started) == 3)
        assert calls.in_flight == 3
        handler.release.set()
        await calls.idle()
        return handler

    assert asyncio.run(scenario()).peak == 3


def test_beyond_the_limit_a_call_waits_for_a_free_slot():
    async def scenario():
        calls = ConcurrentCalls(2)
        handler = _Calls()
        receive = calls.callback(handler)
        await receive(0)
        await receive(1)
        third = asyncio.create_task(receive(2))
        await asyncio.sleep(0.05)
        assert not third.done()  # the subscription holds its next messages
        assert handler.started == [0, 1]
        # Counted while it waits: idle() waits for it too.
        assert calls.in_flight == 3
        handler.release.set()
        await third
        await calls.idle()
        return handler

    handler = asyncio.run(scenario())

    assert handler.started == [0, 1, 2]
    assert handler.peak == 2


def test_idle_waits_for_the_calls_received():
    async def scenario():
        calls = ConcurrentCalls(4)
        handler = _Calls()
        await calls.callback(handler)(0)
        await _until(lambda: handler.running == 1)
        waiting = asyncio.create_task(calls.idle())
        await asyncio.sleep(0.05)
        assert not waiting.done()
        handler.release.set()
        await asyncio.wait_for(waiting, timeout=2)

    asyncio.run(scenario())


def test_cancel_stops_the_calls_still_running():
    async def scenario():
        calls = ConcurrentCalls(4)
        handler = _Calls()
        receive = calls.callback(handler)
        await receive(0)
        await receive(1)
        await _until(lambda: handler.running == 2)
        await calls.cancel()
        return calls, handler

    calls, handler = asyncio.run(scenario())

    assert handler.running == 0
    assert calls.in_flight == 0


def test_a_call_that_fails_frees_its_slot():
    async def scenario():
        calls = ConcurrentCalls(1)
        answered = []

        async def handle(msg):
            if msg == "broken":
                raise ConnectionError("the reply could not be sent")
            answered.append(msg)

        receive = calls.callback(handle)
        await receive("broken")
        await receive("next")
        await calls.idle()
        return answered

    assert asyncio.run(scenario()) == ["next"]
