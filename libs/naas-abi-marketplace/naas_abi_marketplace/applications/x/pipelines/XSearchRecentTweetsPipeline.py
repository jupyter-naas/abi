import hashlib
import json as _json
import posixpath
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Annotated, Any, Optional

from langchain_core.tools import BaseTool, StructuredTool
from naas_abi_core import logger
from naas_abi_core.pipeline import (
    Pipeline,
    PipelineConfiguration,
    PipelineParameters,
)
from naas_abi_core.services.object_storage.ObjectStorageService import (
    ObjectStorageService,
)
from naas_abi_core.services.triple_store.TripleStoreService import TripleStoreService
from naas_abi_core.utils.Expose import APIRouter
from naas_abi_core.utils.StorageUtils import StorageUtils
from naas_abi_marketplace.applications.x import ABIModule
from naas_abi_marketplace.applications.x.integrations.XIntegration import (
    XIntegration,
)
from naas_abi_marketplace.applications.x.ontologies.modules.XOntology import (
    Media,
    SearchInterval,
    SearchQuery,
    SearchRecentTweets,
    SearchResultSet,
    TemporalInstant,
    Tweet,
    XPlatform,
    XUser,
)
from naas_abi_marketplace.applications.x.pipelines.utils import (
    XTweetGraphBuilder,
    parse_dt,
)
from pydantic import Field, model_validator
from rdflib import Graph, Namespace, URIRef

# onto2py classifies single-valued xsd:string data properties as object
# properties when their field is typed Union[URIRef, str]. The generated
# rdf() then emits their values as IRIs instead of literals, which breaks
# Turtle serialization for free-text fields like query_string / result_set_id.
# (Tweet/XUser get the same fix-up inside the shared graph builder.)
for _cls, _data_props in (
    (SearchQuery, {"query_string"}),
    (SearchResultSet, {"result_set_id"}),
):
    _cls._object_properties = _cls._object_properties - _data_props


@dataclass
class XSearchRecentTweetsPipelineConfiguration(PipelineConfiguration):
    """Configuration for XSearchRecentTweetsPipeline.

    Attributes:
        x_integration: The XIntegration used to call the X v2 recent-search
            endpoint at run time.
        triple_store: Service used to check for already-ingested individuals
            (label-based existence check) and to persist new triples.
        object_storage: Service used to save the search results to a file.
        graph_name: Named graph in the triple store where tweets are written.
    """

    x_integration: XIntegration
    triple_store: TripleStoreService
    object_storage: ObjectStorageService
    graph_name: URIRef = field(
        default_factory=lambda: URIRef(
            ABIModule.get_instance().configuration.graph_name
        )
    )
    datastore_path: str = field(
        default_factory=lambda: ABIModule.get_instance().configuration.datastore_path
    )


class XSearchRecentTweetsPipelineParameters(PipelineParameters):
    query: Annotated[
        Optional[str],
        Field(
            default=None,
            description=(
                "X v2 search query (1-4096 chars) — see "
                "https://developer.twitter.com/en/docs/twitter-api/tweets/search/integrate/build-a-query. "
                "Required when file_path is not provided."
            ),
            examples=["(from:TwitterDev OR from:TwitterAPI) has:media -is:retweet"],
        ),
    ] = None
    options: Annotated[
        Optional[dict],
        Field(
            default=None,
            description=(
                "Optional keyword arguments forwarded to "
                "XIntegration.search_recent_tweets — any subset of: "
                "start_time, end_time, since_id, until_id, max_results, "
                "sort_order, tweet_fields, expansions, media_fields, "
                "poll_fields, user_fields, place_fields, max_pages. "
                "Ignored when file_path is provided (options are read from the file)."
            ),
            examples=[
                {
                    "start_time": "2026-05-26T00:00:00Z",
                    "end_time": "2026-06-02T00:00:00Z",
                    "max_results": 100,
                    "sort_order": "recency",
                    "max_pages": 1,
                }
            ],
        ),
    ] = None
    file_path: Annotated[
        Optional[str],
        Field(
            default=None,
            description=(
                "Path to a JSON file previously saved by XIntegration.search_recent_tweets. "
                "The file must contain {query, options, results, started_at, ended_at} "
                "where results is the merged X v2 response {data, includes, meta}. "
                "When provided, the pipeline reads query/options/results from the file "
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

    @model_validator(mode="after")
    def _require_query_or_file_path(self) -> "XSearchRecentTweetsPipelineParameters":
        if not self.file_path and not self.query:
            raise ValueError("Either 'query' or 'file_path' must be provided.")
        return self


# Recognised keyword arguments accepted by XIntegration.search_recent_tweets.
_SEARCH_OPTION_KEYS = frozenset(
    {
        "start_time",
        "end_time",
        "since_id",
        "until_id",
        "max_results",
        "sort_order",
        "tweet_fields",
        "expansions",
        "media_fields",
        "poll_fields",
        "user_fields",
        "place_fields",
        "max_pages",
    }
)


class XSearchRecentTweetsPipeline(Pipeline):
    """Calls XIntegration.search_recent_tweets and maps the result to the graph.

    For every tweet returned by the X v2 ``GET /2/tweets/search/recent``
    endpoint, the pipeline creates a ``Tweet`` individual linked to its author
    ``XUser``, ``TweetPublicMetrics`` and ``TweetLanguage``; all tweets are
    linked to a ``SearchResultSet`` produced by a ``SearchRecentTweets``
    process that uses a ``SearchQuery``. URIs are deterministic (derived from
    the X-side identifiers plus a hash of the request parameters) so re-runs
    are idempotent, and each individual is skipped when one with the same
    ``rdfs:label`` already lives in the configured named graph.
    """

    __configuration: XSearchRecentTweetsPipelineConfiguration
    __storage_utils: StorageUtils

    def __init__(self, configuration: XSearchRecentTweetsPipelineConfiguration):
        super().__init__(configuration)
        self.__configuration = configuration
        self._namespace = ABIModule.get_instance().configuration.ontology_namespace
        self.namespace = Namespace(self._namespace)
        self.__storage_utils = StorageUtils(self.__configuration.object_storage)

    # ----- URI / hash helpers ---------------------------------------------------

    @staticmethod
    def _params_hash(query: str, options: dict) -> str:
        """8-char md5 of (query + sorted options).

        Mirrors the cache-key convention used by
        ``XIntegration.search_recent_tweets`` so a pipeline run that targets
        the same request reuses the same SearchResultSet / SearchRecentTweets
        IRIs across executions.
        """
        payload = {"query": query, **{k: options.get(k) for k in sorted(options)}}
        return hashlib.md5(
            _json.dumps(payload, sort_keys=True, default=str).encode()
        ).hexdigest()[:8]

    # ----- Top-level run --------------------------------------------------------

    def run(self, parameters: XSearchRecentTweetsPipelineParameters) -> Graph:  # type: ignore[override]
        if not isinstance(parameters, XSearchRecentTweetsPipelineParameters):
            raise ValueError(
                "Parameters must be of type XSearchRecentTweetsPipelineParameters"
            )

        if parameters.file_path:
            logger.info(
                f"XSearchRecentTweetsPipeline: loading tweets from file {parameters.file_path!r}"
            )
            # ``get_json`` takes (dir_path, file_name) relative to the object
            # storage root — split the stored path on its final segment.
            dir_path, file_name = posixpath.split(parameters.file_path)
            envelope = self.__storage_utils.get_json(dir_path, file_name)
            # ``get_json`` swallows read errors and returns {}; surface a clear
            # failure rather than silently producing an empty graph.
            if not envelope:
                raise FileNotFoundError(
                    f"XSearchRecentTweetsPipeline: no readable JSON envelope at "
                    f"{parameters.file_path!r} (under the object-storage root)."
                )
        else:
            req_query: str = parameters.query  # type: ignore[assignment]
            req_opts: dict = parameters.options or {}

            # Forward only recognised keys so an unexpected key fails fast at the
            # boundary rather than deep inside the integration.
            unknown = set(req_opts) - _SEARCH_OPTION_KEYS
            if unknown:
                raise ValueError(
                    f"Unknown options for search_recent_tweets: {sorted(unknown)}. "
                    f"Accepted keys: {sorted(_SEARCH_OPTION_KEYS)}"
                )

            logger.info(
                f"XSearchRecentTweetsPipeline: calling search_recent_tweets("
                f"query={req_query!r}, options={req_opts})"
            )
            envelope = self.__configuration.x_integration.search_recent_tweets(
                req_query, **req_opts
            )

        query: str = envelope.get("query", "")
        options: dict = envelope.get("options", {})
        results: dict = envelope.get("results") or {}
        started_at = parse_dt(envelope.get("started_at"))
        ended_at = parse_dt(envelope.get("ended_at"))
        # Path of the persisted envelope: the parameter when ingesting a file,
        # otherwise the path the integration just wrote in the direct-query case.
        file_path: Optional[str] = parameters.file_path or envelope.get("file_path")

        # ``results`` is the merged X v2 response {data, includes, meta}:
        #   data            → tweets that matched the query (the result set)
        #   includes.tweets → referenced/context tweets pulled in by expansions
        #   includes.users  → expanded author / mentioned / reply-to profiles
        #   includes.media  → expanded media attached to the matched tweets
        data: list[dict] = results.get("data") or []
        includes: dict = results.get("includes") or {}
        meta: dict = results.get("meta") or {}
        users: list[dict] = includes.get("users") or []
        tweets: list[dict] = includes.get("tweets") or []
        media: list[dict] = includes.get("media") or []

        logger.info(
            f"XSearchRecentTweetsPipeline: {len(data)} matched tweets, "
            f"{len(users)} expanded users, "
            f"{len(tweets)} context tweets, "
            f"{len(media)} media (query={query!r})"
        )

        # Deterministic id for the *result set* of this request — used as the
        # stable URI fragment for the SearchResultSet / SearchInterval /
        # SearchRecentTweets process individuals.
        result_set_id = self._params_hash(query, options)

        builder = XTweetGraphBuilder(
            self.__configuration.triple_store, self.__configuration.graph_name
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

        # SearchQuery
        query_hash = hashlib.md5(query.encode()).hexdigest()[:8]
        query_label = f"Search Query: {query}"
        search_query = SearchQuery(
            _uri=builder.uri("SearchQuery", query_hash),
            label=query_label,
            query_string=query,
            start_time=parse_dt(options.get("start_time")),
            end_time=parse_dt(options.get("end_time")),
            since_id=options.get("since_id"),
            until_id=options.get("until_id"),
            max_results=options.get("max_results"),
            sort_order=options.get("sort_order"),
            max_pages=options.get("max_pages"),
            tweet_fields=self._join(options.get("tweet_fields")),
            expansions=self._join(options.get("expansions")),
            media_fields=self._join(options.get("media_fields")),
            poll_fields=self._join(options.get("poll_fields")),
            user_fields=self._join(options.get("user_fields")),
            place_fields=self._join(options.get("place_fields")),
        )
        if not builder.label_exists(query_label, SearchQuery._class_uri):
            graph += search_query.rdf()
            builder.mark_existing(SearchQuery._class_uri, query_label)

        # SearchResultSet
        rs_label = f"Search Result Set {result_set_id}"
        rs_uri = builder.uri("SearchResultSet", result_set_id)
        result_set = SearchResultSet(
            _uri=rs_uri,
            label=rs_label,
            result_set_id=result_set_id,
            result_count=meta.get("result_count") or len(data),
            newest_id=meta.get("newest_id"),
            oldest_id=meta.get("oldest_id"),
            next_token=meta.get("next_token"),
            file_path=file_path,
        )
        if not builder.label_exists(rs_label, SearchResultSet._class_uri):
            graph += result_set.rdf()
            builder.mark_existing(SearchResultSet._class_uri, rs_label)

        # SearchInterval bounded by the started_at / ended_at instants of the
        # API call (taken from the file envelope or measured around the call).
        now = datetime.now(timezone.utc)
        interval_label = f"Search Interval {result_set_id}"
        interval = SearchInterval(
            _uri=builder.uri("SearchInterval", result_set_id),
            label=interval_label,
        )
        for bound, interval_field in (
            (started_at, "search_started_at"),
            (ended_at, "search_ended_at"),
        ):
            if bound is None:
                continue
            instant_label = bound.isoformat()
            instant = TemporalInstant(
                _uri=builder.uri("TemporalInstant", instant_label),
                label=instant_label,
            )
            if not builder.label_exists(instant_label, TemporalInstant._class_uri):
                graph += instant.rdf()
                builder.mark_existing(TemporalInstant._class_uri, instant_label)
            setattr(interval, interval_field, [URIRef(instant._uri)])
        if not builder.label_exists(interval_label, SearchInterval._class_uri):
            graph += interval.rdf()
            builder.mark_existing(SearchInterval._class_uri, interval_label)

        # Deterministic URIs of every entity this search brought back, so the
        # SearchRecentTweets process can carry the participation relations to
        # them (x:retrievesTweet / x:retrievesUser / x:retrievesMedia). The URIs
        # mirror exactly what build_tweet / build_user / build_media mint below,
        # so the links resolve to the individuals emitted in this same graph.
        retrieved_tweet_uris: list[Tweet | URIRef | str] = [
            URIRef(builder.uri("Tweet", str(record["id"])))
            for record in data
            if record.get("id")
        ]
        retrieved_user_uris: list[XUser | URIRef | str] = [
            URIRef(builder.uri("XUser", str(user_record["id"])))
            for user_record in users
            if user_record.get("id")
        ]
        retrieved_media_uris: list[Media | URIRef | str] = [
            URIRef(builder.uri("Media", str(media_record["media_key"])))
            for media_record in media
            if media_record.get("media_key")
        ]

        # SearchRecentTweets process linking it all together
        process_label = f"Search Recent Tweets {result_set_id}"
        process = SearchRecentTweets(
            _uri=builder.uri("SearchRecentTweets", result_set_id),
            label=process_label,
            uses_search_query=[URIRef(search_query._uri)],
            produces_search_result=[URIRef(result_set._uri)],
            has_search_interval=[URIRef(interval._uri)],
            occursIn=[URIRef(platform._uri)],
            retrieves_tweet=retrieved_tweet_uris or None,
            retrieves_user=retrieved_user_uris or None,
            retrieves_media=retrieved_media_uris or None,
            created=now,
        )
        if not builder.label_exists(process_label, SearchRecentTweets._class_uri):
            graph += process.rdf()
            builder.mark_existing(SearchRecentTweets._class_uri, process_label)

        # Expanded users first (rich profiles + metrics) so they win the
        # label-dedup race against the minimal author stubs build_tweet emits.
        for user_record in users:
            _, user_graph = builder.build_user(user_record)
            graph += user_graph

        # Expanded media, so attachments.media_keys links resolve.
        for media_record in media:
            _, media_graph = builder.build_media(media_record)
            graph += media_graph

        # Matched tweets — delegate per-tweet mapping to the shared builder so
        # file ingestion gets the identical graph shape. These carry the link
        # to the SearchResultSet.
        for record in data:
            graph += builder.build_tweet(record, source_set_uri=result_set._uri)

        # Context tweets (referenced_tweets.id expansion) — mapped without a
        # result-set link since they did not match the search themselves.
        # Mapped after the matched tweets so a tweet present in both keeps
        # its result-set link.
        for record in tweets:
            graph += builder.build_tweet(record, source_set_uri=None)

        logger.info(
            f"XSearchRecentTweetsPipeline: produced graph with {len(graph)} triples"
        )

        if parameters.persist:
            self.__configuration.triple_store.insert(
                graph, self.__configuration.graph_name
            )
            logger.info(
                f"XSearchRecentTweetsPipeline: inserted {len(graph)} triples into "
                f"<{self.__configuration.graph_name}>"
            )

        return graph

    # ----- Utilities ------------------------------------------------------------

    @staticmethod
    def _join(value: Any) -> Optional[str]:
        """Render a list-valued X v2 expansion field as the comma-joined form
        stored on SearchQuery (matching the wire format sent to the API)."""
        if value is None:
            return None
        if isinstance(value, list):
            return ",".join(str(v) for v in value) or None
        return str(value)

    # ----- Framework hooks ------------------------------------------------------

    def as_tools(self) -> list[BaseTool]:
        return [
            StructuredTool(
                name="x_add_recent_tweets_to_graph",
                description=(
                    "Call XIntegration.search_recent_tweets with the given "
                    "query (and optional X v2 parameters) and map the result "
                    "into the ABI knowledge graph as Tweet, XUser, "
                    "XUserPublicMetrics, TweetPublicMetrics, TweetLanguage, "
                    "Media, ContextAnnotation, TweetURL, SearchQuery, "
                    "SearchResultSet and SearchRecentTweets individuals."
                ),
                func=lambda **kwargs: self.run(
                    XSearchRecentTweetsPipelineParameters(**kwargs)
                ).serialize(format="turtle"),
                args_schema=XSearchRecentTweetsPipelineParameters,
            )
        ]

    def as_api(
        self,
        router: APIRouter,
        route_name: str = "",
        name: str = "",
        description: str = "",
        description_stream: str = "",
        tags: list[str | Enum] | None = None,
    ) -> None:
        if tags is None:
            tags = []
        return None
