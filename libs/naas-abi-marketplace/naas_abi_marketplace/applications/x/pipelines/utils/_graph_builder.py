"""Shared helper that maps X v2 ``Tweet``-shaped dicts into RDF triples.

:class:`XSearchRecentTweetsPipeline` uses this for every tweet record it maps
— whether the records come straight from the X v2 search API or are replayed
from a persisted JSON envelope in object storage (``file_path`` mode). This
module owns that mapping so the graph shape is identical across both paths.

The public entry point is :class:`XTweetGraphBuilder`: instantiate it once
with the configured triple store + named graph, then call
``build_tweet(record, source_set_uri)`` for each record. The per-entity
mappers live in sibling modules (:mod:`build_tweet`, :mod:`build_user`,
:mod:`build_media`); the matching builder methods delegate to them. The
small private sub-entity helpers (``_build_user`` stub, ``_build_metrics``,
``_build_language``, ``_build_context_annotation``, ``_build_url_entity``)
stay here since they are only reached through ``build_tweet``.
"""

from __future__ import annotations

import hashlib
from typing import Optional

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
)

# Re-exported so existing ``from ...utils._graph_builder import parse_dt`` /
# ``first`` / ``uri_for`` import sites keep working now the helpers live in
# their own leaf module.
from naas_abi_marketplace.applications.x.pipelines.utils._helpers import (
    first,
    parse_dt,
    uri_for,
)
from rdflib import Graph, URIRef
from rdflib.namespace import RDFS

__all__ = ["XTweetGraphBuilder", "first", "parse_dt", "uri_for"]


class XTweetGraphBuilder:
    """Maps X v2 tweet dicts to RDF, dedup'd against an existing named graph.

    Stateless apart from the triple-store handle + graph_name + a small
    in-process cache so the per-tweet label-existence ASK isn't repeated for
    users / languages / metrics we've already emitted in this run.
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
        language individual hundreds of thousands of times and re-asking each
        time is wasteful.
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

    # ----- Per-entity builders (public API; delegate to sibling modules) --------

    def build_user(self, record: dict) -> tuple[XUser, Graph]:
        """Map an expanded X v2 ``User`` object to RDF (see :mod:`build_user`)."""
        from naas_abi_marketplace.applications.x.pipelines.utils.build_user import (
            build_user,
        )

        return build_user(self, record)

    def build_media(self, record: dict) -> tuple[Media, Graph]:
        """Map an expanded X v2 ``Media`` object to RDF (see :mod:`build_media`)."""
        from naas_abi_marketplace.applications.x.pipelines.utils.build_media import (
            build_media,
        )

        return build_media(self, record)

    def build_tweet(self, record: dict, source_set_uri: Optional[str] = None) -> Graph:
        """Map a single X v2 tweet record to RDF (see :mod:`build_tweet`)."""
        from naas_abi_marketplace.applications.x.pipelines.utils.build_tweet import (
            build_tweet,
        )

        return build_tweet(self, record, source_set_uri)

    # ----- Private sub-entity helpers (reached only through build_tweet) --------

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
