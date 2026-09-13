from naas_abi_marketplace.applications.x.apps.x_proxy.cache.reader import CacheReader


def test_release_window_cache_preserves_full_history_frame():
    reader = CacheReader(None)  # type: ignore[arg-type]
    full_history = object()
    reader._posts = {
        ("2026-08",): object(),
        ("2026-08", "2026-09"): object(),
        None: full_history,
    }

    released = reader.release_window_cache()

    assert released == 2
    assert reader._posts == {None: full_history}
