"""Publish ``globals/graph.json`` - how much is in the tweet graph.

One number the whole app can quote: how many posts the graph holds, split
between the ones that answered a followed query and the ones the expansions
pulled in as context. It is *not* scoped by a query or a window - it is the
size of the dataset behind every page.

Answered from the Parquet projection when there is one (a column scan over ids
already in memory), and from SPARQL otherwise. Both count **distinct tweets**,
so a post carried by two queries or two windows is one post.
"""

from __future__ import annotations

from typing import Any

from naas_abi_core import logger
from naas_abi_marketplace.applications.x.apps.x_proxy.api.common import SnapshotContext


def _counts_from_cache(ctx: SnapshotContext) -> dict[str, int] | None:
    cache = ctx.cache
    if cache is None:
        return None
    import polars as pl

    posts = cache.posts()
    if posts.is_empty():
        return {"posts": 0, "matched": 0, "referenced": 0}
    # One row per (tweet, kind, query): distinct ids are the posts, and a post
    # is matched if any of its rows is - which is how `posts()` already resolves
    # a post that was context for one query and a match for another.
    per_post = posts.group_by("tweet_id").agg(
        (pl.col("kind") == "matched").any().alias("matched")
    )
    matched = int(per_post.get_column("matched").sum())
    total = int(per_post.height)
    return {"posts": total, "matched": matched, "referenced": total - matched}


def _counts_from_sparql(ctx: SnapshotContext) -> dict[str, int]:
    """One scan per class. Both are pure cardinality - no window, no filter."""
    counts: dict[str, int] = {}
    for key, tweet_class in (("posts", "x:Tweet"), ("referenced", "x:ReferencedTweet")):
        sparql = f"""
        PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
        PREFIX x:   <{ctx.namespace}>
        SELECT (COUNT(DISTINCT ?tweet) AS ?n)
        WHERE {{
          GRAPH <{ctx.tweet_graph_name}> {{
            ?tweet rdf:type {tweet_class} .
          }}
        }}
        """
        rows = ctx._query_rows(sparql, f"graph totals ({tweet_class})")
        value = getattr(rows[0], "n", 0) if rows else 0
        counts[key] = int(str(value) or 0)
    # ``x:Tweet`` is the superclass, so the matched posts are what is left.
    counts["matched"] = max(0, counts["posts"] - counts["referenced"])
    return counts


def publish(ctx: SnapshotContext) -> dict[str, Any]:
    counts = _counts_from_cache(ctx)
    source = "projection"
    if counts is None:
        counts = _counts_from_sparql(ctx)
        source = "sparql"
    logger.info(
        f"X app graph totals ({source}): {counts['posts']} post(s), "
        f"{counts['matched']} matched / {counts['referenced']} referenced"
    )
    doc = {"updated_at": ctx.built_at.isoformat(), **counts}
    ctx.save_json("globals", "graph.json", doc)
    return doc
