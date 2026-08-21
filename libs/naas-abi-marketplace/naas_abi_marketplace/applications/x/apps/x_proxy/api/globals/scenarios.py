"""Publish ``globals/scenarios.json`` — Scenario filter values."""

from __future__ import annotations

from naas_abi_marketplace.applications.x.apps.x_proxy.api.common import SnapshotContext


def publish(ctx: SnapshotContext) -> dict:
    """Write scenarios with ``id``, ``label``, ``start_time``, ``end_time``."""
    doc = {
        "updated_at": ctx.built_at.isoformat(),
        "scenarios": ctx.scenarios,
    }
    ctx.save_json("globals", "scenarios.json", doc)
    return doc
