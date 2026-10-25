"""The ``reprocess_tweet_envelopes`` workflow: every envelope under a prefix, again.

Launched by hand (no trigger), for a backfill, or after a mapping change, or to
catch up what a failed run left behind, without calling the X API. It lists the
envelopes, leaves out those already in the graph **and** the dataset (unless
``force``), maps the rest as ``map_tweet_envelope`` child runs, syncs the dataset
and republishes the app. A second run finds nothing to do: it starts no child and
syncs nothing.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from naas_abi_marketplace.applications.x.flows.common import (
    envelope_paths_in_dataset,
    jsonable,
    normalize_envelope_path,
    publish_x_app,
    sync_x_dataset_paths_batched,
)
from naas_abi_marketplace.applications.x.flows.envelopes import (
    filter_paths_by_max_age,
    list_envelope_paths,
    mapped_file_paths,
)
from naas_abi_marketplace.applications.x.flows.models import (
    ReprocessTweetEnvelopesInput,
    ReprocessTweetEnvelopesOutput,
)
from naas_abi_marketplace.applications.x.flows.search import (
    DATASET_BATCH_SIZE,
    MAP_CONCURRENCY,
    MAP_WORKFLOW,
)


def plan_reprocess(module, inp: ReprocessTweetEnvelopesInput) -> dict[str, Any]:
    """List the envelopes and sort them: ``to_map`` (not in the graph, or all of
    them with ``force``), ``dataset_only`` (in the graph, not in the dataset),
    and how many are already complete. Two bulk probes, whatever the count."""
    cutoff = (
        datetime.now(UTC) - timedelta(hours=inp.max_age_hours)
        if inp.max_age_hours is not None
        else None
    )
    paths, skipped_age = list_envelope_paths(
        module.engine.services.object_storage, inp.prefix, cutoff=cutoff
    )
    if cutoff is not None:
        paths, rechecked = filter_paths_by_max_age(paths, cutoff=cutoff)
        skipped_age += rechecked
    paths = sorted(set(paths))

    to_map: list[str] = []
    dataset_only: list[str] = []
    complete = 0
    if inp.force:
        to_map = paths
    else:
        in_graph = mapped_file_paths(
            module.engine.services.triple_store,
            module.configuration.graph_name,
            module.configuration.ontology_namespace,
        )
        in_dataset = envelope_paths_in_dataset(module, paths)
        for path in paths:
            if path not in in_graph:
                to_map.append(path)
            elif normalize_envelope_path(path) in in_dataset:
                complete += 1
            else:
                dataset_only.append(path)
    # One page of work per run: the plan is a journaled step (256 KiB at most).
    truncated = len(to_map) + len(dataset_only) > inp.max_envelopes
    to_map = to_map[: inp.max_envelopes]
    dataset_only = dataset_only[: inp.max_envelopes - len(to_map)]
    return {
        "listed": len(paths),
        "skipped_age": skipped_age,
        "to_map": to_map,
        "dataset_only": dataset_only,
        "complete": complete,
        "truncated": truncated,
    }


def _sync_dataset(module, paths: list[str]) -> dict[str, Any]:
    return jsonable(
        sync_x_dataset_paths_batched(module, paths, batch_size=DATASET_BATCH_SIZE)
    )


def _publish(module) -> dict[str, Any]:
    return jsonable(publish_x_app(module, enabled=True))


def run_reprocess_tweet_envelopes(
    module, ctx, inp: ReprocessTweetEnvelopesInput
) -> ReprocessTweetEnvelopesOutput:
    """Handler body (``ctx`` is a ``SyncFlowContext``)."""
    plan = ctx.step("plan", lambda: jsonable(plan_reprocess(module, inp)))
    to_map: list[str] = plan["to_map"]

    mapped_paths: list[str] = []
    if to_map:
        results = ctx.map_call(
            "map",
            ctx.runtime.module_id,
            MAP_WORKFLOW,
            [
                {"path": path, "persist": inp.persist, "force": inp.force}
                for path in to_map
            ],
            concurrency=MAP_CONCURRENCY,
        )
        mapped_paths = [p for p, result in zip(to_map, results) if result is not None]

    to_sync = mapped_paths + plan["dataset_only"]
    dataset = ctx.step("dataset", _sync_dataset, module, to_sync) if to_sync else None
    app = (
        ctx.step("publish", _publish, module)
        if inp.app_publish and mapped_paths
        else None
    )
    return ReprocessTweetEnvelopesOutput(
        prefix=inp.prefix,
        listed=plan["listed"],
        mapped=len(mapped_paths),
        skipped=plan["complete"],
        dataset_only=len(plan["dataset_only"]),
        truncated=plan["truncated"],
        dataset=dataset,
        app=app,
    )
