"""The snapshot route serves only the cameras of the API's own list, by id, as
images or video."""

from __future__ import annotations

import importlib
import threading
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest
from fastapi.testclient import TestClient

PAGES = {
    "/cam.jpg": ("image/jpeg", b"\xff\xd8jpeg"),
    "/page": ("text/html", b"<html><script>1</script></html>"),
    "/live/index.m3u8": ("application/vnd.apple.mpegurl", b"#EXTM3U\nseg-1.ts\n"),
    "/other/index.m3u8": (
        "application/vnd.apple.mpegurl",
        b"#EXTM3U\nhttp://127.0.0.2:9/seg.ts\n",
    ),
    "/live/seg-1.ts": ("video/mp2t", b"segment"),
}


class Upstream(BaseHTTPRequestHandler):
    def log_message(self, *args: object) -> None:
        pass

    def do_GET(self) -> None:  # noqa: N802
        content_type, body = PAGES.get(self.path, ("text/plain", b"missing"))
        self.send_response(200 if self.path in PAGES else 404)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    upstream = ThreadingHTTPServer(("127.0.0.1", 0), Upstream)
    threading.Thread(target=upstream.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{upstream.server_port}"

    from main import app
    from ports.models import CCTVCamera
    from services.cctv import cctv_service

    # The module (the package re-exports the class under the same name).
    service_module = importlib.import_module("services.cctv.CCTVService")

    def camera(id: str, image: str = "", video: str = "", type: str = "hls") -> CCTVCamera:
        return CCTVCamera(
            id=id,
            name=id,
            lat=0,
            lon=0,
            city="x",
            imageUrl=image,
            videoUrl=video,
            type=type,
            source="nyc",
        )

    cameras = [
        camera("jpeg", image=f"{base}/cam.jpg"),
        camera("html", image=f"{base}/page"),
        camera("hls", video=f"{base}/live/index.m3u8"),
        camera("hls-elsewhere", video=f"{base}/other/index.m3u8"),
    ]

    class Source:
        async def fetch(self) -> list[CCTVCamera]:
            return cameras

    monkeypatch.setattr(cctv_service, "_adapters", [Source()])
    service_module._camera_cache._store.clear()
    service_module._snap_cache._store.clear()
    with TestClient(app) as test_client:
        yield test_client
    upstream.shutdown()


def test_cctv_snapshot_keeps_to_listed_cameras(client: TestClient) -> None:
    assert client.get("/api/cctv/snapshot", params={"url": "http://127.0.0.1/"}).status_code == 422
    assert client.get("/api/cctv/snapshot", params={"id": "unknown"}).status_code == 404
    assert (
        client.get("/api/cctv/snapshot", params={"id": "jpeg", "kind": "video"}).status_code == 404
    )

    image = client.get("/api/cctv/snapshot", params={"id": "jpeg"})

    assert image.status_code == 200
    assert image.content == b"\xff\xd8jpeg"
    assert image.headers["content-type"] == "image/jpeg"
    assert image.headers.get("access-control-allow-origin") is None


def test_cctv_snapshot_keeps_other_content_as_plain_bytes(client: TestClient) -> None:
    page = client.get("/api/cctv/snapshot", params={"id": "html"})

    assert page.headers["content-type"] == "application/octet-stream"
    assert page.headers["x-content-type-options"] == "nosniff"


def test_cctv_snapshot_keeps_hls_segments_on_the_playlists_origin(client: TestClient) -> None:
    segment = client.get("/api/cctv/snapshot", params={"id": "hls", "kind": "video"})
    elsewhere = client.get("/api/cctv/snapshot", params={"id": "hls-elsewhere", "kind": "video"})

    assert segment.status_code == 200 and segment.content == b"segment"
    assert segment.headers["content-type"] == "video/mp2t"
    assert elsewhere.status_code == 502
