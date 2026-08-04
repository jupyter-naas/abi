"""Publish the Users page dataset: every author in the tweet graph, sharded.

The web app reads this dataset straight from object storage — no SPARQL runs at
request time — so everything the page needs has to be here::

    search_users/
    ├── users.json          # the picker index: every author, compact rows
    ├── shards.json         # shard manifest (content hashes, counts)
    └── posts/<shard>.json  # profile + every post, for the authors in a shard

Authors are grouped into :data:`USER_SHARD_COUNT` post files by
``sha1(username)`` (see :func:`user_shard`), so selecting an author downloads
one small file instead of the whole dataset, and pagination by 100 happens in
the browser over the author's full post list.

Re-publishing is incremental: a shard whose serialized content is byte-identical
to the last publish is not re-uploaded. That matters because the ingestion
orchestrations republish on every pipeline run, and only a handful of authors
change on a typical tick.
"""

from __future__ import annotations

from typing import Any

from naas_abi_core import logger
from naas_abi_marketplace.applications.x.apps.x.api.common import (
    USER_SHARD_COUNT,
    USER_SHARD_HEX,
    SnapshotContext,
    content_digest,
    encode_compact,
    user_shard,
)

# Column order of the compact rows in ``users.json``. Written as arrays rather
# than objects: at ~60k authors the object form more than doubles the file the
# picker has to download.
#
# ``shard`` is carried per row so the web app never has to hash a username to
# find an author's posts — a browser can only compute sha1 through SubtleCrypto,
# which is undefined on a page served over plain http from a non-localhost host.
INDEX_COLUMNS = [
    "username",
    "posts",
    "last_post_at",
    "location",
    "verified_type",
    "shard",
]

# Bumped whenever the on-disk shape changes, so a web app served from a stale
# export can tell it is looking at a dataset it does not understand.
DATASET_FORMAT = 1


def _index_row(author: dict[str, Any]) -> list[Any]:
    username = author.get("username", "")
    return [
        username,
        int(author.get("posts") or 0),
        author.get("last_post_at") or "",
        author.get("location") or "",
        author.get("verified_type") or "",
        user_shard(username),
    ]


def _profile(author: dict[str, Any], account: dict[str, Any]) -> dict[str, Any]:
    """Merge the tweet-derived aggregates with the account's own fields.

    The account wins where it has a value — ``accounts_for_usernames`` only sets
    ``location`` / ``verified_type`` when the XUser individual actually carries
    one, so a stub account never blanks out the sample taken from the tweets.

    Empty fields are dropped rather than published as ``""`` / ``null``. Most
    authors are ingested as tweet-author stubs carrying almost nothing, and at
    ~60k of them the placeholders are a large share of the dataset. The profile
    card treats a missing field and an empty one identically.
    """
    merged = dict(author)
    merged.update(account)

    profile: dict[str, Any] = {}
    for key, value in merged.items():
        if key == "metrics":
            metrics = {k: v for k, v in (value or {}).items() if v is not None}
            if metrics:
                profile["metrics"] = metrics
            continue
        if value in ("", None):
            continue
        profile[key] = value
    return profile


def publish(ctx: SnapshotContext) -> dict:
    """Write the whole Users dataset and return a summary.

    Deliberately *not* scoped by followed query or scenario window: the Users
    page looks an author up across the entire tweet graph.
    """
    authors = ctx.all_authors()
    usernames = [a["username"] for a in authors]

    index_doc = {
        "updated_at": ctx.built_at.isoformat(),
        "format": DATASET_FORMAT,
        "shard_hex": USER_SHARD_HEX,
        "count": len(authors),
        "columns": INDEX_COLUMNS,
        "users": [_index_row(a) for a in authors],
    }
    ctx.save_json_compact("search_users", "users.json", index_doc)
    logger.info(f"X app users dataset: indexed {len(authors)} author(s)")

    if not usernames:
        empty = {
            "updated_at": ctx.built_at.isoformat(),
            "format": DATASET_FORMAT,
            "shards": {},
        }
        ctx.save_json_compact("search_users", "shards.json", empty)
        return {
            "users": len(authors),
            "posts": 0,
            "shards_written": 0,
            "shards_unchanged": 0,
        }

    accounts = ctx.accounts_for_usernames(usernames)
    posts_by_user = ctx.posts_for_usernames(usernames)

    # Group authors by shard before writing so each shard file is built once.
    grouped: dict[str, dict[str, Any]] = {}
    total_posts = 0
    for author in authors:
        username = author["username"]
        posts = posts_by_user.get(username, [])
        total_posts += len(posts)
        shard = user_shard(username)
        grouped.setdefault(shard, {})[username] = {
            "profile": _profile(author, accounts.get(username, {})),
            "posts": posts,
        }

    previous = (ctx.read_json("search_users", "shards.json") or {}).get("shards") or {}
    manifest: dict[str, Any] = {}
    written = 0
    unchanged = 0
    for shard, shard_authors in sorted(grouped.items()):
        # Serialized once: the same bytes decide whether to write and are what
        # gets written.
        payload = encode_compact(
            {"format": DATASET_FORMAT, "shard": shard, "authors": shard_authors}
        )
        digest = content_digest(payload)
        manifest[shard] = {
            "hash": digest,
            "authors": len(shard_authors),
            "posts": sum(len(a["posts"]) for a in shard_authors.values()),
            "bytes": len(payload),
        }
        if (previous.get(shard) or {}).get("hash") == digest:
            unchanged += 1
            continue
        ctx.save_bytes("search_users/posts", f"{shard}.json", payload)
        written += 1

    manifest_doc = {
        "updated_at": ctx.built_at.isoformat(),
        "format": DATASET_FORMAT,
        "shard_hex": USER_SHARD_HEX,
        "shard_count": USER_SHARD_COUNT,
        "shards": manifest,
    }
    ctx.save_json_compact("search_users", "shards.json", manifest_doc)

    summary = {
        "users": len(authors),
        "posts": total_posts,
        "shards_written": written,
        "shards_unchanged": unchanged,
    }
    logger.info(f"X app users dataset: {summary}")
    return summary
