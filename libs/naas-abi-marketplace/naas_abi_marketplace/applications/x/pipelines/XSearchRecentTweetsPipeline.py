import hashlib
import json as _json
from dataclasses import dataclass
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
from naas_abi_core.services.triple_store.TripleStorePorts import ITripleStoreService
from naas_abi_core.utils.Expose import APIRouter
from naas_abi_marketplace.applications.x import ABIModule
from naas_abi_marketplace.applications.x.integrations.XIntegration import (
    XIntegration,
)
from naas_abi_marketplace.applications.x.ontologies.modules.XOntology import (
    SearchInterval,
    SearchQuery,
    SearchRecentTweets,
    SearchResultSet,
    XPlatform,
)
from naas_abi_marketplace.applications.x.pipelines._graph_builder import (
    XTweetGraphBuilder,
    parse_dt,
)
from pydantic import Field
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
        graph_name: Named graph in the triple store where tweets are written.
    """

    x_integration: XIntegration
    triple_store: ITripleStoreService
    graph_name: URIRef


class XSearchRecentTweetsPipelineParameters(PipelineParameters):
    query: Annotated[
        str,
        Field(
            description=(
                "X v2 search query (1-4096 chars) — see "
                "https://developer.twitter.com/en/docs/twitter-api/tweets/search/integrate/build-a-query"
            ),
            example="(from:TwitterDev OR from:TwitterAPI) has:media -is:retweet",
        ),
    ]
    options: Annotated[
        dict,
        Field(
            default_factory=dict,
            description=(
                "Optional keyword arguments forwarded to "
                "XIntegration.search_recent_tweets — any subset of: "
                "start_time, end_time, since_id, until_id, max_results, "
                "sort_order, tweet_fields, expansions, media_fields, "
                "poll_fields, user_fields, place_fields, max_pages."
            ),
            example={
                "start_time": "2026-05-26T00:00:00Z",
                "end_time": "2026-06-02T00:00:00Z",
                "max_results": 100,
                "sort_order": "recency",
                "max_pages": 1,
            },
        ),
    ]
    persist: Annotated[
        bool,
        Field(
            description=(
                "Whether to insert the generated graph into the configured "
                "triple store. Set False to only return the graph."
            ),
        ),
    ] = True


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

    def __init__(self, configuration: XSearchRecentTweetsPipelineConfiguration):
        super().__init__(configuration)
        self.__configuration = configuration
        self._namespace = ABIModule.get_instance().configuration.ontology_namespace
        self.namespace = Namespace(self._namespace)

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

        # Forward only recognised keys so an unexpected key fails fast at the
        # boundary rather than deep inside the integration.
        unknown = set(parameters.options) - _SEARCH_OPTION_KEYS
        if unknown:
            raise ValueError(
                f"Unknown options for search_recent_tweets: {sorted(unknown)}. "
                f"Accepted keys: {sorted(_SEARCH_OPTION_KEYS)}"
            )

        logger.info(
            f"XSearchRecentTweetsPipeline: calling search_recent_tweets("
            f"query={parameters.query!r}, options={parameters.options})"
        )
        tweets: list[dict] = self.__configuration.x_integration.search_recent_tweets(
            parameters.query, **parameters.options
        )
        logger.info(f"XSearchRecentTweetsPipeline: fetched {len(tweets)} tweets")

        # Deterministic id for the *result set* of this request — used as the
        # stable URI fragment for the SearchResultSet / SearchInterval /
        # SearchRecentTweets process individuals.
        result_set_id = self._params_hash(parameters.query, parameters.options)

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
        query_hash = hashlib.md5(parameters.query.encode()).hexdigest()[:8]
        query_label = f"Search Query: {parameters.query}"
        query = SearchQuery(
            _uri=builder.uri("SearchQuery", query_hash),
            label=query_label,
            query_string=parameters.query,
            start_time=parse_dt(parameters.options.get("start_time")),
            end_time=parse_dt(parameters.options.get("end_time")),
            since_id=parameters.options.get("since_id"),
            until_id=parameters.options.get("until_id"),
            max_results=parameters.options.get("max_results"),
            sort_order=parameters.options.get("sort_order"),
            max_pages=parameters.options.get("max_pages"),
            tweet_fields=self._join(parameters.options.get("tweet_fields")),
            expansions=self._join(parameters.options.get("expansions")),
            media_fields=self._join(parameters.options.get("media_fields")),
            poll_fields=self._join(parameters.options.get("poll_fields")),
            user_fields=self._join(parameters.options.get("user_fields")),
            place_fields=self._join(parameters.options.get("place_fields")),
        )
        if not builder.label_exists(query_label, SearchQuery._class_uri):
            graph += query.rdf()
            builder.mark_existing(SearchQuery._class_uri, query_label)

        # SearchResultSet
        rs_label = f"Search Result Set {result_set_id}"
        rs_uri = builder.uri("SearchResultSet", result_set_id)
        result_set = SearchResultSet(
            _uri=rs_uri,
            label=rs_label,
            result_set_id=result_set_id,
            result_count=len(tweets),
        )
        if not builder.label_exists(rs_label, SearchResultSet._class_uri):
            graph += result_set.rdf()
            builder.mark_existing(SearchResultSet._class_uri, rs_label)

        # SearchInterval (one instant — the run time)
        now = datetime.now(timezone.utc)
        interval_label = f"Search Interval {result_set_id}"
        interval = SearchInterval(
            _uri=builder.uri("SearchInterval", result_set_id),
            label=interval_label,
        )
        if not builder.label_exists(interval_label, SearchInterval._class_uri):
            graph += interval.rdf()
            builder.mark_existing(SearchInterval._class_uri, interval_label)

        # SearchRecentTweets process linking it all together
        process_label = f"Search Recent Tweets {result_set_id}"
        process = SearchRecentTweets(
            _uri=builder.uri("SearchRecentTweets", result_set_id),
            label=process_label,
            uses_search_query=[URIRef(query._uri)],
            produces_search_result=[URIRef(result_set._uri)],
            has_search_interval=[URIRef(interval._uri)],
            occursIn=[URIRef(platform._uri)],
            created=now,
        )
        if not builder.label_exists(process_label, SearchRecentTweets._class_uri):
            graph += process.rdf()
            builder.mark_existing(SearchRecentTweets._class_uri, process_label)

        # Tweets — delegate per-tweet mapping to the shared builder so file
        # ingestion gets the identical graph shape.
        for record in tweets:
            graph += builder.build_tweet(record, source_set_uri=result_set._uri)

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
                    "TweetPublicMetrics, TweetLanguage, SearchQuery, "
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
