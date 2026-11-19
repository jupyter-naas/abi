"""Expensive work runs off the event loop, a few at a time, a bounded number a
minute per caller."""

from __future__ import annotations

import asyncio
import threading

import pytest
from fastapi import HTTPException
from naas_abi.apps.nexus.apps.api.app.core.bounded_work import BoundedWork


class Clock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


async def _status(work: BoundedWork, caller: str, fn=lambda: "ok") -> int:
    try:
        await work.run(caller, fn)
        return 200
    except HTTPException as exc:
        return exc.status_code


def test_bounded_work_keeps_a_per_caller_rate() -> None:
    clock = Clock()
    work = BoundedWork("tests", concurrent=2, per_user=3, window_seconds=60, clock=clock)

    async def scenario() -> list[int]:
        codes = [await _status(work, "ada") for _ in range(4)]
        codes.append(await _status(work, "bob"))  # another caller has their own
        clock.now += 60
        codes.append(await _status(work, "ada"))
        return codes

    assert asyncio.run(scenario()) == [200, 200, 200, 429, 200, 200]
    with pytest.raises(HTTPException) as refused:
        asyncio.run(work.run("ada", lambda: 1))
        asyncio.run(work.run("ada", lambda: 1))
        asyncio.run(work.run("ada", lambda: 1))
    assert int(refused.value.headers["Retry-After"]) == 60


def test_bounded_work_keeps_a_ceiling_of_concurrent_jobs() -> None:
    work = BoundedWork("tests", concurrent=1, per_user=100)
    inside = threading.Event()
    release = threading.Event()

    def held() -> str:
        inside.set()
        release.wait(5)
        return "done"

    async def scenario() -> tuple[str, int, int]:
        first = asyncio.create_task(work.run("ada", held))
        await asyncio.to_thread(inside.wait, 5)
        busy = await _status(work, "bob")
        release.set()
        result = await first
        return result, busy, await _status(work, "bob")

    assert asyncio.run(scenario()) == ("done", 429, 200)


def test_bounded_work_keeps_its_slot_while_work_outlives_its_request() -> None:
    """A request that goes away does not free the slot of the work still running."""
    work = BoundedWork("tests", concurrent=1, per_user=100)
    inside = threading.Event()
    release = threading.Event()
    finished = threading.Event()

    def held() -> None:
        inside.set()
        release.wait(5)
        finished.set()

    async def scenario() -> tuple[int, int]:
        request = asyncio.create_task(work.run("ada", held))
        await asyncio.to_thread(inside.wait, 5)
        request.cancel()  # the client went away
        with pytest.raises(asyncio.CancelledError):
            await request
        while_running = await _status(work, "bob")
        release.set()
        await asyncio.to_thread(finished.wait, 5)
        await asyncio.sleep(0.05)
        return while_running, await _status(work, "bob")

    assert asyncio.run(scenario()) == (429, 200)


def test_a_busy_refusal_keeps_the_callers_budget() -> None:
    work = BoundedWork("tests", concurrent=1, per_user=2)
    inside = threading.Event()
    release = threading.Event()

    def held() -> None:
        inside.set()
        release.wait(5)

    async def scenario() -> list[int]:
        first = asyncio.create_task(work.run("ada", held))
        await asyncio.to_thread(inside.wait, 5)
        busy = [await _status(work, "bob") for _ in range(5)]
        release.set()
        await first
        return busy + [await _status(work, "bob"), await _status(work, "bob")]

    assert asyncio.run(scenario()) == [429] * 5 + [200, 200]


def test_bounded_work_keeps_the_event_loop_free() -> None:
    work = BoundedWork("tests", concurrent=2, per_user=10)

    async def scenario() -> tuple[int, int]:
        loop_thread = threading.get_ident()
        ran_in = await work.run("ada", threading.get_ident)
        return loop_thread, ran_in

    loop_thread, ran_in = asyncio.run(scenario())
    assert loop_thread != ran_in
