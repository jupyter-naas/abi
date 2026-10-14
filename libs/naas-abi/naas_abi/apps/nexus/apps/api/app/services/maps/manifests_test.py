from __future__ import annotations

import json
import logging
from pathlib import Path
from types import SimpleNamespace

from fastapi import FastAPI
from naas_abi.apps.nexus.apps.api.app.services.maps.layouts.layouts__schema import (
    FEED_OBJECT_STORAGE,
)
from naas_abi.apps.nexus.apps.api.app.services.maps.manifests import (
    register_module_manifests,
    scan_maps_dir,
)
from naas_abi.apps.nexus.apps.api.app.services.maps.seeds import maps_seed_registry

DATA = "intelligence/organizations/Acme/maps/acme-facilities.geojson"
SVG = b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1 1"/>'


def _feed(**overrides) -> dict:
    manifest = {
        "slug": "acme-facilities",
        "name": "Acme",
        "version": 3,
        "group": "Organizations Facilities",
        "icon": "Building2",
        "color": "#171c8f",
        "logo_path": "intelligence/organizations/Acme/logos/Acme.ico",
        "basemap": "acme-countries",
        "layers": [
            {"slug": "acme-offices", "name": "Offices", "storage_path": DATA},
            {
                "slug": "acme-headquarters",
                "name": "Headquarters",
                "icon": "Landmark",
                "color": "#000000",
                "storage_path": DATA,
                "class_labels": ["Headquarters"],
            },
        ],
    }
    manifest.update(overrides)
    return manifest


def _write(root: Path, folder: str, manifest: dict, files: dict[str, bytes] | None = None) -> None:
    """``folder`` under artifacts/maps (``layers/...`` for feeds, ``basemaps/<id>``)."""
    target = root / "artifacts" / "maps" / folder
    target.mkdir(parents=True, exist_ok=True)
    (target / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    for name, body in (files or {}).items():
        (target / name).write_bytes(body)


def _basemap() -> dict:
    return {
        "slug": "acme-countries",
        "name": "Acme",
        "version": 2,
        "category": "organization",
        "order": 10,
        "renderer": {"kind": "countries", "palette": {"fill": "#e2e8f0", "stroke": "#ffffff"}},
        "preview": "preview.svg",
    }


def test_a_feed_manifest_becomes_an_object_storage_feed_and_its_layers(tmp_path) -> None:
    _write(tmp_path, "layers/facilities/acme", _feed())
    scan = scan_maps_dir(tmp_path)
    assert scan.issues == []
    [entry] = scan.feeds
    assert entry.version == 3
    feed = entry.layout
    assert (feed.id, feed.title, feed.feed_type, feed.logo_path, feed.basemap_id) == (
        "acme-facilities",
        "Acme",
        FEED_OBJECT_STORAGE,
        "intelligence/organizations/Acme/logos/Acme.ico",
        "acme-countries",
    )
    offices, hq = entry.layers
    # A layer without color or icon takes the feed's color; order follows the list.
    assert (offices.feed_id, offices.color, offices.storage_path, offices.order) == (
        "acme-facilities",
        "#171c8f",
        DATA,
        1,
    )
    assert (hq.icon, hq.color, hq.class_labels, hq.order) == (
        "Landmark",
        "#000000",
        ("Headquarters",),
        2,
    )


def test_a_basemap_manifest_carries_its_preview(tmp_path) -> None:
    _write(tmp_path, "basemaps/acme-countries", _basemap(), {"preview.svg": SVG})
    [seed] = scan_maps_dir(tmp_path).basemaps
    assert (seed.basemap.id, seed.basemap.category, seed.basemap.renderer["kind"]) == (
        "acme-countries",
        "organization",
        "countries",
    )
    assert seed.preview is not None and seed.preview.content_type == "image/svg+xml"


def test_broken_manifests_are_reported_and_skipped(tmp_path) -> None:
    _write(tmp_path, "layers/unknown-key", _feed(slug="unknown-key", default_on=True))
    _write(
        tmp_path,
        "layers/bad-path",
        _feed(
            slug="bad-path",
            layers=[{"slug": "bad-path", "name": "X", "storage_path": "../x.geojson"}],
        ),
    )
    _write(tmp_path, "layers/no-layers", _feed(slug="no-layers", layers=[]))
    (tmp_path / "artifacts/maps/layers/not-json").mkdir()
    (tmp_path / "artifacts/maps/layers/not-json/manifest.json").write_text("{", encoding="utf-8")
    _write(tmp_path, "layers/acme", _feed())

    scan = scan_maps_dir(tmp_path)
    assert [entry.layout.id for entry in scan.feeds] == ["acme-facilities"]
    reported = " ".join(scan.issues)
    for folder in ("unknown-key", "bad-path", "no-layers", "not-json"):
        assert folder in reported


def test_a_module_without_maps_has_nothing_to_scan(tmp_path) -> None:
    scan = scan_maps_dir(tmp_path)
    assert (scan.feeds, scan.basemaps, scan.issues) == ([], [], [])


def test_module_manifests_feed_the_seed_registry_with_their_version(tmp_path, caplog) -> None:
    one, two = tmp_path / "one", tmp_path / "two"
    _write(one, "layers/facilities/acme", _feed())
    _write(one, "basemaps/acme-countries", _basemap(), {"preview.svg": SVG})
    # Same feed slug in another module: an error, neither copy is registered twice.
    _write(two, "layers/facilities/acme", _feed(name="Acme again"))
    modules = [
        SimpleNamespace(module_root_path=str(one)),
        SimpleNamespace(module_root_path=str(two)),
        SimpleNamespace(),
    ]

    app = FastAPI()
    with caplog.at_level(logging.ERROR):
        register_module_manifests(app, modules)
    registry = maps_seed_registry(app)
    assert registry.layouts["acme-facilities"].title == "Acme"
    assert set(registry.feed_layers) == {"acme-offices", "acme-headquarters"}
    assert registry.revisions["layout:acme-facilities"] == 3
    assert registry.revisions["layer:acme-offices"] == 3
    assert "acme-countries" in registry.basemaps
    assert registry.basemap_revisions()["acme-countries"] == 2
    assert "acme-facilities" in caplog.text


def test_registering_twice_is_a_no_op(tmp_path, caplog) -> None:
    _write(tmp_path, "layers/facilities/acme", _feed())
    modules = [SimpleNamespace(module_root_path=str(tmp_path))]
    app = FastAPI()
    register_module_manifests(app, modules)
    with caplog.at_level(logging.ERROR):
        again = register_module_manifests(app, modules)  # startup hooks may run twice
    assert again.issues == [] and "already registered" not in caplog.text
    assert list(maps_seed_registry(app).layouts) == ["acme-facilities"]


def test_feeds_are_read_from_any_depth_under_layers_only(tmp_path) -> None:
    _write(tmp_path, "layers/facilities/acme", _feed())
    _write(
        tmp_path,
        "layers/weather",
        _feed(
            slug="storms",
            layers=[
                {"slug": "storm-tracks", "name": "Tracks", "storage_path": "weather/storms.geojson"}
            ],
        ),
    )
    _write(tmp_path, "layers/facilities/_draft", _feed(slug="draft"))
    _write(tmp_path, "layers/.cache/old", _feed(slug="old"))
    # A feed outside layers/ is not read, and reported.
    _write(tmp_path, "legacy-facilities", _feed(slug="legacy-facilities"))

    scan = scan_maps_dir(tmp_path)
    assert sorted(entry.layout.id for entry in scan.feeds) == ["acme-facilities", "storms"]
    assert len(scan.issues) == 1 and "legacy-facilities" in scan.issues[0]
    assert "move it under layers/" in scan.issues[0]
