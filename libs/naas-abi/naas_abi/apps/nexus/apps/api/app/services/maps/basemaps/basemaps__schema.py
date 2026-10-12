"""Workspace basemaps: the backgrounds offered by the Maps map-type picker.

A basemap is data, not code: a display name, a picker column, an order, a
renderer config the web client knows how to draw, and a preview image kept as
bytes. Nexus seeds the generic ones (street, countries, satellite, topo);
deployments seed their own through ``services/maps/seeds.py``.
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from typing import Any

BASEMAP_ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]{0,47}$")
COLOR_PATTERN = re.compile(r"^#[0-9a-fA-F]{6}$")
MAX_TITLE_LENGTH = 80
MAX_ATTRIBUTION_LENGTH = 400
MAX_GEOJSON_BYTES = 5_000_000
MAX_PREVIEW_BYTES = 512_000

# Picker columns, left to right.
CATEGORIES = ("standard", "organization", "custom")

RENDERER_TILE = "tile"
# Natural Earth country polygons, theme-aware or with a fixed palette.
RENDERER_COUNTRIES = "countries"
# Polygons uploaded with the basemap (regions, footprints).
RENDERER_GEOJSON = "geojson"
RENDERER_KINDS = (RENDERER_TILE, RENDERER_COUNTRIES, RENDERER_GEOJSON)

PREVIEW_CONTENT_TYPES = frozenset({"image/png", "image/jpeg", "image/webp", "image/svg+xml"})
PALETTE_KEYS = ("fill", "stroke", "background")


@dataclass(frozen=True)
class MapsBasemap:
    id: str
    title: str
    renderer: dict[str, Any]
    category: str = "custom"
    order: int = 100
    # Seeded by Nexus or the deployment: renamable, hideable, never deleted.
    system: bool = False
    preview_content_type: str | None = None
    # Bumped on every preview upload; clients add it to the preview URL.
    preview_version: int = 0
    # Set on basemaps another workspace shares with this one (read-only here).
    shared_from: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_json(self) -> str:
        data = self.to_dict()
        for key in ("preview_content_type", "preview_version", "shared_from"):
            data.pop(key)
        return json.dumps(data)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> MapsBasemap:
        renderer = data.get("renderer")
        return cls(
            id=str(data["id"]),
            title=str(data.get("title", "")),
            renderer=dict(renderer) if isinstance(renderer, dict) else {},
            category=str(data.get("category", "custom") or "custom"),
            order=int(data.get("order", 100)),
            system=bool(data.get("system", False)),
            preview_content_type=data.get("preview_content_type") or None,
            preview_version=int(data.get("preview_version", 0) or 0),
            shared_from=str(data.get("shared_from", "") or ""),
        )


@dataclass(frozen=True)
class MapsBasemapPreview:
    content_type: str
    content: bytes


@dataclass(frozen=True)
class MapsBasemapList:
    basemaps: list[MapsBasemap]
    hidden: set[str] = field(default_factory=set)


class MapsBasemapValidationError(ValueError):
    def __init__(self, errors: list[str]):
        super().__init__("; ".join(errors))
        self.errors = errors


class MapsBasemapNotFoundError(LookupError):
    pass


class MapsBasemapPolicyError(PermissionError):
    """Refused by policy (e.g. deleting a seeded basemap)."""


def _is_tile_template(value: Any) -> bool:
    return (
        isinstance(value, str)
        and value.startswith("https://")
        and all(token in value for token in ("{z}", "{x}", "{y}"))
        and len(value) <= 500
        and not any(ch.isspace() for ch in value)
    )


def _validate_palette(palette: Any, errors: list[str]) -> None:
    if palette is None:
        return
    if not isinstance(palette, dict):
        errors.append("renderer.palette must be an object")
        return
    for key, value in palette.items():
        if key not in PALETTE_KEYS:
            errors.append(f"renderer.palette.{key} is not supported")
        elif not isinstance(value, str) or not COLOR_PATTERN.match(value):
            errors.append(f"renderer.palette.{key} must be a #rrggbb hex value")


def validate_renderer(renderer: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    kind = renderer.get("kind")
    if kind not in RENDERER_KINDS:
        return ["renderer.kind must be one of " + ", ".join(RENDERER_KINDS)]
    if kind == RENDERER_TILE:
        if not _is_tile_template(renderer.get("url")):
            errors.append("renderer.url must be an https:// tile template with {z} {x} {y}")
        dark = renderer.get("dark_url")
        if dark is not None and not _is_tile_template(dark):
            errors.append("renderer.dark_url must be an https:// tile template with {z} {x} {y}")
        subdomains = renderer.get("subdomains")
        if subdomains is not None and (
            not isinstance(subdomains, list)
            or not all(isinstance(s, str) and re.fullmatch(r"[a-z0-9]{1,8}", s) for s in subdomains)
        ):
            errors.append("renderer.subdomains must be a list of short names")
        attribution = renderer.get("attribution", "")
        if not isinstance(attribution, str) or len(attribution) > MAX_ATTRIBUTION_LENGTH:
            errors.append(f"renderer.attribution must be text (max {MAX_ATTRIBUTION_LENGTH})")
        max_zoom = renderer.get("max_zoom", 19)
        if not isinstance(max_zoom, int) or not 1 <= max_zoom <= 22:
            errors.append("renderer.max_zoom must be between 1 and 22")
    elif kind == RENDERER_COUNTRIES:
        _validate_palette(renderer.get("palette"), errors)
        width = renderer.get("stroke_width")
        if width is not None and (not isinstance(width, int | float) or not 0 <= width <= 5):
            errors.append("renderer.stroke_width must be between 0 and 5")
    else:
        _validate_palette(renderer.get("palette"), errors)
        collection = renderer.get("feature_collection")
        if (
            not isinstance(collection, dict)
            or collection.get("type") != "FeatureCollection"
            or not isinstance(collection.get("features"), list)
        ):
            errors.append("renderer.feature_collection must be a GeoJSON FeatureCollection")
        elif len(json.dumps(collection)) > MAX_GEOJSON_BYTES:
            errors.append(
                f"renderer.feature_collection is too large (max {MAX_GEOJSON_BYTES} bytes)"
            )
    return errors


def validate_basemap(basemap: MapsBasemap) -> list[str]:
    errors: list[str] = []
    if not BASEMAP_ID_PATTERN.match(basemap.id):
        errors.append("id must be lowercase letters, digits and dashes (max 48)")
    title = basemap.title.strip()
    if not title:
        errors.append("title is required")
    elif len(title) > MAX_TITLE_LENGTH:
        errors.append(f"title is too long (max {MAX_TITLE_LENGTH})")
    if basemap.category not in CATEGORIES:
        errors.append("category must be one of " + ", ".join(CATEGORIES))
    errors.extend(validate_renderer(basemap.renderer))
    return errors


def sniff_preview_type(content: bytes) -> str | None:
    """The image type the bytes really are; the declared type must match."""
    if content.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if content.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if content[:4] == b"RIFF" and content[8:12] == b"WEBP":
        return "image/webp"
    head = content[:512].lstrip().lower()
    if head.startswith(b"<svg") or (head.startswith(b"<?xml") and b"<svg" in head):
        return "image/svg+xml"
    return None


def validate_preview(content_type: str, content: bytes) -> list[str]:
    declared = content_type.split(";", 1)[0].strip().lower()
    if declared not in PREVIEW_CONTENT_TYPES:
        return ["preview must be PNG, JPEG, WebP or SVG"]
    if not content:
        return ["preview is empty"]
    if len(content) > MAX_PREVIEW_BYTES:
        return [f"preview is too large (max {MAX_PREVIEW_BYTES // 1000} KB)"]
    if sniff_preview_type(content) != declared:
        return [f"preview content is not {declared}"]
    return []
