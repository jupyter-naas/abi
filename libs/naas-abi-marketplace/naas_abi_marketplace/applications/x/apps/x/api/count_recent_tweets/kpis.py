"""Publish ``count_recent_tweets/kpis.json`` from the free counts graph."""

from __future__ import annotations

from datetime import datetime

from naas_abi_marketplace.applications.x.apps.x.api.common import (
    SnapshotContext,
    previous_window,
    slugify,
)


def publish(ctx: SnapshotContext) -> dict:
    """KPIs per query × scenario: total / mean / high / low (+ previous deltas)."""
    entries: list[dict] = []
    for entry in ctx.queries:
        query_string = str(entry.get("query") or "").strip()
        if not query_string:
            continue
        slug = slugify(entry.get("name") or query_string)
        buckets = ctx.timeseries(query_string)
        for scenario in ctx.scenarios:
            sid = scenario["id"]
            start, end = scenario["start_time"], scenario["end_time"]
            prev_start, prev_end = previous_window(start, end)
            hours = int(
                (
                    datetime.fromisoformat(end) - datetime.fromisoformat(start)
                ).total_seconds()
                // 3600
            )
            daily = hours > 48
            cur_pts = ctx.aggregate_buckets(buckets, start, end, daily=daily)
            prev_pts = ctx.aggregate_buckets(buckets, prev_start, prev_end, daily=daily)
            cur_total = sum(p["value"] for p in cur_pts)
            prev_total = sum(p["value"] for p in prev_pts)
            cur_mean = cur_total / len(cur_pts) if cur_pts else 0.0
            prev_mean = prev_total / len(prev_pts) if prev_pts else 0.0
            top = max(cur_pts, key=lambda p: p["value"]) if cur_pts else None
            low = min(cur_pts, key=lambda p: p["value"]) if cur_pts else None
            unit = "day" if daily else "hour"
            entries.append(
                {
                    "query_slug": slug,
                    "scenario_id": sid,
                    "items": [
                        {
                            "id": "total",
                            "label": "Total Tweets",
                            "value": cur_total,
                            "prev_value": prev_total,
                            "delta": cur_total - prev_total,
                            "hint": (
                                f"{prev_total} prev. period"
                                if prev_pts
                                else "no prior period"
                            ),
                        },
                        {
                            "id": "mean",
                            "label": f"Mean / {unit}",
                            "value": round(cur_mean, 1),
                            "prev_value": round(prev_mean, 1),
                            "delta": round(cur_mean - prev_mean, 1),
                            "hint": (
                                f"{round(prev_mean, 1)} prev. period"
                                if prev_pts
                                else "no prior period"
                            ),
                        },
                        {
                            "id": "high",
                            "label": "High",
                            "value": top["value"] if top else None,
                            "prev_value": None,
                            "delta": None,
                            "hint": top["range_label"] if top else "",
                        },
                        {
                            "id": "low",
                            "label": "Low",
                            "value": low["value"] if low else None,
                            "prev_value": None,
                            "delta": None,
                            "hint": low["range_label"] if low else "",
                        },
                    ],
                }
            )
    doc = {"updated_at": ctx.built_at.isoformat(), "kpis": entries}
    ctx.save_json("count_recent_tweets", "kpis.json", doc)
    return doc
