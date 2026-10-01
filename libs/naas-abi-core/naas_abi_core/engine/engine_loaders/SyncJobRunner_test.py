import asyncio
import threading
import time

import pytest
from naas_abi_core.engine.engine_loaders.SyncJobRunner import (
    JobInterrupted,
    SyncJobRunner,
)
from naas_abi_core.module.jobs import JobContext


def _ctx():
    return JobContext("run-1", "job", 1, {"kind": "manual"}, {})


class _Recorder:
    """Records the job thread so tests can check it really stopped."""

    def __init__(self):
        self.thread: threading.Thread | None = None
        self.reached_end = False

    def started(self):
        self.thread = threading.current_thread()


def test_returns_the_result_from_a_dedicated_thread():
    seen = _Recorder()

    def handler(ctx):
        seen.started()
        return {"rows": 3}

    result = asyncio.run(SyncJobRunner(handler, interrupt_grace_seconds=1)(_ctx()))

    assert result == {"rows": 3}
    assert seen.thread is not threading.main_thread()
    assert seen.thread.name == "abi-job-run-1"


def test_handler_errors_propagate():
    def handler(ctx):
        raise ValueError("bad payload")

    with pytest.raises(ValueError, match="bad payload"):
        asyncio.run(SyncJobRunner(handler, interrupt_grace_seconds=1)(_ctx()))


def test_timeout_interrupts_a_busy_handler_and_waits_for_its_thread():
    seen = _Recorder()

    def handler(ctx):
        seen.started()
        while True:  # ignores ctx.cancelled
            time.sleep(0.01)

    async def scenario():
        task = asyncio.create_task(
            SyncJobRunner(handler, interrupt_grace_seconds=0.1)(_ctx())
        )
        await asyncio.sleep(0.1)
        task.cancel()  # what JobHost does on timeout or close
        with pytest.raises(asyncio.CancelledError):
            await task
        return task

    asyncio.run(scenario())

    assert seen.thread is not None and not seen.thread.is_alive()


def test_cooperative_handlers_stop_before_the_grace_period_ends():
    interrupted = []

    def handler(ctx):
        try:
            while not ctx.cancelled.is_set():
                time.sleep(0.01)
            return "stopped cleanly"
        except JobInterrupted:
            interrupted.append(True)
            raise

    async def scenario():
        ctx = _ctx()
        run = asyncio.create_task(
            SyncJobRunner(handler, interrupt_grace_seconds=5)(ctx)
        )
        await asyncio.sleep(0.05)
        ctx.cancelled.set()  # JobRun.cancel()
        started = time.monotonic()
        result = await run
        return result, time.monotonic() - started

    result, waited = asyncio.run(scenario())

    assert result == "stopped cleanly"
    assert waited < 1 and not interrupted


def test_cancel_request_escalates_to_an_interrupt_after_the_grace_period():
    def handler(ctx):
        while True:
            time.sleep(0.01)

    async def scenario():
        ctx = _ctx()
        run = asyncio.create_task(
            SyncJobRunner(handler, interrupt_grace_seconds=0.1)(ctx)
        )
        await asyncio.sleep(0.05)
        ctx.cancelled.set()
        await run

    with pytest.raises(JobInterrupted):
        asyncio.run(scenario())


def test_without_a_grace_period_the_runner_never_interrupts_but_still_waits():
    seen = _Recorder()

    def handler(ctx):
        seen.started()
        time.sleep(0.3)
        seen.reached_end = True
        return "done"

    async def scenario():
        task = asyncio.create_task(
            SyncJobRunner(handler, interrupt_grace_seconds=None)(_ctx())
        )
        await asyncio.sleep(0.05)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    asyncio.run(scenario())

    assert seen.reached_end and not seen.thread.is_alive()


def test_job_interrupted_is_not_caught_by_except_exception():
    assert not issubclass(JobInterrupted, Exception)
