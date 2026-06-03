import hashlib
import json as _json
import re
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
from naas_abi_marketplace.applications.x import X_NAMESPACE
from naas_abi_marketplace.applications.x.integrations.XIntegration import (
    XIntegration,
)
from naas_abi_marketplace.applications.x.ontologies.modules.XOntology import (
    SearchInterval,
    SearchQuery,
    SearchRecentTweets,
    SearchResultSet,
    Tweet,
    TweetLanguage,
    TweetPublicMetrics,
    XPlatform,
    XUser,
)
from pydantic import Field
from rdflib import Graph, Namespace, URIRef
from rdflib.namespace import RDFS

X_PLATFORM_URI = f"{X_NAMESPACE}XPlatform/x.com"

# onto2py classifies single-valued xsd:string data properties as object
# properties when their field is typed Union[URIRef, str]. The generated
# rdf() then emits their values as IRIs instead of literals, which breaks
# Turtle serialization for free-text fields like tweet_text. Drop the
# affected names from _object_properties so they round-trip as literals.
for _cls, _data_props in (
    (Tweet, {"tweet_id", "tweet_text"}),
    (XUser, {"author_id"}),
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

    # ----- URI / label helpers --------------------------------------------------

    @staticmethod
    def _uri(class_name: str, stable_id: str) -> str:
        safe = re.sub(r"[^A-Za-z0-9_\-]", "_", stable_id)
        return f"{X_NAMESPACE}{class_name}/{safe}"

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

    def _label_exists(self, label: str, class_uri: str) -> bool:
        """Return True iff an instance of *class_uri* with *label* already exists.

        Run as a SPARQL ASK against the pipeline's named graph. We compare on
        the literal label rather than the IRI so the check is robust to two
        sources picking different URI conventions for the same real-world
        entity.
        """
        escaped = label.replace("\\", "\\\\").replace('"', '\\"')
        sparql = (
            f"ASK {{ GRAPH <{self.__configuration.graph_name}> {{ "
            f"?s a <{class_uri}> ; "
            f'<{RDFS.label}> "{escaped}" . }} }}'
        )
        try:
            return bool(self.__configuration.triple_store.query(sparql).askAnswer)
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                f"XSearchRecentTweetsPipeline: label-existence ASK failed "
                f"({exc}); assuming absent"
            )
            return False

    # ----- Per-entity builders --------------------------------------------------

    def _build_user(self, author_id: str) -> tuple[XUser, Graph]:
        label = f"X User {author_id}"
        uri = self._uri("XUser", author_id)
        user = XUser(_uri=uri, label=label, author_id=author_id)
        graph = Graph() if self._label_exists(label, XUser._class_uri) else user.rdf()
        return user, graph

    def _build_metrics(
        self, tweet_id: str, metrics: dict
    ) -> tuple[TweetPublicMetrics, Graph]:
        label = f"Public metrics of tweet {tweet_id}"
        uri = self._uri("TweetPublicMetrics", f"metrics-{tweet_id}")
        instance = TweetPublicMetrics(
            _uri=uri,
            label=label,
            retweet_count=metrics.get("retweet_count"),
            reply_count=metrics.get("reply_count"),
            like_count=metrics.get("like_count"),
            quote_count=metrics.get("quote_count"),
            bookmark_count=metrics.get("bookmark_count"),
            impression_count=metrics.get("impression_count"),
        )
        graph = (
            Graph()
            if self._label_exists(label, TweetPublicMetrics._class_uri)
            else instance.rdf()
        )
        return instance, graph

    def _build_language(
        self, lang_code: Optional[str], tweet: Tweet
    ) -> Optional[tuple[TweetLanguage, Graph]]:
        if not lang_code:
            return None
        label = f"Tweet language {lang_code}"
        uri = self._uri("TweetLanguage", lang_code)
        instance = TweetLanguage(
            _uri=uri,
            label=label,
            language_code=lang_code,
            inheresIn=[URIRef(tweet._uri)],
        )
        graph = (
            Graph()
            if self._label_exists(label, TweetLanguage._class_uri)
            else instance.rdf()
        )
        return instance, graph

    def _build_tweet(self, record: dict, result_set_uri: str) -> Graph:
        tweet_id = record["id"]
        author_id = record.get("author_id", "")
        tweet_label = f"Tweet {tweet_id}"
        tweet_uri = self._uri("Tweet", tweet_id)

        tweet = Tweet(
            _uri=tweet_uri,
            label=tweet_label,
            tweet_id=tweet_id,
            tweet_text=record.get("text"),
            tweet_created_at=self._parse_dt(record.get("created_at")),
            edit_history_tweet_id=self._first(record.get("edit_history_tweet_ids")),
            is_contained_in_search_result_set=[URIRef(result_set_uri)],
        )

        # Author
        graph = Graph()
        if author_id:
            user, user_graph = self._build_user(author_id)
            tweet.is_authored_by = [URIRef(user._uri)]
            graph += user_graph

        # Public metrics
        metrics_payload = record.get("public_metrics") or {}
        if metrics_payload:
            metrics, metrics_graph = self._build_metrics(tweet_id, metrics_payload)
            tweet.has_public_metrics = [URIRef(metrics._uri)]
            graph += metrics_graph

        # Tweet itself (skip if already in store)
        if not self._label_exists(tweet_label, Tweet._class_uri):
            graph += tweet.rdf()

        # Language quality — inheres in the tweet, so build after tweet has a URI
        lang_pair = self._build_language(record.get("lang"), tweet)
        if lang_pair is not None:
            _, lang_graph = lang_pair
            graph += lang_graph

        return graph

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

        graph = Graph()
        graph.bind("x", Namespace(X_NAMESPACE))

        # Platform (singleton site)
        platform = XPlatform(_uri=X_PLATFORM_URI, label="X Platform")
        if not self._label_exists("X Platform", XPlatform._class_uri):
            graph += platform.rdf()

        # SearchQuery
        query_hash = hashlib.md5(parameters.query.encode()).hexdigest()[:8]
        query_label = f"Search Query: {parameters.query}"
        query = SearchQuery(
            _uri=self._uri("SearchQuery", query_hash),
            label=query_label,
            query_string=parameters.query,
            start_time=self._parse_dt(parameters.options.get("start_time")),
            end_time=self._parse_dt(parameters.options.get("end_time")),
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
        if not self._label_exists(query_label, SearchQuery._class_uri):
            graph += query.rdf()

        # SearchResultSet
        rs_label = f"Search Result Set {result_set_id}"
        rs_uri = self._uri("SearchResultSet", result_set_id)
        result_set = SearchResultSet(
            _uri=rs_uri,
            label=rs_label,
            result_set_id=result_set_id,
            result_count=len(tweets),
        )
        if not self._label_exists(rs_label, SearchResultSet._class_uri):
            graph += result_set.rdf()

        # SearchInterval (one instant — the run time)
        now = datetime.now(timezone.utc)
        interval_label = f"Search Interval {result_set_id}"
        interval = SearchInterval(
            _uri=self._uri("SearchInterval", result_set_id),
            label=interval_label,
        )
        if not self._label_exists(interval_label, SearchInterval._class_uri):
            graph += interval.rdf()

        # SearchRecentTweets process linking it all together
        process_label = f"Search Recent Tweets {result_set_id}"
        process = SearchRecentTweets(
            _uri=self._uri("SearchRecentTweets", result_set_id),
            label=process_label,
            uses_search_query=[URIRef(query._uri)],
            produces_search_result=[URIRef(result_set._uri)],
            has_search_interval=[URIRef(interval._uri)],
            occursIn=[URIRef(platform._uri)],
            created=now,
        )
        if not self._label_exists(process_label, SearchRecentTweets._class_uri):
            graph += process.rdf()

        # Tweets
        for record in tweets:
            graph += self._build_tweet(record, result_set_uri=result_set._uri)

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
    def _parse_dt(value: Any) -> Optional[datetime]:
        if not value:
            return None
        if isinstance(value, datetime):
            return value
        try:
            return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _first(value: Any) -> Optional[str]:
        if isinstance(value, list) and value:
            return str(value[0])
        if isinstance(value, str):
            return value
        return None

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
