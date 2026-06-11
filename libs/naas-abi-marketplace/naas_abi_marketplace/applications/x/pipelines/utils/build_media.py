"""Map an expanded X v2 ``Media`` object (``includes.media[]``) to RDF.

Extracted from :class:`XTweetGraphBuilder` so the per-entity mapping lives
in one focused module; the builder method ``build_media`` delegates here.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from naas_abi_marketplace.applications.x.ontologies.modules.XOntology import (
    Media,
)
from rdflib import Graph

if TYPE_CHECKING:
    from naas_abi_marketplace.applications.x.pipelines.utils._graph_builder import (
        XTweetGraphBuilder,
    )


def build_media(builder: "XTweetGraphBuilder", record: dict) -> tuple[Media, Graph]:
    """Map an expanded X v2 ``Media`` object (``includes.media[]``) to RDF."""
    media_key = str(record["media_key"])
    label = f"X Media {media_key}"
    uri = builder.uri("Media", media_key)
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
    if builder.label_exists(label, Media._class_uri):
        return media, Graph()
    graph = media.rdf()
    builder.mark_existing(Media._class_uri, label)
    return media, graph
