"""The ``search_recent_tweets`` workflow: one tick of one search filter.

Spend guard, fetch and save the envelopes, map them as child runs, follow the
counts, sync the dataset, publish the app. Each stage is a checkpointed step, so
a retry after a crash resumes where the run stopped: it does not call the X API
again once the fetch is journaled, and it re-attaches to the mapping runs it
already started.

The mapping does not wait for ``ObjectPut`` events (at-most-once: lost while no
host runs). The run knows which envelopes it just saved and hands them to
``map_tweet_envelope` itself.
"""

from __future__ import annotations

from typing import Any

from naas_abi_core import logger
from naas_abi_core.module.workflows import ChildRunFailed, InvalidWorkflowInput
from naas_abi_marketplace.applications.x.flows.common import (
    fetch_search_envelopes,
    jsonable,
    publish_x_app,
    search_budget_blocked,
    sync_x_dataset_paths_batched,
)
from naas_abi_marketplace.applications.x.flows.guard import skip_if_overlapping
from naas_abi_marketplace.applications.x.flows.models import (
    SearchRecentTweetsInput,
    SearchRecentTweetsOutput,
)

MAP_WORKFLOW = "map_tweet_envelope"
COUNT_WORKFLOW = "count_recent_tweets"
# Mapping runs of one search run at a time. They write to the graph, so the
# concurrency stays small; the mapping workflow has the same number of slots.
MAP_CONCURRENCY = 4
DATASET_BATCH_SIZE = 64


def find_filter(module, name: str):
    """The ``search_recent_tweets_workflow`` entry called *name*."""
    for config in module.configuration.search_recent_tweets_workflow:
        if config.name == name:
            return config
    raise InvalidWorkflowInput(
        f"No search_recent_tweets_workflow entry named {name!r} in the X module configuration"
    )


def _unique(paths: list[str]) -> list[str]:
    return list(dict.fromkeys(paths))


def _fetch(module, config) -> dict[str, Any]:
    fetched = fetch_search_envelopes(module, config)
    return {**fetched, "file_paths": _unique(fetched["file_paths"])}


def _sync_dataset(module, paths: list[str]) -> dict[str, Any]:
    return jsonable(
        sync_x_dataset_paths_batched(module, paths, batch_size=DATASET_BATCH_SIZE)
    )


def _publish(module) -> dict[str, Any]:
    return jsonable(publish_x_app(module, enabled=True))


def run_search_recent_tweets(
    module, ctx, inp: SearchRecentTweetsInput
) -> SearchRecentTweetsOutput | None:
    """Handler body (``ctx`` is a ``SyncFlowContext``)."""
    config = find_filter(module, inp.filter)
    module_id = ctx.runtime.module_id

    # A tick whose previous run is still going has nothing to add: SKIPPED, not queued.
    if skip_if_overlapping(
        module, ctx, same_target=lambda payload: payload.get("filter") == inp.filter
    ):
        return None

    blocked = ctx.step("budget", search_budget_blocked, module, config)
    if blocked:
        ctx.skip(blocked)
        return None

    fetched = ctx.step("fetch", _fetch, module, config)
    if fetched["budget_blocked"]:  # the cap was reached between the two checks
        ctx.skip(fetched["budget_reason"] or "spend cap reached")
        return None
    paths: list[str] = fetched["file_paths"]

    mapped = 0
    mapped_paths: list[str] = []
    if paths:
        results = ctx.map_call(
            "map",
            module_id,
            MAP_WORKFLOW,
            [{"path": path, "persist": config.persist} for path in paths],
            concurrency=MAP_CONCURRENCY,
        )
        # A run that ended SKIPPED (the envelope is gone) has no output.
        mapped_paths = [p for p, result in zip(paths, results) if result is not None]
        mapped = len(mapped_paths)

    counts_followed = False
    if config.count_recent_tweets:
        try:
            ctx.call(module_id, COUNT_WORKFLOW, {"query": config.query}, key="count")
            counts_followed = True
        except ChildRunFailed as error:  # never fail the search on counts
            ctx.log(f"count follow-up failed: {error}")
            logger.warning(
                f"X search[{config.name}]: count follow-up failed ({error}); "
                f"search envelopes were still saved and mapped"
            )

    dataset = (
        ctx.step("dataset", _sync_dataset, module, mapped_paths)
        if mapped_paths
        else None
    )
    app = ctx.step("publish", _publish, module) if config.app_publish else None

    return SearchRecentTweetsOutput(
        filter=config.name,
        envelopes=len(paths),
        new_tweets=int(fetched.get("total_new_tweets") or 0),
        mapped=mapped,
        counts_followed=counts_followed,
        dataset=dataset,
        app=app,
    )
