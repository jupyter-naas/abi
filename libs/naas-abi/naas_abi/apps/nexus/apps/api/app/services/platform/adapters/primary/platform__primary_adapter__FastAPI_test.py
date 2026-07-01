from __future__ import annotations

import contextlib
import io
from collections.abc import Iterator

from fastapi import FastAPI
from fastapi.testclient import TestClient
from naas_abi.apps.nexus.apps.api.app.api.endpoints.auth import (
    User,
    get_current_user_required,
)
from naas_abi.apps.nexus.apps.api.app.services.platform.adapters.primary import (
    platform__primary_adapter__FastAPI as platform,
)


class _FakeStorage:
    """Minimal object-storage stand-in keyed by the full ``prefix/key`` path."""

    def __init__(self) -> None:
        self._objs: dict[str, bytes] = {}

    def put(self, full_key: str, data: bytes) -> None:
        self._objs[full_key] = data

    def list_objects(self, prefix: str) -> list[str]:
        pre = prefix.rstrip("/") + "/"
        keys = [k for k in self._objs if k.startswith(pre)]
        if not keys:  # mirrors the S3 adapter: unknown prefix raises
            raise KeyError(prefix)
        return keys

    def put_object_stream(self, prefix: str, key: str, stream: io.IOBase) -> None:
        self._objs[f"{prefix}/{key}"] = stream.read()

    def get_object_metadata(self, prefix: str, key: str) -> dict:
        full = f"{prefix}/{key}"
        if full not in self._objs:
            raise KeyError(full)
        return {"size": len(self._objs[full])}

    @contextlib.contextmanager
    def get_object_stream(self, prefix: str, key: str) -> Iterator[io.BytesIO]:
        yield io.BytesIO(self._objs[f"{prefix}/{key}"])


def _client(storage: _FakeStorage) -> TestClient:
    app = FastAPI()
    app.include_router(platform.router, prefix="/platform")
    app.state.object_storage = storage
    app.dependency_overrides[get_current_user_required] = lambda: User.model_construct(
        id="u1", email="u1@example.com", name="U1"
    )
    return TestClient(app)


def test_ls_and_download_scoped_to_user() -> None:
    s = _FakeStorage()
    s.put("users/u1/hello.txt", b"hi")
    s.put("users/u1/data/x.bin", b"xx")
    s.put("users/other/secret.txt", b"nope")  # another user's object
    client = _client(s)

    # ls returns only this user's objects, as keys relative to the namespace
    items = client.get("/platform/storage/ls").json()["items"]
    assert items == ["data/x.bin", "hello.txt"]
    assert all("other" not in i for i in items)

    # download streams the bytes
    resp = client.get("/platform/storage/download?path=hello.txt")
    assert resp.status_code == 200, resp.text
    assert resp.content == b"hi"

    # missing object -> clean 404
    assert client.get("/platform/storage/download?path=missing.bin").status_code == 404

    # path traversal is confined to the caller's namespace (can't reach other/)
    assert (
        client.get("/platform/storage/download?path=../other/secret.txt").status_code == 404
    )


def test_ls_empty_when_nothing_stored() -> None:
    client = _client(_FakeStorage())
    assert client.get("/platform/storage/ls").json() == {"items": []}


def test_cli_endpoint_serves_a_runnable_script() -> None:
    resp = _client(_FakeStorage()).get("/platform/cli")
    assert resp.status_code == 200, resp.text
    assert resp.text.startswith("#!/usr/bin/env python3")
    assert "def storage_cp" in resp.text  # the actual CLI source, verbatim


def test_upload_then_download_round_trip() -> None:
    s = _FakeStorage()
    client = _client(s)
    # upload streams into the caller's namespace
    up = client.post("/platform/storage/upload?path=out/report.bin", content=b"payload-bytes")
    assert up.status_code == 200, up.text
    assert up.json() == {"ok": True, "path": "out/report.bin"}
    assert s._objs["users/u1/out/report.bin"] == b"payload-bytes"
    # and it comes back via download + shows in ls
    assert client.get("/platform/storage/download?path=out/report.bin").content == b"payload-bytes"
    assert "out/report.bin" in client.get("/platform/storage/ls").json()["items"]
