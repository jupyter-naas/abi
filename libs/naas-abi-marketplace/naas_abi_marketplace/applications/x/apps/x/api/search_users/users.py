"""Publish the Users page dataset: every author in the tweet graph, sharded.

The web app reads this dataset straight from object storage — no SPARQL runs at
request time — so everything the page needs has to be here::

    search_users/
    ├── users.json          # the search index: every author, compact rows
    ├── shards.json         # shard manifest (content hashes, counts)
    └── posts/<shard>.json  # profile + every post, for the authors in a shard

Authors are grouped into :data:`USER_SHARD_COUNT` post files by
``sha1(username)`` (see :func:`user_shard`), so selecting an author downloads
one small file instead of the whole dataset, and pagination by 100 happens in
the browser over the author's full post list.

Re-publishing is incremental in three stages:

0. ``shards.json`` records the tweet graph's ``source_state`` — its post total
   and newest timestamp. When that pair is unchanged the dataset cannot have
   changed either, so the publish returns immediately and the two full-graph
   aggregates below are never run. This is the common case on a quiet tick.
1. Each shard carries a ``fingerprint`` in ``shards.json`` — a digest of the
   tweet-derived state (``username``, post count, ``last_post_at``) of its
   authors, all of which comes from the single :meth:`all_authors` aggregate.
   A shard whose fingerprint is unchanged is **not queried at all**: its posts
   and accounts are never fetched and its manifest entry is carried forward.
2. A shard that *was* rebuilt is still only re-uploaded when its serialized
   bytes differ from the last publish.

Stage 1 is what keeps a republish cheap when posts *did* land. Without it every publish ran
``posts_for_usernames`` over *every* author — a full dump of the tweet graph,
with a media join and ``GROUP_CONCAT`` per post — on a dataset that only grows.
On a typical ingest tick a handful of authors post, so one or two of the 256
shards are stale and the rest cost nothing.

The trade-off: a profile edit (bio, follower counts) that arrives *without* a
new post does not move the fingerprint, so it lands on the shard's next
rebuild. Accounts are re-ingested whenever the author tweets again, and
``publish(ctx, full=True)`` forces a complete rebuild on demand.
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
# search page has to download.
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
    "description",
]

# Bumped whenever the on-disk shape changes, so a web app served from a stale
# export can tell it is looking at a dataset it does not understand.
#
# NOT bumped for ``description``: it is a trailing column, so both directions
# degrade rather than break — an older app destructures the columns it knows and
# ignores it, a newer one reads it as empty when an older publish omits it. The
# format also gates shard reuse below, and a bump would force all
# :data:`USER_SHARD_COUNT` shards to be re-queried for a change that touches
# none of them.
DATASET_FORMAT = 1

# Bios are rendered as the one-line snippet under a search result, and X caps
# them at 160 characters anyway; the cap is what bounds this column's share of
# a ~60k-row index.
MAX_DESCRIPTION_CHARS = 160


def _index_row(author: dict[str, Any], descriptions: dict[str, str]) -> list[Any]:
    username = author.get("username", "")
    description = descriptions.get(username, "")
    if len(description) > MAX_DESCRIPTION_CHARS:
        description = description[: MAX_DESCRIPTION_CHARS - 1].rstrip() + "…"
    return [
        username,
        int(author.get("posts") or 0),
        author.get("last_post_at") or "",
        author.get("location") or "",
        author.get("verified_type") or "",
        user_shard(username),
        description,
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


def _shard_fingerprint(shard_authors: list[dict[str, Any]]) -> str:
    """Digest of the tweet-derived state that decides a shard's content.

    Built purely from the :meth:`all_authors` rows, so deciding whether a shard
    is stale costs no extra SPARQL. ``posts`` and ``last_post_at`` move whenever
    an author in the shard gains a post, which is the only thing that changes a
    shard's post lists; ``location`` / ``verified_type`` are included because
    they are published in the profile too.
    """
    rows = sorted(
        [
            author.get("username", ""),
            int(author.get("posts") or 0),
            author.get("last_post_at") or "",
            author.get("location") or "",
            author.get("verified_type") or "",
        ]
        for author in shard_authors
    )
    return content_digest(encode_compact(rows))


def publish(ctx: SnapshotContext, *, full: bool = False) -> dict:
    """Write the Users dataset and return a summary.

    Deliberately *not* scoped by followed query or scenario window: the Users
    page looks an author up across the entire tweet graph.

    Only shards whose fingerprint changed since the last publish are queried and
    rebuilt. Pass *full* to rebuild every shard regardless — also what happens
    automatically when the previous manifest is missing or was written by a
    different dataset format / shard layout.

    Before any of that, the whole rebuild is skipped when the tweet graph has not
    moved since the last publish — see :meth:`SnapshotContext.tweet_graph_state`.
    """
    previous_doc = ctx.read_json("search_users", "shards.json") or {}
    previous = previous_doc.get("shards") or {}
    # A manifest from a different format / shard layout describes files this
    # publish cannot reuse, and one without fingerprints (written before this
    # was incremental) can't be compared — either way, rebuild everything once.
    reusable = (
        not full
        and previous_doc.get("format") == DATASET_FORMAT
        and previous_doc.get("shard_hex") == USER_SHARD_HEX
    )

    # Whatever backs this dataset, the rebuild is skipped when the source has not
    # moved. With the projection that signal is its watermark (one small read);
    # against the graph it is a post-count/newest-timestamp probe.
    cache = getattr(ctx, "cache", None)
    source_state = (
        cache.projection_state() if cache is not None else ctx.tweet_graph_state()
    )
    if reusable and source_state and previous_doc.get("source_state") == source_state:
        logger.info(
            f"X app users dataset: source unchanged ({source_state}) — "
            "kept the published dataset"
        )
        return {
            "skipped": True,
            "users": int(previous_doc.get("count") or 0),
            "posts": sum(int((e or {}).get("posts") or 0) for e in previous.values()),
            "shards_rebuilt": 0,
            "shards_written": 0,
            "shards_unchanged": len(previous),
        }

    if cache is not None:
        authors = cache.author_index()
        descriptions = cache.descriptions()
    else:
        authors = ctx.all_authors()
        descriptions = ctx.all_descriptions()

    # Digested without ``updated_at`` so an unchanged index is recognised as
    # unchanged — the timestamp alone would make every publish look different
    # and re-upload a multi-MB file for nothing.
    index_body = {
        "format": DATASET_FORMAT,
        "shard_hex": USER_SHARD_HEX,
        "count": len(authors),
        "columns": INDEX_COLUMNS,
        "users": [_index_row(a, descriptions) for a in authors],
    }
    index_hash = content_digest(encode_compact(index_body))
    if reusable and previous_doc.get("index_hash") == index_hash:
        index_written = False
    else:
        ctx.save_bytes(
            "search_users",
            "users.json",
            encode_compact({"updated_at": ctx.built_at.isoformat(), **index_body}),
        )
        index_written = True
    logger.info(
        f"X app users dataset: indexed {len(authors)} author(s), "
        f"{len(descriptions)} with a bio"
        f"{'' if index_written else ' (index unchanged, not re-uploaded)'}"
    )

    if not authors:
        empty = {
            "updated_at": ctx.built_at.isoformat(),
            "format": DATASET_FORMAT,
            "shard_hex": USER_SHARD_HEX,
            "count": 0,
            "index_hash": index_hash,
            "source_state": source_state,
            "shards": {},
        }
        ctx.save_json_compact("search_users", "shards.json", empty)
        return {
            "users": 0,
            "posts": 0,
            "shards_rebuilt": 0,
            "shards_written": 0,
            "shards_unchanged": 0,
        }

    # Group by shard from the index alone — no per-author query yet.
    by_shard: dict[str, list[dict[str, Any]]] = {}
    for author in authors:
        by_shard.setdefault(user_shard(author["username"]), []).append(author)

    fingerprints = {shard: _shard_fingerprint(rows) for shard, rows in by_shard.items()}
    stale = [
        shard
        for shard, fingerprint in fingerprints.items()
        if not reusable or (previous.get(shard) or {}).get("fingerprint") != fingerprint
    ]

    # The expensive pair — one full-graph post dump each on the SPARQL path — now
    # sees only the authors sitting in a stale shard.
    stale_usernames = [a["username"] for shard in stale for a in by_shard[shard]]
    if cache is not None:
        # The projection is already resident, so the shard filter buys nothing on
        # the accounts side; posts are still narrowed to the stale authors.
        accounts = cache.accounts_by_username() if stale_usernames else {}
        posts_by_user = (
            cache.posts_by_username(stale_usernames) if stale_usernames else {}
        )
    else:
        accounts = (
            ctx.accounts_for_usernames(stale_usernames) if stale_usernames else {}
        )
        posts_by_user = (
            ctx.posts_for_usernames(stale_usernames) if stale_usernames else {}
        )
    logger.info(
        f"X app users dataset: {len(stale)}/{len(by_shard)} shard(s) stale — "
        f"queried posts for {len(stale_usernames)} of {len(authors)} author(s)"
    )

    manifest: dict[str, Any] = {}
    total_posts = 0
    written = 0
    unchanged = 0
    stale_set = set(stale)
    for shard in sorted(by_shard):
        if shard not in stale_set:
            # Untouched: carry the previous entry forward, file and all.
            entry = dict(previous.get(shard) or {})
            entry["fingerprint"] = fingerprints[shard]
            manifest[shard] = entry
            total_posts += int(entry.get("posts") or 0)
            unchanged += 1
            continue

        shard_authors = {
            author["username"]: {
                "profile": _profile(author, accounts.get(author["username"], {})),
                "posts": posts_by_user.get(author["username"], []),
            }
            for author in by_shard[shard]
        }
        # Serialized once: the same bytes decide whether to write and are what
        # gets written.
        payload = encode_compact(
            {"format": DATASET_FORMAT, "shard": shard, "authors": shard_authors}
        )
        digest = content_digest(payload)
        shard_posts = sum(len(a["posts"]) for a in shard_authors.values())
        total_posts += shard_posts
        manifest[shard] = {
            "hash": digest,
            "fingerprint": fingerprints[shard],
            "authors": len(shard_authors),
            "posts": shard_posts,
            "bytes": len(payload),
        }
        # A rebuilt shard can still be byte-identical (e.g. a fingerprint that
        # moved on a field the payload does not carry) — don't re-upload it.
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
        "count": len(authors),
        # Both are read back on the next publish: ``source_state`` to decide
        # whether to rebuild at all, ``index_hash`` to decide whether users.json
        # needs re-uploading.
        "source_state": source_state,
        "index_hash": index_hash,
        "shards": manifest,
    }
    ctx.save_json_compact("search_users", "shards.json", manifest_doc)

    summary = {
        "users": len(authors),
        "posts": total_posts,
        "index_written": index_written,
        "shards_rebuilt": len(stale),
        "shards_written": written,
        "shards_unchanged": unchanged,
    }
    logger.info(f"X app users dataset: {summary}")
    return summary
