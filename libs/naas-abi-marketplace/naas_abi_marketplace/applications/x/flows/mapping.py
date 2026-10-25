"""The ``map_tweet_envelope`` workflow: one search envelope into the graph.

Idempotent, because it is at-least-once and also launched by hand: a run for an
envelope that is gone, or already in the graph **and** the dataset, ends SKIPPED;
one for an envelope the graph has but the dataset lacks does not run the pipeline
again (the caller syncs the dataset); only a missing envelope is mapped.
"""

from __future__ import annotations

import posixpath
from typing import Any

from naas_abi_core import logger
from naas_abi_core.services.object_storage.ObjectStoragePort import Exceptions
from naas_abi_marketplace.applications.x.flows.common import (
    run_search_pipeline_for_file,
    search_envelope_fully_projected,
    search_envelope_ingested,
)
from naas_abi_marketplace.applications.x.flows.models import (
    MapTweetEnvelopeInput,
    MapTweetEnvelopeOutput,
)


def envelope_exists(module, path: str) -> bool:
    """False when the object is gone; fails open (``True``) on any other storage
    error, since the pipeline reports a missing file clearly."""
    prefix, key = posixpath.split(path)
    try:
        module.engine.services.object_storage.get_object_metadata(prefix, key)
    except Exceptions.ObjectNotFound:
        return False
    except Exception as error:  # noqa: BLE001 - transient storage error: do not drop it
        logger.warning(
            f"X mapping: metadata probe failed for {path!r} ({error}); mapping anyway"
        )
    return True


def _map(module, inp: MapTweetEnvelopeInput) -> None:
    run_search_pipeline_for_file(
        inp.path, persist=inp.persist, graph_name=inp.graph_name, module=module
    )


def run_map_tweet_envelope(
    module, ctx, inp: MapTweetEnvelopeInput
) -> MapTweetEnvelopeOutput | None:
    """Handler body (``ctx`` is a ``SyncFlowContext``)."""
    if not envelope_exists(module, inp.path):
        ctx.skip("the envelope no longer exists")
        return None
    graph: Any = inp.graph_name
    if not inp.force:
        if search_envelope_fully_projected(module, inp.path, graph_name=graph):
            ctx.skip("already in the graph and the dataset")
            return None
        if search_envelope_ingested(module, inp.path, graph_name=graph):
            return MapTweetEnvelopeOutput(path=inp.path, status="dataset_only")
    ctx.step("pipeline", _map, module, inp)
    return MapTweetEnvelopeOutput(path=inp.path, status="mapped")
