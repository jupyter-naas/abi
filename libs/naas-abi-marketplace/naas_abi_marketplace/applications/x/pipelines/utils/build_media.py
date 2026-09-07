"""Map an expanded X v2 ``Media`` object (``includes.media[]``) to RDF.

Extracted from :class:`XTweetGraphBuilder` so the per-entity mapping lives
in one focused module; the builder method ``build_media`` delegates here.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from naas_abi_marketplace.applications.x.ontologies.modules.XOntology import (
    Media,
)
from rdflib import Graph

if TYPE_CHECKING:
    from naas_abi_marketplace.applications.x.pipelines.utils._graph_builder import (
        XTweetGraphBuilder,
    )


def best_media_url(record: dict[str, Any]) -> str | None:
    """Direct asset URL for a media object, including the best MP4 for video/GIF.

    Photos expose ``url``. Videos and animated GIFs do not — their playable
    files live under ``variants``. Picking the highest-bitrate ``video/mp4``
    lets the Users page embed the original format instead of only a preview
    still.
    """
    url = record.get("url")
    if isinstance(url, str) and url.strip():
        return url.strip()
    variants = record.get("variants") or []
    if not isinstance(variants, list):
        return None
    mp4s = [
        v
        for v in variants
        if isinstance(v, dict)
        and v.get("content_type") == "video/mp4"
        and isinstance(v.get("url"), str)
        and v["url"].strip()
    ]
    if not mp4s:
        return None
    best = max(mp4s, key=lambda v: int(v.get("bit_rate") or 0))
    return str(best["url"]).strip()


def build_media(builder: XTweetGraphBuilder, record: dict) -> tuple[Media, Graph]:
    """Map an expanded X v2 ``Media`` object (``includes.media[]``) to RDF."""
    media_key = str(record["media_key"])
    label = f"X Media {media_key}"
    uri = builder.uri("Media", media_key)
    media = Media(
        _uri=uri,
        label=label,
        media_key=media_key,
        media_type=record.get("type"),
        media_url=best_media_url(record),
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
