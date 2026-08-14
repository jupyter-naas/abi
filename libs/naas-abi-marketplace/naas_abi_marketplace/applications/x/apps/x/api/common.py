"""Shared constants, scenarios, SPARQL helpers and storage I/O for X app snapshots."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Iterable, Iterator
from datetime import UTC, datetime, timedelta
from typing import Any, TypeVar

from naas_abi_core import logger
from naas_abi_core.services.object_storage.ObjectStorageService import (
    ObjectStorageService,
)
from naas_abi_core.services.triple_store.TripleStoreService import TripleStoreService
from naas_abi_core.utils.StorageUtils import StorageUtils

_T = TypeVar("_T")

DEFAULT_COUNT_GRAPH = "http://ontology.naas.ai/graph/x_recent_posts_count"
DEFAULT_TWEET_GRAPH = "http://ontology.naas.ai/graph/x"
DEFAULT_NAMESPACE = "http://ontology.naas.ai/x/"
DEFAULT_APP_PREFIX = "x/apps/x"

# Cap for Search page tweet tables / author bars (KPI counts and the ingested
# tweets line chart are uncapped). ``tweets_in_window`` orders the *full* graph
# match by recency before applying this LIMIT, so a capped read is the newest N
# tweets in the window — never an arbitrary sample.
DEFAULT_TWEET_LIMIT = 1000

# The Users page reads a published dataset rather than querying the graph, so
# the author list is uncapped: every author in the tweet graph is findable.
# These bound the *publish* side instead.
#
# Authors resolved per bulk SPARQL query. The graph-wide dump is split into
# batches of this many usernames (bound with VALUES) so peak memory stays flat
# whatever the graph size — a single unbounded dump of ~110k posts parses into
# hundreds of MB of rdflib terms, which the orchestration container runs on
# every ingest tick.
AUTHOR_BATCH_SIZE = 2000

# Authors are grouped into ``16 ** USER_SHARD_HEX`` post files by the first hex
# digits of sha1(username). Two digits gives 256 shards — a few hundred KB each
# at ~110k posts, so the Users page downloads one small file per selected
# author instead of the whole dataset.
USER_SHARD_HEX = 2
USER_SHARD_COUNT = 16**USER_SHARD_HEX

# Rolling windows shown in the Scenario filter (id / label / hours).
# start_time / end_time are filled at publish time, floored to the clock hour.
SCENARIO_SPECS: list[dict[str, Any]] = [
    {"id": "24h", "label": "Last 24 hours", "hours": 24},
    {"id": "48h", "label": "Last 48 hours", "hours": 48},
    {"id": "7d", "label": "Last 7 days", "hours": 168},
    {"id": "30d", "label": "Last 30 days", "hours": 720},
]


def slugify(value: str) -> str:
    """Filesystem-safe slug for a query string (kept short and stable)."""
    keep = []
    for ch in value.lower():
        keep.append(ch if ch.isalnum() else "_")
    slug = "".join(keep).strip("_")
    while "__" in slug:
        slug = slug.replace("__", "_")
    return slug[:80] or "query"


def user_shard(username: str) -> str:
    """Which post shard an author's tweets are published in.

    Hashed rather than derived from the username's first letter so the shards
    stay evenly filled — usernames cluster hard on a few prefixes.
    """
    digest = hashlib.sha1(username.strip().lower().encode("utf-8")).hexdigest()
    return digest[:USER_SHARD_HEX]


def encode_compact(data: dict | list) -> bytes:
    """Minified UTF-8 JSON — the on-disk form of every published snapshot."""
    return json.dumps(data, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def content_digest(payload: bytes) -> str:
    """Stable content hash, used to skip re-uploading unchanged shards."""
    return hashlib.sha256(payload).hexdigest()


def batched(values: list[str], size: int) -> Iterator[list[str]]:
    """Yield *values* in chunks of at most *size* (never an empty chunk)."""
    step = max(1, int(size))
    for start in range(0, len(values), step):
        yield values[start : start + step]


def build_scenarios(now: datetime | None = None) -> list[dict[str, str]]:
    """Four scenario filters with ``id``, ``label``, ``start_time``, ``end_time``.

    Both edges are floored to the clock hour. The count workflow only ever
    ingests *complete* clock hours, and :meth:`SnapshotContext.aggregate_buckets`
    keeps a bucket only when its ``start`` falls inside the window — so an
    unaligned window silently dropped the partially-overlapped first bucket
    (a publish at 13:02 lost the whole 13:00–14:00 hour). Flooring also makes a
    window reproducible: two publishes in the same hour describe the same range.

    The trade-off is that the in-progress hour is excluded, which is what the
    bucket data supports anyway.
    """
    now = now or datetime.now(UTC)
    end = now.astimezone(UTC).replace(minute=0, second=0, microsecond=0)
    scenarios: list[dict[str, str]] = []
    for spec in SCENARIO_SPECS:
        start = end - timedelta(hours=int(spec["hours"]))
        scenarios.append(
            {
                "id": str(spec["id"]),
                "label": str(spec["label"]),
                "start_time": start.isoformat(),
                "end_time": end.isoformat(),
            }
        )
    return scenarios


def previous_window(start_time: str, end_time: str) -> tuple[str, str]:
    """Equal-length window immediately preceding ``[start_time, end_time)``."""
    start = datetime.fromisoformat(start_time)
    end = datetime.fromisoformat(end_time)
    delta = end - start
    prev_end = start
    prev_start = start - delta
    return prev_start.isoformat(), prev_end.isoformat()


def scenario_bands(
    scenarios: list[dict[str, str]], *, include_previous: bool = True
) -> list[tuple[str, str]]:
    """Consecutive ``[start, end)`` bands that tile every scenario window.

    :func:`build_scenarios` gives every scenario the *same* ``end_time``, so the
    windows are strictly nested and each one — plus each :func:`previous_window`
    — is exactly a union of consecutive bands. Splitting the graph once at every
    window boundary lets a single banded aggregate answer all of them, instead of
    one full scan per window.

    Bands are returned newest first, so band 0 is the most recent slice. Pass
    ``include_previous=False`` for the current windows only, which is all the
    column facets need — the extra previous-period edges would just split the
    aggregate into more groups for no benefit.
    """
    edges: set[str] = set()
    for scenario in scenarios:
        start, end = scenario["start_time"], scenario["end_time"]
        edges.add(start)
        edges.add(end)
        if include_previous:
            prev_start, prev_end = previous_window(start, end)
            edges.add(prev_start)
            edges.add(prev_end)
    ordered = sorted(edges, key=datetime.fromisoformat, reverse=True)
    return [(ordered[i + 1], ordered[i]) for i in range(len(ordered) - 1)]


def bands_for_window(
    bands: list[tuple[str, str]], start_time: str, end_time: str
) -> list[int] | None:
    """Indices of the bands that exactly tile ``[start_time, end_time)``.

    ``None`` when the window is not band-aligned — every caller then falls back
    to querying that window directly, so a caller passing an arbitrary range
    (the HTTP layer does) still gets an exact answer.
    """
    start = datetime.fromisoformat(start_time)
    end = datetime.fromisoformat(end_time)
    indices = [
        index
        for index, (band_start, band_end) in enumerate(bands)
        if datetime.fromisoformat(band_start) >= start
        and datetime.fromisoformat(band_end) <= end
    ]
    if not indices:
        return None
    # The selected bands must cover the window with no gap, or a sum over them
    # would silently under-report.
    covered_start = datetime.fromisoformat(bands[indices[-1]][0])
    covered_end = datetime.fromisoformat(bands[indices[0]][1])
    if covered_start != start or covered_end != end:
        return None
    return indices


def _escape_sparql_string(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def _band_bind_expression(
    bands: list[tuple[str, str]], variable: str = "?created"
) -> str:
    """Nested ``IF`` assigning each row the index of the band it falls in.

    Rows older than the last band are never bound — the query carrying this
    expression also filters to the banded range — so the final ``else`` can be
    the last index rather than a sentinel.
    """
    expression = str(len(bands) - 1)
    for index in range(len(bands) - 2, -1, -1):
        edge = _escape_sparql_string(bands[index][0])
        expression = f'IF({variable} >= "{edge}"^^xsd:dateTime, {index}, {expression})'
    return expression


def extrapolate_partial_hour(
    partial: dict[str, Any] | None,
    buckets: list[dict[str, Any]],
) -> dict[str, Any] | None:
    """Top up an in-progress hour with a J-1 pro-rated estimate.

    The counts endpoint can only report the minutes that have elapsed, so the
    newest point always dips. The missing minutes are estimated from the *same
    clock hour yesterday*, pro-rated:
    ``J1_hour_count * missing_minutes / 60``.

    Returns ``{start, end, observed, estimated_value, missing_minutes, value}``
    where ``value`` is observed + estimate, or ``None`` when there is nothing to
    extrapolate. When yesterday's hour is absent (a gap, or under 24 h of
    history) no estimate is invented — ``value`` is the observed count and
    ``estimated_value`` is 0, so the point is honest rather than guessed.
    """
    if not partial:
        return None
    try:
        hour_start = datetime.fromisoformat(str(partial["start"]))
        observed_end = datetime.fromisoformat(str(partial["end"]))
    except (KeyError, ValueError):
        return None
    observed = int(partial.get("count") or 0)

    elapsed_minutes = (observed_end - hour_start).total_seconds() / 60.0
    missing_minutes = 60.0 - elapsed_minutes
    if missing_minutes <= 0:
        # The hour is effectively complete; nothing to add.
        return {
            "start": hour_start.isoformat(),
            "end": observed_end.isoformat(),
            "observed": observed,
            "estimated_value": 0,
            "missing_minutes": 0,
            "value": observed,
        }

    yesterday = hour_start - timedelta(hours=24)
    j1_count: int | None = None
    for bucket in buckets:
        try:
            if datetime.fromisoformat(str(bucket["start"])) == yesterday:
                j1_count = int(bucket.get("count") or 0)
                break
        except (KeyError, ValueError):
            continue

    estimated = 0 if j1_count is None else round(j1_count * missing_minutes / 60.0)
    return {
        "start": hour_start.isoformat(),
        "end": observed_end.isoformat(),
        "observed": observed,
        "estimated_value": int(estimated),
        "missing_minutes": round(missing_minutes),
        "value": observed + int(estimated),
    }


# Per-column SPARQL expressions for the Search page tweet table. Every entry
# resolves to a plain string (unbound OPTIONALs collapse to "") so the same
# expression works for substring search, exact value-set matching and the
# distinct-value lists behind the column filter checkboxes.
TWEET_COLUMN_EXPRESSIONS: dict[str, str] = {
    "created_at": "STR(?created)",
    "text": ('CONCAT(COALESCE(STR(?fullText), ""), " ", COALESCE(STR(?text), ""))'),
    "url": 'COALESCE(STR(?url), "")',
    "username": 'COALESCE(STR(?username), "")',
    "location": 'COALESCE(STR(?location), "")',
    "verified_type": 'COALESCE(STR(?verifiedType), "")',
}

# Columns whose distinct values are small enough to enumerate as checkboxes.
# ``text`` / ``url`` / ``created_at`` are effectively unique per tweet, so the
# column filter offers substring search on those instead of a value list.
TWEET_FACET_COLUMNS: tuple[str, ...] = ("username", "location", "verified_type")


def normalize_tweet_filters(
    filters: dict[str, Any] | None,
) -> dict[str, dict[str, Any]]:
    """Coerce raw column filters into ``{column: {contains, values}}``.

    Unknown columns are dropped so a caller (including the HTTP layer) can
    never inject an arbitrary expression into the generated SPARQL. Both keys
    are optional: ``contains`` is a case-insensitive substring, ``values`` an
    exact-match set (OR within a column, AND across columns).
    """
    normalized: dict[str, dict[str, Any]] = {}
    for column, spec in (filters or {}).items():
        if column not in TWEET_COLUMN_EXPRESSIONS or not isinstance(spec, dict):
            continue
        contains = str(spec.get("contains") or "").strip()
        raw_values = spec.get("values") or []
        values = [str(v) for v in raw_values] if isinstance(raw_values, list) else []
        if not contains and not values:
            continue
        normalized[column] = {"contains": contains, "values": values}
    return normalized


def _tweet_filter_clauses(filters: dict[str, dict[str, Any]]) -> str:
    """SPARQL FILTER lines for *filters*, matched case-insensitively."""
    clauses: list[str] = []
    for column, spec in filters.items():
        expression = TWEET_COLUMN_EXPRESSIONS[column]
        contains = spec.get("contains") or ""
        if contains:
            needle = _escape_sparql_string(contains.lower())
            clauses.append(
                f'            FILTER(CONTAINS(LCASE({expression}), "{needle}"))'
            )
        values = spec.get("values") or []
        if values:
            literals = ", ".join(
                f'"{_escape_sparql_string(str(v).lower())}"' for v in values
            )
            clauses.append(f"            FILTER(LCASE({expression}) IN ({literals}))")
    return "\n".join(clauses)


def _account_from_row(row: Any) -> dict[str, Any]:
    """Map one ``XUser`` SPARQL row into the profile dict the web app reads.

    The username is returned under ``_username`` so the caller can key on it
    without it also landing in the published payload (it is already the key).
    """

    def _s(key: str) -> str:
        value = getattr(row, key, None)
        return "" if value is None else str(value)

    def _i(key: str) -> int | None:
        value = getattr(row, key, None)
        if value is None:
            return None
        try:
            return int(str(value))
        except (TypeError, ValueError):
            return None

    def _b(key: str) -> bool | None:
        value = getattr(row, key, None)
        if value is None:
            return None
        return str(value).strip().lower() in {"true", "1"}

    account: dict[str, Any] = {
        "_username": _s("username").strip(),
        "author_id": _s("authorId"),
        "display_name": _s("displayName"),
        "description": _s("description"),
        "user_url": _s("userUrl"),
        "user_created_at": _s("userCreatedAt"),
        "profile_image_url": _s("imageUrl"),
        "profile_banner_url": _s("bannerUrl"),
        "verified": _b("verified"),
        "is_identity_verified": _b("identityVerified"),
        "protected": _b("protectedFlag"),
        "pinned_tweet_id": _s("pinnedTweetId"),
        "most_recent_tweet_id": _s("recentTweetId"),
        "metrics": {
            "followers_count": _i("followers"),
            "following_count": _i("following"),
            "tweet_count": _i("tweetCount"),
            "listed_count": _i("listed"),
            "like_count": _i("likes"),
            "media_count": _i("mediaCount"),
        },
    }
    # The account's own values win over the tweet-derived samples merged in by
    # the publisher, so only set them when the account actually carries one.
    if _s("userLocation"):
        account["location"] = _s("userLocation")
    if _s("verifiedType"):
        account["verified_type"] = _s("verifiedType")
    return account


def _account_richness(account: dict[str, Any]) -> int:
    """How many fields an account actually carries — used to pick a winner."""
    filled = sum(
        1 for k, v in account.items() if k != "metrics" and v not in (None, "")
    )
    metrics = account.get("metrics") or {}
    return filled + sum(1 for v in metrics.values() if v is not None)


class SnapshotContext:
    """Runtime context shared by every page/element snapshot script."""

    def __init__(
        self,
        object_storage: ObjectStorageService,
        triple_store: TripleStoreService,
        *,
        queries: list[dict[str, Any]],
        scenarios: list[dict[str, str]] | None = None,
        graph_name: str = DEFAULT_COUNT_GRAPH,
        tweet_graph_name: str = DEFAULT_TWEET_GRAPH,
        namespace: str = DEFAULT_NAMESPACE,
        app_prefix: str = DEFAULT_APP_PREFIX,
        tweet_limit: int = DEFAULT_TWEET_LIMIT,
        built_at: datetime | None = None,
        cache: Any | None = None,
    ) -> None:
        self.object_storage = object_storage
        self.triple_store = triple_store
        self.storage = StorageUtils(object_storage)
        self.queries = list(queries)
        self.scenarios = scenarios or build_scenarios()
        self.graph_name = graph_name
        self.tweet_graph_name = tweet_graph_name
        self.namespace = namespace
        self.app_prefix = app_prefix.rstrip("/")
        self.tweet_limit = int(tweet_limit)
        self.built_at = built_at or datetime.now(UTC)
        # Optional columnar projection of the same ingest. When present, the
        # snapshots that would otherwise scan the whole graph read it instead;
        # everything else keeps using SPARQL, so a missing projection degrades
        # to the previous behaviour rather than failing.
        self.cache = cache
        # Band decompositions of the scenario windows, computed once. ``bands``
        # covers the current *and* previous windows (the KPI counts need both);
        # ``facet_bands`` splits only at the current windows' edges, since the
        # column facets never look at a previous period.
        self.bands = scenario_bands(self.scenarios)
        self.facet_bands = scenario_bands(self.scenarios, include_previous=False)
        # Per-publish SPARQL memo. A SnapshotContext is built once per
        # publish_app run and thrown away, so a hit can never serve state from
        # an earlier publish — and nothing reads the graph at HTTP request time
        # (routes.py serves published objects only), so there is no live path
        # this could go stale on.
        #
        # It exists because the page scripts ask for the same rows repeatedly:
        # tables and barcharts each call tweets_in_window for the same
        # (query, scenario) — and every sum_counts_in_window re-runs the same
        # graph-wide timeseries aggregate. The Search line chart reads
        # ingested_timeseries instead (uncapped matched tweets, by created_at).
        self._query_cache: dict[tuple, Any] = {}
        # Unfiltered tweet pages actually fetched this publish, keyed by
        # (query, end_time, cap) — the pool :meth:`_derive_tweets` reuses so the
        # nested scenario windows cost one scan rather than four.
        self._tweet_pages: dict[tuple[str, str, int], list[tuple[str, list]]] = {}

    def _cache_slug(self, query_string: str) -> str | None:
        """The projection's slug for *query_string*, or ``None`` to use SPARQL.

        Gates every read that could be served columnar. Two conditions, both
        required, and both failing *closed* — an unusable projection returns
        ``None`` and the caller queries the graph exactly as before:

        * a projection is attached at all (``publish_app`` only attaches one it
          could read a watermark from), and
        * it actually holds rows for this query.

        The second is not paranoia. The SPARQL path matches a configured query
        against the ingested ``SearchQuery`` by substring in either direction, so
        it still answers when the two differ; slug equality is exact. Without the
        check, a query renamed since its envelopes were written would publish a
        confident zero instead of falling back to the graph that still has it.
        """
        if self.cache is None:
            return None
        slug = slugify(query_string)
        try:
            known = self._memo(("cache_slugs",), self.cache.known_query_slugs)
        except Exception as exc:  # noqa: BLE001 — an unreadable projection is not fatal
            logger.warning(f"X app: projection unreadable ({exc}); using SPARQL")
            return None
        if slug not in known:
            logger.info(
                f"X app: projection has no rows for {query_string!r} "
                f"(slug {slug!r}); using SPARQL"
            )
            return None
        return slug

    def _memo(self, key: tuple, compute: Callable[[], _T]) -> _T:
        """Run *compute* at most once per *key* for this publish.

        Cached values are handed back **shared, not copied** — callers must
        treat query results as read-only (every current one does: they build
        new dicts rather than mutating rows).
        """
        if key not in self._query_cache:
            self._query_cache[key] = compute()
        return self._query_cache[key]

    @staticmethod
    def _filters_key(filters: dict[str, dict[str, Any]]) -> str:
        """Stable cache-key fragment for a normalized filter set."""
        return json.dumps(filters, sort_keys=True, default=str)

    def _query_rows(self, sparql: str, description: str) -> list[Any]:
        """Run *sparql* and return its rows, or ``[]`` when it fails.

        The materialization is the point: an rdflib-backed adapter — the ``fs``
        local-dev triple store returns ``Graph.query()`` straight through —
        evaluates the query lazily, *during iteration*, not inside ``query()``.
        A ``try`` around the call alone therefore caught nothing, and a SPARQL
        error escaped the fail-soft handler and took down the whole publish
        instead of degrading one snapshot. Jena and Oxigraph parse a full
        result set up front, which is why this only ever bit locally.

        Every caller treats "the query failed" and "the query matched nothing"
        identically — an empty section rather than a broken publish — so one
        empty list serves both.
        """
        try:
            return list(self.triple_store.query(sparql))
        except Exception as exc:  # noqa: BLE001 — degrade this snapshot, not the run
            logger.warning(f"SnapshotContext.{description} failed ({exc})")
            return []

    def save_json(self, relative_dir: str, filename: str, data: dict | list) -> str:
        """Write JSON under ``x/apps/x/<relative_dir>/<filename>``."""
        prefix = f"{self.app_prefix}/{relative_dir}".rstrip("/")
        self.storage.save_json(data, prefix, filename, copy=False)
        path = f"{prefix}/{filename}"
        logger.info(f"X app snapshot: wrote {path}")
        return path

    def read_json(self, relative_dir: str, filename: str) -> dict:
        """Read back a previously published snapshot, ``{}`` when absent."""
        prefix = f"{self.app_prefix}/{relative_dir}".rstrip("/")
        try:
            raw = self.object_storage.get_object(prefix, filename)
        except Exception:  # noqa: BLE001 — absent on a first publish
            return {}
        try:
            decoded = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, ValueError):
            return {}
        return decoded if isinstance(decoded, dict) else {}

    def save_bytes(self, relative_dir: str, filename: str, payload: bytes) -> str:
        """Write raw bytes under ``x/apps/x/<relative_dir>/<filename>``."""
        prefix = f"{self.app_prefix}/{relative_dir}".rstrip("/")
        self.object_storage.put_object(prefix, filename, payload)
        path = f"{prefix}/{filename}"
        logger.debug(f"X app snapshot: wrote {path} ({len(payload)} bytes)")
        return path

    def save_json_compact(
        self, relative_dir: str, filename: str, data: dict | list
    ) -> str:
        """Write minified JSON under ``x/apps/x/<relative_dir>/<filename>``.

        :meth:`save_json` pretty-prints with ``indent=4``, which roughly triples
        the users dataset (tens of MB of tweet text). These files are only ever
        read by the web app, so they are written minified.
        """
        return self.save_bytes(relative_dir, filename, encode_compact(data))

    # ----- SPARQL: counts (hourly buckets) ---------------------------------

    def timeseries(self, query_string: str) -> list[dict[str, Any]]:
        """Hourly ``{start, end, count}`` buckets for *query_string*, oldest first.

        Memoized per publish: every :meth:`sum_counts_in_window` call re-derives
        its total from this same full bucket list.
        """
        return self._memo(
            ("timeseries", query_string), lambda: self._timeseries(query_string)
        )

    def _timeseries(self, query_string: str) -> list[dict[str, Any]]:
        escaped = _escape_sparql_string(query_string)
        sparql = f"""
        PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
        PREFIX x:   <{self.namespace}>
        SELECT ?start ?end (MAX(?count) AS ?tweetCount)
        WHERE {{
          GRAPH <{self.graph_name}> {{
            ?resultSet rdf:type x:TweetCountResultSet ;
                       x:query_string "{escaped}" ;
                       x:containsCountBucket ?bucket .
            ?bucket x:bucket_tweet_count ?count ;
                    x:hasCountInterval ?interval .
            ?interval x:bucket_start ?start .
            OPTIONAL {{ ?interval x:bucket_end ?end . }}
            # Complete hours only. The in-progress-hour slot shares its
            # bucket_start with the hour it belongs to, so including it here
            # would emit a second, non-final point for that hour.
            FILTER(!STRENDS(STR(?interval), "-partial"))
          }}
        }}
        GROUP BY ?start ?end
        ORDER BY ?start
        """
        buckets: list[dict[str, Any]] = []
        rows = self._query_rows(sparql, f"timeseries for {query_string!r}")
        for row in rows:
            start = getattr(row, "start", None)
            if start is None:
                continue
            end = getattr(row, "end", None)
            count = getattr(row, "tweetCount", None)
            buckets.append(
                {
                    "start": str(start),
                    "end": str(end) if end is not None else None,
                    "count": int(str(count)) if count is not None else 0,
                }
            )
        return buckets

    def sum_counts_in_window(
        self, query_string: str, start_time: str, end_time: str
    ) -> int:
        """Sum count-endpoint buckets whose start falls in ``[start, end)``."""
        start_ms = datetime.fromisoformat(start_time).timestamp()
        end_ms = datetime.fromisoformat(end_time).timestamp()
        total = 0
        for bucket in self.timeseries(query_string):
            try:
                t = datetime.fromisoformat(str(bucket["start"])).timestamp()
            except ValueError:
                continue
            if start_ms <= t < end_ms:
                total += int(bucket["count"])
        return total

    def ingested_timeseries(
        self, query_string: str, start_time: str, end_time: str
    ) -> list[dict[str, Any]]:
        """Hourly ``{start, end, count}`` of ingested **matched** tweets.

        Bucketed by each tweet's ``created_at``, not by ingest time. Referenced
        context is excluded — quoted/replied-to originals can predate the
        window. Count-endpoint totals are a different population (what X
        reported, not what was ingested).

        Memoized per publish: the Search line chart derives every scenario
        window (and its previous period) from one span.
        """
        return self._memo(
            ("ingested_timeseries", query_string, start_time, end_time),
            lambda: self._ingested_timeseries(query_string, start_time, end_time),
        )

    def _ingested_timeseries(
        self, query_string: str, start_time: str, end_time: str
    ) -> list[dict[str, Any]]:
        cache = self.cache
        slug = self._cache_slug(query_string)
        if cache is not None and slug is not None:
            return cache.hourly_counts(start_time, end_time, query_slug=slug)
        return self._ingested_timeseries_sparql(query_string, start_time, end_time)

    def _ingested_timeseries_sparql(
        self, query_string: str, start_time: str, end_time: str
    ) -> list[dict[str, Any]]:
        escaped = _escape_sparql_string(query_string)
        start_lit = _escape_sparql_string(start_time)
        end_lit = _escape_sparql_string(end_time)
        sparql = f"""
        PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
        PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>
        PREFIX x:   <{self.namespace}>
        SELECT DISTINCT ?tweet ?created
        WHERE {{
          GRAPH <{self.tweet_graph_name}> {{
            ?sq rdf:type x:SearchQuery ; x:query_string ?qs .
            FILTER(
              CONTAINS(LCASE(STR(?qs)), LCASE("{escaped}"))
              || CONTAINS(LCASE("{escaped}"), LCASE(STR(?qs)))
            )
            ?proc rdf:type x:SearchRecentTweets ;
                  x:usesSearchQuery ?sq ;
                  x:producesSearchResult ?rs .
            ?tweet rdf:type x:Tweet ;
                   x:isContainedInSearchResultSet ?rs ;
                   x:tweet_created_at ?created .
            FILTER(
              ?created >= "{start_lit}"^^xsd:dateTime
              && ?created < "{end_lit}"^^xsd:dateTime
            )
          }}
        }}
        """
        counts: dict[datetime, int] = {}
        rows = self._query_rows(
            sparql,
            f"ingested_timeseries for {query_string!r} [{start_time} → {end_time}]",
        )
        for row in rows:
            raw = getattr(row, "created", None)
            if raw is None:
                continue
            try:
                created = (
                    raw
                    if isinstance(raw, datetime)
                    else datetime.fromisoformat(str(raw))
                )
            except ValueError:
                continue
            if created.tzinfo is None:
                created = created.replace(tzinfo=UTC)
            hour = created.astimezone(UTC).replace(minute=0, second=0, microsecond=0)
            counts[hour] = counts.get(hour, 0) + 1
        return [
            {
                "start": hour.isoformat(),
                "end": (hour + timedelta(hours=1)).isoformat(),
                "count": n,
            }
            for hour, n in sorted(counts.items())
        ]

    # ----- SPARQL: ingested tweets -----------------------------------------

    def count_tweets_in_window(
        self,
        query_string: str,
        start_time: str,
        end_time: str,
        *,
        limit: int | None = None,
    ) -> int:
        """Number of ingested tweets **matching the query** in ``[start, end)``.

        Counts only posts linked to the result set by
        ``x:isContainedInSearchResultSet`` — the X v2 ``data`` array. The reply
        parents, quoted tweets and retweeted originals the expansions pulled in
        are counted by :meth:`count_referenced_tweets_in_window` instead.

        When *limit* is ``None`` or ``<= 0``, the count is uncapped (full graph
        cardinality). A positive *limit* wraps an inner ``SELECT DISTINCT`` with
        ``LIMIT`` — used only when a capped sample is intentional.

        Memoized per publish: adjacent scenarios ask for overlapping windows
        (a scenario's ``previous_window`` is often another's current one).
        """
        cap = None if limit is None or int(limit) <= 0 else int(limit)
        return self._memo(
            ("count_tweets", query_string, start_time, end_time, cap),
            lambda: self._count_posts_in_window(
                query_string,
                start_time,
                end_time,
                tweet_class="x:Tweet",
                membership="x:isContainedInSearchResultSet",
                cap=cap,
            ),
        )

    def count_referenced_tweets_in_window(
        self,
        query_string: str,
        start_time: str,
        end_time: str,
        *,
        limit: int | None = None,
    ) -> int:
        """Number of ingested **referenced** tweets in ``[start, end)``.

        These are the ``x:ReferencedTweet`` individuals a search brought back
        as conversational context for its matches — linked to the result set by
        ``x:isReferencedTweetOfSearchResultSet``. They did not match the query,
        so they are reported alongside the matched count rather than folded
        into it.

        Memoized under its own cache key so a referenced count never collides
        with the matched count for the same window.
        """
        cap = None if limit is None or int(limit) <= 0 else int(limit)
        return self._memo(
            ("count_referenced_tweets", query_string, start_time, end_time, cap),
            lambda: self._count_posts_in_window(
                query_string,
                start_time,
                end_time,
                tweet_class="x:ReferencedTweet",
                membership="x:isReferencedTweetOfSearchResultSet",
                cap=cap,
            ),
        )

    def _count_posts_in_window(
        self,
        query_string: str,
        start_time: str,
        end_time: str,
        *,
        tweet_class: str,
        membership: str,
        cap: int | None,
    ) -> int:
        """Count posts of *tweet_class* joined to a result set by *membership*."""
        escaped = _escape_sparql_string(query_string)
        start_lit = _escape_sparql_string(start_time)
        end_lit = _escape_sparql_string(end_time)
        limit_clause = f"\n            LIMIT {cap}" if cap is not None else ""
        sparql = f"""
        PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
        PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>
        PREFIX x:   <{self.namespace}>
        SELECT (COUNT(?tweet) AS ?n)
        WHERE {{
          {{
            SELECT DISTINCT ?tweet WHERE {{
              GRAPH <{self.tweet_graph_name}> {{
                ?sq rdf:type x:SearchQuery ; x:query_string ?qs .
                FILTER(
                  CONTAINS(LCASE(STR(?qs)), LCASE("{escaped}"))
                  || CONTAINS(LCASE("{escaped}"), LCASE(STR(?qs)))
                )
                ?proc rdf:type x:SearchRecentTweets ;
                      x:usesSearchQuery ?sq ;
                      x:producesSearchResult ?rs .
                ?tweet rdf:type {tweet_class} ;
                       {membership} ?rs ;
                       x:tweet_created_at ?created .
                FILTER(
                  ?created >= "{start_lit}"^^xsd:dateTime
                  && ?created < "{end_lit}"^^xsd:dateTime
                )
              }}
            }}{limit_clause}
          }}
        }}
        """
        rows = self._query_rows(
            sparql,
            f"count_posts_in_window({tweet_class}) for "
            f"{query_string!r} [{start_time} → {end_time}]",
        )
        if not rows:
            return 0
        n = getattr(rows[0], "n", None)
        try:
            return int(str(n)) if n is not None else 0
        except (TypeError, ValueError):
            return 0

    # ----- SPARQL: banded aggregates ---------------------------------------
    #
    # One scan per population / column, split by :func:`scenario_bands`, instead
    # of one scan per window. Every scenario window and its previous period is a
    # union of consecutive bands, so the per-window numbers are Python sums over
    # the same result — which is what the KPI and facet snapshots read.

    def banded_count_for_window(
        self, query_string: str, start_time: str, end_time: str, *, referenced: bool
    ) -> int:
        """Posts in ``[start, end)``, summed from the banded aggregate.

        Answered from the projection when one covers this query — it filters a
        resident column instead of scanning the graph, and needs no band
        alignment because any window is just a predicate. Otherwise the banded
        aggregate, falling back to a direct windowed count when the window is
        not band-aligned, so an arbitrary range still gets an exact answer.
        """
        cache = self.cache
        slug = self._cache_slug(query_string)
        if cache is not None and slug is not None:
            return cache.count_in_window(
                start_time, end_time, referenced=referenced, query_slug=slug
            )
        indices = bands_for_window(self.bands, start_time, end_time)
        if indices is None:
            if referenced:
                return self.count_referenced_tweets_in_window(
                    query_string, start_time, end_time, limit=0
                )
            return self.count_tweets_in_window(
                query_string, start_time, end_time, limit=0
            )
        counts = self._banded_post_counts(query_string, referenced=referenced)
        return sum(counts.get(index, 0) for index in indices)

    def _banded_post_counts(
        self, query_string: str, *, referenced: bool
    ) -> dict[int, int]:
        """``{band index: post count}`` for one population, memoized per publish."""
        return self._memo(
            ("banded_counts", query_string, referenced),
            lambda: self._query_banded_post_counts(query_string, referenced=referenced),
        )

    def _query_banded_post_counts(
        self, query_string: str, *, referenced: bool
    ) -> dict[int, int]:
        tweet_class = "x:ReferencedTweet" if referenced else "x:Tweet"
        membership = (
            "x:isReferencedTweetOfSearchResultSet"
            if referenced
            else "x:isContainedInSearchResultSet"
        )
        escaped = _escape_sparql_string(query_string)
        range_start = _escape_sparql_string(self.bands[-1][0])
        range_end = _escape_sparql_string(self.bands[0][1])
        sparql = f"""
        PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
        PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>
        PREFIX x:   <{self.namespace}>
        SELECT ?band (COUNT(DISTINCT ?tweet) AS ?n)
        WHERE {{
          GRAPH <{self.tweet_graph_name}> {{
            ?sq rdf:type x:SearchQuery ; x:query_string ?qs .
            FILTER(
              CONTAINS(LCASE(STR(?qs)), LCASE("{escaped}"))
              || CONTAINS(LCASE("{escaped}"), LCASE(STR(?qs)))
            )
            ?proc rdf:type x:SearchRecentTweets ;
                  x:usesSearchQuery ?sq ;
                  x:producesSearchResult ?rs .
            ?tweet rdf:type {tweet_class} ;
                   {membership} ?rs ;
                   x:tweet_created_at ?created .
            FILTER(
              ?created >= "{range_start}"^^xsd:dateTime
              && ?created < "{range_end}"^^xsd:dateTime
            )
          }}
          BIND({_band_bind_expression(self.bands)} AS ?band)
        }}
        GROUP BY ?band
        """
        counts: dict[int, int] = {}
        rows = self._query_rows(
            sparql,
            f"banded_post_counts({tweet_class}) for {query_string!r}",
        )
        for row in rows:
            band = getattr(row, "band", None)
            n = getattr(row, "n", None)
            if band is None:
                continue
            try:
                counts[int(str(band))] = int(str(n)) if n is not None else 0
            except (TypeError, ValueError):
                continue
        return counts

    def facet_values_for_window(
        self,
        query_string: str,
        start_time: str,
        end_time: str,
        column: str,
        *,
        limit: int = 500,
    ) -> list[dict[str, Any]]:
        """Distinct values of *column* in ``[start, end)``, most frequent first.

        The banded equivalent of :meth:`distinct_column_values` with no active
        filters — same payload, one scan per column for every scenario instead
        of one per column *per* scenario. Unaligned windows and filtered reads
        keep going through :meth:`distinct_column_values`.

        Values that differ only in surrounding whitespace are merged, because
        that is how they are displayed: ``user_location`` holds both
        ``"United States"`` and ``"United States "``, and the per-window query
        returned them as two rows that rendered as two identical checkboxes
        splitting one country's count. Merging also survives the value cap —
        the old query applied its ``LIMIT`` to the *unmerged* rows, so variants
        ranked below it were dropped instead of counted.

        Note the filter side is unchanged and still matches on the stored value,
        so ticking a merged entry selects the exact spelling, not the variants.
        """
        cache = self.cache
        slug = self._cache_slug(query_string)
        if cache is not None and slug is not None and column in TWEET_FACET_COLUMNS:
            return cache.facet_values(
                start_time, end_time, column, limit=limit, query_slug=slug
            )
        indices = bands_for_window(self.facet_bands, start_time, end_time)
        if indices is None or column not in TWEET_COLUMN_EXPRESSIONS:
            return self.distinct_column_values(
                query_string, start_time, end_time, column, limit=limit
            )
        banded = self._banded_facet_values(query_string, column)
        totals: dict[str, int] = {}
        for index in indices:
            for value, count in banded.get(index, {}).items():
                # Keyed on the displayed form, so whitespace variants of the
                # same value land in one entry rather than several identical
                # checkboxes.
                display = value.strip()
                totals[display] = totals.get(display, 0) + count
        # Ties broken by value so the published order is stable across runs;
        # SPARQL's ORDER BY DESC(?n) alone left them at the engine's mercy.
        ranked = sorted(totals.items(), key=lambda kv: (-kv[1], kv[0]))
        return [{"value": value, "count": count} for value, count in ranked[:limit]]

    def _banded_facet_values(
        self, query_string: str, column: str
    ) -> dict[int, dict[str, int]]:
        """``{band index: {value: tweet count}}`` for *column*, memoized."""
        return self._memo(
            ("banded_facets", query_string, column),
            lambda: self._query_banded_facet_values(query_string, column),
        )

    def _query_banded_facet_values(
        self, query_string: str, column: str
    ) -> dict[int, dict[str, int]]:
        """One aggregate per column.

        Deliberately *not* one query grouping all faceted columns at once: an
        author carrying two ``x:user_location`` values would contribute two rows,
        and summing them per username would count that tweet twice, where
        ``COUNT(DISTINCT ?tweet)`` per column counts it once.
        """
        expression = TWEET_COLUMN_EXPRESSIONS[column]
        range_start = self.facet_bands[-1][0]
        range_end = self.facet_bands[0][1]
        block = self._tweet_match_block(query_string, range_start, range_end, {})
        sparql = f"""
        PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
        PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>
        PREFIX x:   <{self.namespace}>
        SELECT ?band ?value (COUNT(DISTINCT ?tweet) AS ?n)
        WHERE {{
{block}
          BIND({_band_bind_expression(self.facet_bands)} AS ?band)
          BIND({expression} AS ?value)
        }}
        GROUP BY ?band ?value
        """
        out: dict[int, dict[str, int]] = {}
        rows = self._query_rows(
            sparql, f"banded_facet_values for {query_string!r} column={column!r}"
        )
        for row in rows:
            band = getattr(row, "band", None)
            raw = getattr(row, "value", None)
            count = getattr(row, "n", None)
            if band is None:
                continue
            try:
                index = int(str(band))
                n = int(str(count)) if count is not None else 0
            except (TypeError, ValueError):
                continue
            value = "" if raw is None else str(raw).strip()
            bucket = out.setdefault(index, {})
            bucket[value] = bucket.get(value, 0) + n
        return out

    def tweet_graph_state(self) -> dict[str, str]:
        """Cheap fingerprint of the tweet graph: post total + newest timestamp.

        Used to decide whether the Users dataset needs rebuilding at all. The
        pair catches every change that would alter it — new posts (both move), a
        backfill of older posts (only the total moves) and deletions (the total
        drops) — for one small aggregate instead of the two full-graph scans the
        rebuild itself costs.
        """
        sparql = f"""
        PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
        PREFIX x:   <{self.namespace}>
        SELECT (COUNT(?tweet) AS ?tweets) (MAX(?created) AS ?newest)
        WHERE {{
          GRAPH <{self.tweet_graph_name}> {{
            ?tweet rdf:type x:Tweet ;
                   x:tweet_created_at ?created .
          }}
        }}
        """
        rows = self._query_rows(sparql, "tweet_graph_state")
        if not rows:
            return {}
        tweets = getattr(rows[0], "tweets", None)
        newest = getattr(rows[0], "newest", None)
        if tweets is None:
            return {}
        return {
            "tweets": str(tweets),
            "newest": "" if newest is None else str(newest),
        }

    def _tweet_match_block(
        self,
        query_string: str,
        start_time: str,
        end_time: str,
        filters: dict[str, dict[str, Any]],
    ) -> str:
        """The shared GRAPH body matching every tweet for a query + window.

        Column FILTERs land after the OPTIONALs so author / text variables are
        already bound when they are evaluated.
        """
        escaped = _escape_sparql_string(query_string)
        start_lit = _escape_sparql_string(start_time)
        end_lit = _escape_sparql_string(end_time)
        filter_clauses = _tweet_filter_clauses(filters)
        return f"""          GRAPH <{self.tweet_graph_name}> {{
            ?sq rdf:type x:SearchQuery ; x:query_string ?qs .
            FILTER(
              CONTAINS(LCASE(STR(?qs)), LCASE("{escaped}"))
              || CONTAINS(LCASE("{escaped}"), LCASE(STR(?qs)))
            )
            ?proc rdf:type x:SearchRecentTweets ;
                  x:usesSearchQuery ?sq ;
                  x:producesSearchResult ?rs .
            ?tweet rdf:type x:Tweet ;
                   x:isContainedInSearchResultSet ?rs ;
                   x:tweet_created_at ?created .
            FILTER(
              ?created >= "{start_lit}"^^xsd:dateTime
              && ?created < "{end_lit}"^^xsd:dateTime
            )
            OPTIONAL {{ ?tweet x:full_text ?fullText . }}
            OPTIONAL {{ ?tweet x:tweet_text ?text . }}
            OPTIONAL {{ ?tweet x:url ?url . }}
            OPTIONAL {{
              ?tweet x:isAuthoredBy ?author .
              OPTIONAL {{ ?author x:username ?username . }}
              OPTIONAL {{ ?author x:user_location ?location . }}
              OPTIONAL {{ ?author x:verified_type ?verifiedType . }}
            }}
{filter_clauses}
          }}"""

    def distinct_column_values(
        self,
        query_string: str,
        start_time: str,
        end_time: str,
        column: str,
        *,
        contains: str = "",
        filters: dict[str, Any] | None = None,
        limit: int = 500,
    ) -> list[dict[str, Any]]:
        """Distinct values of *column* with tweet counts, most frequent first.

        Powers the checkbox list behind a column filter. The scan covers every
        tweet matching *query_string* in the window (optionally narrowed by the
        other columns' *filters*), not just the rows currently in the table, so
        the offered values are the full graph's — the same guarantee
        :meth:`search_tweets` gives for the rows themselves.

        Memoized per publish on the *normalized* filters, like
        :meth:`search_tweets`. The publish path reads facets through
        :meth:`facet_values_for_window` instead, which needs one scan per column
        for all scenarios rather than one per column per scenario.
        """
        if column not in TWEET_COLUMN_EXPRESSIONS:
            return []
        # The column being enumerated must not filter its own value list, or
        # ticking one box would hide every other option (Excel behaviour).
        active = normalize_tweet_filters(filters)
        active.pop(column, None)
        if contains.strip():
            active[column] = {"contains": contains.strip(), "values": []}
        return self._memo(
            (
                "distinct_column_values",
                query_string,
                start_time,
                end_time,
                column,
                int(limit),
                self._filters_key(active),
            ),
            lambda: self._distinct_column_values(
                query_string, start_time, end_time, column, active, int(limit)
            ),
        )

    def _distinct_column_values(
        self,
        query_string: str,
        start_time: str,
        end_time: str,
        column: str,
        active: dict[str, dict[str, Any]],
        limit: int,
    ) -> list[dict[str, Any]]:
        expression = TWEET_COLUMN_EXPRESSIONS[column]
        block = self._tweet_match_block(query_string, start_time, end_time, active)
        sparql = f"""
        PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
        PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>
        PREFIX x:   <{self.namespace}>
        SELECT ?value (COUNT(DISTINCT ?tweet) AS ?n)
        WHERE {{
{block}
          BIND({expression} AS ?value)
        }}
        GROUP BY ?value
        ORDER BY DESC(?n)
        LIMIT {int(limit)}
        """
        rows = self._query_rows(
            sparql,
            f"distinct_column_values for {query_string!r} column={column!r}",
        )
        values: list[dict[str, Any]] = []
        for row in rows:
            raw = getattr(row, "value", None)
            count = getattr(row, "n", None)
            try:
                n = int(str(count)) if count is not None else 0
            except (TypeError, ValueError):
                n = 0
            values.append(
                {"value": "" if raw is None else str(raw).strip(), "count": n}
            )
        return values

    def search_tweets(
        self,
        query_string: str,
        start_time: str,
        end_time: str,
        *,
        filters: dict[str, Any] | None = None,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        """Newest tweets in ``[start_time, end_time)`` matching *filters*.

        The column *filters* are pushed into SPARQL rather than applied to an
        already-capped page, so a keyword search returns the newest ``limit``
        tweets that actually match across the whole graph — not the matches
        that happen to fall inside the newest ``limit`` tweets overall.

        Memoized per publish on the *normalized* filters, so the tables /
        barcharts / linecharts scripts share one execution per
        (query, window) instead of running five.

        Unfiltered reads are additionally resolved against pages already fetched
        for the same ``end_time`` — see :meth:`_derive_tweets`. Since every
        scenario shares an ``end_time`` and the scenarios are visited
        narrowest-first, one 24 h scan typically answers all four.
        """
        cap = self.tweet_limit if limit is None else int(limit)
        active = normalize_tweet_filters(filters)
        key = (
            "search_tweets",
            query_string,
            start_time,
            end_time,
            cap,
            self._filters_key(active),
        )
        if key in self._query_cache:
            return self._query_cache[key]

        rows: list[dict[str, Any]] | None = None
        if not active:
            # The projection answers an unfiltered page directly — no page-reuse
            # reasoning needed, since a window is just a predicate over resident
            # rows. Filtered reads stay on SPARQL: the filters are pushed into
            # the query so a keyword search sees the whole graph, not a capped
            # page, and the projection has no equivalent.
            cache = self.cache
            slug = self._cache_slug(query_string)
            if cache is not None and slug is not None:
                rows = cache.newest_posts(
                    start_time, end_time, limit=cap, query_slug=slug
                )
            else:
                rows = self._derive_tweets(query_string, start_time, end_time, cap)
        if rows is None:
            rows = self._search_tweets(query_string, start_time, end_time, active, cap)
            if not active:
                self._tweet_pages.setdefault((query_string, end_time, cap), []).append(
                    (start_time, rows)
                )
        self._query_cache[key] = rows
        return rows

    def _derive_tweets(
        self, query_string: str, start_time: str, end_time: str, cap: int
    ) -> list[dict[str, Any]] | None:
        """Reuse an already-fetched page for ``[start_time, end_time)``, or ``None``.

        Two rules, both exact, for pages sharing this window's ``end_time``:

        **Wider → narrower.** A page for ``[s', end)`` with ``s' <= start`` holds
        the newest *cap* posts of a window that contains this one. Every post in
        ``[start, end)`` that could belong in this window's newest *cap* is newer
        than that page's oldest row, so filtering the page to ``start`` is exact
        — whether or not the page came back full.

        **Narrower → wider.** A *full* page for ``[s', end)`` with ``s' > start``
        whose oldest row is newer than its own ``s'`` never reached its window's
        edge: there are already *cap* posts newer than that row, so the wider
        window's newest *cap* are the very same rows.
        """
        pages = self._tweet_pages.get((query_string, end_time, cap))
        if not pages:
            return None
        try:
            start = datetime.fromisoformat(start_time)
        except ValueError:
            return None

        def created(row: dict[str, Any]) -> datetime | None:
            try:
                return datetime.fromisoformat(str(row["created_at"]))
            except (KeyError, ValueError):
                return None

        for page_start, rows in pages:
            try:
                page_start_dt = datetime.fromisoformat(page_start)
            except ValueError:
                continue
            if page_start_dt == start:
                return rows
            if page_start_dt < start:
                filtered = []
                for row in rows:
                    moment = created(row)
                    if moment is None or moment >= start:
                        filtered.append(row)
                return filtered
            # Narrower page: only usable when it never reached its own edge.
            if len(rows) >= cap and rows:
                oldest = created(rows[-1])
                if oldest is not None and oldest > page_start_dt:
                    return rows
        return None

    def _search_tweets(
        self,
        query_string: str,
        start_time: str,
        end_time: str,
        active: dict[str, dict[str, Any]],
        cap: int,
    ) -> list[dict[str, Any]]:
        block = self._tweet_match_block(query_string, start_time, end_time, active)
        sparql = f"""
        PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
        PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>
        PREFIX x:   <{self.namespace}>
        SELECT DISTINCT ?created ?fullText ?text ?url ?username ?location ?verifiedType
        WHERE {{
{block}
        }}
        ORDER BY DESC(?created)
        LIMIT {cap}
        """
        tweets: list[dict[str, Any]] = []
        rows = self._query_rows(sparql, f"search_tweets for {query_string!r}")

        def _s(row: Any, key: str) -> str:
            value = getattr(row, key, None)
            return "" if value is None else str(value)

        for row in rows:
            created = getattr(row, "created", None)
            if created is None:
                continue
            full = _s(row, "fullText")
            tweets.append(
                {
                    "created_at": str(created),
                    "text": full or _s(row, "text"),
                    "url": _s(row, "url"),
                    "username": _s(row, "username"),
                    "location": _s(row, "location"),
                    "verified_type": _s(row, "verifiedType"),
                }
            )
        return tweets

    def tweets_in_window(
        self,
        query_string: str,
        start_time: str,
        end_time: str,
        *,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        """Tweet rows for tables/bars in ``[start_time, end_time)``, newest first."""
        return self.search_tweets(
            query_string, start_time, end_time, filters=None, limit=limit
        )

    # ----- SPARQL: authors, graph-wide (no query / window scope) -----------
    #
    # These feed the published Users dataset. They are deliberately unscoped —
    # the Users page looks an author up across the whole tweet graph, not inside
    # a followed query's rolling window — and deliberately *bulk*: the app reads
    # the published dataset, so nothing here runs per HTTP request.

    def all_authors(self) -> list[dict[str, Any]]:
        """Every author in the tweet graph with their all-time post totals.

        Uncapped on purpose: this is the Users search page's whole index, so an
        author with a single post stays findable. One aggregate over the graph
        rather than a scan per author.
        """
        sparql = f"""
        PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
        PREFIX x:   <{self.namespace}>
        SELECT ?username (COUNT(DISTINCT ?tweet) AS ?n) (MAX(?created) AS ?last)
               (MIN(?created) AS ?first) (SAMPLE(?location) AS ?loc)
               (SAMPLE(?verifiedType) AS ?vt)
        WHERE {{
          GRAPH <{self.tweet_graph_name}> {{
            ?tweet rdf:type x:Tweet ;
                   x:tweet_created_at ?created ;
                   x:isAuthoredBy ?author .
            ?author x:username ?username .
            OPTIONAL {{ ?author x:user_location ?location . }}
            OPTIONAL {{ ?author x:verified_type ?verifiedType . }}
          }}
        }}
        GROUP BY ?username
        ORDER BY DESC(?n)
        """
        authors: list[dict[str, Any]] = []
        rows = self._query_rows(sparql, "all_authors")

        def _s(row: Any, key: str) -> str:
            value = getattr(row, key, None)
            return "" if value is None else str(value)

        for row in rows:
            username = _s(row, "username").strip()
            if not username:
                continue
            raw_n = getattr(row, "n", None)
            try:
                posts = int(str(raw_n)) if raw_n is not None else 0
            except (TypeError, ValueError):
                posts = 0
            authors.append(
                {
                    "username": username,
                    "posts": posts,
                    "last_post_at": _s(row, "last"),
                    "first_post_at": _s(row, "first"),
                    "location": _s(row, "loc"),
                    "verified_type": _s(row, "vt"),
                }
            )
        return authors

    def all_descriptions(self) -> dict[str, str]:
        """Every author bio in the graph, keyed by username.

        Deliberately *not* :meth:`accounts_for_usernames`: that one reads whole
        accounts in ``VALUES`` batches, and the search index needs one field for
        every author at once. Requiring ``x:user_description`` (rather than
        making it OPTIONAL) keeps this to the hydrated accounts — most authors
        are tweet-author stubs with no bio at all — so it stays one pass over a
        small slice of the graph.

        An author can have several ``XUser`` individuals across ingests (a stub
        plus a hydrated one); the longest bio wins, as the richest.
        """
        sparql = f"""
        PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
        PREFIX x:   <{self.namespace}>
        SELECT ?username ?description
        WHERE {{
          GRAPH <{self.tweet_graph_name}> {{
            ?user rdf:type x:XUser ;
                  x:username ?username ;
                  x:user_description ?description .
          }}
        }}
        """
        out: dict[str, str] = {}
        for row in self._query_rows(sparql, "all_descriptions"):
            username = str(getattr(row, "username", "") or "").strip()
            description = " ".join(
                str(getattr(row, "description", "") or "").split()
            ).strip()
            if not username or not description:
                continue
            if len(description) > len(out.get(username, "")):
                out[username] = description
        return out

    def all_display_names(self) -> dict[str, str]:
        """Every author display name in the graph, keyed by username.

        Same shape as :meth:`all_descriptions`: one pass over hydrated accounts
        (those that carry ``x:user_name``), not the per-shard account query.
        An author can have several ``XUser`` individuals; the longest name wins.
        """
        sparql = f"""
        PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
        PREFIX x:   <{self.namespace}>
        SELECT ?username ?displayName
        WHERE {{
          GRAPH <{self.tweet_graph_name}> {{
            ?user rdf:type x:XUser ;
                  x:username ?username ;
                  x:user_name ?displayName .
          }}
        }}
        """
        out: dict[str, str] = {}
        for row in self._query_rows(sparql, "all_display_names"):
            username = str(getattr(row, "username", "") or "").strip()
            display_name = " ".join(
                str(getattr(row, "displayName", "") or "").split()
            ).strip()
            if not username or not display_name:
                continue
            if len(display_name) > len(out.get(username, "")):
                out[username] = display_name
        return out

    def _values_clause(self, usernames: Iterable[str]) -> str:
        """``VALUES ?username { … }`` binding an exact batch of author names.

        Exact-match (not ``LCASE``) because every caller passes usernames read
        straight back from :meth:`all_authors`, i.e. the strings stored in the
        graph. Binding them up front lets Jena drive the join from the username
        index instead of scanning every tweet.
        """
        literals = " ".join(
            f'"{_escape_sparql_string(u)}"' for u in usernames if u.strip()
        )
        return f"VALUES ?username {{ {literals} }}"

    def posts_for_usernames(
        self, usernames: list[str]
    ) -> dict[str, list[dict[str, Any]]]:
        """Every post by each of *usernames*, newest first, keyed by username.

        Covers search matches *and* referenced context (a quote/reply/retweet
        original this account wrote). Context-only rows are flagged
        ``referenced=True``; matches omit the key. ``x:Tweet`` already includes
        ``x:ReferencedTweet``, so no extra type filter is needed.

        Resolved in batches of :data:`AUTHOR_BATCH_SIZE` so peak memory is a
        function of the batch, not of the graph. Photos carry ``media_url``;
        videos and animated GIFs store their best MP4 variant there at ingest
        time (falling back to ``preview_image_url`` when no playable URL was
        ingested). ``?mediaAny`` prefers ``media_url`` then the preview so a
        video still shows something when only the still was stored.

        ``?mediaAny`` is wrapped in ``COALESCE(…, "")`` inside the aggregate
        because a tweet with no attached media leaves it unbound: Jena follows
        the spec and skips unbound values, but rdflib (the ``fs`` local-dev
        adapter) raises ``NotBoundError`` and killed the whole publish whenever
        a batch happened to contain no media at all. The empty strings it adds
        are absorbed by the ``.strip()`` below, so the published value is
        unchanged either way.
        """
        out: dict[str, list[dict[str, Any]]] = {}
        for batch in batched(usernames, AUTHOR_BATCH_SIZE):
            sparql = f"""
            PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
            PREFIX x:   <{self.namespace}>
            SELECT ?username ?created ?fullText ?text ?url ?isReferenced
                   (GROUP_CONCAT(DISTINCT COALESCE(?mediaAny, "");
                                 separator=" ") AS ?mediaUrls)
            WHERE {{
              GRAPH <{self.tweet_graph_name}> {{
                {self._values_clause(batch)}
                ?author x:username ?username .
                ?tweet rdf:type x:Tweet ;
                       x:tweet_created_at ?created ;
                       x:isAuthoredBy ?author .
                BIND(EXISTS {{ ?tweet rdf:type x:ReferencedTweet }} AS ?isReferenced)
                OPTIONAL {{ ?tweet x:full_text ?fullText . }}
                OPTIONAL {{ ?tweet x:tweet_text ?text . }}
                OPTIONAL {{ ?tweet x:url ?url . }}
                OPTIONAL {{
                  ?tweet x:hasAttachedMedia ?media .
                  OPTIONAL {{ ?media x:media_url ?mediaUrl . }}
                  OPTIONAL {{ ?media x:preview_image_url ?mediaPreview . }}
                  BIND(COALESCE(?mediaUrl, ?mediaPreview) AS ?mediaAny)
                }}
              }}
            }}
            GROUP BY ?tweet ?username ?created ?fullText ?text ?url ?isReferenced
            """
            rows = self._query_rows(
                sparql, f"posts_for_usernames for a batch of {len(batch)} author(s)"
            )

            def _s(row: Any, key: str) -> str:
                value = getattr(row, key, None)
                return "" if value is None else str(value)

            for row in rows:
                created = getattr(row, "created", None)
                username = _s(row, "username").strip()
                if created is None or not username:
                    continue
                full = _s(row, "fullText")
                post: dict[str, Any] = {
                    "created_at": str(created),
                    "text": full or _s(row, "text"),
                    "url": _s(row, "url"),
                    "username": username,
                }
                if _s(row, "isReferenced").lower() in ("true", "1"):
                    post["referenced"] = True
                # Space-separated: a tweet can carry up to four media. Omitted
                # rather than published empty — most posts have none, and the
                # table renders a missing key and an empty one identically.
                # Re-joined on whitespace rather than just stripped: the
                # COALESCE above contributes an empty string per media node that
                # carries neither URL, which would otherwise leave a double
                # separator mid-value for a tweet that mixes the two.
                media = " ".join(_s(row, "mediaUrls").split())
                if media:
                    post["media_url"] = media
                out.setdefault(username, []).append(post)
        # SPARQL cannot order per group, so the newest-first guarantee the table
        # relies on is applied here. ``url`` is the tie-breaker so authors who
        # post several times in the same second keep a stable order.
        for posts in out.values():
            posts.sort(key=lambda p: (p["created_at"], p["url"]), reverse=True)
        return out

    def accounts_for_usernames(self, usernames: list[str]) -> dict[str, dict[str, Any]]:
        """The ``XUser`` profile fields + public metrics for each of *usernames*.

        Separate from the tweet aggregates in :meth:`all_authors`: this reads
        the accounts themselves (bio, images, join date, follower counts). Every
        field is OPTIONAL — accounts ingested only as a tweet-author stub carry
        just ``author_id`` and ``username``.
        """
        out: dict[str, dict[str, Any]] = {}
        for batch in batched(usernames, AUTHOR_BATCH_SIZE):
            sparql = f"""
            PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
            PREFIX x:   <{self.namespace}>
            SELECT ?username ?authorId ?displayName ?description ?userLocation
                   ?userUrl ?userCreatedAt ?imageUrl ?bannerUrl ?verified
                   ?verifiedType ?identityVerified ?protectedFlag ?pinnedTweetId
                   ?recentTweetId ?followers ?following ?tweetCount ?listed
                   ?likes ?mediaCount
            WHERE {{
              GRAPH <{self.tweet_graph_name}> {{
                {self._values_clause(batch)}
                ?user rdf:type x:XUser ;
                      x:username ?username .
                OPTIONAL {{ ?user x:author_id ?authorId . }}
                OPTIONAL {{ ?user x:user_name ?displayName . }}
                OPTIONAL {{ ?user x:user_description ?description . }}
                OPTIONAL {{ ?user x:user_location ?userLocation . }}
                OPTIONAL {{ ?user x:user_url ?userUrl . }}
                OPTIONAL {{ ?user x:user_created_at ?userCreatedAt . }}
                OPTIONAL {{ ?user x:profile_image_url ?imageUrl . }}
                OPTIONAL {{ ?user x:profile_banner_url ?bannerUrl . }}
                OPTIONAL {{ ?user x:verified ?verified . }}
                OPTIONAL {{ ?user x:verified_type ?verifiedType . }}
                OPTIONAL {{ ?user x:is_identity_verified ?identityVerified . }}
                OPTIONAL {{ ?user x:protected ?protectedFlag . }}
                OPTIONAL {{ ?user x:pinned_tweet_id ?pinnedTweetId . }}
                OPTIONAL {{ ?user x:most_recent_tweet_id ?recentTweetId . }}
                OPTIONAL {{
                  ?user x:hasUserPublicMetrics ?metrics .
                  OPTIONAL {{ ?metrics x:followers_count ?followers . }}
                  OPTIONAL {{ ?metrics x:following_count ?following . }}
                  OPTIONAL {{ ?metrics x:user_tweet_count ?tweetCount . }}
                  OPTIONAL {{ ?metrics x:listed_count ?listed . }}
                  OPTIONAL {{ ?metrics x:user_like_count ?likes . }}
                  OPTIONAL {{ ?metrics x:user_media_count ?mediaCount . }}
                }}
              }}
            }}
            """
            rows = self._query_rows(
                sparql,
                f"accounts_for_usernames for a batch of {len(batch)} author(s)",
            )
            for row in rows:
                account = _account_from_row(row)
                username = account.pop("_username", "")
                if not username:
                    continue
                # An author may have several XUser individuals across ingests
                # (a stub plus a fully hydrated one). Keep the richest.
                previous = out.get(username)
                if previous is None or _account_richness(account) > _account_richness(
                    previous
                ):
                    out[username] = account
        return out

    def partial_bucket(self, query_string: str) -> dict[str, Any] | None:
        """The in-progress hour's ``{start, end, count}``, or ``None``.

        Kept out of :meth:`timeseries` so every existing consumer keeps seeing
        complete hours only; the chart opts in explicitly.
        """
        escaped = _escape_sparql_string(query_string)
        sparql = f"""
        PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
        PREFIX x:   <{self.namespace}>
        SELECT ?start ?end (MAX(?count) AS ?tweetCount)
        WHERE {{
          GRAPH <{self.graph_name}> {{
            ?resultSet rdf:type x:TweetCountResultSet ;
                       x:query_string "{escaped}" ;
                       x:containsCountBucket ?bucket .
            ?bucket x:bucket_tweet_count ?count ;
                    x:hasCountInterval ?interval .
            ?interval x:bucket_start ?start ;
                      x:bucket_end ?end .
            FILTER(STRENDS(STR(?interval), "-partial"))
          }}
        }}
        GROUP BY ?start ?end
        ORDER BY DESC(?start)
        LIMIT 1
        """
        rows = self._query_rows(sparql, f"partial_bucket for {query_string!r}")
        if not rows:
            return None
        row = rows[0]
        start = getattr(row, "start", None)
        end = getattr(row, "end", None)
        count = getattr(row, "tweetCount", None)
        if start is None or end is None:
            return None
        return {
            "start": str(start),
            "end": str(end),
            "count": int(str(count)) if count is not None else 0,
        }

    def aggregate_buckets(
        self,
        buckets: list[dict[str, Any]],
        start_time: str,
        end_time: str,
        *,
        daily: bool,
    ) -> list[dict[str, Any]]:
        """Aggregate count buckets into chart points for a scenario window."""
        start_ms = datetime.fromisoformat(start_time).timestamp()
        end_ms = datetime.fromisoformat(end_time).timestamp()
        in_range = []
        for b in buckets:
            try:
                t = datetime.fromisoformat(str(b["start"])).timestamp()
            except ValueError:
                continue
            if start_ms <= t < end_ms:
                in_range.append(b)
        if not daily:
            points: list[dict[str, Any]] = []
            for b in in_range:
                start = datetime.fromisoformat(str(b["start"]))
                end = None
                if b.get("end"):
                    end = datetime.fromisoformat(str(b["end"]))
                if end is None or end <= start:
                    end = start + timedelta(hours=1)
                label = (
                    start.strftime("%b ") + str(start.day) + start.strftime(", %H:00")
                )
                points.append(
                    {
                        "t": start.isoformat(),
                        "value": int(b["count"]),
                        "label": label,
                        "range_label": f"{label} – {end.strftime('%H:00')}",
                    }
                )
            return points

        by_day: dict[str, int] = {}
        for b in in_range:
            start = datetime.fromisoformat(str(b["start"]))
            key = start.strftime("%Y-%m-%d")
            by_day[key] = by_day.get(key, 0) + int(b["count"])
        return [
            {
                "t": f"{day}T12:00:00+00:00",
                "value": value,
                "label": datetime.fromisoformat(f"{day}T12:00:00+00:00").strftime("%b ")
                + str(datetime.fromisoformat(f"{day}T12:00:00+00:00").day),
                "range_label": day,
            }
            for day, value in sorted(by_day.items())
        ]


def complete_hourly_buckets(
    buckets: list[dict[str, Any]],
    start_time: str,
    end_time: str,
) -> list[dict[str, Any]]:
    """Pad *buckets* so every hour in ``[start, end)`` is present.

    The Search line chart plots by index (same as Count), so a sparse series of
    only the hours that had a tweet would stretch those hours across the axis
    and overlay current vs previous by rank rather than by clock hour. Zero
    hours keep the series aligned with the window, the way the count endpoint's
    hourly buckets already are.
    """
    by_hour: dict[datetime, int] = {}
    for bucket in buckets:
        try:
            hour = datetime.fromisoformat(str(bucket["start"]))
        except ValueError:
            continue
        if hour.tzinfo is None:
            hour = hour.replace(tzinfo=UTC)
        hour = hour.astimezone(UTC).replace(minute=0, second=0, microsecond=0)
        by_hour[hour] = by_hour.get(hour, 0) + int(bucket.get("count") or 0)

    start = datetime.fromisoformat(start_time)
    end = datetime.fromisoformat(end_time)
    if start.tzinfo is None:
        start = start.replace(tzinfo=UTC)
    if end.tzinfo is None:
        end = end.replace(tzinfo=UTC)
    start = start.astimezone(UTC).replace(minute=0, second=0, microsecond=0)

    out: list[dict[str, Any]] = []
    hour = start
    while hour < end:
        nxt = hour + timedelta(hours=1)
        out.append(
            {
                "start": hour.isoformat(),
                "end": nxt.isoformat(),
                "count": by_hour.get(hour, 0),
            }
        )
        hour = nxt
    return out
