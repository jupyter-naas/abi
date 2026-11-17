"""The ``map_tweet_envelope`` workflow: one search envelope into the graph.

Idempotent, because it is at-least-once and also launched by hand: a run for an
envelope that is gone, or already in the graph **and** the dataset, ends SKIPPED;
one for an envelope the graph has but the dataset lacks does not run the pipeline
again (the caller syncs the dataset); only a missing envelope is mapped.
"""

from __future__ import annotations

import asyncio
import posixpath
from typing import Any

from naas_abi_apps.x.flows.common import (
    run_search_pipeline_for_file,
    search_envelope_fully_projected,
    search_envelope_ingested,
)
from naas_abi_apps.x.flows.models import (
    MapTweetEnvelopeInput,
    MapTweetEnvelopeOutput,
)
from naas_abi_apps.x.services import ObjectNotFound, logger


def envelope_exists(sync: Any, path: str) -> bool:
    """False when the object is gone; fails open (``True``) on any other storage
    error, since the pipeline reports a missing file clearly."""
    prefix, key = posixpath.split(path)
    try:
        sync.engine.services.object_storage.get_object_metadata(prefix, key)
    except ObjectNotFound:
        return False
    except Exception as error:  # noqa: BLE001 - transient storage error: do not drop it
        logger.warning(
            f"X mapping: metadata probe failed for {path!r} ({error}); mapping anyway"
        )
    return True


def _state(sync: Any, inp: MapTweetEnvelopeInput) -> str:
    """``gone``, ``complete`` (graph and dataset), ``graph_only`` or ``missing``;
    without ``force`` only ``missing`` runs the pipeline."""
    if not envelope_exists(sync, inp.path):
        return "gone"
    if inp.force:
        return "missing"
    graph: Any = inp.graph_name
    if search_envelope_fully_projected(sync, inp.path, graph_name=graph):
        return "complete"
    if search_envelope_ingested(sync, inp.path, graph_name=graph):
        return "graph_only"
    return "missing"


def _map(sync: Any, inp: MapTweetEnvelopeInput) -> None:
    run_search_pipeline_for_file(
        sync, inp.path, persist=inp.persist, graph_name=inp.graph_name
    )


async def run_map_tweet_envelope(
    module: Any, ctx: Any, inp: MapTweetEnvelopeInput
) -> MapTweetEnvelopeOutput | None:
    """Handler body: ``module`` is the SDK module, ``ctx`` its ``FlowContext``.
    The probes and the pipeline run in worker threads, on ``module.sync``."""
    sync = module.sync
    state = await asyncio.to_thread(_state, sync, inp)
    if state == "gone":
        ctx.skip("the envelope no longer exists")
        return None
    if state == "complete":
        ctx.skip("already in the graph and the dataset")
        return None
    if state == "graph_only":
        return MapTweetEnvelopeOutput(path=inp.path, status="dataset_only")
    await ctx.step("pipeline", _map, sync, inp)
    return MapTweetEnvelopeOutput(path=inp.path, status="mapped")
