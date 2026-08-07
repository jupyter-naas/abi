"""Publish ``search_recents_tweets/kpis.json``.

``tweets_ingested`` is a full (uncapped) SPARQL count over the scenario window.
Its value is every post ingested for the query — matched tweets *plus* the
referenced tweets the expansions returned as context — with the two broken out
in ``matched`` / ``referenced`` and summarised in the hint. ``coverage`` stays
matched-only, since the count endpoint it divides into only counts matches.
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

            # Uncapped cardinality — one SPARQL count per population per
            # scenario. ``matched`` is the tweets that answered the query;
            # ``referenced`` is the reply parents, quoted tweets and retweeted
            # originals the expansions pulled in as context. Both were ingested,
            # so the headline KPI is their sum, split out in the hint.
            matched = ctx.count_tweets_in_window(query_string, start, end, limit=0)
            referenced = ctx.count_referenced_tweets_in_window(
                query_string, start, end, limit=0
            )
            ingested = matched + referenced
            prev_matched = ctx.count_tweets_in_window(
                query_string, prev_start, prev_end, limit=0
            )
            prev_referenced = ctx.count_referenced_tweets_in_window(
                query_string, prev_start, prev_end, limit=0
            )
            prev_ingested = prev_matched + prev_referenced
            total = ctx.sum_counts_in_window(query_string, start, end)
            prev_total = ctx.sum_counts_in_window(query_string, prev_start, prev_end)
            # Coverage is measured against the count endpoint's total for the
            # query, whose population is matches only — referenced tweets never
            # answered the query, so folding them in here would push coverage
            # past 100%.
            coverage = (100.0 * matched / total) if total > 0 else None
            prev_coverage = (
                (100.0 * prev_matched / prev_total) if prev_total > 0 else None
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
                            "label": "Total Posts Ingested",
                            "value": ingested,
                            "prev_value": prev_ingested,
                            "delta": ingested - prev_ingested,
                            "matched": matched,
                            "referenced": referenced,
                            "hint": (
                                f"{matched} tweets · {referenced} referenced"
                                if ingested
                                else "no posts ingested"
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
