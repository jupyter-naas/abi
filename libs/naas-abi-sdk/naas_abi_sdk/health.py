"""HTTP liveness and readiness for a module process. Standard library only."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable

logger = logging.getLogger(__name__)

# Discovery off means this process has no registry gate. It is ready once it
# is serving. Every other non-READY status, including DRAINING and STAGED,
# fails the readiness probe so a restart is not how a drain finishes.
_READY = frozenset({"READY", "DISABLED"})
_MAX_REQUEST_BYTES = 8192


class HealthServer:
    """GET /health is liveness. GET /ready is readiness."""

    def __init__(self, status: Callable[[], str], host: str, port: int):
        self._status = status
        self.host = host
        self.port = port
        self._server: asyncio.Server | None = None

    async def start(self) -> None:
        self._server = await asyncio.start_server(self._handle, self.host, self.port)
        sockets = self._server.sockets
        if sockets:
            self.port = sockets[0].getsockname()[1]
        logger.info("Health probe listening on %s:%s", self.host, self.port)

    async def close(self) -> None:
        if self._server is None:
            return
        self._server.close()
        await self._server.wait_closed()
        self._server = None

    async def _handle(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        try:
            data = await asyncio.wait_for(_read_request(reader), timeout=2)
            writer.write(_response(*_route(data, self._status)))
            await writer.drain()
        except (asyncio.IncompleteReadError, asyncio.TimeoutError, ConnectionError):
            return
        except Exception:
            logger.exception("Health probe failed")
            writer.write(_response(503, "Service Unavailable", "UNAVAILABLE"))
        finally:
            writer.close()
            try:
                await writer.wait_closed()
            except (ConnectionError, RuntimeError):
                return


async def _read_request(reader: asyncio.StreamReader) -> bytes:
    data = b""
    while b"\r\n\r\n" not in data and len(data) <= _MAX_REQUEST_BYTES:
        chunk = await reader.read(1024)
        if not chunk:
            break
        data += chunk
    return data


def _route(data: bytes, status: Callable[[], str]) -> tuple[int, str, str]:
    line = data.split(b"\r\n", 1)[0].decode("latin-1", errors="replace")
    parts = line.split(" ")
    if len(parts) < 2 or parts[0] != "GET":
        return 405, "Method Not Allowed", "method not allowed"
    path = parts[1].split("?", 1)[0]
    if path == "/health":
        return 200, "OK", "ok"
    if path != "/ready":
        return 404, "Not Found", "not found"
    try:
        current = str(status()).splitlines()[0][:64] or "UNAVAILABLE"
    except Exception:
        logger.exception("Readiness status failed")
        current = "UNAVAILABLE"
    if current in _READY:
        return 200, "OK", current
    return 503, "Service Unavailable", current


def _response(code: int, reason: str, body: str) -> bytes:
    payload = (body + "\n").encode()
    head = (
        f"HTTP/1.1 {code} {reason}\r\n"
        "Content-Type: text/plain; charset=utf-8\r\n"
        f"Content-Length: {len(payload)}\r\n"
        "Connection: close\r\n"
        "\r\n"
    )
    return head.encode() + payload
