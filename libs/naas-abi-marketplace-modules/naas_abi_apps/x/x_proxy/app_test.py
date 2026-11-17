"""The Recent Tweets ASGI app, as the SDK app host calls it.

Every page of the app is a path exported as its own ``index.html``, so the app
serves a directory tree rather than a single index. The requests carry the
``root_path`` the SDK sets (``/app-remote/<grant>/applications.x/x_proxy``)
and a path under it, as ``AppHost`` builds the scope.
"""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from naas_abi_apps.x.x_proxy.api.common import DEFAULT_APP_PREFIX
from naas_abi_apps.x.x_proxy.app import (
    APP_ROOT_PLACEHOLDER,
    LEGACY_APP_PREFIX,
    browser_root,
    create_app,
    rewrite_root,
)
from naas_abi_apps.x.x_proxy.testing import FakeDataset, MemoryObjectStorage

ROOT = "/app-remote/abi_gk_1_secret/applications.x/x_proxy"


def _storage(objects: dict[str, bytes]) -> MemoryObjectStorage:
    storage = MemoryObjectStorage()
    for path, content in objects.items():
        prefix, _, name = path.rpartition("/")
        storage.put_object(prefix, name, content)
    return storage


def _published(**extra: bytes) -> MemoryObjectStorage:
    """A published export: the root index, every page, and one snapshot."""
    objects = {
        f"{DEFAULT_APP_PREFIX}/index.html": b"<html>root</html>",
        f"{DEFAULT_APP_PREFIX}/index.txt": b"root payload",
        f"{DEFAULT_APP_PREFIX}/users/search/index.html": b"<html>users</html>",
        f"{DEFAULT_APP_PREFIX}/users/search/index.txt": b"users payload",
        f"{DEFAULT_APP_PREFIX}/posts/get-posts-counts-recent/index.html": b"<html>count</html>",
        f"{DEFAULT_APP_PREFIX}/posts/search-posts-recent/index.html": b"<html>search</html>",
        f"{DEFAULT_APP_PREFIX}/parameters/index.html": b"<html>parameters</html>",
        f"{DEFAULT_APP_PREFIX}/_next/static/chunks/main.js": b"console.log(1)",
        f"{DEFAULT_APP_PREFIX}/globals/scenarios.json": b'{"scenarios": []}',
    }
    objects.update(extra)
    return _storage(objects)


def _module(storage, dataset=None, *, read_enabled: bool = False):
    configuration = SimpleNamespace(
        app=SimpleNamespace(
            dataset=SimpleNamespace(
                read_enabled=read_enabled,
                sync_enabled=read_enabled,
                media_max_bytes=1024,
            )
        )
    )
    services = SimpleNamespace(object_storage=storage, dataset=dataset)
    sync = SimpleNamespace(
        configuration=configuration, engine=SimpleNamespace(services=services)
    )
    return SimpleNamespace(sync=sync, configuration=configuration)


def _client(storage, dataset=None, *, read_enabled: bool = False) -> TestClient:
    app = create_app(_module(storage, dataset, read_enabled=read_enabled))
    return TestClient(app, root_path=ROOT)


def _get(client: TestClient, path: str, **kwargs):
    return client.get(f"{ROOT}{path}", **kwargs)


def test_each_page_serves_its_own_html() -> None:
    client = _client(_published())
    for path, body in (
        ("/users/search/", b"users"),
        ("/posts/get-posts-counts-recent/", b"count"),
        ("/posts/search-posts-recent/", b"search"),
        ("/parameters/", b"parameters"),
    ):
        response = _get(client, path)
        assert response.status_code == 200, path
        assert body in response.content, path
        assert response.headers["content-type"].startswith("text/html")


def test_app_root_serves_the_root_index() -> None:
    client = _client(_published())
    for path in ("/", "/index.html"):
        response = _get(client, path)
        assert response.status_code == 200
        assert b"root" in response.content


def test_router_payload_is_served_as_text() -> None:
    """Without it, moving between pages is a full reload instead of a click."""
    response = _get(_client(_published()), "/users/search/index.txt")
    assert response.status_code == 200
    assert response.content == b"users payload"
    assert response.headers["content-type"].startswith("text/plain")


def test_missing_payload_is_a_404_not_an_error() -> None:
    """An older publish has no payloads; the client then does a full load."""
    response = _get(_client(_published()), "/parameters/index.txt")
    assert response.status_code == 404


def test_users_page_serves_without_a_trailing_slash() -> None:
    """``search?user=`` must not bounce to ``search/?user=``."""
    response = _get(
        _client(_published()), "/users/search?user=grok", follow_redirects=False
    )
    assert response.status_code == 200
    assert b"users" in response.content
    assert response.headers["content-type"].startswith("text/html")


def test_unslashed_router_payload_aliases_the_exported_index() -> None:
    response = _get(_client(_published()), "/users/search.txt")
    assert response.status_code == 200
    assert response.content == b"users payload"
    assert response.headers["content-type"].startswith("text/plain")


def test_unpublished_page_falls_back_to_the_app_root() -> None:
    """An old bookmark boots the app instead of 404-ing."""
    response = _get(_client(_published()), "/users/retired-page/")
    assert response.status_code == 200
    assert b"root" in response.content


def test_snapshots_and_assets_still_serve() -> None:
    client = _client(_published())
    snapshot = _get(client, "/globals/scenarios.json")
    assert snapshot.status_code == 200
    assert snapshot.headers["content-type"].startswith("application/json")
    asset = _get(client, "/_next/static/chunks/main.js")
    assert asset.status_code == 200
    # mimetypes calls JS text/javascript on some Pythons, application/… on others.
    assert "javascript" in asset.headers["content-type"]
    assert "immutable" in asset.headers["cache-control"]


def test_search_tweet_indexes_are_served() -> None:
    client = _client(
        _published(
            **{
                f"{DEFAULT_APP_PREFIX}/search_tweets/posts_preview.json": (
                    b'{"posts":[["123"]]}'
                ),
                f"{DEFAULT_APP_PREFIX}/search_tweets/posts.json": b'{"posts":[["123"]]}',
            }
        )
    )
    for name in ("posts_preview.json", "posts.json"):
        response = _get(client, f"/search_tweets/{name}")
        assert response.status_code == 200
        assert response.json()["posts"] == [["123"]]


def test_dataset_search_requires_read_enabled() -> None:
    client = _client(_published())
    for path in (
        "/dataset/posts/search.json?page=0&per_page=25",
        "/dataset/users/search.json?page=0&per_page=25",
    ):
        assert _get(client, path).status_code == 503
    assert _get(client, "/dataset/posts/search.json?page=x").status_code == 400


def test_direct_artifacts_and_media_are_served_with_cache_validators() -> None:
    digest = "a" * 64
    client = _client(
        _published(
            **{
                f"{DEFAULT_APP_PREFIX}/posts/by-id/123/post.json": b'{"post":{}}',
                f"{DEFAULT_APP_PREFIX}/posts/by-id/123/media/{digest}.png": b"png",
                f"{DEFAULT_APP_PREFIX}/users/by-handle/alice/user.json": b'{"bundle":{}}',
            }
        )
    )
    post = _get(client, "/posts/by-id/123/post.json")
    assert post.status_code == 200
    assert post.headers["etag"]
    assert "must-revalidate" in post.headers["cache-control"]
    cached = _get(
        client,
        "/posts/by-id/123/post.json",
        headers={"If-None-Match": post.headers["etag"]},
    )
    assert cached.status_code == 304

    media = _get(client, f"/posts/by-id/123/media/{digest}.png")
    assert media.status_code == 200
    assert media.headers["content-type"].startswith("image/png")
    assert "immutable" in media.headers["cache-control"]


def test_unapproved_nested_artifact_path_is_a_404() -> None:
    response = _get(_client(_published()), "/posts/by-id/not-a-number/post.json")
    assert response.status_code == 404


def test_nothing_published_serves_the_publish_hint() -> None:
    client = _client(_storage({}))
    for path in ("/", "/users/search/"):
        response = _get(client, path)
        assert response.status_code == 200
        assert b"has not been published yet" in response.content
        assert APP_ROOT_PLACEHOLDER.encode() not in response.content
        assert f"{ROOT}/favicon.svg".encode() in response.content


def test_legacy_prefix_objects_still_serve() -> None:
    """The pre-rename publish (``x/apps/x``) is read when ``x_proxy`` lacks it."""
    client = _client(
        _storage(
            {
                f"{LEGACY_APP_PREFIX}/index.html": b"<html>legacy-root</html>",
                f"{LEGACY_APP_PREFIX}/posts/get-posts-counts-recent/index.html": (
                    b"<html>legacy-count</html>"
                ),
                f"{LEGACY_APP_PREFIX}/_next/static/chunks/main.js": b"console.log(0)",
            }
        )
    )
    assert b"legacy-count" in _get(client, "/posts/get-posts-counts-recent/").content
    assert b"legacy-root" in _get(client, "/").content
    assert b"console.log(0)" in _get(client, "/_next/static/chunks/main.js").content


# --- the base path ---------------------------------------------------------------

_PAGE = (
    f'<link rel="stylesheet" href="{APP_ROOT_PLACEHOLDER}/_next/static/css/a.css">'
    f'<script src="{APP_ROOT_PLACEHOLDER}/_next/static/chunks/main.js"></script>'
    f'<script>self.__next_f.push([1,"{APP_ROOT_PLACEHOLDER}/users/search/"])</script>'
).encode()
_CHUNK = (
    f'var basePath="{APP_ROOT_PLACEHOLDER}";var a="\\/__x_proxy_app_root__\\/x";'
).encode()


def test_the_build_base_path_becomes_the_request_root_path() -> None:
    storage = _published(
        **{
            f"{DEFAULT_APP_PREFIX}/index.html": _PAGE,
            f"{DEFAULT_APP_PREFIX}/users/search/index.txt": _PAGE,
            f"{DEFAULT_APP_PREFIX}/_next/static/chunks/main.js": _CHUNK,
            f"{DEFAULT_APP_PREFIX}/globals/scenarios.json": (
                f'{{"u": "{APP_ROOT_PLACEHOLDER}/x"}}'.encode()
            ),
        }
    )
    client = _client(storage)
    for path in ("/", "/users/search/index.txt", "/globals/scenarios.json"):
        body = _get(client, path).content
        assert APP_ROOT_PLACEHOLDER.encode() not in body, path
        assert ROOT.encode() in body, path
    chunk = _get(client, "/_next/static/chunks/main.js").content
    assert f'basePath="{ROOT}"'.encode() in chunk
    assert ROOT.replace("/", "\\/").encode() in chunk


def test_each_session_root_gets_its_own_body_and_etag() -> None:
    storage = _published(**{f"{DEFAULT_APP_PREFIX}/index.html": _PAGE})
    module = _module(storage)
    other_root = "/app-remote/abi_gk_2_other/applications.x/x_proxy"
    first = TestClient(create_app(module), root_path=ROOT).get(f"{ROOT}/")
    second = TestClient(create_app(module), root_path=other_root).get(f"{other_root}/")
    assert other_root.encode() in second.content
    assert ROOT.encode() not in second.content
    assert first.headers["etag"] != second.headers["etag"]


def test_binary_files_are_never_rewritten() -> None:
    png = b"\x89PNG" + APP_ROOT_PLACEHOLDER.encode()
    digest = "b" * 64
    client = _client(
        _published(**{f"{DEFAULT_APP_PREFIX}/posts/by-id/1/media/{digest}.png": png})
    )
    assert _get(client, f"/posts/by-id/1/media/{digest}.png").content == png


def test_a_root_path_cannot_break_out_of_a_string() -> None:
    root = browser_root('/app-remote/g"><script>/applications.x/x_proxy/')
    assert '"' not in root and "<" not in root and ">" not in root
    assert root.endswith("/x_proxy")
    assert rewrite_root(b"no placeholder", root) == b"no placeholder"


def test_served_without_a_root_path_the_base_is_the_host_root() -> None:
    storage = _published(**{f"{DEFAULT_APP_PREFIX}/index.html": _PAGE})
    body = TestClient(create_app(_module(storage))).get("/").content
    assert b'href="/_next/static/css/a.css"' in body


# --- dataset-backed endpoints ------------------------------------------------------


def _post_row(tweet_id: str, author_id: str = "a1", **extra) -> dict:
    now = datetime(2026, 6, 1, 12, tzinfo=UTC)
    row = {
        "tweet_id": tweet_id,
        "kind": "matched",
        "query_slug": "q",
        "created_at": now,
        "created_month": now.strftime("%Y-%m"),
        "author_id": author_id,
        "text": "hi",
        "full_text": "hi there",
        "lang": "en",
        "conversation_id": "",
        "like_count": 0,
        "retweet_count": 0,
        "reply_count": 0,
        "media_urls": "",
    }
    row.update(extra)
    return row


@pytest.fixture
def dataset_client():
    from naas_abi_apps.x.x_proxy.dataset.store import (
        AUTHORS_V1,
        POSTS_V1,
        PROJECTION_COMMITS_V1,
        upsert_table,
    )

    dataset = FakeDataset()
    upsert_table(dataset, POSTS_V1, [_post_row("4242"), _post_row("4243")])
    upsert_table(
        dataset,
        AUTHORS_V1,
        [{"author_id": "a1", "username": "alice", "seen_at": "2026-06-01"}],
    )
    from naas_abi_apps.x.x_proxy.dataset.author_stats import recompute_author_stats

    recompute_author_stats(dataset, ["a1"])
    upsert_table(
        dataset,
        PROJECTION_COMMITS_V1,
        [
            {
                "commit_id": "c1",
                "committed_at": datetime(2026, 6, 1, tzinfo=UTC),
                "envelope_count": 1,
                "active": True,
                "detail": {"paths": []},
            }
        ],
    )
    client = _client(_published(), dataset, read_enabled=True)
    client.app.state.x_proxy.warm_landing_views = lambda generation: None
    return client, dataset


def test_dataset_post_is_cached_and_revalidates_with_304(dataset_client) -> None:
    client, dataset = dataset_client
    first = _get(client, "/dataset/posts/4242.json")
    assert first.status_code == 200
    assert first.json()["post"]["tweet_id"] == "4242"
    assert first.json()["post"]["username"] == "alice"
    assert first.headers["cache-control"] == "private, no-cache"
    queries = len(dataset.queries)
    again = _get(
        client,
        "/dataset/posts/4242.json",
        headers={"If-None-Match": first.headers["etag"]},
    )
    assert again.status_code == 304
    # The generation is trusted for a few seconds: no new dataset query.
    assert len(dataset.queries) == queries


def test_dataset_search_users_posts_and_totals(dataset_client) -> None:
    client, _ = dataset_client
    posts = _get(client, "/dataset/posts/search.json?q=there&page=0&per_page=10")
    assert posts.status_code == 200
    assert posts.json()["count"] == 2
    assert {p["tweet_id"] for p in posts.json()["posts"]} == {"4242", "4243"}

    users = _get(client, "/dataset/users/search.json?q=ali")
    assert users.json()["count"] == 1
    assert users.json()["users"][0]["username"] == "alice"

    feed = _get(client, "/dataset/users/alice/posts.json?kind=matched")
    assert feed.status_code == 200
    assert feed.json()["count"] == 2
    assert _get(client, "/dataset/users/alice/posts.json?kind=bad").status_code == 400
    assert _get(client, "/dataset/users/nobody/posts.json").status_code == 404

    totals = _get(client, "/globals/graph.json").json()
    assert (totals["posts"], totals["matched"], totals["referenced"]) == (2, 2, 0)

    assert _get(client, "/dataset/posts/abc.json").status_code == 400
    assert _get(client, "/dataset/posts/999.json").status_code == 404
    assert _get(client, "/search_users/users.json").status_code == 410


def test_dataset_media_maps_to_the_media_prefix(dataset_client) -> None:
    client, _ = dataset_client
    storage = client.app.state.x_proxy.storage
    digest = "c" * 64
    storage.put_object("x/media/3_1", f"{digest}.jpg", b"jpeg")
    response = _get(client, f"/dataset/media/3_1/{digest}.jpg")
    assert response.status_code == 200
    assert response.content == b"jpeg"


def test_post_media_downloads_once_on_first_view(dataset_client, monkeypatch) -> None:
    from naas_abi_apps.x.x_proxy.dataset import media_worker
    from naas_abi_apps.x.x_proxy.dataset.store import (
        MEDIA_V1,
        POST_MEDIA_V1,
        upsert_table,
    )

    client, dataset = dataset_client
    upsert_table(
        dataset,
        MEDIA_V1,
        [
            {
                "media_key": "3_1",
                "media_type": "photo",
                "source_url": "https://pbs.twimg.com/media/a.jpg",
                "status": "pending",
                "updated_at": datetime(2026, 6, 1, tzinfo=UTC),
            }
        ],
    )
    upsert_table(
        dataset, POST_MEDIA_V1, [{"tweet_id": "4242", "media_key": "3_1", "ordinal": 0}]
    )
    calls: list[str] = []

    def download(url: str, *, max_bytes: int) -> tuple[bytes, str]:
        calls.append(url)
        return b"jpeg-bytes", "image/jpeg"

    monkeypatch.setattr(media_worker, "_stream_download", download)
    doc = _get(client, "/dataset/posts/4242/media.json").json()
    assert doc["ready"] is True
    assert doc["media_urls"].startswith("dataset/media/3_1/")
    again = _get(client, "/dataset/posts/4242/media.json").json()
    assert again["media_urls"] == doc["media_urls"]
    assert calls == ["https://pbs.twimg.com/media/a.jpg"]
    served = _get(client, f"/{doc['media_urls']}")
    assert served.content == b"jpeg-bytes"


def test_blocking_work_runs_off_the_event_loop(monkeypatch) -> None:
    """Each request's storage calls run in a worker thread, never on the loop."""
    import asyncio

    seen: list[bool] = []

    class Probe(MemoryObjectStorage):
        def get_object(self, prefix: str, key: str) -> bytes:
            try:
                asyncio.get_running_loop()
                seen.append(True)
            except RuntimeError:
                seen.append(False)
            return super().get_object(prefix, key)

    storage = Probe()
    storage.put_object(DEFAULT_APP_PREFIX, "index.html", b"<html>root</html>")
    response = TestClient(create_app(_module(storage)), root_path=ROOT).get(f"{ROOT}/")
    assert response.status_code == 200
    assert seen == [False]


def test_the_app_folder_is_a_valid_sdk_app_of_browser_assets_only() -> None:
    """The SDK serves ``apps/x_proxy/`` files as they are, before this app:
    nothing there may shadow a page (an ``index.html`` would hide the
    published one), and the entry opens the Search Tweets page."""
    from pathlib import Path

    from naas_abi_sdk.apps import read_app

    folder = Path(__file__).resolve().parents[1] / "apps" / "x_proxy"
    assert sorted(p.name for p in folder.iterdir()) == ["manifest.json"]
    descriptor = read_app(folder)
    assert descriptor.name == "x_proxy"
    assert descriptor.title == "X Proxy"
    assert descriptor.entry == "posts/search-tweets/"
