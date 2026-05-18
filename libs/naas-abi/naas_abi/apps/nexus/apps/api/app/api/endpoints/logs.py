"""Live log streaming WebSocket endpoint.

Installs a Python logging handler that captures every log record produced
by the ABI API process.  Browser clients (e.g. the Code IDE log panel) can
connect to /api/logs/ws to receive a ring-buffered tail of recent log lines
plus a live stream of new ones.
"""

from __future__ import annotations

import asyncio
import logging
from collections import deque

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

router = APIRouter()

# ─── In-process log capture ───────────────────────────────────────────────────

_BUFFER_SIZE = 500
_log_buffer: deque[str] = deque(maxlen=_BUFFER_SIZE)
_listeners: list[asyncio.Queue[str]] = []


class _BroadcastHandler(logging.Handler):
    """Append every formatted record to the ring buffer and notify listeners."""

    def emit(self, record: logging.LogRecord) -> None:
        try:
            line = self.format(record)
        except Exception:
            return
        _log_buffer.append(line)
        for q in list(_listeners):
            try:
                q.put_nowait(line)
            except asyncio.QueueFull:
                pass


_fmt = logging.Formatter(
    "%(asctime)s  %(levelname)-8s  %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)

_handler = _BroadcastHandler()
_handler.setFormatter(_fmt)
_handler.setLevel(logging.DEBUG)

# Attach to the root logger so every library log is captured too.
logging.getLogger().addHandler(_handler)


# ─── WebSocket endpoint ───────────────────────────────────────────────────────

@router.websocket("/ws")
async def logs_ws(websocket: WebSocket) -> None:
    await websocket.accept()

    queue: asyncio.Queue[str] = asyncio.Queue(maxsize=200)
    _listeners.append(queue)

    try:
        # Replay recent history so the panel isn't empty on connect.
        for line in list(_log_buffer):
            await websocket.send_text(line + "\r\n")

        while True:
            try:
                line = await asyncio.wait_for(queue.get(), timeout=20.0)
                await websocket.send_text(line + "\r\n")
            except TimeoutError:
                # Send a keep-alive ping so the browser doesn't close the socket.
                try:
                    await websocket.send_text("")
                except Exception:
                    break
    except WebSocketDisconnect:
        pass
    except Exception:
        pass
    finally:
        try:
            _listeners.remove(queue)
        except ValueError:
            pass
