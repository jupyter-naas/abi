"""Publish ``count_recent_tweets/linecharts.json`` — posts over time."""

from __future__ import annotations

from datetime import datetime

from naas_abi_marketplace.applications.x.apps.x.api.common import (
    SnapshotContext,
    extrapolate_partial_hour,
    previous_window,
    slugify,
)


def _append_partial_point(
    points: list[dict],
    estimate: dict,
    *,
    daily: bool,
    window_end: str,
) -> None:
    """Add the extrapolated in-progress hour to *points*, in place.

    Hourly charts gain a new trailing point; daily charts fold the value into
    the day it belongs to (the partial hour is otherwise missing from that day's
    total, since ``timeseries`` only returns complete hours).
    """
    try:
        hour_start = datetime.fromisoformat(estimate["start"])
        end_dt = datetime.fromisoformat(window_end)
    except ValueError:
        return
    # The scenario window is floored to the hour, so an in-progress hour sits at
    # or past its end. Only chart it when the window actually reaches it.
    if hour_start >= end_dt:
        return

    if not daily:
        label = (
            hour_start.strftime("%b ")
            + str(hour_start.day)
            + hour_start.strftime(", %H:00")
        )
        points.append(
            {
                "t": hour_start.isoformat(),
                "value": estimate["value"],
                "label": label,
                "range_label": f"{label} – in progress",
                "observed": estimate["observed"],
                "estimated_value": estimate["estimated_value"],
                "missing_minutes": estimate["missing_minutes"],
            }
        )
        return

    day_key = hour_start.strftime("%Y-%m-%d")
    for point in points:
        try:
            if datetime.fromisoformat(str(point["t"])).strftime("%Y-%m-%d") == day_key:
                point["value"] = int(point.get("value") or 0) + estimate["value"]
                point["estimated_value"] = estimate["estimated_value"]
                return
        except (KeyError, ValueError):
            continue


def publish(ctx: SnapshotContext) -> dict:
    charts: list[dict] = []
    for entry in ctx.queries:
        query_string = str(entry.get("query") or "").strip()
        if not query_string:
            continue
        slug = slugify(entry.get("name") or query_string)
        buckets = ctx.timeseries(query_string)
        # The in-progress hour, topped up with a J-1 pro-rated estimate for the
        # minutes not yet elapsed, so the trailing point stops under-reading.
        estimate = extrapolate_partial_hour(ctx.partial_bucket(query_string), buckets)
        for scenario in ctx.scenarios:
            start, end = scenario["start_time"], scenario["end_time"]
            prev_start, prev_end = previous_window(start, end)
            hours = int(
                (
                    datetime.fromisoformat(end) - datetime.fromisoformat(start)
                ).total_seconds()
                // 3600
            )
            daily = hours > 48
            cur = ctx.aggregate_buckets(buckets, start, end, daily=daily)
            prev = ctx.aggregate_buckets(buckets, prev_start, prev_end, daily=daily)
            if estimate:
                _append_partial_point(cur, estimate, daily=daily, window_end=end)
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
