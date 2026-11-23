"""Process-wide state of the X app code, reset around every test."""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _fresh_process_state():
    from naas_abi_apps.x.x_proxy.dataset import matched_tweets, read_cache

    def reset() -> None:
        matched_tweets._index_ready = None
        matched_tweets._rebuild_started = False
        matched_tweets._rebuild_failed_at = None
        read_cache.GENERATION.reset()
        read_cache.SEARCH_RESPONSE_CACHE.clear()

    reset()
    yield
    reset()
