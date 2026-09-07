"""Publish ``search_recents_tweets/barcharts.json`` - top authors / locations.

Author (and location) ranks are aggregated over the **whole** scenario window,
not the newest ``DEFAULT_TWEET_LIMIT`` table rows. Ranking from that sample made
every scenario look the same whenever 24 h already held more posts than the cap.
"""

from __future__ import annotations

from naas_abi_marketplace.applications.x.apps.x_proxy.api.common import (
    SnapshotContext,
    is_all_time,
    previous_window,
    slugify,
)
from naas_abi_marketplace.applications.x.apps.x_proxy.app_config import app_config


def _counts(
    ctx: SnapshotContext,
    query_string: str,
    start: str,
    end: str,
    column: str,
    limit: int,
) -> dict[str, int]:
    rows = ctx.facet_values_for_window(query_string, start, end, column, limit=limit)
    out: dict[str, int] = {}
    for row in rows:
        key = (row.get("value") or "").strip() or "-"
        try:
            out[key] = int(row.get("count") or 0)
        except (TypeError, ValueError):
            out[key] = 0
    return out


def publish(ctx: SnapshotContext) -> dict:
    # How many bars each chart carries - `charts:` in config.yaml.
    limits = app_config().charts
    # Previous-period lookup is wider than the bar cap so a current top author
    # that was quieter last window still gets a delta rather than "+N vs 0".
    prev_limit = max(limits.top_authors_bars, limits.top_locations_bars, 500)
    charts: list[dict] = []
    for entry in ctx.queries:
        query_string = str(entry.get("query") or "").strip()
        if not query_string:
            continue
        slug = slugify(entry.get("name") or query_string)
        for scenario in ctx.scenarios:
            start, end = scenario["start_time"], scenario["end_time"]
            all_time = is_all_time(scenario)
            cur_authors = ctx.facet_values_for_window(
                query_string, start, end, "username", limit=limits.top_authors_bars
            )
            cur_locs = ctx.facet_values_for_window(
                query_string, start, end, "location", limit=limits.top_locations_bars
            )
            prev_authors: dict[str, int] = {}
            prev_locs: dict[str, int] = {}
            if not all_time:
                prev_start, prev_end = previous_window(start, end)
                prev_authors = _counts(
                    ctx, query_string, prev_start, prev_end, "username", prev_limit
                )
                prev_locs = _counts(
                    ctx, query_string, prev_start, prev_end, "location", prev_limit
                )

            author_bars = []
            for row in cur_authors:
                username = (row.get("value") or "").strip() or "-"
                try:
                    value = int(row.get("count") or 0)
                except (TypeError, ValueError):
                    value = 0
                author_bars.append(
                    {
                        "label": f"@{username}",
                        "value": value,
                        "delta": (
                            None if all_time else value - prev_authors.get(username, 0)
                        ),
                        "href": (
                            f"https://x.com/{username}"
                            if username and username != "-"
                            else None
                        ),
                    }
                )
            location_bars = []
            for row in cur_locs:
                location = (row.get("value") or "").strip()
                if not location:
                    continue
                try:
                    value = int(row.get("count") or 0)
                except (TypeError, ValueError):
                    value = 0
                location_bars.append(
                    {
                        "label": location,
                        "value": value,
                        "delta": (
                            None if all_time else value - prev_locs.get(location, 0)
                        ),
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
