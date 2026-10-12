from __future__ import annotations

import asyncio

import pytest
from naas_abi.apps.nexus.apps.api.app.services.maps.basemaps.adapters.secondary.memory import (
    InMemoryMapsBasemapStore,
)
from naas_abi.apps.nexus.apps.api.app.services.maps.basemaps.basemaps__schema import (
    MapsBasemap,
    MapsBasemapNotFoundError,
    MapsBasemapPolicyError,
    MapsBasemapPreview,
    MapsBasemapValidationError,
)
from naas_abi.apps.nexus.apps.api.app.services.maps.basemaps.service import MapsBasemapService
from naas_abi.apps.nexus.apps.api.app.services.maps.seeds import core_registry
from naas_abi.apps.nexus.apps.api.app.services.maps.settings.adapters.secondary.memory import (
    InMemoryMapsSettingsStore,
)

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 16
SVG = b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1 1"/>'


def _custom(**overrides) -> MapsBasemap:
    values = {
        "id": "emea",
        "title": "EMEA",
        "category": "custom",
        "renderer": {"kind": "countries", "palette": {"fill": "#e2e8f0", "stroke": "#ffffff"}},
    }
    values.update(overrides)
    return MapsBasemap(**values)


def _seeds():
    return [(seed.basemap, seed.preview) for seed in core_registry().basemaps.values()]


@pytest.fixture
def service() -> MapsBasemapService:
    return MapsBasemapService(InMemoryMapsBasemapStore(), InMemoryMapsSettingsStore())


def test_core_seeds_arrive_with_previews_in_picker_order(service) -> None:
    listed = asyncio.run(service.list("ws-1", seeds=_seeds()))

    assert [b.id for b in listed.basemaps] == [
        "openstreetmap",
        "natural-earth",
        "esri-imagery",
        "opentopomap",
    ]
    assert all(b.system and b.preview_version == 1 for b in listed.basemaps)
    preview = asyncio.run(service.get_preview("ws-1", "openstreetmap"))
    assert preview.content_type == "image/png" and preview.content.startswith(b"\x89PNG")


def test_create_rename_delete_custom_basemap(service) -> None:
    asyncio.run(service.list("ws-1", seeds=_seeds()))
    asyncio.run(service.save("ws-1", _custom(), user_id="u"))
    asyncio.run(service.save("ws-1", _custom(title="  Europe  "), user_id="u"))

    listed = asyncio.run(service.list("ws-1", seeds=_seeds()))
    assert listed.basemaps[-1].title == "Europe" and not listed.basemaps[-1].system

    asyncio.run(service.set_hidden("ws-1", "emea", True, user_id="u"))
    asyncio.run(service.delete("ws-1", "emea"))
    after = asyncio.run(service.list("ws-1"))
    assert "emea" not in {b.id for b in after.basemaps}
    assert after.hidden == set()
    with pytest.raises(MapsBasemapNotFoundError):
        asyncio.run(service.delete("ws-1", "emea"))


def test_seeded_basemaps_are_renamable_and_hideable_not_deletable(service) -> None:
    asyncio.run(service.list("ws-1", seeds=_seeds()))
    street = asyncio.run(service.get("ws-1", "openstreetmap"))

    renamed = asyncio.run(
        service.save(
            "ws-1",
            MapsBasemap(**{**street.to_dict(), "title": "Roads", "system": False}),
            user_id="u",
        )
    )
    assert renamed.title == "Roads" and renamed.system and renamed.preview_version == 1

    with pytest.raises(MapsBasemapPolicyError):
        asyncio.run(service.delete("ws-1", "openstreetmap"))
    assert asyncio.run(service.set_hidden("ws-1", "openstreetmap", True, user_id="u")) == {
        "openstreetmap"
    }
    # Hidden in one workspace only.
    assert asyncio.run(service.list("ws-2", seeds=_seeds())).hidden == set()


def test_preview_upload_checks_type_size_and_bumps_version(service) -> None:
    asyncio.run(service.save("ws-1", _custom(), user_id="u"))

    saved = asyncio.run(service.set_preview("ws-1", "emea", "image/svg+xml", SVG, user_id="u"))
    assert (saved.preview_content_type, saved.preview_version) == ("image/svg+xml", 1)
    saved = asyncio.run(service.set_preview("ws-1", "emea", "image/png", PNG, user_id="u"))
    assert saved.preview_version == 2
    assert asyncio.run(service.get_preview("ws-1", "emea")).content == PNG

    for content_type, content in (
        ("image/png", SVG),  # declared type must match the bytes
        ("text/html", b"<html></html>"),
        ("image/png", b""),
        ("image/png", PNG + b"\x00" * 600_000),
    ):
        with pytest.raises(MapsBasemapValidationError):
            asyncio.run(service.set_preview("ws-1", "emea", content_type, content, user_id="u"))
    with pytest.raises(MapsBasemapNotFoundError):
        asyncio.run(service.set_preview("ws-1", "nope", "image/png", PNG, user_id="u"))


@pytest.mark.parametrize(
    ("renderer", "message"),
    [
        ({"kind": "wms"}, "renderer.kind"),
        ({"kind": "tile", "url": "http://tiles/{z}/{x}/{y}.png"}, "renderer.url"),
        ({"kind": "tile", "url": "https://tiles/static.png"}, "renderer.url"),
        ({"kind": "countries", "palette": {"fill": "red"}}, "palette.fill"),
        ({"kind": "countries", "palette": {"glow": "#ffffff"}}, "palette.glow"),
        ({"kind": "geojson", "feature_collection": {"type": "Feature"}}, "feature_collection"),
    ],
)
def test_invalid_renderers_are_refused(service, renderer, message) -> None:
    with pytest.raises(MapsBasemapValidationError) as exc_info:
        asyncio.run(service.save("ws-1", _custom(renderer=renderer), user_id="u"))
    assert any(message in e for e in exc_info.value.errors), exc_info.value.errors


def test_invalid_id_title_and_category(service) -> None:
    with pytest.raises(MapsBasemapValidationError) as exc_info:
        asyncio.run(
            service.save("ws-1", _custom(id="Bad Id", title=" ", category="x"), user_id="u")
        )
    assert len(exc_info.value.errors) == 3


def test_seed_with_preview_round_trips_through_memory_store() -> None:
    store = InMemoryMapsBasemapStore()
    service = MapsBasemapService(store, InMemoryMapsSettingsStore())
    seed = (_custom(id="group", category="organization"), MapsBasemapPreview("image/svg+xml", SVG))
    asyncio.run(service.list("ws-1", seeds=[seed]))

    listed = asyncio.run(service.list("ws-1", seeds=[seed]))
    assert [(b.id, b.category, b.system) for b in listed.basemaps] == [
        ("group", "organization", True)
    ]
