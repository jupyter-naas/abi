"""On-demand tweet media resolution."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

from naas_abi_apps.x.x_proxy.dataset import media_worker
from naas_abi_apps.x.x_proxy.dataset.media_resolve import (
    MEDIA_RETRY_AFTER,
    object_storage_prefix_for_public_rel,
    public_media_rel,
    retry_due,
)


def test_a_failed_media_is_retried_only_after_the_backoff() -> None:
    now = datetime(2026, 6, 1, 12, tzinfo=UTC)
    recent = now - MEDIA_RETRY_AFTER + timedelta(seconds=1)
    old = now - MEDIA_RETRY_AFTER
    assert retry_due({"status": "pending", "updated_at": now}, now)
    assert not retry_due({"status": "failed", "updated_at": recent}, now)
    # Naive and text timestamps (as the dataset may return them) are UTC.
    assert not retry_due(
        {"status": "failed", "updated_at": recent.replace(tzinfo=None)}, now
    )
    assert not retry_due({"status": "failed", "updated_at": recent.isoformat()}, now)
    assert retry_due({"status": "failed", "updated_at": old}, now)
    assert retry_due({"status": "failed", "updated_at": None}, now)


def test_a_large_media_gets_time_in_proportion_to_its_size(monkeypatch) -> None:
    """The timeout bounds the whole download: 30 s would cut off any large video."""
    asked: list[float] = []

    async def fetch(url, *, headers, max_bytes, timeout):
        asked.append(timeout)
        return SimpleNamespace(
            url=url,
            status_code=200,
            headers={"content-type": "video/mp4"},
            content=b"mp4",
            truncated=False,
        )

    monkeypatch.setattr(media_worker, "fetch_public", fetch)
    url = "https://video.twimg.com/v.mp4"
    media_worker._stream_download(url, max_bytes=media_worker.DEFAULT_MAX_BYTES)
    media_worker._stream_download(url, max_bytes=1024 * 1024)
    big, small = asked
    assert big == media_worker.media_timeout(media_worker.DEFAULT_MAX_BYTES)
    assert big >= 250.0 and small <= 35.0
    assert media_worker.media_timeout(10**12) == media_worker.MEDIA_MAX_TIMEOUT


def test_public_media_rel() -> None:
    assert public_media_rel("3_123", "abc.jpg") == "dataset/media/3_123/abc.jpg"


def test_object_storage_prefix_for_public_rel() -> None:
    rel = "dataset/media/3_123/" + "a" * 64 + ".jpg"
    mapped = object_storage_prefix_for_public_rel(rel)
    assert mapped == ("x/media/3_123", "a" * 64 + ".jpg")
