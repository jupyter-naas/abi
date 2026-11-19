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

import asyncio
from collections.abc import Iterable
from typing import Any

from naas_abi_sdk.jobs import NonRetryable
from naas_abi_sdk.workflows import ChildRunFailed

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


async def call_each(
    ctx: Any,
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
    index of each failed child to its error. ``ctx`` is the run's ``FlowContext``.
    Anything but a failed child (a cancel, a truncated output) stops the others
    and goes up; a retry re-attaches to the children that were started.
    """
    items = list(inputs)
    outputs: list[Any] = [None] * len(items)
    failures: dict[int, str] = {}
    if not items:
        return outputs, failures
    slots = asyncio.Semaphore(max(1, concurrency))

    async def one(index: int) -> None:
        async with slots:
            try:
                outputs[index] = await ctx.call(
                    module_id, workflow, items[index], key=f"{key}[{index}]"
                )
            except ChildRunFailed as error:
                failures[index] = str(error)[:MAX_ERROR_CHARS]

    tasks = [asyncio.ensure_future(one(index)) for index in range(len(items))]
    try:
        await asyncio.gather(*tasks)
    except BaseException:
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        raise
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
