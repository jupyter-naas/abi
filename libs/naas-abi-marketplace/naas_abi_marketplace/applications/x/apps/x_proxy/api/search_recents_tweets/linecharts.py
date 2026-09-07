"""Publish ``search_recents_tweets/linecharts.json`` - ingested tweets over time.

Same shape as the Count page's "Posts over time": per-hour or per-day **counts**
(not a cumulative running total), current vs previous period.

The series is ingested **matched** tweets bucketed by ``created_at``. It is not
the count-endpoint total (a different population) and not referenced context
(those posts can predate the window). The 1 000-row table sample is not used -
the cardinality is the same uncapped window the Tweets KPI reports.
"""

from __future__ import annotations

from datetime import datetime

from naas_abi_marketplace.applications.x.apps.x_proxy.api.common import (
    SnapshotContext,
    complete_hourly_buckets,
    is_all_time,
    previous_window,
    slugify,
)


def publish(ctx: SnapshotContext) -> dict:
    charts: list[dict] = []
    rolling = [s for s in ctx.scenarios if not is_all_time(s)]
    if rolling:
        span_start = min(
            previous_window(s["start_time"], s["end_time"])[0] for s in rolling
        )
        span_end = max(s["end_time"] for s in rolling)
    elif ctx.scenarios:
        span_start = min(s["start_time"] for s in ctx.scenarios)
        span_end = max(s["end_time"] for s in ctx.scenarios)
    else:
        span_start = span_end = ""
    for entry in ctx.queries:
        query_string = str(entry.get("query") or "").strip()
        if not query_string:
            continue
        slug = slugify(entry.get("name") or query_string)
        if not ctx.scenarios:
            continue
        buckets: list[dict] = []
        if rolling and span_start and span_end:
            buckets = complete_hourly_buckets(
                ctx.ingested_timeseries(query_string, span_start, span_end),
                span_start,
                span_end,
            )
        for scenario in ctx.scenarios:
            start, end = scenario["start_time"], scenario["end_time"]
            hours = int(
                (
                    datetime.fromisoformat(end) - datetime.fromisoformat(start)
                ).total_seconds()
                // 3600
            )
            daily = hours > 48
            if is_all_time(scenario):
                # Don't pad years of zero hours: All time is a daily (or sparse
                # hourly) series of the hours that actually have posts.
                raw = ctx.ingested_timeseries(query_string, start, end)
                current_points = ctx.aggregate_buckets(raw, start, end, daily=daily)
                previous_points: list[dict] = []
            else:
                current_points = ctx.aggregate_buckets(buckets, start, end, daily=daily)
                prev_start, prev_end = previous_window(start, end)
                previous_points = ctx.aggregate_buckets(
                    buckets, prev_start, prev_end, daily=daily
                )
            charts.append(
                {
                    "query_slug": slug,
                    "scenario_id": scenario["id"],
                    "granularity": "day" if daily else "hour",
                    "series": [
                        {
                            "id": "current",
                            "label": "Current",
                            "points": current_points,
                        },
                        {
                            "id": "previous",
                            "label": "Previous period",
                            "points": previous_points,
                        },
                    ],
                }
            )
    doc = {"updated_at": ctx.built_at.isoformat(), "linecharts": charts}
    ctx.save_json("search_recents_tweets", "linecharts.json", doc)
    return doc
