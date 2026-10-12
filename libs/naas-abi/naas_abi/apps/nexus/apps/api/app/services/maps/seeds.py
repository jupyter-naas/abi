"""Deployment seeds for the Maps catalog.

Nexus seeds its generic basemaps; a module adds its own feeds, their layers and
basemaps in its FastAPI hook::

    register_maps_seeds(
        app,
        layouts=[MapsLayout(...)],          # feeds
        feed_layers=[MapsFeedLayer(...)],   # layers on those feeds (else one "all" layer)
        basemaps=[MapsBasemapSeed(...)],
    )

Seeds are copied into a workspace the first time its catalog is listed and are
then managed from Settings → Maps (renamed, recolored, hidden; never deleted).
A seed changed in code does not overwrite the workspace's copy.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any

from naas_abi.apps.nexus.apps.api.app.services.maps.basemaps.basemaps__schema import (
    MapsBasemap,
    MapsBasemapPreview,
    validate_basemap,
    validate_preview,
)
from naas_abi.apps.nexus.apps.api.app.services.maps.basemaps.builtin import (
    CORE_BASEMAPS,
    core_preview,
)
from naas_abi.apps.nexus.apps.api.app.services.maps.feed_layers.feed_layers__schema import (
    MapsFeedLayer,
    validate_feed_layer,
)
from naas_abi.apps.nexus.apps.api.app.services.maps.layouts.layouts__schema import MapsLayout
from naas_abi.apps.nexus.apps.api.app.services.maps.layouts.service import validate_layout


@dataclass(frozen=True)
class MapsBasemapSeed:
    basemap: MapsBasemap
    preview: MapsBasemapPreview | None = None


@dataclass
class MapsSeedRegistry:
    layouts: dict[str, MapsLayout] = field(default_factory=dict)
    basemaps: dict[str, MapsBasemapSeed] = field(default_factory=dict)
    feed_layers: dict[str, MapsFeedLayer] = field(default_factory=dict)
    # Seed revision per "layout:<id>" / "layer:<id>" (default 1). Raising it
    # re-applies the seed to the workspaces' system copy: a data migration.
    revisions: dict[str, int] = field(default_factory=dict)

    def layout_revisions(self) -> dict[str, int]:
        return {i: self.revisions.get(f"layout:{i}", 1) for i in self.layouts}

    def feed_layer_revisions(self) -> dict[str, int]:
        return {i: self.revisions.get(f"layer:{i}", 1) for i in self.feed_layers}

    def add_layout(self, layout: MapsLayout) -> None:
        errors = validate_layout(layout)
        if errors:
            raise ValueError(f"Invalid Maps layer seed {layout.id!r}: {'; '.join(errors)}")
        if layout.id in self.layouts:
            raise ValueError("Maps layer seed already registered: " + layout.id)
        self.layouts[layout.id] = layout

    def add_feed_layer(self, layer: MapsFeedLayer) -> None:
        errors = validate_feed_layer(layer)
        if layer.feed_id not in self.layouts:
            errors.append(f"feed {layer.feed_id!r} is not a registered feed seed")
        if errors:
            raise ValueError(f"Invalid map layer seed {layer.id!r}: {'; '.join(errors)}")
        if layer.id in self.feed_layers:
            raise ValueError("Map layer seed already registered: " + layer.id)
        self.feed_layers[layer.id] = layer

    def add_basemap(self, seed: MapsBasemapSeed) -> None:
        errors = validate_basemap(seed.basemap)
        if seed.preview is not None:
            errors += validate_preview(seed.preview.content_type, seed.preview.content)
        if errors:
            raise ValueError(f"Invalid basemap seed {seed.basemap.id!r}: {'; '.join(errors)}")
        if seed.basemap.id in self.basemaps:
            raise ValueError("Basemap seed already registered: " + seed.basemap.id)
        self.basemaps[seed.basemap.id] = seed


def core_registry() -> MapsSeedRegistry:
    registry = MapsSeedRegistry()
    for basemap in CORE_BASEMAPS:
        registry.add_basemap(MapsBasemapSeed(basemap, core_preview(basemap.id)))
    return registry


def maps_seed_registry(app: Any) -> MapsSeedRegistry:
    """The app's registry (created with the Nexus core seeds on first use)."""
    registry = getattr(app.state, "maps_seeds", None)
    if registry is None:
        registry = core_registry()
        app.state.maps_seeds = registry
    return registry


def register_maps_seeds(
    app: Any,
    *,
    layouts: Iterable[MapsLayout] = (),
    feed_layers: Iterable[MapsFeedLayer] = (),
    basemaps: Iterable[MapsBasemapSeed] = (),
    revision: int = 1,
) -> None:
    """``revision`` applies to the feeds and layers passed: bump it to migrate them."""
    registry = maps_seed_registry(app)
    for layout in layouts:
        registry.add_layout(layout)
        registry.revisions[f"layout:{layout.id}"] = revision
    for layer in feed_layers:
        registry.add_feed_layer(layer)
        registry.revisions[f"layer:{layer.id}"] = revision
    for seed in basemaps:
        registry.add_basemap(seed)
