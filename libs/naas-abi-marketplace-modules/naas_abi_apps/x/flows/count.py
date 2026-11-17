"""The ``count_recent_tweets`` workflow: follow the hourly post count of a query.

Two steps: fetch the newest hourly counts (``XCountRecentTweetsWorkflow``, which
calls the X API and saves the envelopes), then map them into the count graph and
the dataset (``XCountRecentTweetsPipeline``). The fetch is journaled, so a retry
maps without calling the API again. Idempotent per clock hour.
"""

from __future__ import annotations

from typing import Any

from naas_abi_apps.x.flows.common import (
    fetch_counts_for_query,
    jsonable,
    map_counts_for_query,
    sync_counts_dataset,
)
from naas_abi_apps.x.flows.models import (
    CountRecentTweetsInput,
    CountRecentTweetsOutput,
)


def _fetch(sync: Any, query: str) -> dict[str, Any]:
    output = fetch_counts_for_query(sync, query)
    # What the mapping needs; the per-query ``results`` are not for the journal.
    return jsonable(
        {
            "total_buckets": output.get("total_buckets", 0),
            "file_paths": output.get("file_paths", []),
            "partial_file_paths": output.get("partial_file_paths", []),
        }
    )


def _map(sync: Any, query: str, output: dict[str, Any]) -> dict[str, Any]:
    mapped = map_counts_for_query(sync, query, output)
    return jsonable(
        {**mapped, "dataset_sync": sync_counts_dataset(sync, query, output)}
    )


async def run_count_recent_tweets(
    module: Any, ctx: Any, inp: CountRecentTweetsInput
) -> CountRecentTweetsOutput:
    """Handler body: ``module`` is the SDK module, ``ctx`` its ``FlowContext``.
    Both steps run on the module's threads (``module.sync.threaded``)."""
    sync = module.sync
    fetched = await ctx.step("fetch", sync.threaded(_fetch), sync, inp.query)
    mapped = await ctx.step("map", sync.threaded(_map), sync, inp.query, fetched)
    return CountRecentTweetsOutput(
        query=inp.query,
        buckets=int(fetched.get("total_buckets") or 0),
        mapped=int(mapped["mapped"]),
        partial_mapped=int(mapped["partial_mapped"]),
        dataset_sync=mapped.get("dataset_sync"),
    )
