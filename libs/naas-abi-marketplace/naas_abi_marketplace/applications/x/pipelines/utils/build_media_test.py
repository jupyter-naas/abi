"""Unit tests for :mod:`build_media` URL resolution."""

from __future__ import annotations

from naas_abi_marketplace.applications.x.pipelines.utils.build_media import (
    best_media_url,
)


def test_best_media_url_prefers_photo_url():
    assert (
        best_media_url({"url": "https://pbs.twimg.com/media/a.jpg"})
        == "https://pbs.twimg.com/media/a.jpg"
    )


def test_best_media_url_picks_highest_bitrate_mp4():
    record = {
        "variants": [
            {
                "content_type": "application/x-mpegURL",
                "url": "https://video.twimg.com/a.m3u8",
            },
            {
                "bit_rate": 256000,
                "content_type": "video/mp4",
                "url": "https://video.twimg.com/low.mp4",
            },
            {
                "bit_rate": 2176000,
                "content_type": "video/mp4",
                "url": "https://video.twimg.com/high.mp4",
            },
        ]
    }
    assert best_media_url(record) == "https://video.twimg.com/high.mp4"


def test_best_media_url_returns_none_without_playable_asset():
    assert best_media_url({"preview_image_url": "https://pbs.twimg.com/thumb.jpg"}) is None
    assert best_media_url({"variants": []}) is None
