from __future__ import annotations

import pytest
from naas_abi.apps.nexus.apps.api.app.services.maps.storage_keys import (
    DATA_EXTENSIONS,
    IMAGE_EXTENSIONS,
    image_content_type,
    is_storage_key,
)

DATA = "intelligence/organizations/ForvisMazars/maps/forvis-mazars-facilities.geojson"


def test_relative_keys_with_the_right_extension_are_accepted() -> None:
    assert is_storage_key(DATA, DATA_EXTENSIONS)
    assert is_storage_key("maps/edf.json", DATA_EXTENSIONS)
    assert is_storage_key("intelligence/organizations/AXA/logos/AXA.ico", IMAGE_EXTENSIONS)


@pytest.mark.parametrize(
    "key",
    [
        "",
        "/intelligence/x.geojson",
        "../x.geojson",
        "maps/../secret.geojson",
        "maps//x.geojson",
        "maps\\x.geojson",
        "maps/x y.geojson",
        "maps/x.txt",
        "maps/",
        "a/" * 200 + "x.geojson",
    ],
)
def test_unsafe_or_wrong_keys_are_refused(key: str) -> None:
    assert not is_storage_key(key, DATA_EXTENSIONS)


def test_image_content_type_follows_the_extension() -> None:
    assert image_content_type("a/b/logo.ICO") == "image/x-icon"
    assert image_content_type("a/b/logo.svg") == "image/svg+xml"
    assert image_content_type("a/b/logo.geojson") is None
