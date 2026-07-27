"""Publish ``count_recent_tweets/linecharts.json`` — posts over time."""

from __future__ import annotations

from datetime import datetime

from naas_abi_marketplace.applications.x.apps.x.api.common import (
    SnapshotContext,
    previous_window,
    slugify,
)


def publish(ctx: SnapshotContext) -> dict:
    charts: list[dict] = []
    for entry in ctx.queries:
        query_string = str(entry.get("query") or "").strip()
        if not query_string:
            continue
        slug = slugify(entry.get("name") or query_string)
        buckets = ctx.timeseries(query_string)
        for scenario in ctx.scenarios:
            start, end = scenario["start_time"], scenario["end_time"]
            prev_start, prev_end = previous_window(start, end)
            hours = int(
                (
                    datetime.fromisoformat(end)
                    - datetime.fromisoformat(start)
                ).total_seconds()
                // 3600
            )
            daily = hours > 48
            cur = ctx.aggregate_buckets(buckets, start, end, daily=daily)
            prev = ctx.aggregate_buckets(buckets, prev_start, prev_end, daily=daily)
            charts.append(
                {
                    "query_slug": slug,
                    "scenario_id": scenario["id"],
                    "granularity": "day" if daily else "hour",
                    "series": [
                        {
                            "id": "current",
                            "label": "Current",
                            "points": cur,
                        },
                        {
                            "id": "previous",
                            "label": "Previous period",
                            "points": prev,
                        },
                    ],
                }
            )
    doc = {"updated_at": ctx.built_at.isoformat(), "linecharts": charts}
    ctx.save_json("count_recent_tweets", "linecharts.json", doc)
    return doc
