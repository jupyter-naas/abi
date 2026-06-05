"""Shared helpers that map an X v2 ``Tweet``-shaped dict into RDF triples.

Both :class:`XSearchRecentTweetsPipeline` (which fetches tweets from the
X v2 search API) and :class:`XFileIngestionPipeline` (which streams tweets
from a JSON file in object storage) emit the same Tweet / XUser /
TweetPublicMetrics / TweetLanguage individuals from each record. This
module owns that mapping so the two pipelines stay byte-for-byte
identical in what they put in the graph.

The public entry point is :class:`XTweetGraphBuilder`: instantiate it
once with the configured triple store + named graph, then call
``build_tweet(record, source_set_uri)`` for each record. ``record`` must
be a v2-shaped dict with at least ``id`` and ``text`` (everything else
is optional and degrades gracefully).
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Optional

from naas_abi_core import logger
from naas_abi_core.services.triple_store.TripleStorePorts import (
    ITripleStoreService,
)
from naas_abi_marketplace.applications.x import X_NAMESPACE
from naas_abi_marketplace.applications.x.ontologies.modules.XOntology import (
    Tweet,
    TweetLanguage,
    TweetPublicMetrics,
    XUser,
)
from rdflib import Graph, URIRef
from rdflib.namespace import RDFS

# Same onto2py round-trip fix as the parent pipeline applies — keep it in
# the shared module so callers don't have to remember to monkey-patch.
for _cls, _data_props in (
    (Tweet, {"tweet_id", "tweet_text"}),
    (XUser, {"author_id"}),
):
    _cls._object_properties = _cls._object_properties - _data_props


class XTweetGraphBuilder:
    """Maps X v2 tweet dicts to RDF, dedup'd against an existing named graph.

    Stateless apart from the triple-store handle + graph_name + a small
    in-process cache so the per-tweet label-existence ASK isn't repeated
    for users / languages / metrics we've already emitted in this run.
    """

    def __init__(
        self,
        triple_store: ITripleStoreService,
        graph_name: URIRef | str,
    ) -> None:
        self._triple_store = triple_store
        self._graph_name = str(graph_name)
        # (class_uri, label) -> exists  — populated lazily; cleared on
        # construction so two consecutive builders against the same graph
        # don't carry stale state from each other.
        self._exists_cache: dict[tuple[str, str], bool] = {}

    # ----- URI / label helpers --------------------------------------------------

    @staticmethod
    def uri(class_name: str, stable_id: str) -> str:
        """Deterministic IRI for an instance of *class_name* keyed on *stable_id*."""
        safe = re.sub(r"[^A-Za-z0-9_\-]", "_", stable_id)
        return f"{X_NAMESPACE}{class_name}/{safe}"

    def label_exists(self, label: str, class_uri: str) -> bool:
        """Return True iff an instance of *class_uri* with *label* already exists.

        The check is a SPARQL ASK against the configured named graph. We
        memoize the result per (class_uri, label) for the lifetime of this
        builder — a single file-ingestion run can reference the same
        language individual hundreds of thousands of times and re-asking
        each time is wasteful.
        """
        key = (class_uri, label)
        cached = self._exists_cache.get(key)
        if cached is not None:
            return cached

        escaped = label.replace("\\", "\\\\").replace('"', '\\"')
        sparql = (
            f"ASK {{ GRAPH <{self._graph_name}> {{ "
            f"?s a <{class_uri}> ; "
            f'<{RDFS.label}> "{escaped}" . }} }}'
        )
        try:
            exists = bool(self._triple_store.query(sparql).askAnswer)
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                f"XTweetGraphBuilder: label-existence ASK failed "
                f"({exc}); assuming absent"
            )
            exists = False
        self._exists_cache[key] = exists
        return exists

    def mark_existing(self, class_uri: str, label: str) -> None:
        """Force-record that (class, label) is now in the graph.

        Used after we emit a new individual within this run so subsequent
        records in the same batch don't re-emit identical triples.
        """
        self._exists_cache[(class_uri, label)] = True

    # ----- Per-entity builders --------------------------------------------------

    def _build_user(self, author_id: str) -> tuple[XUser, Graph]:
        label = f"X User {author_id}"
        uri = self.uri("XUser", author_id)
        user = XUser(_uri=uri, label=label, author_id=author_id)
        if self.label_exists(label, XUser._class_uri):
            return user, Graph()
        graph = user.rdf()
        self.mark_existing(XUser._class_uri, label)
        return user, graph

    def _build_metrics(
        self, tweet_id: str, metrics: dict
    ) -> tuple[TweetPublicMetrics, Graph]:
        label = f"Public metrics of tweet {tweet_id}"
        uri = self.uri("TweetPublicMetrics", f"metrics-{tweet_id}")
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
        if self.label_exists(label, TweetPublicMetrics._class_uri):
            return instance, Graph()
        graph = instance.rdf()
        self.mark_existing(TweetPublicMetrics._class_uri, label)
        return instance, graph

    def _build_language(
        self, lang_code: Optional[str], tweet: Tweet
    ) -> Optional[tuple[TweetLanguage, Graph]]:
        if not lang_code:
            return None
        label = f"Tweet language {lang_code}"
        uri = self.uri("TweetLanguage", lang_code)
        instance = TweetLanguage(
            _uri=uri,
            label=label,
            language_code=lang_code,
            inheresIn=[URIRef(tweet._uri)],
        )
        if self.label_exists(label, TweetLanguage._class_uri):
            return instance, Graph()
        graph = instance.rdf()
        self.mark_existing(TweetLanguage._class_uri, label)
        return instance, graph

    def build_tweet(self, record: dict, source_set_uri: str) -> Graph:
        """Return the RDF graph for a single tweet record.

        *record* is an X v2 ``Tweet`` dict (``id``, ``text`` required;
        ``author_id``, ``created_at``, ``public_metrics``, ``lang`` and
        ``edit_history_tweet_ids`` optional).

        *source_set_uri* is the IRI of the ``SearchResultSet`` (or any
        equivalent "batch of tweets" individual) the tweet belongs to —
        the file-ingestion pipeline passes the per-file result-set IRI so
        the BFO process metadata stays attached. The Tweet links back via
        ``x:isContainedInSearchResultSet``.
        """
        tweet_id = record["id"]
        author_id = record.get("author_id", "")
        tweet_label = f"Tweet {tweet_id}"
        tweet_uri = self.uri("Tweet", tweet_id)

        tweet = Tweet(
            _uri=tweet_uri,
            label=tweet_label,
            tweet_id=tweet_id,
            tweet_text=record.get("text"),
            tweet_created_at=parse_dt(record.get("created_at")),
            edit_history_tweet_id=first(record.get("edit_history_tweet_ids")),
            is_contained_in_search_result_set=[URIRef(source_set_uri)],
        )

        graph = Graph()
        if author_id:
            user, user_graph = self._build_user(str(author_id))
            tweet.is_authored_by = [URIRef(user._uri)]
            graph += user_graph

        metrics_payload = record.get("public_metrics") or {}
        if metrics_payload:
            metrics, metrics_graph = self._build_metrics(
                str(tweet_id), metrics_payload
            )
            tweet.has_public_metrics = [URIRef(metrics._uri)]
            graph += metrics_graph

        if not self.label_exists(tweet_label, Tweet._class_uri):
            graph += tweet.rdf()
            self.mark_existing(Tweet._class_uri, tweet_label)

        lang_pair = self._build_language(record.get("lang"), tweet)
        if lang_pair is not None:
            _, lang_graph = lang_pair
            graph += lang_graph

        return graph


# ----- Module-level utilities (used by both pipelines and tests) -------------


def parse_dt(value: Any) -> Optional[datetime]:
    """Parse an X v2 ISO-8601 timestamp, tolerating the trailing ``Z`` form."""
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None


def first(value: Any) -> Optional[str]:
    """Return the first item of a list, the string itself, or None."""
    if isinstance(value, list) and value:
        return str(value[0])
    if isinstance(value, str):
        return value
    return None
