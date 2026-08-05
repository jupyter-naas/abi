"""Schedule an ABI OS restart for the local dev runtime."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path

RESTART_PENDING = Path(".abi/dev/restart.pending")
INSTANCE_FILE = Path(".abi/dev/instance.json")


@dataclass(frozen=True)
class OsRestartSchedule:
    scheduled: bool
    mode: str
    project_root: str
    message: str


def find_dev_project_root(start: Path | None = None) -> Path | None:
    """Return the project root when `.abi/dev/instance.json` exists."""
    cursor = (start or Path.cwd()).resolve()
    for candidate in (cursor, *cursor.parents):
        if (candidate / INSTANCE_FILE).is_file():
            return candidate
    return None


def is_restart_pending(root: Path | None = None) -> bool:
    base = root or find_dev_project_root()
    if base is None:
        return False
    return (base / RESTART_PENDING).is_file()


def read_restart_pending(root: Path | None = None) -> dict | None:
    base = root or find_dev_project_root()
    if base is None:
        return None
    path = base / RESTART_PENDING
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"requested_at": None}
    return payload if isinstance(payload, dict) else {"requested_at": None}


def _restart_command() -> list[str]:
    if shutil.which("abi"):
        return ["abi", "dev", "restart"]
    if shutil.which("uv"):
        return ["uv", "run", "abi", "dev", "restart"]
    return [sys.executable, "-m", "naas_abi_cli.cli", "dev", "restart"]


def schedule_os_restart(*, delay_seconds: float = 0.75) -> OsRestartSchedule:
    """
    Queue a detached ``abi dev restart`` so the API can return before exit.

    Raises ``RuntimeError`` when no local dev instance is present (Docker/stack
    deployments must restart via their supervisor).
    """
    root = find_dev_project_root()
    if root is None:
        raise RuntimeError(
            "ABI dev runtime not detected. Restart the platform from the shell "
            "(`abi dev restart` locally, or restart the Docker stack in production)."
        )

    pending = root / RESTART_PENDING
    pending.parent.mkdir(parents=True, exist_ok=True)
    pending.write_text(
        json.dumps({"requested_at": time.time(), "delay_seconds": delay_seconds}),
        encoding="utf-8",
    )

    cmd = _restart_command()

    def _spawn() -> None:
        if delay_seconds > 0:
            time.sleep(delay_seconds)
        subprocess.Popen(
            cmd,
            cwd=str(root),
            start_new_session=True,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            env=os.environ.copy(),
        )

    import threading

    threading.Thread(target=_spawn, daemon=True, name="abi-os-restart").start()

    return OsRestartSchedule(
        scheduled=True,
        mode="dev",
        project_root=str(root),
        message=(
            "Restart OS scheduled. Services will reload in a few seconds to apply "
            "module and configuration changes."
        ),
    )
