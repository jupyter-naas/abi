"""Code terminal WebSocket primary adapter."""

from __future__ import annotations

import asyncio
import fcntl
import json
import os
import pty
import select
import struct
import termios

from fastapi import APIRouter, Depends, Query, WebSocket, WebSocketDisconnect
from naas_abi.apps.nexus.apps.api.app.core.database import get_db
from naas_abi.apps.nexus.apps.api.app.services.auth.adapters.secondary.postgres import (
    AuthSecondaryAdapterPostgres,
)
from naas_abi.apps.nexus.apps.api.app.services.auth.service import AuthService
from naas_abi.apps.nexus.apps.api.app.services.code.adapters.primary.code__primary_adapter__dependencies import (
    get_code_workdir_sync_service,
)
from naas_abi.apps.nexus.apps.api.app.services.code.workdir_sync_service import (
    CodeWorkdirSyncService,
)

terminal_router = APIRouter()

SHELL = os.environ.get("SHELL", "/bin/bash")
DEFAULT_WORKDIR = os.environ.get("FILESYSTEM_ROOT", "/app")


async def _auth_ws(websocket: WebSocket, token: str) -> str | None:
    async for db in get_db():
        service = AuthService(adapter=AuthSecondaryAdapterPostgres(db=db))
        user = await service.get_user_from_access_token(token)
        if user is None:
            await websocket.close(code=4001, reason="Unauthorized")
            return None
        return user.id
    return None


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


@terminal_router.websocket("/ws")
async def terminal_ws(
    websocket: WebSocket,
    token: str = Query(..., description="Bearer access token"),
    sync_service: CodeWorkdirSyncService = Depends(get_code_workdir_sync_service),
) -> None:
    user_id = await _auth_ws(websocket, token)
    if not user_id:
        return
    await websocket.accept()

    try:
        sync_result = sync_service.pull(user_id)
        workdir = sync_result.local_path
    except Exception:
        workdir = DEFAULT_WORKDIR

    master_fd, slave_fd = pty.openpty()
    _set_winsize(master_fd, 24, 80)

    env = {
        **os.environ,
        "TERM": "xterm-256color",
        "COLORTERM": "truecolor",
        "LANG": os.environ.get("LANG", "en_US.UTF-8"),
    }

    def _set_controlling_tty() -> None:
        os.setsid()
        if hasattr(termios, "TIOCSCTTY"):
            fcntl.ioctl(0, termios.TIOCSCTTY, 0)

    proc = await asyncio.create_subprocess_exec(
        SHELL,
        "--login",
        "-i",
        stdin=slave_fd,
        stdout=slave_fd,
        stderr=slave_fd,
        close_fds=True,
        cwd=workdir,
        env=env,
        preexec_fn=_set_controlling_tty,
    )
    os.close(slave_fd)

    loop = asyncio.get_event_loop()
    stop = asyncio.Event()

    async def _pump_output() -> None:
        while not stop.is_set():
            data = await loop.run_in_executor(None, _read_master, master_fd)
            if data:
                try:
                    await websocket.send_bytes(data)
                except Exception:
                    break
        stop.set()

    async def _pump_input() -> None:
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
            sync_service.push(user_id)
        except Exception:
            pass
        try:
            proc.terminate()
        except Exception:
            pass
        try:
            os.close(master_fd)
        except Exception:
            pass
