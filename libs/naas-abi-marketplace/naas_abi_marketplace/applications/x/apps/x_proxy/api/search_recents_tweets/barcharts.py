"""Publish ``search_recents_tweets/barcharts.json`` - top authors / locations."""

from __future__ import annotations

from collections import Counter

from naas_abi_marketplace.applications.x.apps.x_proxy.api.common import (
    SnapshotContext,
    previous_window,
    slugify,
)
from naas_abi_marketplace.applications.x.apps.x_proxy.app_config import app_config


def publish(ctx: SnapshotContext) -> dict:
    # How many bars each chart carries - `charts:` in config.yaml.
    limits = app_config().charts
    charts: list[dict] = []
    for entry in ctx.queries:
        query_string = str(entry.get("query") or "").strip()
        if not query_string:
            continue
        slug = slugify(entry.get("name") or query_string)
        for scenario in ctx.scenarios:
            start, end = scenario["start_time"], scenario["end_time"]
            prev_start, prev_end = previous_window(start, end)
            cur = ctx.tweets_in_window(query_string, start, end)
            prev = ctx.tweets_in_window(query_string, prev_start, prev_end)

            cur_authors = Counter((t.get("username") or "-") for t in cur)
            prev_authors = Counter((t.get("username") or "-") for t in prev)
            cur_locs = Counter(
                (t.get("location") or "").strip()
                for t in cur
                if (t.get("location") or "").strip()
            )
            prev_locs = Counter(
                (t.get("location") or "").strip()
                for t in prev
                if (t.get("location") or "").strip()
            )

            author_bars = []
            for username, value in cur_authors.most_common(limits.top_authors_bars):
                author_bars.append(
                    {
                        "label": f"@{username}",
                        "value": value,
                        "delta": value - prev_authors.get(username, 0),
                        "href": (
                            f"https://x.com/{username}"
                            if username and username != "-"
                            else None
                        ),
                    }
                )
            location_bars = []
            for location, value in cur_locs.most_common(limits.top_locations_bars):
                location_bars.append(
                    {
                        "label": location,
                        "value": value,
                        "delta": value - prev_locs.get(location, 0),
                        "href": None,
                    }
                )

            charts.append(
                {
                    "query_slug": slug,
                    "scenario_id": scenario["id"],
                    "items": [
                        {
                            "id": "top_authors",
                            "label": "Top authors",
                            "bars": author_bars,
                        },
                        {
                            "id": "top_locations",
                            "label": "Top author locations",
                            "bars": location_bars,
                        },
                    ],
                }
            )
    doc = {"updated_at": ctx.built_at.isoformat(), "barcharts": charts}
    ctx.save_json("search_recents_tweets", "barcharts.json", doc)
    return doc
