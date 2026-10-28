"""The ``search_recent_tweets`` workflow: one tick of one search filter.

Spend guard, fetch and save the envelopes, map them as child runs, follow the
counts, sync the dataset, publish the app. Each stage is a checkpointed step, so
a retry after a crash resumes where the run stopped: it does not call the X API
again once the fetch is journaled, and it re-attaches to the mapping runs it
already started.

The mapping does not wait for ``ObjectPut`` events (at-most-once: lost while no
host runs). The run knows which envelopes it just saved and hands them to
``map_tweet_envelope`` itself, including those a fetch saved before it failed
part-way.

A stage that fails does not stop the ones that can still run, as one bad envelope
only affected itself under Dagster. A fetch that failed after saving, a mapping run
that failed, a dataset sync that failed: the rest goes on (the envelopes that did
map are synced and published), and the run ends FAILED at the end, with what
worked and what did not in its error (``FlowIncomplete``; ``FetchFailed``, which is
not retried, when the fetch failed). A failed app publish is
only logged, as ``publish_app_after_search`` always did: the next rebuild catches up.
"""

from __future__ import annotations

from typing import Any

from naas_abi_core import logger
from naas_abi_core.module.workflows import (
    ChildRunFailed,
    InvalidWorkflowInput,
    WorkflowCancelled,
)
from naas_abi_marketplace.applications.x.flows.common import (
    fetch_search_envelopes,
    jsonable,
    publish_x_app,
    search_budget_blocked,
    sync_x_dataset_paths_batched,
)
from naas_abi_marketplace.applications.x.flows.fanout import (
    FetchFailed,
    FlowIncomplete,
    call_each,
    describe_failures,
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
    """Fetch and save. A failure after some batches were saved is **returned**, not
    raised, so the journal keeps the saved paths for the mapping."""
    saved: list[str] = []
    try:
        fetched = fetch_search_envelopes(module, config, saved_paths=saved)
    except Exception as error:  # noqa: BLE001 - reported at the end of the run
        logger.warning(
            f"X search[{config.name}]: fetch failed after saving {len(saved)} "
            f"envelope(s) ({error})"
        )
        return {
            "file_paths": _unique(saved),
            "total_new_tweets": 0,
            "budget_blocked": False,
            "budget_reason": None,
            "error": f"{type(error).__name__}: {error}"[:500],
        }
    return {**fetched, "file_paths": _unique(fetched["file_paths"]), "error": None}


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
    problems: list[str] = []
    if fetched.get("error"):
        problems.append(
            f"the fetch failed after saving {len(paths)} envelope(s): {fetched['error']}"
        )

    mapped_paths: list[str] = []
    if paths:
        outputs, failures = call_each(
            ctx,
            "map",
            module_id,
            MAP_WORKFLOW,
            [{"path": path, "persist": config.persist} for path in paths],
            concurrency=MAP_CONCURRENCY,
        )
        # A run that ended SKIPPED (the envelope is gone) has no output.
        mapped_paths = [
            path
            for i, path in enumerate(paths)
            if i not in failures and outputs[i] is not None
        ]
        if failures:
            problems.append(describe_failures("mapping", paths, failures))

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

    # The step keys carry the count: a retry that mapped more envelopes syncs and
    # publishes again instead of finding the journal of the smaller set.
    n = len(mapped_paths)
    dataset = None
    if mapped_paths:
        try:
            dataset = ctx.step(f"dataset[{n}]", _sync_dataset, module, mapped_paths)
        except WorkflowCancelled:
            raise
        except Exception as error:  # noqa: BLE001 - the rest still goes on
            problems.append(f"the dataset sync failed: {error}")
    app = None
    if config.app_publish:
        try:
            app = ctx.step(f"publish[{n}]", _publish, module)
        except WorkflowCancelled:
            raise
        except Exception as error:  # noqa: BLE001 - never fail the search on publish
            ctx.log(f"app publish failed: {error}")
            logger.warning(
                f"X search[{config.name}]: app republish failed ({error}); "
                f"the next rebuild catches up"
            )
            app = {"failed": True, "error": str(error)[:500]}

    if problems:
        summary = (
            f"search {config.name!r}: saved {len(paths)} envelope(s), "
            f"mapped {len(mapped_paths)}"
        )
        for problem in problems:
            ctx.log(problem)
        # A failed fetch is journaled: another attempt would replay it. End the run
        # (what it saved is mapped); the next tick fetches again.
        failure = FetchFailed if fetched.get("error") else FlowIncomplete
        raise failure(f"{summary}; " + "; ".join(problems))

    return SearchRecentTweetsOutput(
        filter=config.name,
        envelopes=len(paths),
        new_tweets=int(fetched.get("total_new_tweets") or 0),
        mapped=len(mapped_paths),
        counts_followed=counts_followed,
        dataset=dataset,
        app=app,
    )
