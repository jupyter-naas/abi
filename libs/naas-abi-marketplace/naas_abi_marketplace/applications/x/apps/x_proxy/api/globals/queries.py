"""Publish ``globals/queries.json`` - Query dropdown values."""

from __future__ import annotations

from naas_abi_marketplace.applications.x.apps.x_proxy.api.common import (
    SnapshotContext,
    slugify,
)


def publish(ctx: SnapshotContext) -> dict:
    queries = []
    for entry in ctx.queries:
        query_string = str(entry.get("query") or "").strip()
        if not query_string:
            continue
        slug = slugify(entry.get("name") or query_string)
        queries.append(
            {
                "slug": slug,
                "query": query_string,
                "label": str(entry.get("label") or entry.get("name") or query_string),
            }
        )
    doc = {"updated_at": ctx.built_at.isoformat(), "queries": queries}
    ctx.save_json("globals", "queries.json", doc)
    return doc
