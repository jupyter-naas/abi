from naas_abi_marketplace.applications.x.apps.x_proxy.api import publish


def test_publish_app_runs_count_and_search_from_dataset(monkeypatch):
    calls: list[str] = []

    class _Reader:
        def earliest_matched_created_at(self):
            return None

    monkeypatch.setattr(
        publish, "DatasetSnapshotReader", lambda _dataset: _Reader()
    )
    monkeypatch.setattr(
        publish, "publish_globals", lambda _ctx: calls.append("globals") or {}
    )
    monkeypatch.setattr(
        publish, "publish_count_page", lambda _ctx: calls.append("count") or {}
    )
    monkeypatch.setattr(
        publish, "publish_search_page", lambda _ctx: calls.append("recent") or {}
    )
    monkeypatch.setattr(publish, "upload_web_export", lambda *_args, **_kwargs: {})

    summary = publish.publish_app(
        None,  # type: ignore[arg-type]
        None,  # type: ignore[arg-type]
        [],
        require_web=False,
        dataset=object(),
    )

    assert calls == ["count", "recent", "globals"]
    assert summary["mode"] == "dataset"
