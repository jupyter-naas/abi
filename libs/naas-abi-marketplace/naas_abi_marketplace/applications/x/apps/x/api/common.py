"""Shared constants, scenarios, SPARQL helpers and storage I/O for X app snapshots."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from naas_abi_core import logger
from naas_abi_core.services.object_storage.ObjectStorageService import (
    ObjectStorageService,
)
from naas_abi_core.services.triple_store.TripleStoreService import TripleStoreService
from naas_abi_core.utils.StorageUtils import StorageUtils

DEFAULT_COUNT_GRAPH = "http://ontology.naas.ai/graph/x_recent_posts_count"
DEFAULT_TWEET_GRAPH = "http://ontology.naas.ai/graph/x"
DEFAULT_NAMESPACE = "http://ontology.naas.ai/x/"
DEFAULT_APP_PREFIX = "x/apps/x"

# Cap for Search page tweet tables / author bars (KPI counts are uncapped).
# ``tweets_in_window`` orders the *full* graph match by recency before applying
# this LIMIT, so a capped read is the newest N tweets in the window — never an
# arbitrary sample.
DEFAULT_TWEET_LIMIT = 1000

# Cap for the Users page author list. Counts there are SPARQL aggregates over
# the whole window, so this bounds the *number of authors* published, not the
# tweets they are computed from.
DEFAULT_USER_LIMIT = 2000

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


def _escape_sparql_string(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


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

    def save_json(self, relative_dir: str, filename: str, data: dict | list) -> str:
        """Write JSON under ``x/apps/x/<relative_dir>/<filename>``."""
        prefix = f"{self.app_prefix}/{relative_dir}".rstrip("/")
        self.storage.save_json(data, prefix, filename, copy=False)
        path = f"{prefix}/{filename}"
        logger.info(f"X app snapshot: wrote {path}")
        return path

    # ----- SPARQL: counts (hourly buckets) ---------------------------------

    def timeseries(self, query_string: str) -> list[dict[str, Any]]:
        """Hourly ``{start, end, count}`` buckets for *query_string*, oldest first."""
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
        try:
            rows = self.triple_store.query(sparql)
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                f"SnapshotContext.timeseries failed for {query_string!r} ({exc})"
            )
            return buckets
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

    # ----- SPARQL: ingested tweets -----------------------------------------

    def count_tweets_in_window(
        self,
        query_string: str,
        start_time: str,
        end_time: str,
        *,
        limit: int | None = None,
    ) -> int:
        """Number of ingested tweets in ``[start_time, end_time)``.

        When *limit* is ``None`` or ``<= 0``, the count is uncapped (full graph
        cardinality). A positive *limit* wraps an inner ``SELECT DISTINCT`` with
        ``LIMIT`` — used only when a capped sample is intentional.
        """
        if limit is None or int(limit) <= 0:
            cap: int | None = None
        else:
            cap = int(limit)
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
                ?tweet rdf:type x:Tweet ;
                       x:isContainedInSearchResultSet ?rs ;
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
        try:
            rows = list(self.triple_store.query(sparql))
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                f"SnapshotContext.count_tweets_in_window failed for "
                f"{query_string!r} [{start_time} → {end_time}] ({exc})"
            )
            return 0
        if not rows:
            return 0
        n = getattr(rows[0], "n", None)
        try:
            return int(str(n)) if n is not None else 0
        except (TypeError, ValueError):
            return 0

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
        """
        if column not in TWEET_COLUMN_EXPRESSIONS:
            return []
        expression = TWEET_COLUMN_EXPRESSIONS[column]
        # The column being enumerated must not filter its own value list, or
        # ticking one box would hide every other option (Excel behaviour).
        active = normalize_tweet_filters(filters)
        active.pop(column, None)
        if contains.strip():
            active[column] = {"contains": contains.strip(), "values": []}
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
        try:
            rows = self.triple_store.query(sparql)
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                f"SnapshotContext.distinct_column_values failed for "
                f"{query_string!r} column={column!r} ({exc})"
            )
            return []
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
        """
        cap = self.tweet_limit if limit is None else int(limit)
        block = self._tweet_match_block(
            query_string, start_time, end_time, normalize_tweet_filters(filters)
        )
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
        try:
            rows = self.triple_store.query(sparql)
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                f"SnapshotContext.search_tweets failed for {query_string!r} ({exc})"
            )
            return tweets

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

    def _author_block(self, username_filter: str) -> str:
        """GRAPH body matching every ingested tweet and its author.

        Deliberately unscoped: the Users page looks an author up across the
        whole tweet graph, not inside a followed query's rolling window.
        """
        return f"""          GRAPH <{self.tweet_graph_name}> {{
            ?tweet rdf:type x:Tweet ;
                   x:tweet_created_at ?created ;
                   x:isAuthoredBy ?author .
            ?author x:username ?username .
            OPTIONAL {{ ?tweet x:full_text ?fullText . }}
            OPTIONAL {{ ?tweet x:tweet_text ?text . }}
            OPTIONAL {{ ?tweet x:url ?url . }}
            OPTIONAL {{ ?author x:user_location ?location . }}
            OPTIONAL {{ ?author x:verified_type ?verifiedType . }}
{username_filter}
          }}"""

    def find_users(
        self,
        contains: str = "",
        *,
        limit: int = DEFAULT_USER_LIMIT,
    ) -> list[dict[str, Any]]:
        """Authors whose username matches *contains*, busiest first.

        Graph-wide: ``posts`` is every tweet by that author in the tweet graph,
        independent of any followed query or scenario window.
        """
        needle = _escape_sparql_string(contains.strip().lower())
        clause = (
            f'            FILTER(CONTAINS(LCASE(STR(?username)), "{needle}"))'
            if needle
            else ""
        )
        sparql = f"""
        PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
        PREFIX x:   <{self.namespace}>
        SELECT ?username (COUNT(DISTINCT ?tweet) AS ?n) (MAX(?created) AS ?last)
               (SAMPLE(?location) AS ?loc) (SAMPLE(?verifiedType) AS ?vt)
        WHERE {{
{self._author_block(clause)}
        }}
        GROUP BY ?username
        ORDER BY DESC(?n)
        LIMIT {int(limit)}
        """
        users: list[dict[str, Any]] = []
        try:
            rows = self.triple_store.query(sparql)
        except Exception as exc:  # noqa: BLE001
            logger.warning(f"SnapshotContext.find_users failed ({contains!r}: {exc})")
            return users

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
            users.append(
                {
                    "username": username,
                    "posts": posts,
                    "last_post_at": _s(row, "last"),
                    "location": _s(row, "loc"),
                    "verified_type": _s(row, "vt"),
                }
            )
        return users

    def user_profile(self, username: str) -> dict[str, Any]:
        """Totals for one author: ``{username, posts, last_post_at, first_post_at}``.

        Counted in SPARQL so the KPI is the author's real total in the graph,
        not the size of the page currently shown in the table.
        """
        user = _escape_sparql_string(username.strip().lower())
        clause = f'            FILTER(LCASE(STR(?username)) = "{user}")'
        sparql = f"""
        PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
        PREFIX x:   <{self.namespace}>
        SELECT (COUNT(DISTINCT ?tweet) AS ?n) (MAX(?created) AS ?last)
               (MIN(?created) AS ?first) (SAMPLE(?location) AS ?loc)
               (SAMPLE(?verifiedType) AS ?vt)
        WHERE {{
{self._author_block(clause)}
        }}
        """
        empty = {
            "username": username,
            "posts": 0,
            "last_post_at": "",
            "first_post_at": "",
            "location": "",
            "verified_type": "",
        }
        try:
            rows = list(self.triple_store.query(sparql))
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                f"SnapshotContext.user_profile failed for {username!r} ({exc})"
            )
            return empty
        if not rows:
            return empty
        row = rows[0]

        def _s(key: str) -> str:
            value = getattr(row, key, None)
            return "" if value is None else str(value)

        raw_n = getattr(row, "n", None)
        try:
            posts = int(str(raw_n)) if raw_n is not None else 0
        except (TypeError, ValueError):
            posts = 0
        return {
            "username": username,
            "posts": posts,
            "last_post_at": _s("last"),
            "first_post_at": _s("first"),
            "location": _s("loc"),
            "verified_type": _s("vt"),
        }

    def tweets_by_username(
        self,
        username: str,
        *,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        """One page of an author's tweets, newest first, graph-wide.

        ``?url`` is the ORDER BY tie-breaker so paging with OFFSET stays stable
        when several tweets share a timestamp.
        """
        user = _escape_sparql_string(username.strip().lower())
        clause = f'            FILTER(LCASE(STR(?username)) = "{user}")'
        sparql = f"""
        PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
        PREFIX x:   <{self.namespace}>
        SELECT DISTINCT ?created ?fullText ?text ?url ?username ?location ?verifiedType
        WHERE {{
{self._author_block(clause)}
        }}
        ORDER BY DESC(?created) STR(?url)
        LIMIT {int(limit)}
        OFFSET {int(offset)}
        """
        tweets: list[dict[str, Any]] = []
        try:
            rows = self.triple_store.query(sparql)
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                f"SnapshotContext.tweets_by_username failed for {username!r} ({exc})"
            )
            return tweets

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
        try:
            rows = list(self.triple_store.query(sparql))
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                f"SnapshotContext.partial_bucket failed for {query_string!r} ({exc})"
            )
            return None
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
