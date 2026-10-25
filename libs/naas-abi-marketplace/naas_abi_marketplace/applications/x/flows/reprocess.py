"""The ``reprocess_tweet_envelopes`` workflow: every envelope under a prefix, again.

Launched by hand (no trigger), for a backfill, or after a mapping change, or to
catch up what a failed run left behind, without calling the X API. It lists the
envelopes, leaves out those already in the graph **and** the dataset (unless
``force``), maps the rest as ``map_tweet_envelope`` child runs, syncs the dataset
and republishes the app. A second run finds nothing to do: it starts no child and
syncs nothing.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from typing import Any

from naas_abi_core import logger
from naas_abi_core.module.workflows import WorkflowCancelled
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
from naas_abi_marketplace.applications.x.flows.fanout import (
    FlowIncomplete,
    call_each,
    describe_failures,
)
from naas_abi_marketplace.applications.x.flows.guard import skip_if_overlapping
from naas_abi_marketplace.applications.x.flows.models import (
    ReprocessTweetEnvelopesInput,
    ReprocessTweetEnvelopesOutput,
)
from naas_abi_marketplace.applications.x.flows.search import (
    DATASET_BATCH_SIZE,
    MAP_CONCURRENCY,
    MAP_WORKFLOW,
)
from pydantic import ValidationError

# What the paths of a plan may weigh: the step cap is 256 KiB, the rest of the plan
# (counts, the other list's envelope) fits in the margin.
PLAN_MAX_BYTES = 200 * 1024


def _encoded_size(path: str) -> int:
    """Bytes a path takes in the journaled plan (JSON string and separator)."""
    return len(json.dumps(path)) + 1


def _page(paths: list[str], count: int, size: int) -> list[str]:
    """The first *paths*, at most *count* of them and *size* bytes once encoded."""
    page: list[str] = []
    used = 0
    for path in paths[: max(count, 0)]:
        used += _encoded_size(path)
        if used > size:
            break
        page.append(path)
    return page


def _prefix_of(payload: Any) -> str | None:
    """The prefix a run's trigger payload resolves to: a payload without one (a
    manual launch with ``{}``) means the default, as the validated input says."""
    try:
        return ReprocessTweetEnvelopesInput.model_validate(payload or {}).prefix
    except ValidationError:
        return None


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
    # One page of work per run: the plan is a journaled step (256 KiB at most), so
    # the page is bounded by count and by the size of the paths it carries.
    total = len(to_map) + len(dataset_only)
    to_map = _page(to_map, inp.max_envelopes, PLAN_MAX_BYTES)
    room = inp.max_envelopes - len(to_map)
    used = sum(_encoded_size(path) for path in to_map)
    dataset_only = _page(dataset_only, room, PLAN_MAX_BYTES - used)
    truncated = len(to_map) + len(dataset_only) < total
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
) -> ReprocessTweetEnvelopesOutput | None:
    """Handler body (``ctx`` is a ``SyncFlowContext``).

    As for the search: a mapping run that fails does not stop the dataset sync of
    the envelopes that mapped; the run ends FAILED at the end, saying what worked
    (``FlowIncomplete``). A failed app publish is only logged.
    """
    # A scheduled sweep that outlasts its interval, or a manual launch over the
    # same folder, would map the same envelopes twice: SKIPPED, not queued.
    if skip_if_overlapping(
        module, ctx, same_target=lambda payload: _prefix_of(payload) == inp.prefix
    ):
        return None

    plan = ctx.step("plan", lambda: jsonable(plan_reprocess(module, inp)))
    to_map: list[str] = plan["to_map"]
    problems: list[str] = []

    mapped_paths: list[str] = []
    if to_map:
        outputs, failures = call_each(
            ctx,
            "map",
            ctx.runtime.module_id,
            MAP_WORKFLOW,
            [
                {"path": path, "persist": inp.persist, "force": inp.force}
                for path in to_map
            ],
            concurrency=MAP_CONCURRENCY,
        )
        mapped_paths = [
            path
            for i, path in enumerate(to_map)
            if i not in failures and outputs[i] is not None
        ]
        if failures:
            problems.append(describe_failures("mapping", to_map, failures))

    to_sync = mapped_paths + plan["dataset_only"]
    dataset = None
    if to_sync:
        try:
            dataset = ctx.step(
                f"dataset[{len(to_sync)}]", _sync_dataset, module, to_sync
            )
        except WorkflowCancelled:
            raise
        except Exception as error:  # noqa: BLE001 - the rest still goes on
            problems.append(f"the dataset sync failed: {error}")
    app = None
    if inp.app_publish and mapped_paths:
        try:
            app = ctx.step(f"publish[{len(mapped_paths)}]", _publish, module)
        except WorkflowCancelled:
            raise
        except Exception as error:  # noqa: BLE001 - never fail the sweep on publish
            ctx.log(f"app publish failed: {error}")
            logger.warning(f"X reprocess: app republish failed ({error})")
            app = {"failed": True, "error": str(error)[:500]}

    if problems:
        for problem in problems:
            ctx.log(problem)
        raise FlowIncomplete(
            f"reprocess of {inp.prefix!r}: listed {plan['listed']}, mapped "
            f"{len(mapped_paths)}; " + "; ".join(problems)
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
