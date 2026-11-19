"""``call_each``: every child gets its run, a failed one is reported, not raised."""

from __future__ import annotations

import asyncio

import pytest
from naas_abi_apps.x.flows.conftest import FakeFlowContext
from naas_abi_apps.x.flows.fanout import (
    FetchFailed,
    FlowIncomplete,
    call_each,
    describe_failures,
)
from naas_abi_sdk.jobs import NonRetryable
from naas_abi_sdk.workflows import ChildRunFailed, WorkflowCancelled


def run(children, inputs, concurrency=3, **kwargs):
    ctx = FakeFlowContext(children=children)
    out = asyncio.run(
        call_each(ctx, "map", "mod", "wf", inputs, concurrency=concurrency, **kwargs)
    )
    return ctx, out


def test_outputs_keep_the_order_of_the_inputs_and_each_child_is_a_keyed_step():
    ctx, (outputs, failures) = run(
        lambda wf, i: i["n"] * 10, [{"n": n} for n in range(5)]
    )
    assert outputs == [0, 10, 20, 30, 40] and failures == {}
    assert sorted(ctx.journal) == [f"map[{i}]" for i in range(5)]


def test_a_failed_child_is_collected_and_the_others_still_run():
    def children(wf, i):
        if i["n"] == 1:
            raise ChildRunFailed("child run ended FAILED: boom")
        return i["n"]

    _, (outputs, failures) = run(children, [{"n": n} for n in range(4)])
    assert outputs == [0, None, 2, 3]
    assert failures == {1: "child run ended FAILED: boom"}


def test_a_skipped_child_is_not_a_failure():
    _, (outputs, failures) = run(lambda wf, i: None, [{"n": 0}])
    assert outputs == [None] and failures == {}


def test_a_cancel_is_not_swallowed_as_a_failed_child():
    def children(wf, i):
        raise WorkflowCancelled("run was cancelled")

    with pytest.raises(WorkflowCancelled):
        run(children, [{"n": 0}, {"n": 1}])


def test_a_cancel_stops_the_children_still_waiting():
    started: list[int] = []

    async def children(wf, i):
        started.append(i["n"])
        if i["n"] == 0:
            raise WorkflowCancelled("run was cancelled")
        await asyncio.sleep(10)

    with pytest.raises(WorkflowCancelled):
        run(children, [{"n": n} for n in range(4)], concurrency=2)
    assert 3 not in started  # the children still waiting for a slot never start


def test_at_most_concurrency_children_run_at_once():
    running, peak = 0, 0

    async def children(wf, i):
        nonlocal running, peak
        running += 1
        peak = max(peak, running)
        await asyncio.sleep(0.01)
        running -= 1
        return i["n"]

    _, (outputs, _) = run(children, [{"n": n} for n in range(7)], concurrency=3)
    assert outputs == list(range(7)) and peak == 3


def test_a_failed_fetch_is_not_retried_and_a_failed_stage_is():
    assert issubclass(FetchFailed, FlowIncomplete)
    assert issubclass(FetchFailed, NonRetryable)
    assert not issubclass(FlowIncomplete, NonRetryable)


def test_no_inputs_starts_nothing():
    ctx, (outputs, failures) = run(lambda wf, i: 1, [])
    assert (outputs, failures, ctx.called) == ([], {}, [])


def test_the_failures_are_described_with_their_paths():
    paths = ["a", "b", "c", "d", "e"]
    text = describe_failures("mapping", paths, {0: "x", 3: "y", 4: "z"}, shown=2)
    assert text == "mapping failed for 3 of 5 envelope(s): a: x; d: y (and 1 more)"
