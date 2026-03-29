"""
Lab terminal – PTY-backed WebSocket shell.

Spawns a bash session inside the Docker container with ~/aia mounted at the
working directory.  Messages from the browser are raw bytes (keyboard input)
OR a JSON resize event: {"type":"resize","cols":N,"rows":N}.
Output from the shell is sent back as raw bytes (xterm.js handles rendering).
"""

import asyncio
import fcntl
import json
import os
import pty
import struct
import termios

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

# Public router — auth via query-param token is skipped for local-only use.
# The shell runs inside the container which only trusted users can reach.
terminal_router = APIRouter()

_AIA_HOST = os.environ.get("AIA_HOST_ROOT", "/app/aia-host")
_SHELL = "/bin/bash"


def _set_winsize(fd: int, rows: int, cols: int) -> None:
    s = struct.pack("HHHH", rows, cols, 0, 0)
    try:
        fcntl.ioctl(fd, termios.TIOCSWINSZ, s)
    except OSError:
        pass


@terminal_router.websocket("/ws")
async def terminal_ws(websocket: WebSocket) -> None:
    await websocket.accept()

    master_fd, slave_fd = pty.openpty()
    _set_winsize(master_fd, 24, 220)

    env = {
        **os.environ,
        "TERM": "xterm-256color",
        "COLORTERM": "truecolor",
        "SHELL": _SHELL,
    }

    # Ensure slave becomes the controlling terminal of the child
    def _preexec() -> None:
        os.setsid()
        try:
            fcntl.ioctl(slave_fd, termios.TIOCSCTTY, 0)
        except OSError:
            pass

    cwd = _AIA_HOST if os.path.isdir(_AIA_HOST) else "/"

    proc = await asyncio.create_subprocess_exec(
        _SHELL,
        "--login",
        stdin=slave_fd,
        stdout=slave_fd,
        stderr=slave_fd,
        env=env,
        cwd=cwd,
        preexec_fn=_preexec,
    )
    os.close(slave_fd)

    # Non-blocking reads from master
    flags = fcntl.fcntl(master_fd, fcntl.F_GETFL)
    fcntl.fcntl(master_fd, fcntl.F_SETFL, flags | os.O_NONBLOCK)

    loop = asyncio.get_running_loop()
    output_queue: asyncio.Queue[bytes | None] = asyncio.Queue()

    def _on_pty_readable() -> None:
        try:
            data = os.read(master_fd, 4096)
            loop.call_soon_threadsafe(output_queue.put_nowait, data)
        except OSError:
            loop.call_soon_threadsafe(output_queue.put_nowait, None)

    loop.add_reader(master_fd, _on_pty_readable)

    async def _send_to_browser() -> None:
        while True:
            chunk = await output_queue.get()
            if chunk is None:
                break
            try:
                await websocket.send_bytes(chunk)
            except Exception:
                break

    async def _recv_from_browser() -> None:
        while True:
            try:
                msg = await websocket.receive()
                if msg["type"] == "websocket.disconnect":
                    break
                raw = msg.get("bytes") or b""
                text = msg.get("text") or ""
                if raw:
                    os.write(master_fd, raw)
                elif text:
                    try:
                        ev = json.loads(text)
                        if ev.get("type") == "resize":
                            _set_winsize(
                                master_fd,
                                int(ev.get("rows", 24)),
                                int(ev.get("cols", 220)),
                            )
                    except (json.JSONDecodeError, OSError):
                        pass
            except WebSocketDisconnect:
                break
            except Exception:
                break

    try:
        await asyncio.gather(_send_to_browser(), _recv_from_browser())
    finally:
        loop.remove_reader(master_fd)
        try:
            proc.kill()
        except ProcessLookupError:
            pass
        try:
            os.close(master_fd)
        except OSError:
            pass
