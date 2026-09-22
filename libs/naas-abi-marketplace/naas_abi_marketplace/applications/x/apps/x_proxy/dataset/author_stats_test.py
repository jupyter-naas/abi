"""Author stats cache."""

from __future__ import annotations

from naas_abi_marketplace.applications.x.apps.x_proxy.dataset.author_stats import (
    merge_profile_with_stats,
)


def test_merge_profile_with_stats_exposes_first_post_at() -> None:
    profile = merge_profile_with_stats(
        {"username": "pilot1", "author_id": "42"},
        {
            "matched_count": 2,
            "referenced_count": 1,
            "first_post_at": "2024-01-01T00:00:00+00:00",
            "last_post_at": "2025-06-01T00:00:00+00:00",
        },
    )
    assert profile["posts"] == 3
    assert profile["first_post_at"] == "2024-01-01T00:00:00+00:00"
    assert profile["last_post_at"] == "2025-06-01T00:00:00+00:00"
