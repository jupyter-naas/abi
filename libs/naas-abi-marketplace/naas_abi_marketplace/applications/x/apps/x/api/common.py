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

# Cap for the Search page "tweets ingested" KPI and related tweet snapshots.
DEFAULT_TWEET_LIMIT = 2000

# Rolling windows shown in the Scenario filter (id / label / hours).
# start_time / end_time are filled at publish time.
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
    """Four scenario filters with ``id``, ``label``, ``start_time``, ``end_time``."""
    now = now or datetime.now(UTC)
    end = now.astimezone(UTC)
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


def previous_window(
    start_time: str, end_time: str
) -> tuple[str, str]:
    """Equal-length window immediately preceding ``[start_time, end_time)``."""
    start = datetime.fromisoformat(start_time)
    end = datetime.fromisoformat(end_time)
    delta = end - start
    prev_end = start
    prev_start = start - delta
    return prev_start.isoformat(), prev_end.isoformat()


def _escape_sparql_string(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


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
                t = datetime.fromisoformat(
                    str(bucket["start"])
                ).timestamp()
            except ValueError:
                continue
            if start_ms <= t < end_ms:
                total += int(bucket["count"])
        return total

    # ----- SPARQL: ingested tweets (capped) --------------------------------

    def count_tweets_in_window(
        self,
        query_string: str,
        start_time: str,
        end_time: str,
        *,
        limit: int | None = None,
    ) -> int:
        """Number of ingested tweets in ``[start_time, end_time)``, capped by *limit*.

        One SPARQL query: inner SELECT DISTINCT with LIMIT, outer COUNT. Run once
        per scenario (four times for the default Scenario filter).
        """
        cap = self.tweet_limit if limit is None else int(limit)
        escaped = _escape_sparql_string(query_string)
        start_lit = _escape_sparql_string(start_time)
        end_lit = _escape_sparql_string(end_time)
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
            }}
            LIMIT {cap}
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

    def tweets_in_window(
        self,
        query_string: str,
        start_time: str,
        end_time: str,
        *,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        """Tweet rows for tables/bars in ``[start_time, end_time)``, newest first."""
        cap = self.tweet_limit if limit is None else int(limit)
        escaped = _escape_sparql_string(query_string)
        start_lit = _escape_sparql_string(start_time)
        end_lit = _escape_sparql_string(end_time)
        sparql = f"""
        PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
        PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>
        PREFIX x:   <{self.namespace}>
        SELECT DISTINCT ?created ?fullText ?text ?url ?username ?location ?verifiedType
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
            OPTIONAL {{ ?tweet x:full_text ?fullText . }}
            OPTIONAL {{ ?tweet x:tweet_text ?text . }}
            OPTIONAL {{ ?tweet x:url ?url . }}
            OPTIONAL {{
              ?tweet x:isAuthoredBy ?author .
              OPTIONAL {{ ?author x:username ?username . }}
              OPTIONAL {{ ?author x:user_location ?location . }}
              OPTIONAL {{ ?author x:verified_type ?verifiedType . }}
            }}
          }}
        }}
        ORDER BY DESC(?created)
        LIMIT {cap}
        """
        tweets: list[dict[str, Any]] = []
        try:
            rows = self.triple_store.query(sparql)
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                f"SnapshotContext.tweets_in_window failed for {query_string!r} ({exc})"
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
                t = datetime.fromisoformat(
                    str(b["start"])
                ).timestamp()
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
                label = start.strftime("%b ") + str(start.day) + start.strftime(", %H:00")
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
