"""Job bodies, kept apart from the module class so they test without a broker.

A job is declared on ``ABIModule`` with ``@job(..., triggers=(...))``:
``Every("1h")``, ``Cron("0 0 2 * * *")`` or ``OnEvent(...)``. JetStream fires the
trigger and one replica of this module runs it. Delivery is at least once, so a
job must tolerate running twice.

A workflow is a job with a typed input and output and checkpointed steps:
``@workflow(...)`` on a method taking ``(self, ctx: FlowContext, inp)``. Each
``ctx.step(key, fn, ...)`` stores its result, so when a run is retried (a deploy,
a crash, a failed step) the steps that finished return their stored results and
only the rest run. Step keys name journal entries: keep them the same on every
attempt. ``ctx.map`` fans out in this process, ``ctx.call`` and ``ctx.map_call``
run other modules' workflows. A step result is JSON, at most 256 KiB: put large
data in object storage and return a reference.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from naas_abi_sdk.jobs import JobContext
    from naas_abi_sdk.workflows import FlowContext

    from {{module_name_snake}} import ABIModule


async def heartbeat(module: ABIModule, ctx: JobContext) -> dict[str, Any]:
    """Record that the module ran. Replace with real work."""
    ctx.log(f"{module.module_id} is alive (attempt {ctx.attempt})")
    # The result is stored on the run record (Nexus System app, Jobs tab).
    return {"module": module.module_id, "at": datetime.now(UTC).isoformat()}


class DigestInput(BaseModel):
    """The workflow's input: the schedule's ``input``, or what a caller passes."""

    topic: str = "news"
    limit: int = Field(default=3, ge=1, le=50)


class DigestOutput(BaseModel):
    topic: str
    items: int
    summary: str


async def collect(topic: str, limit: int) -> list[str]:
    """Step 1. Replace with a call to a service: a search, a database."""
    return [f"{topic} item {number}" for number in range(1, limit + 1)]


def measure(item: str) -> int:
    """Step 2, once per item. A plain function runs in a thread."""
    return len(item)


async def summarize(topic: str, sizes: list[int]) -> str:
    """Step 3."""
    return f"{len(sizes)} items about {topic}, {sum(sizes)} characters"


async def digest(
    module: ABIModule, ctx: FlowContext, inp: DigestInput
) -> DigestOutput:
    """Collect, measure each item, summarize. Retried, the finished steps are skipped."""
    items = await ctx.step("collect", collect, inp.topic, inp.limit, retries=2)
    sizes = await ctx.map("measure", items, measure, concurrency=4)
    summary = await ctx.step("summarize", summarize, inp.topic, sizes)
    ctx.log(f"{module.module_id}: {summary} (attempt {ctx.attempt})")
    return DigestOutput(topic=inp.topic, items=len(items), summary=summary)
