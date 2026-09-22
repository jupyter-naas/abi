"""On-demand tweet media resolution."""

from __future__ import annotations

from naas_abi_marketplace.applications.x.apps.x_proxy.dataset.media_resolve import (
    object_storage_prefix_for_public_rel,
    public_media_rel,
)


def test_public_media_rel() -> None:
    assert (
        public_media_rel("3_123", "abc.jpg")
        == "dataset/media/3_123/abc.jpg"
    )


def test_object_storage_prefix_for_public_rel() -> None:
    rel = "dataset/media/3_123/" + "a" * 64 + ".jpg"
    mapped = object_storage_prefix_for_public_rel(rel)
    assert mapped == ("x/media/3_123", "a" * 64 + ".jpg")
