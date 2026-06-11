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
is optional and degrades gracefully). ``build_user`` / ``build_media``
map the expanded objects returned under ``includes.users`` /
``includes.media`` so the rich profile and media metadata land in the
graph alongside the tweets that reference them.
"""

from __future__ import annotations

import hashlib
import re
from datetime import datetime
from typing import Any, Optional

from naas_abi_core import logger
from naas_abi_core.services.triple_store.TripleStorePorts import (
    ITripleStoreService,
)
from naas_abi_marketplace.applications.x import ABIModule
from naas_abi_marketplace.applications.x.ontologies.modules.XOntology import (
    ContextAnnotation,
    Media,
    Tweet,
    TweetLanguage,
    TweetPublicMetrics,
    TweetURL,
    XUser,
    XUserPublicMetrics,
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

# Map of X v2 ``referenced_tweets[].type`` to the generated Tweet field that
# carries the corresponding x:referencesTweet sub-property.
_REFERENCE_FIELDS = {
    "replied_to": "replies_to_tweet",
    "quoted": "quotes_tweet",
    "retweeted": "retweets_tweet",
}


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
        ontology_namespace: str | None = None,
    ) -> None:
        self._triple_store = triple_store
        self._graph_name = str(graph_name)
        self._ontology_namespace = (
            ontology_namespace
            or ABIModule.get_instance().configuration.ontology_namespace
        )
        # (class_uri, label) -> exists  — populated lazily; cleared on
        # construction so two consecutive builders against the same graph
        # don't carry stale state from each other.
        self._exists_cache: dict[tuple[str, str], bool] = {}

    # ----- URI / label helpers --------------------------------------------------

    def uri(self, class_name: str, stable_id: str) -> str:
        """Deterministic IRI for an instance of *class_name* keyed on *stable_id*."""
        return uri_for(self._ontology_namespace, class_name, stable_id)

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

    def build_user(self, record: dict) -> tuple[XUser, Graph]:
        """Map an expanded X v2 ``User`` object (``includes.users[]``) to RDF.

        Emits a rich ``XUser`` individual (profile fields) plus its
        ``XUserPublicMetrics``. Call this *before* ``build_tweet`` so the
        rich individual wins the label-dedup race against the minimal
        author stub the tweet builder would otherwise emit.
        """
        user_id = str(record["id"])
        label = f"X User {user_id}"
        uri = self.uri("XUser", user_id)

        graph = Graph()
        metrics_uri: Optional[str] = None
        metrics_payload = record.get("public_metrics") or {}
        if metrics_payload:
            metrics_label = f"Public metrics of X user {user_id}"
            metrics_uri = self.uri("XUserPublicMetrics", f"metrics-{user_id}")
            metrics = XUserPublicMetrics(
                _uri=metrics_uri,
                label=metrics_label,
                followers_count=metrics_payload.get("followers_count"),
                following_count=metrics_payload.get("following_count"),
                user_tweet_count=metrics_payload.get("tweet_count"),
                listed_count=metrics_payload.get("listed_count"),
                user_like_count=metrics_payload.get("like_count"),
                user_media_count=metrics_payload.get("media_count"),
            )
            if not self.label_exists(metrics_label, XUserPublicMetrics._class_uri):
                graph += metrics.rdf()
                self.mark_existing(XUserPublicMetrics._class_uri, metrics_label)

        user = XUser(
            _uri=uri,
            label=label,
            author_id=user_id,
            username=record.get("username"),
            user_display_name=record.get("name"),
            user_description=record.get("description") or None,
            user_location=record.get("location"),
            user_url=record.get("url") or None,
            user_created_at=parse_dt(record.get("created_at")),
            verified=record.get("verified"),
            verified_type=record.get("verified_type"),
            protected=record.get("protected"),
            parody=record.get("parody"),
            is_identity_verified=record.get("is_identity_verified"),
            subscription_type=record.get("subscription_type"),
            profile_image_url=record.get("profile_image_url"),
            profile_banner_url=record.get("profile_banner_url"),
            pinned_tweet_id=record.get("pinned_tweet_id"),
            most_recent_tweet_id=record.get("most_recent_tweet_id"),
            has_user_public_metrics=([URIRef(metrics_uri)] if metrics_uri else None),
        )
        if not self.label_exists(label, XUser._class_uri):
            graph += user.rdf()
            self.mark_existing(XUser._class_uri, label)
        return user, graph

    def build_media(self, record: dict) -> tuple[Media, Graph]:
        """Map an expanded X v2 ``Media`` object (``includes.media[]``) to RDF."""
        media_key = str(record["media_key"])
        label = f"X Media {media_key}"
        uri = self.uri("Media", media_key)
        media = Media(
            _uri=uri,
            label=label,
            media_key=media_key,
            media_type=record.get("type"),
            media_url=record.get("url"),
            preview_image_url=record.get("preview_image_url"),
            media_width=record.get("width"),
            media_height=record.get("height"),
            duration_ms=record.get("duration_ms"),
        )
        if self.label_exists(label, Media._class_uri):
            return media, Graph()
        graph = media.rdf()
        self.mark_existing(Media._class_uri, label)
        return media, graph

    def _build_user(
        self, author_id: str, username: Optional[str] = None
    ) -> tuple[XUser, Graph]:
        """Minimal XUser stub when only the id (and maybe handle) is known."""
        label = f"X User {author_id}"
        uri = self.uri("XUser", author_id)
        user = XUser(_uri=uri, label=label, author_id=author_id, username=username)
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

    def _build_context_annotation(
        self, payload: dict
    ) -> Optional[tuple[ContextAnnotation, Graph]]:
        """Map one ``context_annotations[]`` domain/entity pair to RDF."""
        domain = payload.get("domain") or {}
        entity = payload.get("entity") or {}
        domain_id = domain.get("id")
        entity_id = entity.get("id")
        if not domain_id or not entity_id:
            return None
        label = (
            f"Context Annotation {domain_id}:{entity_id} "
            f"{entity.get('name', '')}".rstrip()
        )
        uri = self.uri("ContextAnnotation", f"{domain_id}-{entity_id}")
        instance = ContextAnnotation(
            _uri=uri,
            label=label,
            context_domain_id=str(domain_id),
            context_domain_name=domain.get("name"),
            context_domain_description=domain.get("description"),
            context_entity_id=str(entity_id),
            context_entity_name=entity.get("name"),
            context_entity_description=entity.get("description"),
        )
        if self.label_exists(label, ContextAnnotation._class_uri):
            return instance, Graph()
        graph = instance.rdf()
        self.mark_existing(ContextAnnotation._class_uri, label)
        return instance, graph

    def _build_url_entity(self, payload: dict) -> Optional[tuple[TweetURL, Graph]]:
        """Map one ``entities.urls[]`` record to RDF, keyed on the expanded URL."""
        target = payload.get("expanded_url") or payload.get("url")
        if not target:
            return None
        url_hash = hashlib.md5(target.encode()).hexdigest()[:12]
        label = f"Tweet URL {target}"
        uri = self.uri("TweetURL", url_hash)
        instance = TweetURL(
            _uri=uri,
            label=label,
            url=payload.get("url"),
            expanded_url=payload.get("expanded_url"),
            display_url=payload.get("display_url"),
            unwound_url=payload.get("unwound_url"),
            url_title=payload.get("title"),
            url_description=payload.get("description"),
        )
        if self.label_exists(label, TweetURL._class_uri):
            return instance, Graph()
        graph = instance.rdf()
        self.mark_existing(TweetURL._class_uri, label)
        return instance, graph

    def build_tweet(self, record: dict, source_set_uri: Optional[str] = None) -> Graph:
        """Return the RDF graph for a single tweet record.

        *record* is an X v2 ``Tweet`` dict (``id``, ``text`` required;
        everything else — ``author_id``, ``created_at``, ``public_metrics``,
        ``lang``, ``entities``, ``context_annotations``, ``attachments``,
        ``referenced_tweets``, flags — optional).

        *source_set_uri* is the IRI of the ``SearchResultSet`` (or any
        equivalent "batch of tweets" individual) the tweet belongs to.
        Pass ``None`` for context tweets (``includes.tweets``) that were
        returned as expansions rather than as matches of the search.
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
            conversation_id=record.get("conversation_id"),
            reply_settings=record.get("reply_settings"),
            possibly_sensitive=record.get("possibly_sensitive"),
            paid_partnership=record.get("paid_partnership"),
            card_uri=record.get("card_uri"),
            is_contained_in_search_result_set=(
                [URIRef(source_set_uri)] if source_set_uri else None
            ),
        )

        graph = Graph()
        if author_id:
            user, user_graph = self._build_user(str(author_id))
            tweet.is_authored_by = [URIRef(user._uri)]
            graph += user_graph

        metrics_payload = record.get("public_metrics") or {}
        if metrics_payload:
            metrics, metrics_graph = self._build_metrics(str(tweet_id), metrics_payload)
            tweet.has_public_metrics = [URIRef(metrics._uri)]
            graph += metrics_graph

        # in_reply_to_user_id → minimal XUser stub + x:inReplyToUser
        reply_user_id = record.get("in_reply_to_user_id")
        if reply_user_id:
            reply_user, reply_user_graph = self._build_user(str(reply_user_id))
            tweet.in_reply_to_user = [URIRef(reply_user._uri)]
            graph += reply_user_graph

        # entities.mentions → XUser stubs + x:mentionsUser
        entities = record.get("entities") or {}
        mention_uris: list[XUser | URIRef | str] = []
        for mention in entities.get("mentions") or []:
            mention_id = mention.get("id")
            if not mention_id:
                continue
            mentioned, mentioned_graph = self._build_user(
                str(mention_id), username=mention.get("username")
            )
            mention_uris.append(URIRef(mentioned._uri))
            graph += mentioned_graph
        if mention_uris:
            tweet.mentions_user = mention_uris

        # entities.urls → TweetURL individuals + x:hasUrlEntity
        url_uris: list[TweetURL | URIRef | str] = []
        for url_payload in entities.get("urls") or []:
            pair = self._build_url_entity(url_payload)
            if pair is None:
                continue
            url_entity, url_graph = pair
            url_uris.append(URIRef(url_entity._uri))
            graph += url_graph
        if url_uris:
            tweet.has_url_entity = url_uris

        # context_annotations → ContextAnnotation individuals (shared across tweets)
        annotation_uris: list[ContextAnnotation | URIRef | str] = []
        seen_annotations: set[str] = set()
        for annotation_payload in record.get("context_annotations") or []:
            pair = self._build_context_annotation(annotation_payload)
            if pair is None:
                continue
            annotation, annotation_graph = pair
            if annotation._uri in seen_annotations:
                continue
            seen_annotations.add(annotation._uri)
            annotation_uris.append(URIRef(annotation._uri))
            graph += annotation_graph
        if annotation_uris:
            tweet.has_context_annotation = annotation_uris

        # attachments.media_keys → x:hasAttachedMedia (Media individuals are
        # built by the pipeline from includes.media before tweets are mapped).
        attachments = record.get("attachments") or {}
        media_uris: list[Media | URIRef | str] = [
            URIRef(self.uri("Media", str(media_key)))
            for media_key in attachments.get("media_keys") or []
        ]
        if media_uris:
            tweet.has_attached_media = media_uris

        # referenced_tweets → x:repliesToTweet / x:quotesTweet / x:retweetsTweet
        for reference in record.get("referenced_tweets") or []:
            field = _REFERENCE_FIELDS.get(reference.get("type", ""))
            ref_id = reference.get("id")
            if not field or not ref_id:
                continue
            existing = getattr(tweet, field) or []
            existing.append(URIRef(self.uri("Tweet", str(ref_id))))
            setattr(tweet, field, existing)

        if not self.label_exists(tweet_label, Tweet._class_uri):
            graph += tweet.rdf()
            self.mark_existing(Tweet._class_uri, tweet_label)

        lang_pair = self._build_language(record.get("lang"), tweet)
        if lang_pair is not None:
            _, lang_graph = lang_pair
            graph += lang_graph

        return graph


def uri_for(namespace: str, class_name: str, stable_id: str) -> str:
    """Deterministic IRI under *namespace* for *class_name* keyed on *stable_id*."""
    safe = re.sub(r"[^A-Za-z0-9_\-]", "_", stable_id)
    return f"{namespace}{class_name}/{safe}"


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
