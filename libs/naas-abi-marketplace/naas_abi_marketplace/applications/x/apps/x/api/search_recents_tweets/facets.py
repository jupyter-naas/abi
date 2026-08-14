"""Publish ``search_recents_tweets/facets.json`` — column filter value lists.

The tweet table publishes the newest :data:`DEFAULT_TWEET_LIMIT` rows per query
and scenario, but the column-filter checkboxes should offer the values that
exist in the *whole* window, not just the ones that happen to appear in that
page. Those value lists are aggregated here at publish time so the web app can
render them without querying the graph.

One entry per ``query_slug`` × ``scenario_id`` × faceted column, capped at
:data:`MAX_FACET_VALUES` values (most frequent first).

The value lists come from :meth:`SnapshotContext.facet_values_for_window`, which
aggregates each column once across the scenario bands and sums the per-scenario
totals in Python — one scan per column rather than one per column per scenario.
"""

from __future__ import annotations

from naas_abi_marketplace.applications.x.apps.x.api.common import (
    TWEET_FACET_COLUMNS,
    SnapshotContext,
    slugify,
)

# Values listed per column. The column filter has its own search box, so this only
# needs to cover "the values worth ticking" rather than every distinct string.
MAX_FACET_VALUES = 500


def publish(ctx: SnapshotContext) -> dict:
    facets: list[dict] = []
    for entry in ctx.queries:
        query_string = str(entry.get("query") or "").strip()
        if not query_string:
            continue
        slug = slugify(entry.get("name") or query_string)
        for scenario in ctx.scenarios:
            for column in TWEET_FACET_COLUMNS:
                values = ctx.facet_values_for_window(
                    query_string,
                    scenario["start_time"],
                    scenario["end_time"],
                    column,
                    limit=MAX_FACET_VALUES,
                )
                facets.append(
                    {
                        "query_slug": slug,
                        "scenario_id": scenario["id"],
                        "column": column,
                        "values": values,
                        "truncated": len(values) >= MAX_FACET_VALUES,
                    }
                )
    doc = {"updated_at": ctx.built_at.isoformat(), "facets": facets}
    ctx.save_json("search_recents_tweets", "facets.json", doc)
    return doc
