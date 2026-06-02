import hashlib
import json
import os
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
from pydantic import Field
from rdflib import Graph, Namespace, URIRef
from rdflib.namespace import RDFS

from naas_abi_marketplace.applications.x import X_NAMESPACE
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
        triple_store: Service used to check for already-ingested individuals
            (label-based existence check) and to persist new triples.
        graph_name: Named graph in the triple store where tweets are written.
        datastore_path: Directory holding the JSON files produced by the
            XIntegration.search_recent_tweets cache.
    """

    triple_store: ITripleStoreService
    graph_name: URIRef = URIRef(f"{X_NAMESPACE}graph")
    datastore_path: str = "storage/datastore/x/search_recent_tweets"


class XSearchRecentTweetsPipelineParameters(PipelineParameters):
    result_set_id: Annotated[
        str,
        Field(
            description=(
                "8-character hex digest identifying the cached search result "
                "(matches the JSON filename in the datastore, e.g. '21dcaa8c')."
            ),
            example="21dcaa8c",
        ),
    ]
    query_string: Optional[
        Annotated[
            str,
            Field(
                description=(
                    "The X v2 search query that produced the result set. "
                    "Used to materialise the SearchQuery individual."
                ),
                example="Roland Garros lang:en",
            ),
        ]
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


class XSearchRecentTweetsPipeline(Pipeline):
    """Maps a cached X search_recent_tweets JSON file into the X ontology graph.

    For each tweet in the JSON it creates a ``Tweet`` individual linked to its
    author ``XUser``, ``TweetPublicMetrics``, and ``TweetLanguage``; all tweets
    are linked to a ``SearchResultSet`` produced by a ``SearchRecentTweets``
    process that uses a ``SearchQuery``. URIs are deterministic so re-runs are
    idempotent, and each individual is skipped when one with the same label
    already lives in the configured named graph.
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

    def _label_exists(self, label: str, class_uri: str) -> bool:
        """Return True iff an instance of *class_uri* with *label* already exists.

        Run as a SPARQL ASK against the pipeline's named graph. We compare on
        the literal label rather than the IRI so the check is robust to two
        sources picking different URI conventions for the same real-world
        entity.
        """
        escaped = label.replace("\\", "\\\\").replace('"', '\\"')
        query = (
            f"ASK {{ GRAPH <{self.__configuration.graph_name}> {{ "
            f"?s a <{class_uri}> ; "
            f"<{RDFS.label}> \"{escaped}\" . }} }}"
        )
        try:
            return bool(self.__configuration.triple_store.query(query).askAnswer)
        except Exception as exc:  # noqa: BLE001
            logger.warning(f"XSearchRecentTweetsPipeline: label-existence ASK failed ({exc}); assuming absent")
            return False

    # ----- Per-entity builders --------------------------------------------------

    def _build_user(self, author_id: str) -> tuple[XUser, Graph]:
        label = f"X User {author_id}"
        uri = self._uri("XUser", author_id)
        user = XUser(_uri=uri, label=label, author_id=author_id)
        graph = Graph() if self._label_exists(label, XUser._class_uri) else user.rdf()
        return user, graph

    def _build_metrics(self, tweet_id: str, metrics: dict) -> tuple[TweetPublicMetrics, Graph]:
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

    def _build_language(self, lang_code: Optional[str], tweet: Tweet) -> Optional[tuple[TweetLanguage, Graph]]:
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

    def _build_tweet(
        self,
        record: dict,
        result_set_uri: str,
    ) -> Graph:
        tweet_id = record["id"]
        author_id = record.get("author_id", "")
        tweet_label = f"Tweet {tweet_id}"
        tweet_uri = self._uri("Tweet", tweet_id)

        created_at = self._parse_dt(record.get("created_at"))

        tweet = Tweet(
            _uri=tweet_uri,
            label=tweet_label,
            tweet_id=tweet_id,
            tweet_text=record.get("text"),
            tweet_created_at=created_at,
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
            raise ValueError("Parameters must be of type XSearchRecentTweetsPipelineParameters")

        json_path = os.path.join(
            self.__configuration.datastore_path, f"{parameters.result_set_id}.json"
        )
        logger.info(f"XSearchRecentTweetsPipeline: loading tweets from {json_path}")
        with open(json_path, encoding="utf-8") as f:
            tweets: list[dict] = json.load(f)
        logger.info(f"XSearchRecentTweetsPipeline: read {len(tweets)} tweets from {json_path}")

        graph = Graph()
        graph.bind("x", Namespace(X_NAMESPACE))

        # Platform (singleton site)
        platform = XPlatform(_uri=X_PLATFORM_URI, label="X Platform")
        if not self._label_exists("X Platform", XPlatform._class_uri):
            graph += platform.rdf()

        # SearchQuery
        query_string = parameters.query_string or ""
        query_hash = hashlib.md5(query_string.encode()).hexdigest()[:8] if query_string else parameters.result_set_id
        query_label = (
            f"Search Query: {query_string}" if query_string else f"Search Query {query_hash}"
        )
        query = SearchQuery(
            _uri=self._uri("SearchQuery", query_hash),
            label=query_label,
            query_string=query_string or None,
        )
        if not self._label_exists(query_label, SearchQuery._class_uri):
            graph += query.rdf()

        # SearchResultSet
        rs_label = f"Search Result Set {parameters.result_set_id}"
        rs_uri = self._uri("SearchResultSet", parameters.result_set_id)
        result_set = SearchResultSet(
            _uri=rs_uri,
            label=rs_label,
            result_set_id=parameters.result_set_id,
            result_count=len(tweets),
            datastore_path=json_path,
        )
        if not self._label_exists(rs_label, SearchResultSet._class_uri):
            graph += result_set.rdf()

        # SearchInterval (one instant — the run time)
        now = datetime.now(timezone.utc)
        interval_label = f"Search Interval {parameters.result_set_id}"
        interval = SearchInterval(
            _uri=self._uri("SearchInterval", parameters.result_set_id),
            label=interval_label,
        )
        if not self._label_exists(interval_label, SearchInterval._class_uri):
            graph += interval.rdf()

        # SearchRecentTweets process linking it all together
        process_label = f"Search Recent Tweets {parameters.result_set_id}"
        process = SearchRecentTweets(
            _uri=self._uri("SearchRecentTweets", parameters.result_set_id),
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

        logger.info(f"XSearchRecentTweetsPipeline: produced graph with {len(graph)} triples")

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
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _first(value: Any) -> Optional[str]:
        if isinstance(value, list) and value:
            return str(value[0])
        if isinstance(value, str):
            return value
        return None

    # ----- Framework hooks ------------------------------------------------------

    def as_tools(self) -> list[BaseTool]:
        return [
            StructuredTool(
                name="x_add_recent_tweets_to_graph",
                description=(
                    "Map a cached X search_recent_tweets JSON file into the "
                    "ABI knowledge graph as Tweet, XUser, TweetPublicMetrics, "
                    "TweetLanguage, SearchQuery, SearchResultSet and "
                    "SearchRecentTweets individuals."
                ),
                func=lambda **kwargs: self.run(XSearchRecentTweetsPipelineParameters(**kwargs)).serialize(
                    format="turtle"
                ),
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
