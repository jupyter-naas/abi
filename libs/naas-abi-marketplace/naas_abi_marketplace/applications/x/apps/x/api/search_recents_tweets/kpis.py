"""Publish ``search_recents_tweets/kpis.json``.

``tweets_ingested`` is a full (uncapped) SPARQL count over the scenario window.
Tables / author bars still sample at most ``DEFAULT_TWEET_LIMIT`` rows.
"""

from __future__ import annotations

from naas_abi_marketplace.applications.x.apps.x.api.common import (
    SnapshotContext,
    previous_window,
    slugify,
)


def publish(ctx: SnapshotContext) -> dict:
    entries: list[dict] = []
    for entry in ctx.queries:
        query_string = str(entry.get("query") or "").strip()
        if not query_string:
            continue
        slug = slugify(entry.get("name") or query_string)
        for scenario in ctx.scenarios:
            start, end = scenario["start_time"], scenario["end_time"]
            prev_start, prev_end = previous_window(start, end)

            # Uncapped cardinality — one SPARQL count per scenario.
            ingested = ctx.count_tweets_in_window(query_string, start, end, limit=0)
            prev_ingested = ctx.count_tweets_in_window(
                query_string, prev_start, prev_end, limit=0
            )
            total = ctx.sum_counts_in_window(query_string, start, end)
            prev_total = ctx.sum_counts_in_window(query_string, prev_start, prev_end)
            coverage = (100.0 * ingested / total) if total > 0 else None
            prev_coverage = (
                (100.0 * prev_ingested / prev_total) if prev_total > 0 else None
            )
            coverage_delta = (
                round(coverage - prev_coverage, 1)
                if coverage is not None and prev_coverage is not None
                else None
            )
            entries.append(
                {
                    "query_slug": slug,
                    "scenario_id": scenario["id"],
                    "items": [
                        {
                            "id": "tweets_ingested",
                            "label": "Total Tweets Ingested",
                            "value": ingested,
                            "prev_value": prev_ingested,
                            "delta": ingested - prev_ingested,
                            "hint": (
                                f"{prev_ingested} prev. period"
                                if prev_ingested or prev_total
                                else "no prior period"
                            ),
                        },
                        {
                            "id": "coverage",
                            "label": "Coverage",
                            "value": (
                                round(coverage, 1) if coverage is not None else None
                            ),
                            "prev_value": (
                                round(prev_coverage, 1)
                                if prev_coverage is not None
                                else None
                            ),
                            "delta": coverage_delta,
                            "unit": "%",
                            "hint": (
                                "no count data"
                                if coverage is None
                                else (
                                    f"{round(prev_coverage, 1)}% prev. period"
                                    if prev_coverage is not None
                                    else "no prior period"
                                )
                            ),
                        },
                        {
                            "id": "total",
                            "label": "Total Tweets",
                            "value": total,
                            "prev_value": prev_total,
                            "delta": total - prev_total,
                            "hint": (
                                f"{prev_total} prev. period"
                                if prev_total
                                else "no prior period"
                            ),
                        },
                    ],
                }
            )
    doc = {"updated_at": ctx.built_at.isoformat(), "kpis": entries}
    ctx.save_json("search_recents_tweets", "kpis.json", doc)
    return doc
