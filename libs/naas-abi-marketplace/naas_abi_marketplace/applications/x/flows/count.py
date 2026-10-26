"""The ``count_recent_tweets`` workflow: follow the hourly post count of a query.

Two steps: fetch the newest hourly counts (``XCountRecentTweetsWorkflow``, which
calls the X API and saves the envelopes), then map them into the count graph and
the dataset (``XCountRecentTweetsPipeline``). The fetch is journaled, so a retry
maps without calling the API again. Idempotent per clock hour.
"""

from __future__ import annotations

from typing import Any

from naas_abi_marketplace.applications.x.flows.common import (
    fetch_counts_for_query,
    jsonable,
    map_counts_for_query,
    sync_counts_dataset,
)
from naas_abi_marketplace.applications.x.flows.models import (
    CountRecentTweetsInput,
    CountRecentTweetsOutput,
)


def _fetch(module, query: str) -> dict[str, Any]:
    output = fetch_counts_for_query(module, query)
    # What the mapping needs; the per-query ``results`` are not for the journal.
    return jsonable(
        {
            "total_buckets": output.get("total_buckets", 0),
            "file_paths": output.get("file_paths", []),
            "partial_file_paths": output.get("partial_file_paths", []),
        }
    )


def _map(module, query: str, output: dict[str, Any]) -> dict[str, Any]:
    mapped = map_counts_for_query(module, query, output)
    return jsonable(
        {**mapped, "dataset_sync": sync_counts_dataset(module, query, output)}
    )


def run_count_recent_tweets(
    module, ctx, inp: CountRecentTweetsInput
) -> CountRecentTweetsOutput:
    """Handler body (``ctx`` is a ``SyncFlowContext``)."""
    fetched = ctx.step("fetch", _fetch, module, inp.query)
    mapped = ctx.step("map", _map, module, inp.query, fetched)
    return CountRecentTweetsOutput(
        query=inp.query,
        buckets=int(fetched.get("total_buckets") or 0),
        mapped=int(mapped["mapped"]),
        partial_mapped=int(mapped["partial_mapped"]),
        dataset_sync=mapped.get("dataset_sync"),
    )
