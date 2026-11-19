"""How much of a request body the API reads.

``RequestBodyLimitMiddleware`` refuses a body over the limit with 413: at once
when ``Content-Length`` says so, else as soon as the bytes received pass it
(chunked uploads), before a route or the form parser spools the rest.
``read_upload`` reads an uploaded file in chunks and stops past a route's own
cap, so a route never holds more than that cap in memory.
"""

from __future__ import annotations

import json
from collections.abc import Iterable

from fastapi import HTTPException, UploadFile
from starlette.types import ASGIApp, Message, Receive, Scope, Send

UPLOAD_CHUNK_BYTES = 1024 * 1024


class _BodyTooLarge(HTTPException):
    def __init__(self, limit: int) -> None:
        super().__init__(
            status_code=413,
            detail=f"Request body too large. Max size is {limit // (1024 * 1024)}MB",
        )


class RequestBodyLimitMiddleware:
    """413 for a body over ``max_bytes`` on paths under ``prefixes``."""

    def __init__(self, app: ASGIApp, max_bytes: int, prefixes: Iterable[str] = ("/api/",)) -> None:
        self.app = app
        self.max_bytes = max_bytes
        self.prefixes = tuple(prefixes)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or not str(scope.get("path") or "").startswith(self.prefixes):
            await self.app(scope, receive, send)
            return
        limit = self.max_bytes
        for name, value in scope.get("headers") or ():
            if name == b"content-length":
                try:
                    declared = int(value)
                except ValueError:
                    declared = -1
                if declared > limit or declared < 0:
                    await _send_too_large(send, limit)
                    return
        received = 0
        started = False

        async def limited_receive() -> Message:
            nonlocal received
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > limit:
                    raise _BodyTooLarge(limit)
            return message

        async def tracking_send(message: Message) -> None:
            nonlocal started
            if message["type"] == "http.response.start":
                started = True
            await send(message)

        try:
            await self.app(scope, limited_receive, tracking_send)
        except _BodyTooLarge:
            if started:
                raise
            await _send_too_large(send, limit)


async def _send_too_large(send: Send, limit: int) -> None:
    body = json.dumps(
        {"detail": f"Request body too large. Max size is {limit // (1024 * 1024)}MB"}
    ).encode()
    await send(
        {
            "type": "http.response.start",
            "status": 413,
            "headers": [
                (b"content-type", b"application/json"),
                (b"content-length", str(len(body)).encode()),
                (b"connection", b"close"),
            ],
        }
    )
    await send({"type": "http.response.body", "body": body})


async def read_upload(file: UploadFile, max_bytes: int) -> bytes:
    """The uploaded file's bytes, read in chunks; 413 once they pass ``max_bytes``."""
    chunks: list[bytes] = []
    size = 0
    while True:
        chunk = await file.read(UPLOAD_CHUNK_BYTES)
        if not chunk:
            return b"".join(chunks)
        size += len(chunk)
        if size > max_bytes:
            raise HTTPException(
                status_code=413,
                detail=f"File too large. Max size is {max_bytes // (1024 * 1024)}MB",
            )
        chunks.append(chunk)
