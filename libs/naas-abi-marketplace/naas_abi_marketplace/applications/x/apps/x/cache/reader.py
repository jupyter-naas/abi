"""Read side of the X projection — the questions the snapshots actually ask.

Every method here answers something the publish previously asked SPARQL for, and
answers it by scanning columnar data instead of the whole graph. The cost of a
windowed question is set by the months it touches, not by total history, which is
the property the graph path could not offer.

A reader is built once per publish and holds what it loads, mirroring
``SnapshotContext``: the page scripts ask for overlapping windows repeatedly and
must not pay for the load each time.
"""

from __future__ import annotations

import io
from datetime import datetime, timedelta
from typing import Any

from naas_abi_core import logger
from naas_abi_core.services.object_storage.ObjectStorageService import (
    ObjectStorageService,
)
from naas_abi_marketplace.applications.x.apps.x.cache.schema import (
    AUTHORS_KEY,
    CACHE_PREFIX,
    KIND_MATCHED,
    KIND_REFERENCED,
    MANIFEST_KEY,
    POSTS_DIR,
    author_schema,
    post_schema,
)
from naas_abi_marketplace.applications.x.apps.x.cache.storage import split_key, walk

# Author columns the post-level views need. Kept narrow so the join stays cheap;
# the full profile is only read for the Users dataset.
_JOIN_COLUMNS = ["author_id", "username", "location", "verified_type"]


def _months_between(start: datetime, end: datetime) -> list[str]:
    """Every ``YYYY-MM`` partition overlapping ``[start, end)``."""
    months: list[str] = []
    cursor = start.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    while cursor <= end:
        months.append(cursor.strftime("%Y-%m"))
        cursor = (cursor + timedelta(days=32)).replace(day=1)
    return months


class CacheReader:
    """Query surface over the published Parquet projection."""

    def __init__(self, object_storage: ObjectStorageService) -> None:
        self.object_storage = object_storage
        self._posts: dict[tuple[str, ...] | None, Any] = {}
        self._authors: Any | None = None
        self._matched_ids: Any | None = None

    def projection_state(self) -> dict[str, Any]:
        """Cheap staleness signal: the projection's watermark and schema version.

        A consumer that only needs to know *whether* anything changed reads this
        instead of loading any Parquet — the watermark moves exactly when new
        envelopes have been projected.
        """
        import json

        try:
            raw = self.object_storage.get_object(CACHE_PREFIX, MANIFEST_KEY)
            doc = json.loads(raw.decode("utf-8"))
        except Exception:  # noqa: BLE001 — no projection yet
            return {}
        if not isinstance(doc, dict):
            return {}
        return {
            "watermark": str(doc.get("watermark") or ""),
            "schema_version": doc.get("schema_version"),
            "envelopes_total": doc.get("envelopes_total"),
        }

    # ----- loading ---------------------------------------------------------

    def _read_parquet_objects(self, prefix: str) -> list[Any]:
        """Every part file under *prefix*, oldest part first.

        The order matters: :meth:`posts` keeps the *last* row of each duplicate
        group, so "last" has to mean "most recently projected". Part names carry
        the projection stamp (``part-<YYYYmmddTHHMMSSffffff>.parquet``) and live
        under a ``ym=`` prefix a row's ``created_at`` fully determines, so sorting
        the keys orders each partition chronologically. Sorting is not optional —
        ``list_objects`` is ``os.listdir`` order on the filesystem adapter.
        """
        import polars as pl

        frames = []
        for key in sorted(walk(self.object_storage, prefix, suffix=".parquet")):
            directory, name = split_key(key)
            try:
                raw = self.object_storage.get_object(directory, name)
            except Exception as exc:  # noqa: BLE001
                logger.warning(f"X cache reader: could not read {key} ({exc})")
                continue
            frames.append(pl.read_parquet(io.BytesIO(raw)))
        return frames

    def authors(self):
        """The author dimension table."""
        import polars as pl

        if self._authors is None:
            try:
                raw = self.object_storage.get_object(CACHE_PREFIX, AUTHORS_KEY)
                self._authors = pl.read_parquet(io.BytesIO(raw))
            except Exception as exc:  # noqa: BLE001 — no projection yet
                logger.warning(f"X cache reader: no authors table ({exc})")
                self._authors = pl.DataFrame([], schema=author_schema())
        return self._authors

    def posts(self, months: list[str] | None = None):
        """Posts joined to their author, for *months* (all of history if ``None``).

        One row per ``(tweet_id, kind, query_slug)``, newest projection winning.
        The write side can only enforce that within a single refresh batch — an
        incremental run appends a part file rather than rewriting the month — so
        a post carried by envelopes from two different refreshes lands in two
        parts and has to be collapsed here. Newest wins because the mutable
        columns (the engagement metrics) are a snapshot at ingest time, and the
        later observation is the truer one.

        Referenced rows whose id appears as matched anywhere are dropped, because
        that is what the graph shows: ``XSearchRecentTweetsPipeline`` lets match
        typing win, so a post that ever answered the query is never context. The
        exclusion has to be global rather than per-envelope — a post can be
        referenced on one tick and matched on the next.
        """
        import polars as pl

        cache_key = tuple(months) if months else None
        if cache_key in self._posts:
            return self._posts[cache_key]

        prefixes = [f"{POSTS_DIR}/ym={m}" for m in months] if months else [POSTS_DIR]
        frames: list[Any] = []
        for prefix in prefixes:
            frames.extend(self._read_parquet_objects(prefix))
        if not frames:
            df = pl.DataFrame([], schema=post_schema())
        else:
            df = pl.concat(frames, how="vertical_relaxed").unique(
                subset=["tweet_id", "kind", "query_slug"], keep="last"
            )

        matched_ids = self._all_matched_ids()
        if matched_ids is not None and not df.is_empty():
            df = df.filter(
                (pl.col("kind") == KIND_MATCHED)
                | ~pl.col("tweet_id").is_in(matched_ids)
            )

        authors = self.authors()
        if not authors.is_empty():
            df = df.join(authors.select(_JOIN_COLUMNS), on="author_id", how="left")
        else:
            df = df.with_columns(
                pl.lit("").alias("username"),
                pl.lit("").alias("location"),
                pl.lit("").alias("verified_type"),
            )
        df = df.with_columns(
            pl.col("username").fill_null(""),
            pl.col("location").fill_null(""),
            pl.col("verified_type").fill_null(""),
        )
        self._posts[cache_key] = df
        return df

    def _all_matched_ids(self):
        """Ids that matched in *any* month — one narrow column over history."""
        import polars as pl

        if self._matched_ids is None:
            frames = self._read_parquet_objects(POSTS_DIR)
            if not frames:
                return None
            ids = (
                pl.concat(
                    [f.select("tweet_id", "kind") for f in frames],
                    how="vertical_relaxed",
                )
                .filter(pl.col("kind") == KIND_MATCHED)
                .select("tweet_id")
                .unique()
            )
            self._matched_ids = ids.get_column("tweet_id").implode()
        return self._matched_ids

    def known_query_slugs(self) -> set[str]:
        """Every ``query_slug`` the projection holds rows for.

        Callers scope their reads by slug, and a slug the projection has never
        seen would silently answer zero. Exposing the set lets a caller check
        first and fall back to the graph instead of publishing an empty window.
        """
        posts = self.posts()
        if posts.is_empty():
            return set()
        return set(posts.get_column("query_slug").unique().to_list())

    def window(
        self,
        start_time: str,
        end_time: str,
        *,
        kind: str = KIND_MATCHED,
        query_slug: str | None = None,
    ):
        """Rows of *kind* in ``[start, end)``, optionally for one query only.

        *query_slug* scopes the read the way the SPARQL path scopes on the
        ``SearchQuery`` it came from. Leaving it ``None`` spans every followed
        query, which is only right for genuinely cross-query questions — the
        per-query snapshots must always pass it.
        """
        import polars as pl

        start = datetime.fromisoformat(start_time)
        end = datetime.fromisoformat(end_time)
        df = self.posts(_months_between(start, end))
        predicate = (
            (pl.col("kind") == kind)
            & (pl.col("created_at") >= start)
            & (pl.col("created_at") < end)
        )
        if query_slug is not None:
            predicate = predicate & (pl.col("query_slug") == query_slug)
        return df.filter(predicate)

    # ----- the questions the snapshots ask ---------------------------------

    def count_in_window(
        self,
        start_time: str,
        end_time: str,
        *,
        referenced: bool = False,
        query_slug: str | None = None,
    ) -> int:
        kind = KIND_REFERENCED if referenced else KIND_MATCHED
        return self.window(
            start_time, end_time, kind=kind, query_slug=query_slug
        ).height

    def facet_values(
        self,
        start_time: str,
        end_time: str,
        column: str,
        *,
        limit: int = 500,
        query_slug: str | None = None,
    ) -> list[dict[str, Any]]:
        """Distinct values of *column* with post counts, most frequent first.

        Values are keyed on their displayed (stripped) form so whitespace
        variants of one place — ``"USA"`` and ``"USA "`` both live in
        ``user_location`` — become a single entry rather than duplicate
        checkboxes splitting a count.
        """
        import polars as pl

        if column not in {"username", "location", "verified_type"}:
            return []
        rows = (
            self.window(start_time, end_time, query_slug=query_slug)
            .with_columns(pl.col(column).str.strip_chars().alias("value"))
            .group_by("value")
            .agg(pl.col("tweet_id").n_unique().alias("count"))
            .sort(["count", "value"], descending=[True, False])
            .head(limit)
        )
        return [
            {"value": r["value"], "count": int(r["count"])}
            for r in rows.iter_rows(named=True)
        ]

    def newest_posts(
        self,
        start_time: str,
        end_time: str,
        *,
        limit: int = 1000,
        query_slug: str | None = None,
    ) -> list[dict[str, Any]]:
        """The newest *limit* posts in the window, shaped like the table rows.

        Key-for-key what ``SnapshotContext._search_tweets`` returns, so either
        source can feed the tables / barcharts / linecharts unchanged — including
        ``text`` preferring ``full_text``, which is how the SPARQL path resolves
        a long post's untruncated content.
        """
        rows = (
            self.window(start_time, end_time, query_slug=query_slug)
            .sort("created_at", descending=True)
            .head(limit)
        )
        out: list[dict[str, Any]] = []
        for r in rows.iter_rows(named=True):
            username = r["username"] or ""
            out.append(
                {
                    "created_at": r["created_at"].isoformat(),
                    "text": r["full_text"] or r["text"] or "",
                    "url": (
                        f"https://x.com/{username}/status/{r['tweet_id']}"
                        if username
                        else ""
                    ),
                    "username": username,
                    "location": r["location"] or "",
                    "verified_type": r["verified_type"] or "",
                }
            )
        return out

    def author_index(self) -> list[dict[str, Any]]:
        """Every author with all-time post totals — the Users search index.

        Counts unique tweet ids across matches *and* referenced context (a
        quoted/replied-to/retweeted original this account wrote). ``posts()``
        already drops a referenced row whose id matched somewhere, so a post
        is not counted twice.
        """
        import polars as pl

        posts = self.posts()
        if posts.is_empty():
            return []
        agg = (
            posts.filter(pl.col("username") != "")
            .group_by("username")
            .agg(
                pl.col("tweet_id").n_unique().alias("posts"),
                pl.col("created_at").max().alias("last_post_at"),
                pl.col("created_at").min().alias("first_post_at"),
                pl.col("location").first().alias("location"),
                pl.col("verified_type").first().alias("verified_type"),
            )
            .sort("posts", descending=True)
        )
        return [
            {
                "username": r["username"],
                "posts": int(r["posts"]),
                "last_post_at": r["last_post_at"].isoformat()
                if r["last_post_at"]
                else "",
                "first_post_at": r["first_post_at"].isoformat()
                if r["first_post_at"]
                else "",
                "location": r["location"] or "",
                "verified_type": r["verified_type"] or "",
            }
            for r in agg.iter_rows(named=True)
        ]

    def descriptions(self) -> dict[str, str]:
        """Author bios keyed by username, for the search index snippet."""
        import polars as pl

        authors = self.authors()
        if authors.is_empty():
            return {}
        rows = authors.filter(
            (pl.col("username") != "") & (pl.col("description") != "")
        ).select("username", "description")
        return {
            r["username"]: " ".join(str(r["description"]).split())
            for r in rows.iter_rows(named=True)
        }

    def posts_by_username(self, usernames: list[str]) -> dict[str, list[dict]]:
        """Every post by each of *usernames*, newest first.

        Includes search matches and referenced context (quote/reply/retweet
        originals this account wrote). One row per tweet id: when the same
        post is a match for one query and context for another, the match
        wins. Context-only rows are flagged ``referenced=True`` so the
        author page can tell them apart; matches omit the key.
        """
        import polars as pl

        wanted = set(usernames)
        posts = self.posts()
        if posts.is_empty() or not wanted:
            return {}
        rows = (
            posts.filter(
                (pl.col("username") != "") & pl.col("username").is_in(list(wanted))
            )
            .with_columns((pl.col("kind") == KIND_MATCHED).alias("_is_match"))
            .sort(["_is_match", "created_at"], descending=[True, True])
            .unique(subset=["username", "tweet_id"], keep="first")
            .sort("created_at", descending=True)
        )
        out: dict[str, list[dict]] = {}
        for r in rows.iter_rows(named=True):
            username = r["username"]
            post: dict[str, Any] = {
                "created_at": r["created_at"].isoformat(),
                # ``full_text`` first, matching ``posts_for_usernames`` — a long
                # post is truncated in ``text`` and whole only in ``full_text``.
                "text": r["full_text"] or r["text"] or "",
                "url": f"https://x.com/{username}/status/{r['tweet_id']}",
                "username": username,
            }
            if r["media_urls"]:
                post["media_url"] = r["media_urls"]
            if r["kind"] == KIND_REFERENCED:
                post["referenced"] = True
            out.setdefault(username, []).append(post)
        return out

    def accounts_by_username(self) -> dict[str, dict[str, Any]]:
        """Full profile per username, shaped like the published Users payload."""
        authors = self.authors()
        if authors.is_empty():
            return {}
        out: dict[str, dict[str, Any]] = {}
        for r in authors.iter_rows(named=True):
            username = (r["username"] or "").strip()
            if not username:
                continue
            account: dict[str, Any] = {
                "author_id": r["author_id"],
                "display_name": r["display_name"],
                "description": r["description"],
                "user_url": r["user_url"],
                "user_created_at": r["user_created_at"],
                "profile_image_url": r["profile_image_url"],
                "profile_banner_url": r["profile_banner_url"],
                "verified": r["verified"],
                "is_identity_verified": r["is_identity_verified"],
                "protected": r["protected"],
                "most_recent_tweet_id": r["most_recent_tweet_id"],
                "metrics": {
                    "followers_count": r["followers_count"],
                    "following_count": r["following_count"],
                    "tweet_count": r["tweet_count"],
                    "listed_count": r["listed_count"],
                    "like_count": r["user_like_count"],
                    "media_count": r["media_count"],
                },
            }
            if r["location"]:
                account["location"] = r["location"]
            if r["verified_type"]:
                account["verified_type"] = r["verified_type"]
            out[username] = account
        return out
