"""Publish ``search_recents_tweets/kpis.json``.

Four cards per query × scenario, all uncapped over the window:

* ``tweets_ingested`` — matched + referenced, delta vs the previous window,
  hint is the coverage period.
* ``tweets`` — matched only, delta vs previous, hint is share of posts ingested.
* ``referenced_tweets`` — expansion context, same shape as ``tweets``.
* ``coverage`` — matched / count-endpoint total (referenced excluded, or
  coverage would exceed 100%). Hint is that count-endpoint total; no
  period-over-period comparison.

Tables / author bars still sample at most ``DEFAULT_TWEET_LIMIT`` rows.
"""

from __future__ import annotations

from naas_abi_marketplace.applications.x.apps.x.api.common import (
    SnapshotContext,
    previous_window,
    slugify,
)


def _share_hint(part: int, whole: int) -> str:
    if whole <= 0:
        return "no posts ingested"
    return f"{round(100.0 * part / whole, 1)}% of posts ingested"


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

            # Uncapped cardinality, summed out of the banded aggregate: one
            # scan per population covers all four scenarios and their previous
            # periods, instead of one scan per window. ``matched`` is the tweets
            # that answered the query; ``referenced`` is the reply parents,
            # quoted tweets and retweeted originals the expansions pulled in as
            # context. Both were ingested, so the headline KPI is their sum.
            matched = ctx.banded_count_for_window(
                query_string, start, end, referenced=False
            )
            referenced = ctx.banded_count_for_window(
                query_string, start, end, referenced=True
            )
            ingested = matched + referenced
            prev_matched = ctx.banded_count_for_window(
                query_string, prev_start, prev_end, referenced=False
            )
            prev_referenced = ctx.banded_count_for_window(
                query_string, prev_start, prev_end, referenced=True
            )
            prev_ingested = prev_matched + prev_referenced
            total = ctx.sum_counts_in_window(query_string, start, end)
            # Coverage is measured against the count endpoint's total for the
            # query, whose population is matches only — referenced tweets never
            # answered the query, so folding them in here would push coverage
            # past 100%.
            coverage = (100.0 * matched / total) if total > 0 else None
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
                            "hint": f"{start} to {end}",
                        },
                        {
                            "id": "tweets",
                            "label": "Tweets",
                            "value": matched,
                            "prev_value": prev_matched,
                            "delta": matched - prev_matched,
                            "hint": _share_hint(matched, ingested),
                        },
                        {
                            "id": "referenced_tweets",
                            "label": "Referenced Tweets",
                            "value": referenced,
                            "prev_value": prev_referenced,
                            "delta": referenced - prev_referenced,
                            "hint": _share_hint(referenced, ingested),
                        },
                        {
                            "id": "coverage",
                            "label": "Coverage",
                            "value": (
                                round(coverage, 1) if coverage is not None else None
                            ),
                            "unit": "%",
                            "hint": (
                                f"{total:,} tweets" if total else "no count data"
                            ),
                        },
                    ],
                }
            )
    doc = {"updated_at": ctx.built_at.isoformat(), "kpis": entries}
    ctx.save_json("search_recents_tweets", "kpis.json", doc)
    return doc
