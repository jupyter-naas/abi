"""Publish ``search_recents_tweets/linecharts.json`` — ingested tweets over time."""

from __future__ import annotations

from collections import Counter
from datetime import datetime

from naas_abi_marketplace.applications.x.apps.x.api.common import (
    SnapshotContext,
    previous_window,
    slugify,
)


def _bucket_tweets(tweets: list[dict], *, daily: bool) -> list[dict]:
    counts: Counter[str] = Counter()
    for t in tweets:
        try:
            created = datetime.fromisoformat(str(t["created_at"]))
        except (KeyError, ValueError):
            continue
        key = (
            created.strftime("%Y-%m-%d")
            if daily
            else created.strftime("%Y-%m-%dT%H:00:00+00:00")
        )
        counts[key] += 1
    points: list[dict] = []
    for key, value in sorted(counts.items()):
        if daily:
            point_t = f"{key}T12:00:00+00:00"
            dt = datetime.fromisoformat(point_t)
            label = dt.strftime("%b ") + str(dt.day)
        else:
            point_t = key
            start = datetime.fromisoformat(key)
            label = start.strftime("%b ") + str(start.day) + start.strftime(", %H:00")
        points.append(
            {"t": point_t, "value": value, "label": label, "range_label": label}
        )
    return points


def publish(ctx: SnapshotContext) -> dict:
    charts: list[dict] = []
    for entry in ctx.queries:
        query_string = str(entry.get("query") or "").strip()
        if not query_string:
            continue
        slug = slugify(entry.get("name") or query_string)
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
            cur = ctx.tweets_in_window(query_string, start, end)
            prev = ctx.tweets_in_window(query_string, prev_start, prev_end)
            charts.append(
                {
                    "query_slug": slug,
                    "scenario_id": scenario["id"],
                    "granularity": "day" if daily else "hour",
                    "series": [
                        {
                            "id": "current",
                            "label": "Current",
                            "points": _bucket_tweets(cur, daily=daily),
                        },
                        {
                            "id": "previous",
                            "label": "Previous period",
                            "points": _bucket_tweets(prev, daily=daily),
                        },
                    ],
                }
            )
    doc = {"updated_at": ctx.built_at.isoformat(), "linecharts": charts}
    ctx.save_json("search_recents_tweets", "linecharts.json", doc)
    return doc
