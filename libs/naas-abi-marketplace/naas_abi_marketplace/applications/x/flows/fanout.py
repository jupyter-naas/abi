"""Fan-out over child runs that tolerates a failed child.

``ctx.map_call`` raises on the first child that fails and stops the others: one bad
envelope would stop the dataset sync and the app publish of all the good ones. The
Dagster flow ran one job per envelope, so a bad one only affected itself. This does
the same over ``ctx.call``: every child runs, the failures are collected, and the
handler goes on with what worked and reports the rest at the end.

Each child is the step ``key[i]``, so a retry of the run finds the finished children
in the journal and starts a new child only for one that failed.
"""

from __future__ import annotations

import contextvars
from collections.abc import Iterable
from concurrent.futures import FIRST_EXCEPTION, ThreadPoolExecutor, wait
from typing import Any

from naas_abi_core.module.workflows import POLL_SECONDS, ChildRunFailed, NonRetryable

MAX_ERROR_CHARS = 300


class FlowIncomplete(RuntimeError):
    """A run did what it could and reports what it could not.

    Raised after every stage that could still run did: the message says what
    succeeded and what failed, so a FAILED run does not hide the work it did."""


class FetchFailed(FlowIncomplete, NonRetryable):
    """``FlowIncomplete`` for a run whose fetch failed: it ends FAILED without a retry.

    The fetch is a journaled step, so every attempt would replay the same failure
    while the RETRYING run made the next ticks of its filter skip. The next tick
    fetches again, from the ``since_id`` cursor."""


def call_each(
    ctx,
    key: str,
    module_id: str,
    workflow: str,
    inputs: Iterable[Any],
    *,
    concurrency: int,
) -> tuple[list[Any], dict[int, str]]:
    """One child run of *workflow* per input, *concurrency* at a time.

    Returns ``(outputs, failures)``: ``outputs[i]`` is the child's output (``None``
    for a child that ended SKIPPED, and for a failed one), ``failures`` maps the
    index of each failed child to its error. ``ctx`` is a ``SyncFlowContext``.
    """
    items = list(inputs)
    outputs: list[Any] = [None] * len(items)
    failures: dict[int, str] = {}
    if not items:
        return outputs, failures

    def one(index: int) -> None:
        try:
            outputs[index] = ctx.call(
                module_id, workflow, items[index], key=f"{key}[{index}]"
            )
        except ChildRunFailed as error:
            failures[index] = str(error)[:MAX_ERROR_CHARS]

    pool = ThreadPoolExecutor(
        max_workers=max(1, min(concurrency, len(items))),
        thread_name_prefix=f"x-{key}",
    )
    try:
        pending = {
            pool.submit(contextvars.copy_context().run, one, index)
            for index in range(len(items))
        }
        # Wake regularly: a blocking wait would hold off the run's JobInterrupted.
        while pending:
            done, pending = wait(
                pending, timeout=POLL_SECONDS, return_when=FIRST_EXCEPTION
            )
            for future in done:  # anything but a failed child (a cancel) goes up
                future.result()
    except BaseException:
        # Interrupted, or cancelled: do not hold the handler (and its slot) for the
        # children it waits on. A retry re-attaches to them.
        pool.shutdown(wait=False, cancel_futures=True)
        raise
    pool.shutdown()
    return outputs, failures


def describe_failures(
    what: str, paths: list[str], failures: dict[int, str], shown: int = 3
) -> str:
    """``mapping failed for 2 of 5 envelope(s): path: error; ...``"""
    first = "; ".join(f"{paths[i]}: {failures[i]}" for i in sorted(failures)[:shown])
    more = f" (and {len(failures) - shown} more)" if len(failures) > shown else ""
    return (
        f"{what} failed for {len(failures)} of {len(paths)} envelope(s): {first}{more}"
    )
