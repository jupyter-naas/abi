"""Request bodies of /api/ stay under one limit, and uploads under their cap."""

from __future__ import annotations

import pytest
from fastapi import FastAPI, File, Request, UploadFile
from fastapi.testclient import TestClient
from naas_abi.apps.nexus.apps.api.app.core.request_body import (
    RequestBodyLimitMiddleware,
    read_upload,
)

LIMIT = 64 * 1024


def _app() -> FastAPI:
    app = FastAPI()
    app.add_middleware(RequestBodyLimitMiddleware, max_bytes=LIMIT)
    received: list[int] = []
    app.state.received = received

    @app.post("/api/echo")
    async def echo(request: Request) -> dict[str, int]:
        body = await request.body()
        received.append(len(body))
        return {"size": len(body)}

    @app.post("/api/upload")
    async def upload(file: UploadFile = File(...)) -> dict[str, int]:
        content = await read_upload(file, 1024)
        received.append(len(content))
        return {"size": len(content)}

    @app.post("/app-remote/x")
    async def elsewhere(request: Request) -> dict[str, int]:
        return {"size": len(await request.body())}

    return app


def test_request_body_keeps_under_the_declared_limit() -> None:
    app = _app()
    client = TestClient(app)
    assert client.post("/api/echo", content=b"a" * 1000).json() == {"size": 1000}
    refused = client.post("/api/echo", content=b"a" * (LIMIT + 1))
    assert refused.status_code == 413
    assert app.state.received == [1000]


def test_request_body_keeps_under_the_limit_when_chunked() -> None:
    app = _app()
    client = TestClient(app)

    def chunks():
        for _ in range(8):
            yield b"b" * (LIMIT // 4)

    refused = client.post("/api/echo", content=chunks())  # no Content-Length
    assert refused.status_code == 413
    assert app.state.received == []


def test_request_body_limit_keeps_to_its_paths() -> None:
    client = TestClient(_app())
    assert client.post("/app-remote/x", content=b"c" * (LIMIT + 1)).status_code == 200


def test_upload_keeps_to_its_own_cap() -> None:
    app = _app()
    client = TestClient(app)
    ok = client.post("/api/upload", files={"file": ("a.bin", b"d" * 1024)})
    assert ok.json() == {"size": 1024}
    refused = client.post("/api/upload", files={"file": ("b.bin", b"d" * 4096)})
    assert refused.status_code == 413
    assert app.state.received == [1024]


@pytest.mark.parametrize("value", [b"-5", b"nope"])
def test_request_body_keeps_a_bad_length_out(value: bytes) -> None:
    client = TestClient(_app())
    response = client.post("/api/echo", content=b"x", headers={"content-length": value.decode()})
    assert response.status_code == 413
