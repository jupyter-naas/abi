"""PTY terminal WebSocket endpoint.

Spawns an interactive shell inside the container and relays input/output
over WebSocket so the browser-side xterm.js can drive it.

Protocol:
  Binary frames  raw terminal bytes (both directions)
  Text frames    JSON control messages:
                   {"type": "resize", "cols": 80, "rows": 24}
"""

from __future__ import annotations

import asyncio
import fcntl
import json
import os
import pty
import select
import struct
import termios

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

router = APIRouter()

SHELL = os.environ.get("SHELL", "/bin/bash")
WORKDIR = os.environ.get("FILESYSTEM_ROOT", "/app")


def _set_winsize(fd: int, rows: int, cols: int) -> None:
    fcntl.ioctl(fd, termios.TIOCSWINSZ, struct.pack("HHHH", rows, cols, 0, 0))


def _read_master(fd: int, timeout: float = 0.05) -> bytes:
    r, _, _ = select.select([fd], [], [], timeout)
    if r:
        try:
            return os.read(fd, 4096)
        except OSError:
            return b""
    return b""


@router.websocket("/ws")
async def terminal_ws(websocket: WebSocket) -> None:
    await websocket.accept()

    master_fd, slave_fd = pty.openpty()
    _set_winsize(master_fd, 24, 80)

    env = {
        **os.environ,
        "TERM": "xterm-256color",
        "COLORTERM": "truecolor",
        "LANG": os.environ.get("LANG", "en_US.UTF-8"),
    }

    # Make the slave fd the controlling terminal of a new session so bash
    # can enable job control without the "cannot set terminal process group"
    # warning.
    def _set_controlling_tty() -> None:
        os.setsid()
        if hasattr(termios, "TIOCSCTTY"):
            fcntl.ioctl(0, termios.TIOCSCTTY, 0)  # fd 0 == slave_fd (stdin)

    proc = await asyncio.create_subprocess_exec(
        SHELL, "--login", "-i",
        stdin=slave_fd,
        stdout=slave_fd,
        stderr=slave_fd,
        close_fds=True,
        cwd=WORKDIR,
        env=env,
        preexec_fn=_set_controlling_tty,
    )
    os.close(slave_fd)

    loop = asyncio.get_event_loop()
    stop = asyncio.Event()

    async def _pump_output() -> None:
        """Read PTY master output and forward to WebSocket."""
        while not stop.is_set():
            data = await loop.run_in_executor(None, _read_master, master_fd)
            if data:
                try:
                    await websocket.send_bytes(data)
                except Exception:
                    break
        stop.set()

    async def _pump_input() -> None:
        """Read WebSocket messages and write to PTY master."""
        while not stop.is_set():
            try:
                msg = await websocket.receive()
            except WebSocketDisconnect:
                break
            except Exception:
                break

            if "bytes" in msg and msg["bytes"]:
                try:
                    os.write(master_fd, msg["bytes"])
                except OSError:
                    break
            elif "text" in msg and msg["text"]:
                try:
                    ctrl = json.loads(msg["text"])
                    if ctrl.get("type") == "resize":
                        cols = max(1, int(ctrl.get("cols", 80)))
                        rows = max(1, int(ctrl.get("rows", 24)))
                        _set_winsize(master_fd, rows, cols)
                except (json.JSONDecodeError, OSError):
                    try:
                        os.write(master_fd, msg["text"].encode())
                    except OSError:
                        break
        stop.set()

    try:
        await asyncio.gather(_pump_output(), _pump_input())
    finally:
        stop.set()
        try:
            proc.terminate()
        except Exception:
            pass
        try:
            os.close(master_fd)
        except Exception:
            pass
