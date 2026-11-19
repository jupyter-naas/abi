"""Map an X recent-tweet-count envelope into the count graph.

Port of the in-engine ``XCountRecentTweetsPipeline`` without core: the same
graph, IRIs, label-based dedupe and partial-hour slot.

A plain class, not an SDK ``Pipeline``: its ``run`` is synchronous (a worker
thread, called by ``flows/common.py``), and the SDK would publish a ``Pipeline``
subclass found under ``pipelines/`` as ``pipeline.<slug>``. The triple store and
object storage are the blocking ``SyncService``s of a ``services.SyncModule``.

In ``file_path`` mode (what the flows use) it reads a saved envelope and calls
no API::

    pipeline = XCountRecentTweetsPipeline(
        XCountRecentTweetsPipelineConfiguration(
            triple_store=sync.engine.services.triple_store,
            object_storage=sync.engine.services.object_storage,
            namespace=sync.configuration.ontology_namespace,
        )
    )
    pipeline.run(XCountRecentTweetsPipelineParameters(file_path=path))

The ``query`` mode calls ``x_integration.count_recent_tweets`` through ``run``.
"""

import hashlib
import json as _json
import posixpath
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Annotated, Any

from naas_abi_apps.x.integrations.XIntegration import (
    EXAMPLE_X_SEARCH_QUERY,
    XIntegration,
    slugify_query,
)
from naas_abi_apps.x.ontologies.modules.XOntology import XPlatform
from naas_abi_apps.x.ontologies.processes.XCountRecentTweetsProcess import (
    CountInterval,
    CountRecentTweets,
    TweetCountBucket,
    TweetCountResultSet,
)
from naas_abi_apps.x.pipelines.utils import (
    XTweetGraphBuilder,
    parse_dt,
)
from naas_abi_apps.x.services import StorageUtils, logger
from pydantic import BaseModel, Field, model_validator
from rdflib import Graph, Namespace, URIRef

X_NAMESPACE = "http://ontology.naas.ai/x/"

# Dedicated named graph for the recent-posts count triples, so the counts live
# next to (but never collide with) the tweet-content graph written by
# XSearchRecentTweetsPipeline.
_COUNT_GRAPH_NAME = "http://ontology.naas.ai/graph/x_recent_posts_count"

# Recognised keyword arguments accepted by XIntegration.count_recent_tweets.
_COUNT_OPTION_KEYS = frozenset(
    {
        "start_time",
        "end_time",
        "since_id",
        "until_id",
        "granularity",
        "search_count_fields",
        "max_pages",
    }
)


@dataclass
class XCountRecentTweetsPipelineConfiguration:
    """Configuration for XCountRecentTweetsPipeline.

    Attributes:
        triple_store: The blocking triple store (``SyncService``): the
            label-based existence checks, the partial-slot replacement and the
            insert of new triples.
        object_storage: The blocking object storage (``SyncService``) the count
            envelopes are read from.
        graph_name: Named graph in the triple store where the counts are written
            (defaults to the dedicated x_recent_posts_count graph).
        namespace: The X ontology namespace (the module's ``ontology_namespace``).
        x_integration: The async XIntegration, for the ``query`` mode only.
        run: Runs a coroutine from the calling (worker) thread
            (``SyncModule.run``), for the ``query`` mode only.
    """

    triple_store: Any
    object_storage: Any
    graph_name: URIRef = URIRef(_COUNT_GRAPH_NAME)
    namespace: str = X_NAMESPACE
    datastore_path: str = "x"
    x_integration: XIntegration | None = None
    run: Callable[[Awaitable[Any]], Any] | None = None


class XCountRecentTweetsPipelineParameters(BaseModel):
    query: Annotated[
        str | None,
        Field(
            default=None,
            description=(
                "X v2 search query (1-4096 chars) whose recent-tweet count to "
                "map. Required when file_path is not provided."
            ),
            examples=[EXAMPLE_X_SEARCH_QUERY],
        ),
    ] = None
    options: Annotated[
        dict | None,
        Field(
            default=None,
            description=(
                "Optional keyword arguments forwarded to "
                "XIntegration.count_recent_tweets — any subset of: start_time, "
                "end_time, since_id, until_id, granularity, search_count_fields, "
                "max_pages. Ignored when file_path is provided (options are read "
                "from the file)."
            ),
            examples=[
                {
                    "start_time": "2026-07-01T00:00:00Z",
                    "end_time": "2026-07-08T00:00:00Z",
                    "granularity": "hour",
                }
            ],
        ),
    ] = None
    file_path: Annotated[
        str | None,
        Field(
            default=None,
            description=(
                "Path to a JSON count envelope previously saved by "
                "XIntegration.count_recent_tweets / XCountRecentTweetsWorkflow. "
                "The file must contain {query, options, results, total_tweet_count, "
                "started_at, ended_at} where results.data is the merged list of "
                "count buckets. When provided, the pipeline reads the envelope "
                "instead of calling the X API."
            ),
        ),
    ] = None
    persist: Annotated[
        bool,
        Field(
            description=(
                "Whether to insert the generated graph into the configured "
                "triple store. Set False to only return the graph."
            ),
        ),
    ] = True
    partial: Annotated[
        bool,
        Field(
            description=(
                "Treat the envelope's buckets as an in-progress clock hour. "
                "Partial buckets are written to a separate per-query slot that "
                "each refresh overwrites, so they never occupy — or freeze — the "
                "deduped complete-hour IRIs."
            ),
        ),
    ] = False
    partial_end: Annotated[
        str | None,
        Field(
            default=None,
            description=(
                "Exclusive upper bound actually requested for a partial window "
                "(ISO-8601). Stored as the bucket's end so its covered duration "
                "is exact, rather than trusting the counts response to echo the "
                "sub-hour bound back. Ignored unless partial is True."
            ),
            examples=["2026-07-07T14:32:00Z"],
        ),
    ] = None

    @model_validator(mode="after")
    def _require_query_or_file_path(self) -> "XCountRecentTweetsPipelineParameters":
        if not self.file_path and not self.query:
            raise ValueError("Either 'query' or 'file_path' must be provided.")
        return self


class XCountRecentTweetsPipeline:
    """Maps an X v2 recent-tweet-count envelope into the knowledge graph.

    For a given query the pipeline creates a ``CountRecentTweets`` process that
    produces a ``TweetCountResultSet`` (carrying the query string, granularity,
    window and summed ``total_tweet_count``). Every time bucket becomes a
    ``TweetCountBucket`` occupying a ``CountInterval`` (bucket_start → bucket_end).

    Bucket / interval IRIs are deterministic — keyed on ``<query-slug>-<bucket
    start>`` — so the hourly workflow re-ingesting the same clock hour is
    idempotent: each hour is counted once no matter how many result-set
    snapshots reference it. Individuals are skipped when one with the same
    ``rdfs:label`` already lives in the configured named graph.
    """

    __configuration: XCountRecentTweetsPipelineConfiguration
    __storage_utils: StorageUtils

    def __init__(self, configuration: XCountRecentTweetsPipelineConfiguration):
        self.__configuration = configuration
        self._namespace = configuration.namespace
        self.namespace = Namespace(self._namespace)
        self.__storage_utils = StorageUtils(self.__configuration.object_storage)

    # ----- URI / hash helpers ---------------------------------------------------

    @staticmethod
    def _params_hash(query: str, options: dict) -> str:
        """8-char md5 of (query + sorted options).

        Mirrors the cache-key convention used by
        ``XIntegration.count_recent_tweets`` so the process / result-set IRIs of
        a given request are stable across executions.
        """
        payload = {"query": query, **{k: options.get(k) for k in sorted(options)}}
        return hashlib.md5(
            _json.dumps(payload, sort_keys=True, default=str).encode()
        ).hexdigest()[:8]

    def _clear_partial_slot(self, builder, slug: str) -> None:
        """Drop the previous in-progress-hour triples for *slug*.

        The partial slot holds exactly one bucket per query, so a refresh has to
        replace it rather than accumulate: without this, 14:00-14:12 and
        14:00-14:37 would both linger and any consumer would double-count the
        hour. Also clears the builder's existence cache for the two labels so
        this run re-emits them.
        """
        triple_store = self.__configuration.triple_store
        graph_name = self.__configuration.graph_name
        stable_id = f"{slug}-partial"
        for class_name, class_uri, label in (
            (
                "CountInterval",
                CountInterval._class_uri,
                f"Count Interval {slug} partial",
            ),
            (
                "TweetCountBucket",
                TweetCountBucket._class_uri,
                f"Tweet Count Bucket {slug} partial",
            ),
            (
                "TweetCountResultSet",
                TweetCountResultSet._class_uri,
                f"Tweet Count Result Set {stable_id}",
            ),
            (
                "CountRecentTweets",
                CountRecentTweets._class_uri,
                f"Count Recent Tweets {stable_id}",
            ),
        ):
            subject = builder.uri(class_name, stable_id)
            try:
                existing = triple_store.get_subject_graph(subject, str(graph_name))
            except Exception as exc:  # noqa: BLE001 — nothing stored yet is normal
                logger.debug(
                    f"XCountRecentTweetsPipeline: no partial slot to clear for "
                    f"{subject} ({exc})"
                )
                existing = None
            if existing is not None and len(existing):
                triple_store.remove(existing, graph_name)
            builder._exists_cache.pop((class_uri, label), None)

    # ----- Top-level run --------------------------------------------------------

    def run(self, parameters: XCountRecentTweetsPipelineParameters) -> Graph:
        if not isinstance(parameters, XCountRecentTweetsPipelineParameters):
            raise TypeError(
                "Parameters must be of type XCountRecentTweetsPipelineParameters"
            )

        if parameters.file_path:
            logger.info(
                f"XCountRecentTweetsPipeline: loading counts from file "
                f"{parameters.file_path!r}"
            )
            dir_path, file_name = posixpath.split(parameters.file_path)
            envelope = self.__storage_utils.get_json(dir_path, file_name)
            if not envelope:
                raise FileNotFoundError(
                    f"XCountRecentTweetsPipeline: no readable JSON envelope at "
                    f"{parameters.file_path!r} (under the object-storage root)."
                )
        else:
            req_query: str = parameters.query  # type: ignore[assignment]
            req_opts: dict = parameters.options or {}
            unknown = set(req_opts) - _COUNT_OPTION_KEYS
            if unknown:
                raise ValueError(
                    f"Unknown options for count_recent_tweets: {sorted(unknown)}. "
                    f"Accepted keys: {sorted(_COUNT_OPTION_KEYS)}"
                )
            logger.info(
                f"XCountRecentTweetsPipeline: calling count_recent_tweets("
                f"query={req_query!r}, options={req_opts})"
            )
            x_integration = self.__configuration.x_integration
            run = self.__configuration.run
            if x_integration is None or run is None:
                raise ValueError(
                    "XCountRecentTweetsPipeline: the query mode needs x_integration "
                    "and run in its configuration"
                )
            envelope = run(x_integration.count_recent_tweets(req_query, **req_opts))

        query: str = envelope.get("query", "")
        options: dict = envelope.get("options") or {}
        results: dict = envelope.get("results") or {}
        meta: dict = results.get("meta") or {}
        buckets: list[dict] = results.get("data") or []
        total_tweet_count = envelope.get("total_tweet_count")
        if total_tweet_count is None:
            total_tweet_count = meta.get("total_tweet_count")
        started_at = parse_dt(envelope.get("started_at"))
        file_path: str | None = parameters.file_path or envelope.get("file_path")

        slug = slugify_query(query)
        # A partial is refreshed every few minutes, so hashing its (moving)
        # window would mint a new result set each time and grow without bound.
        # One stable id per query keeps exactly one live partial snapshot.
        result_set_id = (
            f"{slug}-partial"
            if parameters.partial
            else self._params_hash(query, options)
        )
        granularity = options.get("granularity") or "hour"

        logger.info(
            f"XCountRecentTweetsPipeline: {len(buckets)} bucket(s), "
            f"total_tweet_count={total_tweet_count} (query={query!r}, "
            f"granularity={granularity})"
        )

        builder = XTweetGraphBuilder(
            self.__configuration.triple_store,
            self.__configuration.graph_name,
            self._namespace,
        )

        graph = Graph()
        graph.bind("x", self.namespace)

        # Platform (singleton site)
        platform = XPlatform(
            _uri=f"{self._namespace}XPlatform/x.com", label="X Platform"
        )
        if not builder.label_exists("X Platform", XPlatform._class_uri):
            graph += platform.rdf()
            builder.mark_existing(XPlatform._class_uri, "X Platform")

        # One TweetCountBucket + CountInterval per time bucket. Deterministic
        # IRIs keyed on <slug>-<bucket start> make hourly re-ingestion idempotent.
        #
        # A *partial* envelope covers an hour that is still in progress, so its
        # count is not final and must never occupy that hour's slot: the
        # skip-if-the-label-exists rule below would freeze the first partial
        # value and drop the real total once the hour completes. Partials
        # therefore go to a single per-query slot (``<slug>-partial``) that each
        # refresh overwrites, leaving the complete-hour IRIs untouched.
        if parameters.partial:
            self._clear_partial_slot(builder, slug)

        bucket_uris: list[TweetCountBucket | URIRef | str] = []
        for bucket in buckets:
            bucket_start = bucket.get("start")
            bucket_end = bucket.get("end")
            count = bucket.get("tweet_count")
            if bucket_start is None:
                continue
            if parameters.partial:
                stable_id = f"{slug}-partial"
                start_dt = parse_dt(bucket_start)
                # Trust the window we asked for over the response's echo of it:
                # the counts endpoint is not guaranteed to report a sub-hour
                # end, and an end rounded up to the hour boundary would make the
                # slice look complete.
                end_dt = parse_dt(parameters.partial_end) or parse_dt(bucket_end)
                interval_label = f"Count Interval {slug} partial"
                bucket_label = f"Tweet Count Bucket {slug} partial"
            else:
                stable_id = f"{slug}-{bucket_start}"
                start_dt = parse_dt(bucket_start)
                end_dt = parse_dt(bucket_end)
                interval_label = f"Count Interval {slug} {bucket_start}"
                bucket_label = f"Tweet Count Bucket {slug} {bucket_start}"

            interval = CountInterval(
                _uri=builder.uri("CountInterval", stable_id),
                label=interval_label,
                bucket_start=start_dt,
                bucket_end=end_dt,
            )
            # Partials are always rewritten (the slot was just cleared); complete
            # hours keep their idempotent skip-if-present behaviour.
            if parameters.partial or not builder.label_exists(
                interval_label, CountInterval._class_uri
            ):
                graph += interval.rdf()
                builder.mark_existing(CountInterval._class_uri, interval_label)

            count_bucket = TweetCountBucket(
                _uri=builder.uri("TweetCountBucket", stable_id),
                label=bucket_label,
                bucket_tweet_count=count,
                has_count_interval=[URIRef(interval._uri)],
            )
            if parameters.partial or not builder.label_exists(
                bucket_label, TweetCountBucket._class_uri
            ):
                graph += count_bucket.rdf()
                builder.mark_existing(TweetCountBucket._class_uri, bucket_label)
            bucket_uris.append(URIRef(count_bucket._uri))

        # TweetCountResultSet — one snapshot per request; links to every bucket.
        rs_label = f"Tweet Count Result Set {result_set_id}"
        result_set = TweetCountResultSet(
            _uri=builder.uri("TweetCountResultSet", result_set_id),
            label=rs_label,
            query_string=query,
            granularity=granularity,
            start_time=parse_dt(options.get("start_time")),
            end_time=parse_dt(options.get("end_time")),
            total_tweet_count=total_tweet_count,
            file_path=file_path,
            contains_count_bucket=bucket_uris or None,
        )
        if parameters.partial or not builder.label_exists(
            rs_label, TweetCountResultSet._class_uri
        ):
            graph += result_set.rdf()
            builder.mark_existing(TweetCountResultSet._class_uri, rs_label)

        # CountRecentTweets process linking it together.
        now = datetime.now(UTC)
        process_label = f"Count Recent Tweets {result_set_id}"
        process = CountRecentTweets(
            _uri=builder.uri("CountRecentTweets", result_set_id),
            label=process_label,
            produces_count_result=[URIRef(result_set._uri)],
            occurs_in=[URIRef(platform._uri)],
            created=started_at or now,
        )
        if parameters.partial or not builder.label_exists(
            process_label, CountRecentTweets._class_uri
        ):
            graph += process.rdf()
            builder.mark_existing(CountRecentTweets._class_uri, process_label)

        logger.info(
            f"XCountRecentTweetsPipeline: produced graph with {len(graph)} triples"
        )

        if parameters.persist:
            self.__configuration.triple_store.insert(
                graph, self.__configuration.graph_name
            )
            logger.info(
                f"XCountRecentTweetsPipeline: inserted {len(graph)} triples into "
                f"<{self.__configuration.graph_name}>"
            )

        return graph
