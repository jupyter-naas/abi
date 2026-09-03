from __future__ import annotations

import json
import os
import shlex
import shutil
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path
from typing import Literal

from naas_abi_core.services.coding_environment.adapters.secondary.OpencodeHarnessClient import (
    wait_for_healthy as wait_for_opencode_healthy,
)
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
_DEFAULT_HARNESS_PORT_START = 18200
_DEFAULT_HARNESS_PORT_END = 18300
_HEALTH_TIMEOUT_S = 15.0
HarnessKind = Literal["none", "opencode"]


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
        harness: HarnessKind = "none",
        harness_port_start: int = _DEFAULT_HARNESS_PORT_START,
        harness_port_end: int = _DEFAULT_HARNESS_PORT_END,
        opencode_bin: str = "opencode",
        opencode_model: str | None = None,
        opencode_startup_timeout: int = 15,
    ) -> None:
        self._root = Path(workspaces_root).expanduser().resolve()
        self._root.mkdir(parents=True, exist_ok=True)
        self._port_start = sidecar_port_start
        self._port_end = sidecar_port_end
        self._harness = harness
        self._harness_port_start = harness_port_start
        self._harness_port_end = harness_port_end
        self._opencode_bin = opencode_bin
        self._opencode_model = opencode_model
        self._opencode_startup_timeout = opencode_startup_timeout
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

    def _allocate_port(
        self,
        *,
        start: int,
        end: int,
        used_keys: tuple[str, ...] = ("port", "harness_port"),
    ) -> int:
        used: set[int] = set()
        for record in self._workspaces.values():
            for key in used_keys:
                value = record.get(key)
                if value is not None:
                    used.add(int(value))
        for port in range(start, end):
            if port in used:
                continue
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                try:
                    sock.bind(("127.0.0.1", port))
                    return port
                except OSError:
                    continue
        raise ProvisionFailedError("no free port in configured range")

    def _allocate_sidecar_port(self) -> int:
        return self._allocate_port(
            start=self._port_start,
            end=self._port_end,
            used_keys=("port",),
        )

    def _allocate_harness_port(self) -> int:
        return self._allocate_port(
            start=self._harness_port_start,
            end=self._harness_port_end,
            used_keys=("harness_port",),
        )

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

    def _stop_process(self, record: dict, proc_key: str) -> None:
        proc = record.get(proc_key)
        if isinstance(proc, subprocess.Popen) and proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
        record[proc_key] = None

    def _stop_sidecar(self, record: dict) -> None:
        self._stop_process(record, "_proc")

    def _stop_harness(self, record: dict) -> None:
        self._stop_process(record, "_harness_proc")

    @staticmethod
    def _ensure_opencode_auth() -> None:
        from naas_abi_core.services.agent.OpencodeAgent import OpencodeAgent

        OpencodeAgent._ensure_opencode_auth_file_once()

    def _resolve_opencode_bin(self) -> str:
        if shutil.which(self._opencode_bin):
            return self._opencode_bin
        home_bin = Path.home() / ".opencode" / "bin" / "opencode"
        if home_bin.is_file():
            return str(home_bin)
        return self._opencode_bin

    def _start_opencode(self, checkout: Path, port: int) -> subprocess.Popen[str]:
        self._ensure_opencode_auth()
        opencode_bin = self._resolve_opencode_bin()
        launch_command = (
            f"source ~/.bashrc >/dev/null 2>&1; "
            f"{shlex.quote(opencode_bin)} serve --port {port}"
        )
        return subprocess.Popen(
            ["bash", "-lc", launch_command],
            cwd=str(checkout),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            text=True,
        )

    def _ensure_harness(self, record: dict) -> bool:
        if self._harness != "opencode":
            return False
        harness_base = record.get("harness_base")
        proc = record.get("_harness_proc")
        if isinstance(proc, subprocess.Popen) and proc.poll() is None:
            if harness_base and wait_for_opencode_healthy(
                str(harness_base), timeout_s=2.0
            ):
                record["harness_ready"] = True
                return True
        checkout = Path(record["checkout"])
        port = int(record.get("harness_port") or self._allocate_harness_port())
        record["harness_port"] = port
        proc = self._start_opencode(checkout, port)
        record["_harness_proc"] = proc
        harness_base = f"http://127.0.0.1:{port}"
        record["harness_base"] = harness_base
        ready = wait_for_opencode_healthy(
            harness_base, timeout_s=float(self._opencode_startup_timeout)
        )
        record["harness_ready"] = ready
        if not ready and isinstance(proc, subprocess.Popen) and proc.poll() is None:
            proc.kill()
            record["_harness_proc"] = None
        self._persist(record)
        return ready

    def get_runtime_binding(self, *, workspace_id: str) -> tuple[str, str] | None:
        record = self._workspaces.get(workspace_id)
        if record is None:
            return None
        base = record.get("sidecar_base")
        secret = record.get("sidecar_secret")
        if base and secret:
            return str(base), str(secret)
        return None

    def get_harness_binding(self, *, workspace_id: str) -> str | None:
        record = self._workspaces.get(workspace_id)
        if record is None:
            return None
        if self._harness == "none":
            return None
        if not record.get("harness_ready"):
            if not self._ensure_harness(record):
                return None
        base = record.get("harness_base")
        return str(base) if base else None

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

        port = self._allocate_sidecar_port()
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
            "harness": self._harness,
            "phase": PHASE_RUNNING,
            "agent_ready": True,
            "harness_ready": False,
        }
        self._workspaces[workspace_id] = record
        record["_proc"] = proc
        if self._harness == "opencode":
            harness_ready = self._ensure_harness(record)
            if not harness_ready:
                self._stop_sidecar(record)
                self._stop_harness(record)
                shutil.rmtree(checkout, ignore_errors=True)
                self._workspaces.pop(workspace_id, None)
                raise ProvisionFailedError(
                    "OpenCode harness did not become healthy "
                    f"(is `{self._resolve_opencode_bin()}` installed?)"
                )
            record["agent_ready"] = True
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
        lines = [
            f"checkout: {record.get('checkout')}",
            f"sidecar: {record.get('sidecar_base')}",
            f"branch: {record.get('branch')}",
        ]
        if record.get("harness_base"):
            lines.append(f"harness: {record.get('harness_base')}")
        return lines

    def get_status(self, *, workspace_id: str) -> WorkspaceStatus:
        return self._status(workspace_id)

    def start(
        self, *, workspace_id: str, params: dict[str, str] | None = None
    ) -> WorkspaceStatus:
        del params
        record = self._record(workspace_id)
        proc = record.get("_proc")
        sidecar_ok = True
        if not isinstance(proc, subprocess.Popen) or proc.poll() is not None:
            checkout = Path(record["checkout"])
            port = int(record["port"])
            secret = str(record["sidecar_secret"])
            proc = self._start_sidecar(checkout, port, secret)
            record["_proc"] = proc
            sidecar_ok = self._wait_for_sidecar(str(record["sidecar_base"]), secret)
        harness_ok = True
        if self._harness == "opencode":
            harness_ok = self._ensure_harness(record)
        if not sidecar_ok or not harness_ok:
            record["phase"] = PHASE_ERROR
            record["agent_ready"] = False
            return self._status(workspace_id)
        record["phase"] = PHASE_RUNNING
        record["agent_ready"] = True
        return self._status(workspace_id)

    def stop(self, *, workspace_id: str) -> WorkspaceStatus:
        record = self._record(workspace_id)
        self._stop_sidecar(record)
        self._stop_harness(record)
        record["phase"] = PHASE_STOPPED
        record["agent_ready"] = False
        record["harness_ready"] = False
        return self._status(workspace_id)

    def delete(self, *, workspace_id: str) -> None:
        record = self._record(workspace_id)
        self._stop_sidecar(record)
        self._stop_harness(record)
        checkout = Path(record["checkout"])
        shutil.rmtree(checkout, ignore_errors=True)
        self._workspaces.pop(workspace_id, None)

    def get_access(
        self, *, workspace_id: str, user_id: str, app_slug: str
    ) -> WorkspaceAccess:
        del workspace_id, user_id, app_slug
        # Local sandboxes have no embedded IDE — the sidecar is agent-only HTTP.
        return WorkspaceAccess(url="", token=None)
