"""Publish ``count_recent_tweets/barcharts.json`` - peak hours/days bars."""

from __future__ import annotations

from datetime import datetime

from naas_abi_marketplace.applications.x.apps.x_proxy.api.common import (
    SnapshotContext,
    slugify,
)


def publish(ctx: SnapshotContext) -> dict:
    """Same element shape as search barcharts; bars = top buckets in the window."""
    charts: list[dict] = []
    for entry in ctx.queries:
        query_string = str(entry.get("query") or "").strip()
        if not query_string:
            continue
        slug = slugify(entry.get("name") or query_string)
        buckets = ctx.timeseries(query_string)
        for scenario in ctx.scenarios:
            start, end = scenario["start_time"], scenario["end_time"]
            hours = int(
                (
                    datetime.fromisoformat(end) - datetime.fromisoformat(start)
                ).total_seconds()
                // 3600
            )
            daily = hours > 48
            points = ctx.aggregate_buckets(buckets, start, end, daily=daily)
            ranked = sorted(points, key=lambda p: p["value"], reverse=True)[:10]
            charts.append(
                {
                    "query_slug": slug,
                    "scenario_id": scenario["id"],
                    "items": [
                        {
                            "id": "top_buckets",
                            "label": "Top periods" if daily else "Top hours",
                            "bars": [
                                {
                                    "label": p["label"],
                                    "value": p["value"],
                                    "delta": None,
                                    "href": None,
                                }
                                for p in ranked
                            ],
                        }
                    ],
                }
            )
    doc = {"updated_at": ctx.built_at.isoformat(), "barcharts": charts}
    ctx.save_json("count_recent_tweets", "barcharts.json", doc)
    return doc
