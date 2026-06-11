"""Map an X v2 ``Tweet``-shaped dict into RDF triples.

Extracted from :class:`XTweetGraphBuilder` so the per-entity mapping lives
in one focused module; the builder method ``build_tweet`` delegates here.
The sub-entity helpers it relies on (``_build_user``, ``_build_metrics``,
``_build_language``, ``_build_context_annotation``, ``_build_url_entity``)
remain on the builder and are reached through *builder*.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from naas_abi_marketplace.applications.x.ontologies.modules.XOntology import (
    Tweet,
)
from naas_abi_marketplace.applications.x.pipelines.utils._helpers import first, parse_dt
from rdflib import Graph, URIRef

if TYPE_CHECKING:
    from naas_abi_marketplace.applications.x.ontologies.modules.XOntology import (
        ContextAnnotation,
        Media,
        TweetURL,
        XUser,
    )
    from naas_abi_marketplace.applications.x.pipelines.utils._graph_builder import (
        XTweetGraphBuilder,
    )

# Map of X v2 ``referenced_tweets[].type`` to the generated Tweet field that
# carries the corresponding x:referencesTweet sub-property.
_REFERENCE_FIELDS = {
    "replied_to": "replies_to_tweet",
    "quoted": "quotes_tweet",
    "retweeted": "retweets_tweet",
}


def build_tweet(
    builder: "XTweetGraphBuilder",
    record: dict,
    source_set_uri: Optional[str] = None,
) -> Graph:
    """Return the RDF graph for a single tweet record.

    *record* is an X v2 ``Tweet`` dict (``id``, ``text`` required;
    everything else — ``author_id``, ``created_at``, ``public_metrics``,
    ``lang``, ``entities``, ``context_annotations``, ``attachments``,
    ``referenced_tweets``, flags — optional).

    *source_set_uri* is the IRI of the ``SearchResultSet`` (or any
    equivalent "batch of tweets" individual) the tweet belongs to. Pass
    ``None`` for context tweets (``includes.tweets``) that were returned as
    expansions rather than as matches of the search.
    """
    tweet_id = record["id"]
    author_id = record.get("author_id", "")
    tweet_label = f"Tweet {tweet_id}"
    tweet_uri = builder.uri("Tweet", tweet_id)

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
        user, user_graph = builder._build_user(str(author_id))
        tweet.is_authored_by = [URIRef(user._uri)]
        graph += user_graph

    metrics_payload = record.get("public_metrics") or {}
    if metrics_payload:
        metrics, metrics_graph = builder._build_metrics(str(tweet_id), metrics_payload)
        tweet.has_public_metrics = [URIRef(metrics._uri)]
        graph += metrics_graph

    # in_reply_to_user_id → minimal XUser stub + x:inReplyToUser
    reply_user_id = record.get("in_reply_to_user_id")
    if reply_user_id:
        reply_user, reply_user_graph = builder._build_user(str(reply_user_id))
        tweet.in_reply_to_user = [URIRef(reply_user._uri)]
        graph += reply_user_graph

    # entities.mentions → XUser stubs + x:mentionsUser
    entities = record.get("entities") or {}
    mention_uris: list[XUser | URIRef | str] = []
    for mention in entities.get("mentions") or []:
        mention_id = mention.get("id")
        if not mention_id:
            continue
        mentioned, mentioned_graph = builder._build_user(
            str(mention_id), username=mention.get("username")
        )
        mention_uris.append(URIRef(mentioned._uri))
        graph += mentioned_graph
    if mention_uris:
        tweet.mentions_user = mention_uris

    # entities.urls → TweetURL individuals + x:hasUrlEntity
    url_uris: list[TweetURL | URIRef | str] = []
    for url_payload in entities.get("urls") or []:
        pair = builder._build_url_entity(url_payload)
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
        pair = builder._build_context_annotation(annotation_payload)
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
        URIRef(builder.uri("Media", str(media_key)))
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
        existing.append(URIRef(builder.uri("Tweet", str(ref_id))))
        setattr(tweet, field, existing)

    if not builder.label_exists(tweet_label, Tweet._class_uri):
        graph += tweet.rdf()
        builder.mark_existing(Tweet._class_uri, tweet_label)

    lang_pair = builder._build_language(record.get("lang"), tweet)
    if lang_pair is not None:
        _, lang_graph = lang_pair
        graph += lang_graph

    return graph
