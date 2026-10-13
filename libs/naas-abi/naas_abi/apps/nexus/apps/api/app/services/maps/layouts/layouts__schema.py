"""Workspace map layers ("layouts"): SPARQL pin layers and GeoJSON feed layers.

A layout is the server record behind one Maps layer: its metadata (title, group,
icon, logo, color, order, default basemap) and how its pins are fetched. The
sidebar group is a plain label on the feed (``group``), not a record of its own. The
feed itself stays where it was: a SPARQL query run on the workspace graphs, or
a GeoJSON/pins endpoint on the Nexus API that the web proxy calls.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from typing import Any

LAYOUT_ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]{0,47}$")
COLOR_PATTERN = re.compile(r"^#[0-9a-fA-F]{6}$")
MAX_QUERY_LENGTH = 20_000
MAX_PINS = 2_000
MAX_URL_LENGTH = 500
MAX_GROUP_LENGTH = 80
DEFAULT_GROUP = "Custom"
# Labels for the group slugs records stored as ``category`` before ``group``.
LEGACY_GROUP_LABELS = {
    "public": "Public",
    "environment": "Environment",
    "sigint": "SIGINT",
    "situation": "Situation",
    "organizations-facility": "Organizations Facilities",
    "custom": DEFAULT_GROUP,
}

FEED_SPARQL = "sparql"
# Pins / GeoJSON served by an endpoint on the Nexus API (e.g. a module router).
FEED_GEOJSON_URL = "geojson_url"
FEED_TYPES = frozenset({FEED_SPARQL, FEED_GEOJSON_URL})


# Built-in layouts drawn by the web app (web/src/app/workspace/[workspaceId]/maps/lib/datasets.ts).
# A custom layout cannot take one of these ids; any of them can be hidden.
# ``all`` is the route of the combined map.
BUILTIN_LAYOUT_IDS = frozenset(
    {
        "earthquakes",
        "wildfires",
        "temperature",
        "gdacs",
        "eonet-all",
        "openaq",
        "nws-alerts",
        "tropical-storms",
        "volcanoes",
        "flights",
        "conflict",
        "gulf-strikes",
        "news",
        "ais",
        "iss",
        "all",  # the combined All layers map route (/maps/all)
    }
)

# What a layout query must / may project. ?uri links a pin to its record,
# ?graph to the graph it came from; ?detail is the line under the label.
REQUIRED_VARIABLES = frozenset({"label", "lat", "lng"})
OPTIONAL_VARIABLES = frozenset({"uri", "graph", "detail"})


@dataclass(frozen=True)
class MapsLayout:
    """A workspace layer: pins from a SPARQL SELECT or from a Nexus API feed path."""

    id: str
    title: str
    query: str = ""
    description: str = ""
    icon: str = "MapPin"
    color: str = "#2563eb"
    graphs: tuple[str, ...] = field(default_factory=tuple)
    order: int = 100
    feed_type: str = FEED_SPARQL
    # FEED_GEOJSON_URL: path on the Nexus API ("/api/..."), never an absolute URL,
    # because the web proxy forwards the caller's Bearer token to it.
    feed_url: str = ""
    # Sidebar group label; feeds sharing a label (case-insensitive) form one group.
    group: str = DEFAULT_GROUP
    # Sidebar / pin logo: HTTPS URL or a Nexus API path (/api/organizations/logos/...).
    logo_url: str = ""
    basemap_id: str = ""
    meta_label: str = ""
    fit_max_zoom: int | None = None
    # Seeded by the deployment: editable and hideable, never deleted.
    system: bool = False
    # Set on records another workspace shares with this one (read-only here).
    shared_from: str = ""

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["graphs"] = list(self.graphs)
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> MapsLayout:
        fit = data.get("fit_max_zoom")
        return cls(
            id=str(data["id"]),
            title=str(data.get("title", "")),
            query=str(data.get("query", "") or ""),
            description=str(data.get("description", "") or ""),
            icon=str(data.get("icon", "MapPin") or "MapPin"),
            color=str(data.get("color", "#2563eb") or "#2563eb"),
            graphs=tuple(str(g) for g in data.get("graphs", []) or []),
            order=int(data.get("order", 100)),
            feed_type=str(data.get("feed_type", FEED_SPARQL) or FEED_SPARQL),
            feed_url=str(data.get("feed_url", "") or ""),
            group=group_from_record(data),
            logo_url=str(data.get("logo_url", "") or ""),
            basemap_id=str(data.get("basemap_id", "") or ""),
            meta_label=str(data.get("meta_label", "") or ""),
            fit_max_zoom=int(fit) if isinstance(fit, int | float) else None,
            system=bool(data.get("system", False)),
            shared_from=str(data.get("shared_from", "") or ""),
        )


def legacy_group_label(category: str) -> str:
    """The group label for a pre-``group`` category slug (unknown slugs as written)."""
    slug = category.strip()
    return LEGACY_GROUP_LABELS.get(slug.lower(), slug) or DEFAULT_GROUP


def group_from_record(data: dict[str, Any]) -> str:
    group = str(data.get("group", "") or "").strip()
    if group:
        return group
    return legacy_group_label(str(data.get("category", "") or ""))


@dataclass(frozen=True)
class MapsLayoutList:
    layouts: list[MapsLayout]
    hidden: set[str]
    # Color per layer id for layers without a record (built-in, graph layers).
    colors: dict[str, str] = field(default_factory=dict)


class MapsLayoutValidationError(ValueError):
    def __init__(self, errors: list[str]):
        super().__init__("; ".join(errors))
        self.errors = errors


class MapsLayoutNotFoundError(LookupError):
    pass


class MapsLayoutPolicyError(PermissionError):
    """The operation is refused by policy (e.g. deleting a seeded layer)."""
