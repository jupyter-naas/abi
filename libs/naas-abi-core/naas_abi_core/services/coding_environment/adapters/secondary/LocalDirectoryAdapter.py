from __future__ import annotations

import json
import os
import shutil
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path

from naas_abi_core.services.coding_environment.CodingEnvironmentPorts import (
    PHASE_ERROR,
    PHASE_RUNNING,
    PHASE_STOPPED,
    ICodingEnvironmentAdapter,
    ProvisionFailedError,
    WorkspaceAccess,
    WorkspaceNameConflictError,
    WorkspaceNotFoundError,
    WorkspaceStatus,
    WorkspaceTemplate,
)

_SIDECAR_SCRIPT = Path(__file__).with_name("abi_sidecar.py")
_DEFAULT_PORT_START = 18000
_DEFAULT_PORT_END = 18100
_HEALTH_TIMEOUT_S = 15.0


class LocalDirectoryAdapter(ICodingEnvironmentAdapter):
    """Local git checkout + abi_sidecar process (Slides-parity, no Coder).

    Each workspace is a directory under ``workspaces_root/{user_id}/{name}`` with
    a sidecar listening on localhost. ``get_runtime_binding`` returns the base
    URL and bearer secret for agent tools.
    """

    TEMPLATE_ID = "local-directory"
    TEMPLATE_NAME = "local-directory"

    def __init__(
        self,
        *,
        workspaces_root: str,
        sidecar_port_start: int = _DEFAULT_PORT_START,
        sidecar_port_end: int = _DEFAULT_PORT_END,
    ) -> None:
        self._root = Path(workspaces_root).expanduser().resolve()
        self._root.mkdir(parents=True, exist_ok=True)
        self._port_start = sidecar_port_start
        self._port_end = sidecar_port_end
        self._users: dict[str, str] = {}
        self._workspaces: dict[str, dict] = {}
        self._load_existing()

    def _load_existing(self) -> None:
        for meta_path in self._root.glob("*/*/.abi/workspace.json"):
            try:
                payload = json.loads(meta_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            workspace_id = str(payload.get("id") or "")
            if not workspace_id:
                continue
            self._workspaces[workspace_id] = payload

    def _persist(self, record: dict) -> None:
        checkout = Path(record["checkout"])
        meta = checkout / ".abi" / "workspace.json"
        meta.parent.mkdir(parents=True, exist_ok=True)
        serializable = {key: value for key, value in record.items() if not key.startswith("_")}
        meta.write_text(json.dumps(serializable, indent=2, sort_keys=True), encoding="utf-8")

    def _allocate_port(self) -> int:
        used = {int(record["port"]) for record in self._workspaces.values() if record.get("port")}
        for port in range(self._port_start, self._port_end):
            if port in used:
                continue
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                try:
                    sock.bind(("127.0.0.1", port))
                    return port
                except OSError:
                    continue
        raise ProvisionFailedError("no free sidecar port in configured range")

    @staticmethod
    def _wait_for_sidecar(base: str, secret: str) -> bool:
        req = urllib.request.Request(
            f"{base.rstrip('/')}/health",
            headers={"Authorization": f"Bearer {secret}"},
            method="GET",
        )
        deadline = time.monotonic() + _HEALTH_TIMEOUT_S
        while time.monotonic() < deadline:
            try:
                with urllib.request.urlopen(req, timeout=1.0) as resp:  # nosec B310
                    payload = json.loads(resp.read().decode("utf-8"))
                    if payload.get("ok"):
                        return True
            except (urllib.error.URLError, TimeoutError, json.JSONDecodeError):
                time.sleep(0.25)
        return False

    def _start_sidecar(self, checkout: Path, port: int, secret: str) -> subprocess.Popen[str]:
        env = {
            **os.environ,
            "ABI_SIDECAR_ROOT": str(checkout),
            "ABI_SIDECAR_SECRET": secret,
            "ABI_SIDECAR_PORT": str(port),
        }
        return subprocess.Popen(
            [sys.executable, str(_SIDECAR_SCRIPT)],
            cwd=str(checkout),
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            text=True,
        )

    def _stop_sidecar(self, record: dict) -> None:
        proc = record.get("_proc")
        if isinstance(proc, subprocess.Popen) and proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
        record["_proc"] = None

    def get_runtime_binding(self, *, workspace_id: str) -> tuple[str, str] | None:
        record = self._workspaces.get(workspace_id)
        if record is None:
            return None
        base = record.get("sidecar_base")
        secret = record.get("sidecar_secret")
        if base and secret:
            return str(base), str(secret)
        return None

    def ensure_user(self, *, external_id: str, email: str, username: str) -> str:
        del email, username
        if external_id not in self._users:
            self._users[external_id] = external_id
        return self._users[external_id]

    def list_templates(self) -> list[WorkspaceTemplate]:
        return [
            WorkspaceTemplate(
                id=self.TEMPLATE_ID,
                name=self.TEMPLATE_NAME,
                active_version_id="local",
            )
        ]

    def provision(
        self,
        *,
        user_id: str,
        template_id: str,
        name: str,
        params: dict[str, str] | None = None,
    ) -> WorkspaceStatus:
        del template_id
        for existing in self._workspaces.values():
            if existing["user_id"] == user_id and existing["name"] == name:
                raise WorkspaceNameConflictError(
                    f"workspace '{name}' already exists for user {user_id}"
                )

        params = dict(params or {})
        branch = params.get("branch", "main")
        repo_url = params.get("repo_url", "").strip()
        sidecar_secret = params.get("sidecar_secret") or uuid.uuid4().hex

        checkout = self._root / user_id / name
        if checkout.exists():
            shutil.rmtree(checkout)
        checkout.parent.mkdir(parents=True, exist_ok=True)

        if repo_url:
            clone = subprocess.run(
                ["git", "clone", "--branch", branch, repo_url, str(checkout)],
                capture_output=True,
                text=True,
                check=False,
            )
            if clone.returncode != 0:
                raise ProvisionFailedError(
                    (clone.stderr or clone.stdout or "git clone failed").strip()
                )
        else:
            checkout.mkdir(parents=True)
            subprocess.run(["git", "init", "-b", branch], cwd=checkout, check=True)

        port = self._allocate_port()
        proc = self._start_sidecar(checkout, port, sidecar_secret)
        sidecar_base = f"http://127.0.0.1:{port}"
        ready = self._wait_for_sidecar(sidecar_base, sidecar_secret)
        if not ready:
            proc.kill()
            shutil.rmtree(checkout, ignore_errors=True)
            raise ProvisionFailedError("sidecar did not become healthy")

        workspace_id = uuid.uuid4().hex
        record = {
            "id": workspace_id,
            "name": name,
            "user_id": user_id,
            "checkout": str(checkout),
            "port": port,
            "sidecar_base": sidecar_base,
            "sidecar_secret": sidecar_secret,
            "branch": branch,
            "repo_url": repo_url,
            "phase": PHASE_RUNNING,
            "agent_ready": True,
        }
        self._workspaces[workspace_id] = record
        record["_proc"] = proc
        self._persist(record)
        return self._status(workspace_id)

    def _record(self, workspace_id: str) -> dict:
        if workspace_id not in self._workspaces:
            raise WorkspaceNotFoundError(workspace_id)
        return self._workspaces[workspace_id]

    def _status(self, workspace_id: str) -> WorkspaceStatus:
        record = self._record(workspace_id)
        return WorkspaceStatus(
            id=workspace_id,
            name=record["name"],
            phase=record.get("phase", PHASE_RUNNING),
            agent_ready=bool(record.get("agent_ready")),
        )

    def list_environments(self, *, user_id: str) -> list[WorkspaceStatus]:
        return [
            self._status(workspace_id)
            for workspace_id, record in self._workspaces.items()
            if record.get("user_id") == user_id
        ]

    def get_logs(self, *, workspace_id: str) -> list[str]:
        record = self._record(workspace_id)
        return [
            f"checkout: {record.get('checkout')}",
            f"sidecar: {record.get('sidecar_base')}",
            f"branch: {record.get('branch')}",
        ]

    def get_status(self, *, workspace_id: str) -> WorkspaceStatus:
        return self._status(workspace_id)

    def start(
        self, *, workspace_id: str, params: dict[str, str] | None = None
    ) -> WorkspaceStatus:
        del params
        record = self._record(workspace_id)
        proc = record.get("_proc")
        if not isinstance(proc, subprocess.Popen) or proc.poll() is not None:
            checkout = Path(record["checkout"])
            port = int(record["port"])
            secret = str(record["sidecar_secret"])
            proc = self._start_sidecar(checkout, port, secret)
            record["_proc"] = proc
            if not self._wait_for_sidecar(str(record["sidecar_base"]), secret):
                record["phase"] = PHASE_ERROR
                record["agent_ready"] = False
                return self._status(workspace_id)
        record["phase"] = PHASE_RUNNING
        record["agent_ready"] = True
        return self._status(workspace_id)

    def stop(self, *, workspace_id: str) -> WorkspaceStatus:
        record = self._record(workspace_id)
        self._stop_sidecar(record)
        record["phase"] = PHASE_STOPPED
        record["agent_ready"] = False
        return self._status(workspace_id)

    def delete(self, *, workspace_id: str) -> None:
        record = self._record(workspace_id)
        self._stop_sidecar(record)
        checkout = Path(record["checkout"])
        shutil.rmtree(checkout, ignore_errors=True)
        self._workspaces.pop(workspace_id, None)

    def get_access(
        self, *, workspace_id: str, user_id: str, app_slug: str
    ) -> WorkspaceAccess:
        del user_id, app_slug
        record = self._record(workspace_id)
        return WorkspaceAccess(url=str(record.get("sidecar_base", "")), token=None)
