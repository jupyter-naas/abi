"""Basemaps every Nexus workspace starts with (seeded, never hard-coded in the web client)."""

from __future__ import annotations

from pathlib import Path

from naas_abi.apps.nexus.apps.api.app.services.maps.basemaps.basemaps__schema import (
    RENDERER_COUNTRIES,
    RENDERER_TILE,
    MapsBasemap,
    MapsBasemapPreview,
)

ASSETS = Path(__file__).parent / "assets"

# Fallback when a workspace has nothing better: the first standard basemap.
DEFAULT_BASEMAP_ID = "openstreetmap"

_OSM_ATTRIBUTION = (
    '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
)

CORE_BASEMAPS: tuple[MapsBasemap, ...] = (
    MapsBasemap(
        id=DEFAULT_BASEMAP_ID,
        title="Street",
        category="standard",
        order=10,
        renderer={
            "kind": RENDERER_TILE,
            "url": "https://tile.openstreetmap.org/{z}/{x}/{y}.png",
            "attribution": _OSM_ATTRIBUTION,
            "max_zoom": 19,
        },
    ),
    MapsBasemap(
        id="natural-earth",
        title="Countries",
        category="standard",
        order=20,
        renderer={"kind": RENDERER_COUNTRIES},
    ),
    MapsBasemap(
        id="esri-imagery",
        title="Satellite",
        category="standard",
        order=30,
        renderer={
            "kind": RENDERER_TILE,
            "url": (
                "https://server.arcgisonline.com/ArcGIS/rest/services/"
                "World_Imagery/MapServer/tile/{z}/{y}/{x}"
            ),
            "attribution": (
                "Tiles &copy; Esri — Source: Esri, i-cubed, USDA, USGS, AEX, GeoEye, "
                "Getmapping, Aerogrid, IGN, IGP, UPR-EGP, and the GIS User Community"
            ),
            "max_zoom": 19,
        },
    ),
    MapsBasemap(
        id="opentopomap",
        title="Topo",
        category="standard",
        order=40,
        renderer={
            "kind": RENDERER_TILE,
            "url": "https://{s}.tile.opentopomap.org/{z}/{x}/{y}.png",
            "subdomains": ["a", "b", "c"],
            "attribution": (
                "Map data: &copy; OpenStreetMap contributors, SRTM | "
                "Map style: &copy; OpenTopoMap (CC-BY-SA)"
            ),
            "max_zoom": 17,
        },
    ),
)

_PREVIEW_FILES = {
    "openstreetmap": ("openstreetmap.png", "image/png"),
    "natural-earth": ("natural-earth.svg", "image/svg+xml"),
    "esri-imagery": ("esri-imagery.png", "image/png"),
    "opentopomap": ("opentopomap.png", "image/png"),
}


def core_preview(basemap_id: str) -> MapsBasemapPreview | None:
    entry = _PREVIEW_FILES.get(basemap_id)
    if entry is None:
        return None
    path = ASSETS / entry[0]
    if not path.is_file():
        return None
    return MapsBasemapPreview(content_type=entry[1], content=path.read_bytes())
