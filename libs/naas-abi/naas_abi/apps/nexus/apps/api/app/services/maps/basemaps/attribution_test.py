"""A basemap's attribution is text, with links written ``<a href="https://...">label</a>``:
the map writes it as HTML, so the API stores no other markup."""

from __future__ import annotations

import pytest
from naas_abi.apps.nexus.apps.api.app.services.maps.basemaps.basemaps__schema import (
    MapsBasemap,
    is_attribution_text,
    validate_basemap,
)
from naas_abi.apps.nexus.apps.api.app.services.maps.basemaps.builtin import CORE_BASEMAPS


def _tile(attribution: str) -> MapsBasemap:
    return MapsBasemap(
        id="custom-tiles",
        title="Custom",
        category="custom",
        renderer={
            "kind": "tile",
            "url": "https://tile.example/{z}/{x}/{y}.png",
            "attribution": attribution,
        },
    )


@pytest.mark.parametrize(
    "attribution",
    [
        '<img src=x onerror="fetch(`/api/auth/me`)">',
        "© OSM <svg onload=alert(1)>",
        '<a href="javascript:alert(1)">x</a>',
        '<a href="https://x.example" onclick="alert(1)">x</a>',
        "<a href='https://x.example'>x</a>",
        '<a href="https://x.example"><img src=x></a>',
        "<script>alert(1)</script>",
        "a > b",
    ],
)
def test_basemap_attributions_keep_to_text_and_https_links(attribution):
    assert not is_attribution_text(attribution)
    assert any("attribution" in error for error in validate_basemap(_tile(attribution)))


def test_basemap_attributions_keep_the_seeded_forms():
    for basemap in CORE_BASEMAPS:
        assert validate_basemap(basemap) == [], basemap.id
    for attribution in (
        "",
        "Tiles &copy; Esri",
        '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
        'A <a href="https://a.example">one</a> and <a href="https://b.example/x?y=1&amp;z=2">two</a>',
    ):
        assert is_attribution_text(attribution), attribution
        assert validate_basemap(_tile(attribution)) == [], attribution
