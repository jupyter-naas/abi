"""Skip a tick whose previous run is still going, instead of queueing behind it.

A job's ``max_concurrency`` queues a tick behind the runs that fill its slots,
which is not what a poller wants: the next tick would fetch what the running one
is about to fetch. The Dagster triggers looked at the runs in flight and skipped;
this does the same on the job's run records (``RUNNING``, or ``RETRYING`` between
two attempts), in the module's own document namespace.

Two ticks can start at the same instant and each see the other, so only a run
that **started earlier** (a lower stream sequence) blocks: of the runs that
overlap, the oldest always goes ahead. A run never counts itself.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import Any

ACTIVE_STATUSES = ["RUNNING", "RETRYING"]
# Active runs of one job are bounded by its max_concurrency (64 at most), plus the
# ones between two attempts; one page covers them.
PAGE_SIZE = 1000


class OverlapCheckBlind(RuntimeError):
    """The overlap check cannot see this run's own record, so it cannot be trusted.

    The host saves a run as RUNNING before its handler starts, so the lookup must
    find it. If it does not, the collection, a status or a field it relies on
    changed: a check that quietly found nothing would let overlapping ticks fetch
    and spend twice, so the run fails here instead."""


def run_sequence(run_id: str) -> int:
    """The stream sequence in a run id (``<job>:<sequence>``)."""
    return int(run_id.rsplit(":", 1)[1])


async def earlier_active_runs(
    documents: Any,
    collection: str,
    job: str,
    run_id: str,
    same_target: Callable[[dict[str, Any]], bool] = lambda payload: True,
) -> list[str]:
    """Ids of the runs of *job* that started before *run_id* and are still active.

    ``OverlapCheckBlind`` when *run_id* itself is not among the active records.

    *documents* and *collection* are where the job's run records are. *same_target*
    looks at a run's trigger payload: a job that serves several targets (one search
    filter each) only blocks on its own.
    """
    page = await documents.find(
        collection,
        where=[("job", "eq", job), ("status", "in", ACTIVE_STATUSES)],
        limit=PAGE_SIZE,
    )
    if not any(doc.id == run_id for doc in page.items):
        raise OverlapCheckBlind(
            f"The run records of job {job!r} in {collection!r} do not list the running "
            f"run {run_id!r} ({len(page.items)} active record(s) found): the overlap "
            "check cannot tell whether another tick is running"
        )
    mine = run_sequence(run_id)
    return sorted(
        doc.id
        for doc in page.items
        if doc.id != run_id
        and int(doc.data.get("sequence", mine)) < mine
        and same_target(doc.data.get("payload") or {})
    )


def skip_if_overlapping(
    module: Any,
    ctx: Any,
    *,
    key: str = "overlap",
    same_target: Callable[[dict[str, Any]], bool] = lambda payload: True,
) -> bool:
    """Journal whether an earlier run of this job is active; if so, mark this run
    SKIPPED and return ``True`` (the handler returns right away).

    For a workflow (``ctx`` is a ``SyncFlowContext``). The decision is a step, so
    a retry of this run does not look again: an earlier run that started after this
    one's first attempt cannot exist, and one that was active then must not make a
    half-done run skip itself.
    """

    async def look() -> dict[str, Any]:
        # The run records are the host's. Looked up here, not before the step: a
        # replay (the step is journaled) must not need a host that may be stopping.
        host, _ = module._job_host()
        runs = await earlier_active_runs(
            host.documents, host.collection, ctx.job, ctx.run_id, same_target
        )
        return {"runs": runs}

    found = ctx.step(key, look)["runs"]
    if not found:
        return False
    ctx.skip(f"{found[0]} of the same target is still running")
    return True


def earlier_active_runs_sync(module: Any, ctx: Any, timeout: float = 30.0) -> list[str]:
    """``earlier_active_runs`` for a plain job handler (a worker thread), which has
    no journal: it reads the run records through the module's own job host, on the
    host's loop."""
    host, loop = module._job_host()
    return asyncio.run_coroutine_threadsafe(
        earlier_active_runs(host.documents, host.collection, ctx.job, ctx.run_id),
        loop,
    ).result(timeout)
