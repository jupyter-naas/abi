"""Unit tests for the X app's HTTP surface.

Every page of the app is a path exported as its own ``index.html``, so the
middleware has to serve a directory tree rather than a single index — these
tests pin that down against a fake object storage holding a published export.
"""

from fastapi import FastAPI
from fastapi.testclient import TestClient
from naas_abi_core.services.object_storage.ObjectStoragePort import Exceptions
from naas_abi_marketplace.applications.x.apps.x_proxy.api.common import (
    DEFAULT_APP_PREFIX,
)
from naas_abi_marketplace.applications.x.apps.x_proxy.routes import (
    register_x_count_app_routes,
)

BASE = "/app-html/x/apps/x_proxy"


class _FakeObjectStorage:
    """Just enough of ``ObjectStorageService`` to answer ``get_object``."""

    def __init__(self, objects: dict[str, bytes]) -> None:
        self._objects = objects

    def get_object(self, prefix: str, key: str) -> bytes:
        try:
            return self._objects[f"{prefix}/{key}"]
        except KeyError as exc:
            raise Exceptions.ObjectNotFound(f"{prefix}/{key}") from exc


def _published(**extra: bytes) -> _FakeObjectStorage:
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
    return _FakeObjectStorage(objects)


def _client(storage: _FakeObjectStorage) -> TestClient:
    app = FastAPI()

    @app.get("/app-html/{path:path}")
    def _catch_all(path: str):  # Nexus' static catch-all, for fall-through.
        return {"detail": "App HTML not found"}

    register_x_count_app_routes(app, storage)  # type: ignore[arg-type]
    return TestClient(app)


def test_each_page_serves_its_own_html() -> None:
    client = _client(_published())
    for path, body in (
        ("/users/search/", b"users"),
        ("/posts/get-posts-counts-recent/", b"count"),
        ("/posts/search-posts-recent/", b"search"),
        ("/parameters/", b"parameters"),
    ):
        response = client.get(f"{BASE}{path}")
        assert response.status_code == 200, path
        assert body in response.content, path
        assert response.headers["content-type"].startswith("text/html")


def test_app_root_serves_the_root_index() -> None:
    client = _client(_published())
    for path in ("/", "/index.html"):
        response = client.get(f"{BASE}{path}")
        assert response.status_code == 200
        assert b"root" in response.content


def test_router_payload_is_served_as_text() -> None:
    """Without it, moving between pages is a full reload instead of a click."""
    response = _client(_published()).get(f"{BASE}/users/search/index.txt")
    assert response.status_code == 200
    assert response.content == b"users payload"
    assert response.headers["content-type"].startswith("text/plain")


def test_missing_payload_falls_through_instead_of_erroring() -> None:
    """An older publish has no payloads; the client then does a full load."""
    response = _client(_published()).get(f"{BASE}/parameters/index.txt")
    assert response.json() == {"detail": "App HTML not found"}


def test_users_page_serves_without_a_trailing_slash() -> None:
    """``search?user=`` must not bounce to ``search/?user=``."""
    response = _client(_published()).get(
        f"{BASE}/users/search?user=grok", follow_redirects=False
    )
    assert response.status_code == 200
    assert b"users" in response.content
    assert response.headers["content-type"].startswith("text/html")


def test_unslashed_router_payload_aliases_the_exported_index() -> None:
    response = _client(_published()).get(f"{BASE}/users/search.txt")
    assert response.status_code == 200
    assert response.content == b"users payload"
    assert response.headers["content-type"].startswith("text/plain")


def test_unpublished_page_falls_back_to_the_app_root() -> None:
    """An old bookmark boots the app instead of 404-ing."""
    response = _client(_published()).get(f"{BASE}/users/retired-page/")
    assert response.status_code == 200
    assert b"root" in response.content


def test_snapshots_and_assets_still_serve() -> None:
    client = _client(_published())
    snapshot = client.get(f"{BASE}/globals/scenarios.json")
    assert snapshot.status_code == 200
    assert snapshot.headers["content-type"].startswith("application/json")
    asset = client.get(f"{BASE}/_next/static/chunks/main.js")
    assert asset.status_code == 200
    # mimetypes calls JS text/javascript on some Pythons, application/… on others.
    assert "javascript" in asset.headers["content-type"]


def test_nothing_published_falls_through_to_the_catch_all() -> None:
    client = _client(_FakeObjectStorage({}))
    for path in ("/", "/users/search/"):
        response = client.get(f"{BASE}{path}")
        assert response.json() == {"detail": "App HTML not found"}


def test_paths_outside_the_app_are_left_alone() -> None:
    response = _client(_published()).get("/app-html/other/app/")
    assert response.json() == {"detail": "App HTML not found"}
