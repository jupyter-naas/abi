"""Map an expanded X v2 ``User`` object (``includes.users[]``) to RDF.

Extracted from :class:`XTweetGraphBuilder` so the per-entity mapping lives
in one focused module; the builder method ``build_user`` delegates here.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from naas_abi_marketplace.applications.x.ontologies.modules.XOntology import (
    XUser,
    XUserPublicMetrics,
)
from naas_abi_marketplace.applications.x.pipelines.utils._helpers import parse_dt
from rdflib import Graph, URIRef

if TYPE_CHECKING:
    from naas_abi_marketplace.applications.x.pipelines.utils._graph_builder import (
        XTweetGraphBuilder,
    )


def build_user(builder: "XTweetGraphBuilder", record: dict) -> tuple[XUser, Graph]:
    """Map an expanded X v2 ``User`` object (``includes.users[]``) to RDF.

    Emits a rich ``XUser`` individual (profile fields) plus its
    ``XUserPublicMetrics``. Call this *before* ``build_tweet`` so the rich
    individual wins the label-dedup race against the minimal author stub the
    tweet builder would otherwise emit.
    """
    user_id = str(record["id"])
    label = f"X User {user_id}"
    uri = builder.uri("XUser", user_id)

    graph = Graph()
    metrics_uri: Optional[str] = None
    metrics_payload = record.get("public_metrics") or {}
    if metrics_payload:
        metrics_label = f"Public metrics of X user {user_id}"
        metrics_uri = builder.uri("XUserPublicMetrics", f"metrics-{user_id}")
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
        if not builder.label_exists(metrics_label, XUserPublicMetrics._class_uri):
            graph += metrics.rdf()
            builder.mark_existing(XUserPublicMetrics._class_uri, metrics_label)

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
    if not builder.label_exists(label, XUser._class_uri):
        graph += user.rdf()
        builder.mark_existing(XUser._class_uri, label)
    return user, graph
