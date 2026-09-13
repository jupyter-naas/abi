from naas_abi_marketplace.applications.x.apps.x_proxy.api import publish


def test_publish_releases_window_frames_before_full_history_pages(monkeypatch):
    calls: list[str] = []

    class _Cache:
        def earliest_matched_created_at(self):
            return None

        def release_window_cache(self) -> int:
            calls.append("release")
            return 2

    monkeypatch.setattr(publish, "_attach_cache", lambda _storage: _Cache())
    monkeypatch.setattr(
        publish, "publish_globals", lambda _ctx: calls.append("globals") or {}
    )
    monkeypatch.setattr(
        publish, "publish_count_page", lambda _ctx: calls.append("count") or {}
    )
    monkeypatch.setattr(
        publish, "publish_search_page", lambda _ctx: calls.append("recent") or {}
    )
    monkeypatch.setattr(
        publish, "publish_tweets_page", lambda _ctx: calls.append("tweets") or {}
    )
    monkeypatch.setattr(
        publish,
        "publish_users_page",
        lambda _ctx, **_kwargs: calls.append("users") or {},
    )
    monkeypatch.setattr(publish, "upload_web_export", lambda *_args, **_kwargs: {})

    publish.publish_app(None, None, [], require_web=False)  # type: ignore[arg-type]

    assert calls == ["count", "recent", "release", "globals", "tweets", "users"]
