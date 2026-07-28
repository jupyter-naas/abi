import os
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import Enum
from typing import Annotated

from langchain_core.tools import BaseTool, StructuredTool
from naas_abi_core import logger
from naas_abi_core.services.object_storage.ObjectStorageService import (
    ObjectStorageService,
)
from naas_abi_core.services.triple_store.TripleStoreService import TripleStoreService
from naas_abi_core.utils.StorageUtils import StorageUtils
from naas_abi_core.workflow.workflow import (
    Workflow,
    WorkflowConfiguration,
    WorkflowParameters,
)
from naas_abi_marketplace.applications.x import ABIModule
from naas_abi_marketplace.applications.x.integrations.XIntegration import (
    XIntegration,
    slugify_query,
)
from pydantic import Field

# X keeps only the last 7 days of recent tweets; stay just inside that window.
_MAX_LOOKBACK = timedelta(days=7)
_ISO_Z = "%Y-%m-%dT%H:%M:%SZ"

_NAMESPACE = "http://ontology.naas.ai/x/"
_TWEET_GRAPH_NAME = "http://ontology.naas.ai/graph/x"
_COUNT_GRAPH_NAME = "http://ontology.naas.ai/graph/x_recent_posts_count"


def _escape_sparql_string(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def _floor_hour(dt: datetime) -> datetime:
    """Round *dt* down to the start of its clock hour (UTC)."""
    return dt.astimezone(UTC).replace(minute=0, second=0, microsecond=0)


def _parse_iso(value: object) -> datetime | None:
    if not value:
        return None
    text = str(value).replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(text)
    except ValueError:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)


@dataclass
class XCountRecentTweetsWorkflowConfiguration(WorkflowConfiguration):
    """Configuration for XCountRecentTweetsWorkflow.

    Attributes:
        x_integration: The XIntegration used to call the X v2 counts endpoint.
            Its responses are persisted to the datastore.
        object_storage: Service used to persist count envelopes.
        triple_store: Source of truth for what has already been counted and how
            far ingestion has got. The window is resolved from graph state —
            ``MAX(x:tweet_created_at)`` in the tweet graph for the upper bound,
            and the stored ``CountInterval`` starts for the hours already held —
            so counting follows what the pipeline has actually mapped rather
            than wall-clock time or a previously written envelope.
        datastore_path: Object-storage prefix under which the integration writes
            ``count_recent_tweets/<slug>/<timestamp>_<slug>.json`` envelopes.
        granularity: Bucket size requested from the counts endpoint. This
            workflow enforces round clock hours and is designed for "hour".
        max_hours_per_run: Cap on how many missing complete hours a single run
            backfills, oldest first. Bounds the API cost of a cold start or a
            long outage while still converging over successive runs.
        tweet_graph_name: Named graph holding ``x:Tweet`` — the ingestion front.
        count_graph_name: Named graph holding the count buckets.
        namespace: Ontology namespace for the X classes/properties.
    """

    x_integration: XIntegration
    object_storage: ObjectStorageService
    triple_store: TripleStoreService | None = None
    datastore_path: str = field(
        default_factory=lambda: ABIModule.get_instance().configuration.datastore_path
    )
    granularity: str = "hour"
    max_hours_per_run: int = 6
    partial_refresh_seconds: int = 600
    tweet_graph_name: str = _TWEET_GRAPH_NAME
    count_graph_name: str = _COUNT_GRAPH_NAME
    namespace: str = _NAMESPACE


class XCountRecentTweetsWorkflowParameters(WorkflowParameters):
    queries: Annotated[
        list[str],
        Field(
            ...,
            description=(
                "One or more X v2 search queries to follow. For each query the "
                "workflow fetches hourly tweet counts: the first run backfills "
                "the full 7-day window (up to 168 hourly buckets); every "
                "subsequent run only fetches the clock hours that have completed "
                "since the last stored bucket, so historical values are never "
                "recomputed."
            ),
            examples=[
                ["(drone OR drones OR uas OR uav) lang:en -is:retweet"],
            ],
        ),
    ]


class XCountRecentTweetsWorkflow(Workflow[XCountRecentTweetsWorkflowParameters]):
    """Follow hourly X tweet counts for one or more queries, incrementally.

    The window is resolved from **graph state**, not wall-clock time: the newest
    ``x:tweet_created_at`` already mapped for a query is the ingestion front, and
    every complete clock hour below it that has no stored ``CountInterval`` is
    fetched (oldest first, capped per run). The in-progress hour containing that
    newest tweet is fetched separately as a *partial* window, so a tweet at 14:37
    yields ``13:00-14:00`` as a complete hour plus ``14:00-14:37`` as a partial.
    Because gaps are detected per hour rather than resumed from the newest
    bucket, an outage self-heals over successive runs.

    Round hours are enforced end-to-end: the fetch window is always bounded by
    two round clock hours, so every persisted bucket is a complete hour. The
    first run for a query backfills the whole 7-day window (24 × 7 hourly
    buckets); later runs resume from the hour after the newest stored bucket and
    fetch only the newly completed hours — a cheap way to keep the series fresh
    without recomputing the earlier buckets. The counts endpoint returns only
    time-bucketed totals (no tweet content) so it does not consume the
    tweet-retrieval budget.

    Queries are processed concurrently, one worker thread per query. Each fetch
    is persisted by the integration as a JSON envelope under
    ``<datastore>/count_recent_tweets/<slug>/``; the returned ``file_paths`` are
    what the orchestration then feeds to XCountRecentTweetsPipeline.
    """

    __configuration: XCountRecentTweetsWorkflowConfiguration
    __storage_utils: StorageUtils

    def __init__(self, configuration: XCountRecentTweetsWorkflowConfiguration):
        super().__init__(configuration)
        self.__configuration = configuration
        self.__storage_utils = StorageUtils(self.__configuration.object_storage)

    def _query_prefix(self, query: str) -> str:
        return os.path.join(
            self.__configuration.datastore_path,
            "count_recent_tweets",
            slugify_query(query),
        )

    # ----- graph state -----------------------------------------------------

    def latest_tweet_created_at(self, query: str) -> datetime | None:
        """Newest ``x:tweet_created_at`` mapped for *query*, or ``None``.

        This is the ingestion front: counting is driven by what the pipeline
        has actually written to the graph, so the count series can never run
        ahead of the tweets it is meant to describe.
        """
        triple_store = self.__configuration.triple_store
        if triple_store is None:
            return None
        escaped = _escape_sparql_string(query)
        sparql = f"""
        PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
        PREFIX x:   <{self.__configuration.namespace}>
        SELECT (MAX(?created) AS ?latest)
        WHERE {{
          GRAPH <{self.__configuration.tweet_graph_name}> {{
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
          }}
        }}
        """
        try:
            rows = list(triple_store.query(sparql))
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                f"XCountRecentTweetsWorkflow.latest_tweet_created_at failed for "
                f"{query!r} ({exc})"
            )
            return None
        if not rows:
            return None
        return _parse_iso(getattr(rows[0], "latest", None))

    def stored_hour_starts(self, query: str) -> set[datetime]:
        """Every complete-hour ``bucket_start`` already held for *query*.

        Read from the count graph rather than the newest envelope, so a gap
        left by an outage is visible instead of being skipped over by a
        "resume from the newest bucket" rule.
        """
        triple_store = self.__configuration.triple_store
        if triple_store is None:
            return set()
        escaped = _escape_sparql_string(query)
        sparql = f"""
        PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
        PREFIX x:   <{self.__configuration.namespace}>
        SELECT DISTINCT ?start
        WHERE {{
          GRAPH <{self.__configuration.count_graph_name}> {{
            ?rs rdf:type x:TweetCountResultSet ;
                x:query_string ?qs ;
                x:containsCountBucket ?bucket .
            FILTER(
              CONTAINS(LCASE(STR(?qs)), LCASE("{escaped}"))
              || CONTAINS(LCASE("{escaped}"), LCASE(STR(?qs)))
            )
            ?bucket x:hasCountInterval ?interval .
            ?interval x:bucket_start ?start .
            # Exclude the in-progress-hour slot. Its bucket_start is a real
            # clock hour, so counting it as "stored" would make that hour look
            # already covered and it would never be fetched once it completes.
            FILTER(!STRENDS(STR(?interval), "-partial"))
          }}
        }}
        """
        try:
            rows = triple_store.query(sparql)
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                f"XCountRecentTweetsWorkflow.stored_hour_starts failed for "
                f"{query!r} ({exc})"
            )
            return set()
        starts: set[datetime] = set()
        for row in rows:
            parsed = _parse_iso(getattr(row, "start", None))
            if parsed is not None:
                starts.add(_floor_hour(parsed))
        return starts

    def _missing_hours(self, query: str, latest_tweet: datetime) -> list[datetime]:
        """Complete clock hours still missing for *query*, oldest first.

        A clock hour is countable only once ingestion has moved past its end —
        ``latest_tweet`` at 13:02 makes ``12:00-13:00`` the newest complete
        hour. Capped at ``max_hours_per_run`` so a cold start converges over
        several runs instead of issuing 168 requests at once.
        """
        # Exclusive upper bound: the in-progress hour is handled as a partial.
        end = _floor_hour(latest_tweet)
        earliest = _floor_hour(latest_tweet - _MAX_LOOKBACK) + timedelta(hours=1)
        if end <= earliest:
            return []

        stored = self.stored_hour_starts(query)
        missing: list[datetime] = []
        cursor = earliest
        while cursor < end:
            if cursor not in stored:
                missing.append(cursor)
            cursor += timedelta(hours=1)
        cap = max(1, int(self.__configuration.max_hours_per_run))
        return missing[:cap]

    def stored_partial_end(self, query: str) -> datetime | None:
        """``bucket_end`` of the stored in-progress-hour slot for *query*.

        Doubles as the refresh throttle's state: how far the partial already
        reaches *is* when it was last refreshed, so no separate timestamp (or
        key-value store) has to be kept in sync with it.
        """
        triple_store = self.__configuration.triple_store
        if triple_store is None:
            return None
        escaped = _escape_sparql_string(query)
        sparql = f"""
        PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
        PREFIX x:   <{self.__configuration.namespace}>
        SELECT ?end
        WHERE {{
          GRAPH <{self.__configuration.count_graph_name}> {{
            ?rs rdf:type x:TweetCountResultSet ;
                x:query_string ?qs ;
                x:containsCountBucket ?bucket .
            FILTER(
              CONTAINS(LCASE(STR(?qs)), LCASE("{escaped}"))
              || CONTAINS(LCASE("{escaped}"), LCASE(STR(?qs)))
            )
            ?bucket x:hasCountInterval ?interval .
            ?interval x:bucket_end ?end .
            FILTER(STRENDS(STR(?interval), "-partial"))
          }}
        }}
        LIMIT 1
        """
        try:
            rows = list(triple_store.query(sparql))
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                f"XCountRecentTweetsWorkflow.stored_partial_end failed for "
                f"{query!r} ({exc})"
            )
            return None
        if not rows:
            return None
        return _parse_iso(getattr(rows[0], "end", None))

    def _should_refresh_partial(self, query: str, latest_tweet: datetime) -> bool:
        """Whether the in-progress hour is stale enough to re-fetch.

        Envelopes land continuously, so without this the counts endpoint would
        be called on every mapped file. Compared against the ingestion front
        rather than wall-clock, to stay consistent with the rest of the window
        logic.
        """
        stored_end = self.stored_partial_end(query)
        if stored_end is None:
            return True
        # A new clock hour always refreshes: the old slot describes a different
        # hour and must be replaced immediately, however recently it was written.
        if _floor_hour(stored_end) != _floor_hour(latest_tweet):
            return True
        age = (latest_tweet - stored_end).total_seconds()
        return age >= max(0, int(self.__configuration.partial_refresh_seconds))

    def _partial_window(self, latest_tweet: datetime) -> tuple[datetime, datetime]:
        """The in-progress hour so far: ``[floor(latest), latest]``."""
        return _floor_hour(latest_tweet), latest_tweet

    def _fetch_window(
        self, query: str, start: datetime, end: datetime, *, partial: bool
    ) -> dict | None:
        """Call the counts endpoint for one window and return its envelope."""
        start_iso = start.strftime(_ISO_Z)
        end_iso = end.strftime(_ISO_Z)
        logger.info(
            f"XCountRecentTweetsWorkflow: query={query!r} "
            f"{'partial' if partial else 'complete'} window "
            f"{start_iso} → {end_iso} "
            f"(granularity={self.__configuration.granularity})"
        )
        try:
            envelope = self.__configuration.x_integration.count_recent_tweets(
                query,
                start_time=start_iso,
                end_time=end_iso,
                granularity=self.__configuration.granularity,
            )
        except Exception as exc:  # noqa: BLE001 — one bad hour must not abort the run
            logger.warning(
                f"XCountRecentTweetsWorkflow: count fetch failed for {query!r} "
                f"{start_iso} → {end_iso} ({exc}); continuing"
            )
            return None
        if not isinstance(envelope, dict):
            return None
        # Tag the envelope so the pipeline knows whether these buckets are
        # complete clock hours or an in-progress slice of one.
        envelope["is_partial"] = partial
        envelope["window_start"] = start_iso
        envelope["window_end"] = end_iso
        return envelope

    def _process_query(self, query: str, now: datetime) -> dict:
        """Fetch every missing complete hour, then refresh the partial hour.

        ``now`` is only a fallback: the window is driven by the newest tweet
        already mapped for *query*, so counts describe the same period the
        graph does.
        """
        latest_tweet = self.latest_tweet_created_at(query)
        if latest_tweet is None:
            logger.info(
                f"XCountRecentTweetsWorkflow: query={query!r} has no mapped "
                f"tweets yet; nothing to count"
            )
            return {
                "query": query,
                "fetched": False,
                "buckets": 0,
                "file_paths": [],
                "latest_tweet_created_at": None,
            }

        envelopes: list[dict] = []
        buckets = 0

        for hour in self._missing_hours(query, latest_tweet):
            envelope = self._fetch_window(
                query, hour, hour + timedelta(hours=1), partial=False
            )
            if envelope is None:
                continue
            envelopes.append(envelope)
            data = (envelope.get("results") or {}).get("data") or []
            buckets += len(data) if isinstance(data, list) else 0

        partial_start, partial_end = self._partial_window(latest_tweet)
        if partial_end > partial_start and self._should_refresh_partial(
            query, latest_tweet
        ):
            envelope = self._fetch_window(
                query, partial_start, partial_end, partial=True
            )
            if envelope is not None:
                envelopes.append(envelope)
                data = (envelope.get("results") or {}).get("data") or []
                buckets += len(data) if isinstance(data, list) else 0

        return {
            "query": query,
            "fetched": bool(envelopes),
            "buckets": buckets,
            # Complete hours only. Partial envelopes are kept separate because
            # they must not go through the complete-hour path: those buckets are
            # deduped by <slug>-<bucket_start>, so mapping a partial there would
            # freeze an in-progress count into the hour's slot permanently.
            "file_paths": [
                e["file_path"]
                for e in envelopes
                if e.get("file_path") and not e.get("is_partial")
            ],
            # Carries the requested end alongside the path: the pipeline stores
            # it as the bucket's end so the slice's covered duration is exact.
            "partial_envelopes": [
                {"file_path": e["file_path"], "window_end": e.get("window_end")}
                for e in envelopes
                if e.get("is_partial") and e.get("file_path")
            ],
            "latest_tweet_created_at": latest_tweet.isoformat(),
        }

    def run(self, parameters: XCountRecentTweetsWorkflowParameters) -> dict:
        if not isinstance(parameters, XCountRecentTweetsWorkflowParameters):
            raise TypeError(
                "Parameters must be of type XCountRecentTweetsWorkflowParameters"
            )
        queries = parameters.queries
        if not queries:
            return {"total_buckets": 0, "results": []}

        now = datetime.now(UTC)
        with ThreadPoolExecutor(max_workers=len(queries)) as executor:
            results = list(
                executor.map(lambda query: self._process_query(query, now), queries)
            )

        file_paths: list[str] = []
        partial_paths: list[str] = []
        for item in results:
            file_paths.extend(item.get("file_paths") or [])
            partial_paths.extend(item.get("partial_envelopes") or [])

        return {
            "total_buckets": sum(item["buckets"] for item in results),
            # Complete-hour envelopes, safe for the existing pipeline path.
            "file_paths": file_paths,
            # In-progress-hour envelopes. Fetched and persisted, but deliberately
            # NOT in file_paths: they need the pipeline's partial slot, which
            # routes them away from the deduped complete-hour IRIs.
            "partial_file_paths": partial_paths,
            "results": results,
        }

    def as_tools(self) -> list[BaseTool]:
        return [
            StructuredTool(
                name="x_follow_recent_tweet_counts",
                description=(
                    "Follow hourly X tweet counts for one or more queries. The "
                    "first run per query backfills the 7-day window; later runs "
                    "fetch only the newly completed clock hours. Returns, per "
                    "query, the number of buckets fetched and the persisted "
                    "count envelope file_path."
                ),
                func=lambda **kwargs: self.run(
                    XCountRecentTweetsWorkflowParameters(**kwargs)
                ),
                args_schema=XCountRecentTweetsWorkflowParameters,
            )
        ]

    def as_api(
        self,
        router,
        route_name: str = "",
        name: str = "",
        description: str = "",
        description_stream: str = "",
        tags: list[str | Enum] | None = None,
    ) -> None:
        if tags is None:
            tags = []


if __name__ == "__main__":
    """Command-line entry point for XCountRecentTweetsWorkflow.

    ```
    abi dev up
    OXIGRAPH_URL=http://127.0.0.1:8432 uv run python \
        libs/naas-abi-marketplace/naas_abi_marketplace/applications/x/workflows/XCountRecentTweetsWorkflow.py \
        --queries '(drone OR drones OR uas OR uav) lang:en -is:retweet'
    ```
    """
    import argparse

    from naas_abi_core.engine.Engine import Engine
    from naas_abi_marketplace.applications.x.integrations.XIntegration import (
        XIntegrationConfiguration,
    )

    parser = argparse.ArgumentParser(
        description="Follow hourly X tweet counts for one or more queries."
    )
    parser.add_argument(
        "--queries",
        nargs="+",
        default=["(drone OR drones OR uas OR uav) lang:en -is:retweet"],
        help="One or more X v2 search queries to follow.",
    )
    args = parser.parse_args()

    engine = Engine()
    engine.load(module_names=["naas_abi_marketplace.applications.x"])

    bearer_token = engine.services.secret.get("X_BEARER_TOKEN")
    datastore_path = ABIModule.get_instance().configuration.datastore_path
    x_integration = XIntegration(
        XIntegrationConfiguration(
            bearer_token=bearer_token, datastore_path=datastore_path
        )
    )

    workflow = XCountRecentTweetsWorkflow(
        XCountRecentTweetsWorkflowConfiguration(
            x_integration=x_integration,
            object_storage=engine.services.object_storage,
            datastore_path=datastore_path,
        )
    )
    output = workflow.run(XCountRecentTweetsWorkflowParameters(queries=args.queries))
    for item in output["results"]:
        state = "fetched" if item["fetched"] else "up-to-date"
        print(
            f"[{item['query'][:60]}…] {state} — {item['buckets']} bucket(s) "
            f"{item.get('start_time') or ''} → {item.get('end_time') or ''}"
        )
    print(f"Total buckets fetched: {output['total_buckets']}")
