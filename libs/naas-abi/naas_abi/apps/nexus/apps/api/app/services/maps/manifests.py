"""Maps feeds, layers and basemaps declared by modules, like apps (``apps/<name>/manifest.json``).

Each loaded module may ship::

    <module_root>/artifacts/maps/layers/**/manifest.json           a feed and its layers
    <module_root>/artifacts/maps/basemaps/<slug>/manifest.json     a basemap (+ preview file)

Feed folders under ``layers/`` are free-form (``layers/facilities/<org>/``): a
feed is identified by its ``slug``, unique across modules, not by its folder.

Manifests hold metadata only. A layer's data is a GeoJSON object in the
platform's object storage (``storage_path``), the feed logo too (``logo_path``),
so data changes need no commit. At startup every manifest becomes a deployment
seed (``register_maps_seeds``): copied once per workspace, then Settings → Maps
edits win. Raising a ``version`` re-applies the manifest to every workspace's copy.

A broken manifest is logged and skipped; it never stops the API.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from naas_abi.apps.nexus.apps.api.app.services.maps.basemaps.basemaps__schema import (
    MapsBasemap,
    MapsBasemapPreview,
    validate_basemap,
    validate_preview,
)
from naas_abi.apps.nexus.apps.api.app.services.maps.feed_layers.feed_layers__schema import (
    MapsFeedLayer,
    validate_feed_layer,
)
from naas_abi.apps.nexus.apps.api.app.services.maps.layouts.layouts__schema import (
    DEFAULT_GROUP,
    FEED_OBJECT_STORAGE,
    MapsLayout,
)
from naas_abi.apps.nexus.apps.api.app.services.maps.layouts.service import validate_layout
from naas_abi.apps.nexus.apps.api.app.services.maps.seeds import (
    MapsBasemapSeed,
    register_maps_seeds,
)
from naas_abi.apps.nexus.apps.api.app.services.maps.storage_keys import (
    DATA_EXTENSIONS,
    image_content_type,
    is_storage_key,
)
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

logger = logging.getLogger(__name__)

MAPS_DIR = Path("artifacts") / "maps"
BASEMAPS_FOLDER = "basemaps"
LAYERS_FOLDER = "layers"
MANIFEST = "manifest.json"


class LayerManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    slug: str
    name: str
    storage_path: str
    icon: str = ""
    # Empty: the feed's color.
    color: str = ""
    description: str = ""
    # Empty: the list position.
    order: int | None = None
    class_labels: list[str] = Field(default_factory=list)

    @field_validator("storage_path")
    @classmethod
    def _storage_key(cls, value: str) -> str:
        if not is_storage_key(value, DATA_EXTENSIONS):
            raise ValueError("must be a relative object storage key ending in .geojson or .json")
        return value


class FeedManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    slug: str
    name: str
    version: int = Field(default=1, ge=1)
    group: str = DEFAULT_GROUP
    icon: str = "MapPin"
    color: str = "#2563eb"
    logo_path: str = ""
    basemap: str = ""
    description: str = ""
    order: int = 100
    meta_label: str = ""
    fit_max_zoom: int | None = None
    layers: list[LayerManifest] = Field(min_length=1)


class BasemapManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    slug: str
    name: str
    # Bump to re-apply the manifest to the workspaces' system copy.
    version: int = 1
    renderer: dict[str, Any]
    category: str = "custom"
    order: int = 100
    # File next to the manifest (png, jpeg, webp or svg).
    preview: str = ""


@dataclass(frozen=True)
class FeedSeed:
    layout: MapsLayout
    layers: tuple[MapsFeedLayer, ...]
    version: int
    source: Path


@dataclass
class ManifestScan:
    feeds: list[FeedSeed] = field(default_factory=list)
    basemaps: list[MapsBasemapSeed] = field(default_factory=list)
    issues: list[str] = field(default_factory=list)


def _read(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("a manifest is a JSON object")
    return data


def _feed_seed(path: Path) -> FeedSeed:
    manifest = FeedManifest.model_validate(_read(path))
    layout = MapsLayout(
        id=manifest.slug,
        title=manifest.name,
        description=manifest.description,
        icon=manifest.icon,
        color=manifest.color,
        order=manifest.order,
        feed_type=FEED_OBJECT_STORAGE,
        group=manifest.group,
        logo_path=manifest.logo_path,
        basemap_id=manifest.basemap,
        meta_label=manifest.meta_label,
        fit_max_zoom=manifest.fit_max_zoom,
    )
    errors = validate_layout(layout)
    layers = tuple(
        MapsFeedLayer(
            id=layer.slug,
            feed_id=manifest.slug,
            title=layer.name,
            color=layer.color or manifest.color,
            icon=layer.icon,
            description=layer.description,
            order=layer.order if layer.order is not None else index,
            class_labels=tuple(layer.class_labels),
            storage_path=layer.storage_path,
        )
        for index, layer in enumerate(manifest.layers, start=1)
    )
    for layer in layers:
        errors += [f"layer {layer.id!r}: {e}" for e in validate_feed_layer(layer)]
    if errors:
        raise ValueError("; ".join(errors))
    return FeedSeed(layout, layers, manifest.version, path)


def _basemap_seed(path: Path) -> MapsBasemapSeed:
    manifest = BasemapManifest.model_validate(_read(path))
    if manifest.slug != path.parent.name:
        raise ValueError(f"slug {manifest.slug!r} must match its folder {path.parent.name!r}")
    basemap = MapsBasemap(
        id=manifest.slug,
        title=manifest.name,
        renderer=manifest.renderer,
        category=manifest.category,
        order=manifest.order,
    )
    errors = validate_basemap(basemap)
    preview = None
    if manifest.preview:
        preview_path = path.parent / manifest.preview
        content_type = image_content_type(manifest.preview)
        if preview_path.parent != path.parent or not preview_path.is_file() or not content_type:
            errors.append(
                f"preview {manifest.preview!r} must be an image file next to the manifest"
            )
        else:
            content = preview_path.read_bytes()
            errors += validate_preview(content_type, content)
            preview = MapsBasemapPreview(content_type, content)
    if errors:
        raise ValueError("; ".join(errors))
    return MapsBasemapSeed(basemap, preview, manifest.version)


def _issue(path: Path, exc: Exception) -> str:
    if isinstance(exc, ValidationError):
        detail = "; ".join(
            f"{'.'.join(str(p) for p in e['loc']) or 'manifest'}: {e['msg']}" for e in exc.errors()
        )
    else:
        detail = str(exc)
    return f"{path}: {detail}"


def _hidden(path: Path, root: Path) -> bool:
    return any(part.startswith(("_", ".")) for part in path.relative_to(root).parts[:-1])


def scan_maps_dir(module_root: Path) -> ManifestScan:
    """Feeds (``layers/**``) and basemaps (``basemaps/*``) under ``<module_root>/artifacts/maps``;
    bad manifests become issues. Folders starting with ``_`` or ``.`` are skipped."""
    scan = ManifestScan()
    maps_dir = Path(module_root) / MAPS_DIR
    layers_dir = maps_dir / LAYERS_FOLDER
    if layers_dir.is_dir():
        for path in sorted(layers_dir.rglob(MANIFEST)):
            if _hidden(path, layers_dir):
                continue
            try:
                scan.feeds.append(_feed_seed(path))
            except Exception as exc:  # noqa: BLE001 - reported, never fatal
                scan.issues.append(_issue(path, exc))
    basemaps_dir = maps_dir / BASEMAPS_FOLDER
    if basemaps_dir.is_dir():
        for path in sorted(basemaps_dir.glob(f"*/{MANIFEST}")):
            if _hidden(path, basemaps_dir):
                continue
            try:
                scan.basemaps.append(_basemap_seed(path))
            except Exception as exc:  # noqa: BLE001 - reported, never fatal
                scan.issues.append(_issue(path, exc))
    if maps_dir.is_dir():
        for path in sorted(maps_dir.glob(f"*/{MANIFEST}")):
            if path.parent.name not in (LAYERS_FOLDER, BASEMAPS_FOLDER):
                scan.issues.append(f"{path}: not read: move it under {LAYERS_FOLDER}/")
    return scan


def register_module_manifests(app: Any, modules: Iterable[Any]) -> ManifestScan:
    """Register every loaded module's maps manifests as deployment seeds.

    A slug declared twice (feed, layer or basemap, across modules) is an error:
    the first copy is kept and the duplicate reported. Runs once per app.
    """
    done = getattr(app.state, "maps_manifests", None)
    if done is not None:  # startup may run twice (lifespan and startup event)
        return done
    total = ManifestScan()
    app.state.maps_manifests = total
    seen: dict[str, Path] = {}
    for module in modules:
        root = getattr(module, "module_root_path", None)
        if not root:
            continue
        scan = scan_maps_dir(Path(root))
        total.issues += scan.issues
        for feed in scan.feeds:
            ids = [feed.layout.id, *(layer.id for layer in feed.layers)]
            taken = [i for i in ids if i in seen]
            if taken:
                total.issues.append(
                    f"{feed.source}: {', '.join(taken)} already declared by {seen[taken[0]]}"
                )
                continue
            try:
                register_maps_seeds(
                    app, layouts=[feed.layout], feed_layers=feed.layers, revision=feed.version
                )
            except ValueError as exc:
                total.issues.append(f"{feed.source}: {exc}")
                continue
            seen.update(dict.fromkeys(ids, feed.source))
            total.feeds.append(feed)
        for basemap in scan.basemaps:
            try:  # the registry refuses a basemap id declared twice
                register_maps_seeds(app, basemaps=[basemap], revision=basemap.version)
            except ValueError as exc:
                total.issues.append(f"{root}: {exc}")
                continue
            total.basemaps.append(basemap)
    for issue in total.issues:
        logger.error("Maps manifest skipped: %s", issue)
    return total
