from __future__ import annotations

import json
import re
import shutil
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from naas_abi_core.services.coding_environment.adapters.secondary.OpencodeHarnessClient import (
    wait_for_healthy as wait_for_opencode_healthy,
)
from naas_abi_core.services.coding_environment.CodingEnvironmentPorts import (
    PHASE_ERROR,
    PHASE_RUNNING,
    PHASE_STOPPED,
    AccessDeniedError,
    ICodingEnvironmentAdapter,
    InvalidRequestError,
    ProvisionFailedError,
    WorkspaceAccess,
    WorkspaceNameConflictError,
    WorkspaceNotFoundError,
    WorkspaceStatus,
    WorkspaceTemplate,
    environment_name_ok,
)
from naas_abi_core.services.source_control.names import ref_ok, segment_ok
from naas_abi_core.utils.process_environment import allowed_environment

_SIDECAR_SCRIPT = Path(__file__).with_name("abi_sidecar.py")
_DEFAULT_PORT_START = 18000
_DEFAULT_PORT_END = 18100
_DEFAULT_HARNESS_PORT_START = 18200
_DEFAULT_HARNESS_PORT_END = 18300
_HEALTH_TIMEOUT_S = 15.0
HarnessKind = Literal["none", "opencode"]
# A principal id as a directory name.
_USER_DIR = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,199}")
# Every git call: the cloned repository's hooks and fsmonitor never run.
_SAFE_GIT = ("git", "-c", "core.hooksPath=/dev/null", "-c", "core.fsmonitor=false")

SINGLE_USER_ONLY = (
    "The local_directory coding environment runs workspaces on the engine host, "
    "as the engine's own OS user: it is for single-user development only. Set "
    "single_user_development: true to use it, or use the coder adapter."
)


class LocalDirectoryAdapter(ICodingEnvironmentAdapter):
    """Local git checkout + abi_sidecar process (Slides-parity, no Coder).

    Single-user development only. Each workspace is a directory under
    ``workspaces_root/{user_id}/{name}`` with a sidecar listening on localhost,
    run as the engine's own OS user: it is no sandbox, so the adapter must be
    turned on explicitly (``single_user_development``) and serves one user,
    whose workspaces it keeps (another user's provision is refused). The
    sidecar and the OpenCode harness start with an allow-listed environment and
    a home of their own, never the engine's environment; the harness gets its
    own provider credentials file. Repositories are cloned only from the
    platform's forge: the local git root (``repos_root``) or ``forge_url``.
    ``get_runtime_binding`` returns the base URL and bearer secret for agent
    tools.
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
        single_user_development: bool = False,
        repos_root: str | None = None,
        forge_url: str | None = None,
    ) -> None:
        if not single_user_development:
            raise ValueError(SINGLE_USER_ONLY)
        self._repos_root = (
            Path(repos_root).expanduser().resolve() if repos_root else None
        )
        self._forge = urllib.parse.urlsplit(forge_url) if forge_url else None
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

    def _home(self, checkout: Path) -> Path:
        """The workspace runtime's own home, beside its checkout (never the
        engine's): ``workspaces_root/{user}/.home/{name}``."""
        home = checkout.parent / ".home" / checkout.name
        home.mkdir(parents=True, exist_ok=True)
        return home

    def _start_sidecar(self, checkout: Path, port: int, secret: str) -> subprocess.Popen[str]:
        env = allowed_environment(
            home=str(self._home(checkout)),
            extra={
                "ABI_SIDECAR_ROOT": str(checkout),
                "ABI_SIDECAR_SECRET": secret,
                "ABI_SIDECAR_PORT": str(port),
            },
        )
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

    def _resolve_opencode_bin(self) -> str:
        from naas_abi_core.services.agent.OpencodeAgent import resolve_opencode_bin

        return resolve_opencode_bin(self._opencode_bin)

    def _start_opencode(self, checkout: Path, port: int) -> subprocess.Popen[str]:
        from naas_abi_core.services.agent.OpencodeAgent import OpencodeAgent

        home = self._home(checkout)
        env = allowed_environment(home=str(home))
        # Its own credentials: the configured OpenCode providers, in its own
        # data directory, never the engine's files or environment.
        OpencodeAgent.write_opencode_auth_file(
            Path(env["XDG_DATA_HOME"]) / "opencode" / "auth.json"
        )
        return subprocess.Popen(
            [self._resolve_opencode_bin(), "serve", "--port", str(port)],
            cwd=str(checkout),
            env=env,
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

    def ensure_user(
        self,
        *,
        external_id: str,
        email: str,
        username: str,
        vouched_email: bool = False,
    ) -> str:
        del email, username, vouched_email
        if external_id not in self._users:
            self._users[external_id] = external_id
        return self._users[external_id]

    def find_user(self, *, external_id: str) -> str | None:
        # A local user is the principal itself.
        return external_id

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
        self._require_single_user(user_id)
        for existing in self._workspaces.values():
            if existing["user_id"] == user_id and existing["name"] == name:
                raise WorkspaceNameConflictError(
                    f"workspace '{name}' already exists for user {user_id}"
                )

        params = dict(params or {})
        branch = params.get("branch", "main")
        if not ref_ok(branch):
            raise InvalidRequestError(f"Invalid branch: {branch!r}")
        repo_url = params.get("repo_url", "").strip()
        if repo_url:
            self._require_forge_url(repo_url)
        sidecar_secret = params.get("sidecar_secret") or uuid.uuid4().hex

        checkout = self._checkout(user_id, name)
        if checkout.exists() or checkout.is_symlink():
            # Never replaced: whatever is there is not this new workspace's.
            raise ProvisionFailedError(
                f"workspace directory '{name}' already exists for user {user_id}"
            )
        checkout.parent.mkdir(parents=True, exist_ok=True)

        if repo_url:
            clone = subprocess.run(
                [*_SAFE_GIT, "clone", "--branch", branch, "--", repo_url, str(checkout)],
                capture_output=True,
                text=True,
                check=False,
            )
            if clone.returncode != 0:
                shutil.rmtree(checkout, ignore_errors=True)
                # Not git's own words: they may carry the clone URL's credentials.
                raise ProvisionFailedError(
                    f"git clone of branch {branch} failed (exit {clone.returncode})"
                )
        else:
            checkout.mkdir()
            subprocess.run([*_SAFE_GIT, "init", "-b", branch], cwd=checkout, check=True)

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
            "created_at": datetime.now(UTC).isoformat(),
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

    def _require_single_user(self, user_id: str) -> None:
        """One user's workspaces only: the runtime is the engine's own OS user,
        so a second user would share it with the first (and with the engine)."""
        others = {
            str(record.get("user_id") or "")
            for record in self._workspaces.values()
        } - {user_id}
        if others:
            raise AccessDeniedError(
                "local_directory serves a single user, whose workspaces exist here"
            )

    def _checkout(self, user_id: str, name: str) -> Path:
        """``workspaces_root/{user_id}/{name}``, and nowhere else."""
        if not environment_name_ok(name):
            raise InvalidRequestError(f"Invalid environment name: {name!r}")
        if not _USER_DIR.fullmatch(user_id or "") or user_id in (".", ".."):
            raise InvalidRequestError(f"Invalid user: {user_id!r}")
        user_root = self._root / user_id
        checkout = user_root / name
        resolved = checkout.parent.resolve() / checkout.name
        if resolved.parent != user_root.resolve() or self._root not in resolved.parents:
            raise InvalidRequestError(f"Invalid environment name: {name!r}")
        return checkout

    def _require_forge_url(self, repo_url: str) -> None:
        """A repository of the platform's forge only: one ``<owner>/<name>`` of
        the local git root, or of ``forge_url``. Never another path on this
        host, another host, or another scheme."""
        if repo_url.startswith("-") or any(ord(c) < 32 for c in repo_url):
            raise InvalidRequestError("Repositories are cloned from the platform's forge")
        parts = urllib.parse.urlsplit(repo_url)
        if parts.scheme == "file" and self._repos_root is not None:
            path = Path(urllib.parse.unquote(parts.path))
            if (
                not parts.netloc
                and path.is_absolute()
                and path.parent.parent == self._repos_root
                and segment_ok(path.parent.name)
                and segment_ok(path.name)
                and (path / ".git").is_dir()
                and not path.is_symlink()
            ):
                return
        forge = self._forge
        if (
            forge is not None
            and parts.scheme in ("http", "https")
            and parts.scheme == forge.scheme
            and parts.hostname == forge.hostname
            and parts.port == forge.port
            and not parts.query
            and not parts.fragment
        ):
            segments = parts.path.strip("/").removesuffix(".git").split("/")
            prefix = [s for s in forge.path.strip("/").split("/") if s]
            if (
                segments[: len(prefix)] == prefix
                and len(segments) == len(prefix) + 2
                and all(segment_ok(s) for s in segments[len(prefix) :])
            ):
                return
        raise InvalidRequestError("Repositories are cloned from the platform's forge")

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
            owner=str(record.get("user_id") or ""),
            template=self.TEMPLATE_ID,
            created_at=record.get("created_at"),
        )

    def list_environments(self, *, user_id: str) -> list[WorkspaceStatus]:
        return [
            self._status(workspace_id)
            for workspace_id, record in self._workspaces.items()
            if record.get("user_id") == user_id
        ]

    def list_all_environments(self) -> list[WorkspaceStatus]:
        return [self._status(workspace_id) for workspace_id in self._workspaces]

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
        shutil.rmtree(checkout.parent / ".home" / checkout.name, ignore_errors=True)
        self._workspaces.pop(workspace_id, None)

    def get_access(
        self, *, workspace_id: str, user_id: str, app_slug: str
    ) -> WorkspaceAccess:
        del workspace_id, user_id, app_slug
        # Local sandboxes have no embedded IDE — the sidecar is agent-only HTTP.
        return WorkspaceAccess(url="", token=None)
