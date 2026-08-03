"""Publish ``search_recents_tweets/tables.json`` — tweets + authors tables."""

from __future__ import annotations

from naas_abi_marketplace.applications.x.apps.x.api.common import (
    SnapshotContext,
    slugify,
)

TWEETS_COLUMNS = [
    {"key": "created_at", "label": "Date"},
    {"key": "text", "label": "Text"},
    {"key": "username", "label": "Author"},
    {"key": "location", "label": "Location"},
    {"key": "verified_type", "label": "Verified"},
    {"key": "url", "label": "URL"},
]

AUTHORS_COLUMNS = [
    {"key": "rank", "label": "#"},
    {"key": "username", "label": "Author"},
    {"key": "location", "label": "Location"},
    {"key": "verified", "label": "Verified"},
    {"key": "tweet_count", "label": "Tweets"},
]


def _author_rows(tweets: list[dict]) -> list[dict]:
    by_user: dict[str, dict] = {}
    for t in tweets:
        u = t.get("username") or "—"
        e = by_user.get(u) or {
            "username": u,
            "location": t.get("location") or "",
            "verified": t.get("verified_type") or "",
            "tweet_count": 0,
        }
        e["tweet_count"] += 1
        if not e["location"] and t.get("location"):
            e["location"] = t["location"]
        if not e["verified"] and t.get("verified_type"):
            e["verified"] = t["verified_type"]
        by_user[u] = e
    ranked = sorted(by_user.values(), key=lambda r: r["tweet_count"], reverse=True)
    for i, row in enumerate(ranked, start=1):
        row["rank"] = i
    return ranked


def publish(ctx: SnapshotContext) -> dict:
    tables: list[dict] = []
    for entry in ctx.queries:
        query_string = str(entry.get("query") or "").strip()
        if not query_string:
            continue
        slug = slugify(entry.get("name") or query_string)
        for scenario in ctx.scenarios:
            tweets = ctx.tweets_in_window(
                query_string, scenario["start_time"], scenario["end_time"]
            )
            tables.append(
                {
                    "id": "tweets",
                    "query_slug": slug,
                    "scenario_id": scenario["id"],
                    "columns": TWEETS_COLUMNS,
                    "rows": tweets,
                }
            )
            tables.append(
                {
                    "id": "authors",
                    "query_slug": slug,
                    "scenario_id": scenario["id"],
                    "columns": AUTHORS_COLUMNS,
                    "rows": _author_rows(tweets),
                }
            )
    doc = {"updated_at": ctx.built_at.isoformat(), "tables": tables}
    ctx.save_json("search_recents_tweets", "tables.json", doc)
    return doc
