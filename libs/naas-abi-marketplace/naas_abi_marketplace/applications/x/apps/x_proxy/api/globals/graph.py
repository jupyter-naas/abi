"""Publish ``globals/graph.json`` - how much is in the tweet graph.

One number the whole app can quote: how many posts the dataset holds, split
between the ones that answered a followed query and the ones the expansions
pulled in as context. It is *not* scoped by a query or a window - it is the
size of the dataset behind every page.
"""

from __future__ import annotations

from typing import Any

from naas_abi_core import logger
from naas_abi_marketplace.applications.x.apps.x_proxy.api.common import SnapshotContext


def _counts_from_dataset(ctx: SnapshotContext) -> dict[str, int] | None:
    dataset = getattr(ctx, "dataset", None)
    if dataset is None:
        return None
    from naas_abi_marketplace.applications.x.apps.x_proxy.dataset.api import (
        graph_totals,
    )

    return graph_totals(dataset)


def publish(ctx: SnapshotContext) -> dict[str, Any]:
    counts = _counts_from_dataset(ctx)
    if counts is None:
        raise RuntimeError(
            "globals/graph.json publish requires Dataset Service on SnapshotContext"
        )
    logger.info(
        f"X app graph totals (dataset): {counts['posts']} post(s), "
        f"{counts['matched']} matched / {counts['referenced']} referenced"
    )
    doc = {"updated_at": ctx.built_at.isoformat(), **counts}
    ctx.save_json("globals", "graph.json", doc)
    return doc
