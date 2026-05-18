"""
Local dev runtime: starts ABI services as native uv/pnpm processes, no Docker.

Multiple worktrees can run concurrently — each worktree gets a deterministic
per-service port offset derived from its absolute path. Storage is
worktree-local (lives under `./storage`), so there is no cross-worktree state
collision.

Managed services:
  - api         (FastAPI, uvicorn)
  - dagster     (Dagster dev UI)
  - nexus-web   (Next.js dev server)
"""

from __future__ import annotations

import collections
import errno
import hashlib
import json
import os
import shutil
import signal
import socket
import subprocess
import sys
import termios
import threading
import time
import tty
import urllib.error
import urllib.request
import webbrowser
from dataclasses import dataclass
from pathlib import Path

import click
from rich.console import Console, Group
from rich.live import Live
from rich.table import Table
from rich.text import Text

DEV_DIR_NAME = ".abi/dev"
INSTANCE_FILENAME = "instance.json"

PORT_OFFSET_RANGE = 900  # ~3-digit per-worktree offset

# Per-service port bases — chosen so that base + offset ranges never overlap.
SERVICE_PORT_BASES = {
    "oxigraph": 7878,   # 7878..8777
    "api": 9879,        # 9879..10778
    "dagster": 11000,   # 11000..11899
    "nexus-web": 12000, # 12000..12899
}

NEXUS_ROOT = Path("libs/naas-abi/naas_abi/apps/nexus")
NEXUS_WEB_DIR = NEXUS_ROOT / "apps" / "web"

# Order matters: oxigraph must come up before api/dagster, since they connect
# to it on boot. nexus-web is independent of oxigraph but ordered last so
# the API URL is available when Next.js starts polling it.
ALL_SERVICES = ("oxigraph", "api", "dagster", "nexus-web")


@dataclass(frozen=True)
class ServiceSpec:
    name: str
    port: int
    log_relpath: str
    pid_relpath: str


# =============================================================================
# Project paths / instance allocation
# =============================================================================

def _project_root() -> Path:
    # The `abi` entrypoint chdir's to the project root before dispatching.
    return Path.cwd().resolve()


def _dev_dir() -> Path:
    return _project_root() / DEV_DIR_NAME


def _instance_path() -> Path:
    return _dev_dir() / INSTANCE_FILENAME


def _compute_offset(project_root: Path) -> int:
    digest = hashlib.sha256(str(project_root).encode("utf-8")).digest()
    return int.from_bytes(digest[:4], "big") % PORT_OFFSET_RANGE


def _load_or_create_instance() -> dict:
    path = _instance_path()
    if path.exists():
        data = json.loads(path.read_text())
        # Backwards-compat: fill in any newly-added services.
        ports = data.setdefault("ports", {})
        offset = data["offset"]
        for service, base in SERVICE_PORT_BASES.items():
            ports.setdefault(service, base + offset)
        return data

    root = _project_root()
    offset = _compute_offset(root)
    data = {
        "project_root": str(root),
        "offset": offset,
        "ports": {
            service: base + offset for service, base in SERVICE_PORT_BASES.items()
        },
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n")
    return data


def _service_spec(name: str, port: int) -> ServiceSpec:
    return ServiceSpec(
        name=name,
        port=port,
        log_relpath=f"logs/{name}.log",
        pid_relpath=f"{name}.pid",
    )


def _log_path(spec: ServiceSpec) -> Path:
    return _dev_dir() / spec.log_relpath


def _pid_path(spec: ServiceSpec) -> Path:
    return _dev_dir() / spec.pid_relpath


# =============================================================================
# Process helpers
# =============================================================================

def _port_in_use(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.3)
        try:
            sock.bind(("127.0.0.1", port))
        except OSError as exc:
            return exc.errno in (errno.EADDRINUSE, errno.EACCES)
    return False


def _read_pid(spec: ServiceSpec) -> int | None:
    path = _pid_path(spec)
    if not path.exists():
        return None
    try:
        return int(path.read_text().strip())
    except (ValueError, OSError):
        return None


def _pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except OSError as exc:
        return exc.errno == errno.EPERM
    return True


def _ensure_storage_layout() -> None:
    (_project_root() / "storage").mkdir(parents=True, exist_ok=True)
    (_dev_dir() / "logs").mkdir(parents=True, exist_ok=True)


def _spawn(spec: ServiceSpec, cmd: list[str], cwd: Path, env: dict[str, str]) -> int:
    log_file = _log_path(spec)
    log_file.parent.mkdir(parents=True, exist_ok=True)
    # Truncate per session so each `dev up` shows a fresh log.
    log_fh = open(log_file, "wb", buffering=0)
    process = subprocess.Popen(
        cmd,
        cwd=str(cwd),
        env=env,
        stdout=log_fh,
        stderr=subprocess.STDOUT,
        stdin=subprocess.DEVNULL,
        start_new_session=True,
    )
    return process.pid


def _http_ready(port: int, path: str = "/", timeout: float = 1.0) -> bool:
    url = f"http://127.0.0.1:{port}{path}"
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:  # nosec B310 - localhost probe
            return getattr(response, "status", 200) < 500
    except urllib.error.HTTPError as exc:
        return exc.code < 500
    except (urllib.error.URLError, TimeoutError, ConnectionError):
        return False


def _wait_until_ready(port: int, max_wait: float = 90.0, path: str = "/") -> bool:
    deadline = time.monotonic() + max_wait
    while time.monotonic() < deadline:
        if _http_ready(port, path=path):
            return True
        time.sleep(1.0)
    return False


# =============================================================================
# Per-service launchers
# =============================================================================

def _oxigraph_url(ports: dict[str, int]) -> str:
    return f"http://127.0.0.1:{ports['oxigraph']}"


def _launch_oxigraph(spec: ServiceSpec) -> int:
    store_path = _project_root() / "storage" / "triplestore" / "oxigraph"
    store_path.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    cmd = [
        "uv",
        "run",
        "python",
        "-m",
        "naas_abi_core.services.triple_store.oxigraph_server",
        "--location",
        str(store_path),
        "--bind",
        f"127.0.0.1:{spec.port}",
    ]
    return _spawn(spec, cmd, _project_root(), env)


def _launch_api(spec: ServiceSpec, ports: dict[str, int]) -> int:
    env = os.environ.copy()
    env["ABI_PORT"] = str(spec.port)
    env["ABI_HOST"] = env.get("ABI_HOST", "127.0.0.1")
    # Point the triple-store adapter at the worktree-local oxigraph server.
    env["OXIGRAPH_URL"] = _oxigraph_url(ports)
    nexus_url = f"http://127.0.0.1:{ports['nexus-web']}"
    extra = env.get("ABI_CORS_EXTRA_ORIGINS", "")
    extra_list = [o for o in extra.split(",") if o.strip()]
    if nexus_url not in extra_list:
        extra_list.append(nexus_url)
    env["ABI_CORS_EXTRA_ORIGINS"] = ",".join(extra_list)
    cmd = ["uv", "run", "python", "-m", "naas_abi_core.apps.api.api"]
    return _spawn(spec, cmd, _project_root(), env)


def _launch_dagster(spec: ServiceSpec, ports: dict[str, int]) -> int:
    env = os.environ.copy()
    env.setdefault("DAGSTER_HOME", str(_project_root() / ".dagster"))
    Path(env["DAGSTER_HOME"]).mkdir(parents=True, exist_ok=True)
    env["OXIGRAPH_URL"] = _oxigraph_url(ports)
    cmd = [
        "uv",
        "run",
        "dagster",
        "dev",
        "--host",
        "127.0.0.1",
        "--port",
        str(spec.port),
        "-m",
        "naas_abi_core.apps.dagster.dagster",
    ]
    return _spawn(spec, cmd, _project_root(), env)


def _launch_nexus_web(spec: ServiceSpec, ports: dict[str, int]) -> int:
    web_dir = _project_root() / NEXUS_WEB_DIR
    nexus_root = _project_root() / NEXUS_ROOT
    if not web_dir.exists():
        raise click.ClickException(
            f"Nexus web directory not found: {web_dir}. "
            "Check that the naas-abi package is checked out."
        )

    runner = shutil.which("pnpm") or shutil.which("npx")
    if runner is None:
        raise click.ClickException(
            "Neither `pnpm` nor `npx` is on PATH. Install Node.js / pnpm "
            "to run the Nexus web dev server."
        )

    # Auto-install Nexus JS deps when missing. The monorepo uses pnpm
    # workspaces, so install must run from the Nexus root, not the web app.
    if not (web_dir / "node_modules").exists():
        pnpm = shutil.which("pnpm")
        if pnpm is None:
            raise click.ClickException(
                "nexus-web has no node_modules and `pnpm` is not on PATH. "
                "Install pnpm (https://pnpm.io/installation) and retry."
            )
        click.echo(
            "nexus-web: node_modules missing — running `pnpm install` "
            f"in {NEXUS_ROOT} (this can take a few minutes the first time)..."
        )
        result = subprocess.run(
            [pnpm, "install"],
            cwd=str(nexus_root),
        )
        if result.returncode != 0:
            raise click.ClickException(
                f"`pnpm install` failed (exit {result.returncode}). "
                "Inspect the output above and re-run `abi dev up` once fixed."
            )
        click.echo("nexus-web: dependencies installed.")

    env = os.environ.copy()
    env["PORT"] = str(spec.port)
    env["NEXT_PUBLIC_API_URL"] = f"http://127.0.0.1:{ports['api']}"
    env["NEXT_PUBLIC_NEXUS_ENV"] = env.get("NEXT_PUBLIC_NEXUS_ENV", "local")
    env["NODE_ENV"] = env.get("NODE_ENV", "development")

    if runner.endswith("pnpm"):
        cmd = [runner, "exec", "next", "dev", "--port", str(spec.port)]
    else:
        cmd = [runner, "next", "dev", "--port", str(spec.port)]
    return _spawn(spec, cmd, web_dir, env)


# Readiness paths per service. Empty string == skip probing.
SERVICE_READY_PATHS = {
    "oxigraph": "/health",
    "api": "/",
    "dagster": "/",
    "nexus-web": "/",
}


def _start_service(name: str, ports: dict[str, int]) -> ServiceSpec:
    spec = _service_spec(name, ports[name])

    existing_pid = _read_pid(spec)
    if existing_pid and _pid_alive(existing_pid):
        click.echo(f"{name}: already running (pid {existing_pid})")
        return spec

    if _port_in_use(spec.port):
        raise click.ClickException(
            f"{name}: port {spec.port} is in use. Stop the conflicting "
            f"process or delete {_instance_path()} to re-allocate."
        )

    if name == "oxigraph":
        pid = _launch_oxigraph(spec)
    elif name == "api":
        pid = _launch_api(spec, ports)
    elif name == "nexus-web":
        pid = _launch_nexus_web(spec, ports)
    elif name == "dagster":
        pid = _launch_dagster(spec, ports)
    else:
        raise click.ClickException(f"Unknown service: {name}")
    _pid_path(spec).write_text(f"{pid}\n")
    click.echo(f"{name}: started (pid {pid}) on http://127.0.0.1:{spec.port}")
    return spec


def _stop_service(name: str, port: int) -> None:
    spec = _service_spec(name, port)
    pid = _read_pid(spec)
    if pid is None:
        return
    if not _pid_alive(pid):
        _pid_path(spec).unlink(missing_ok=True)
        return
    try:
        os.killpg(os.getpgid(pid), signal.SIGTERM)
    except ProcessLookupError:
        _pid_path(spec).unlink(missing_ok=True)
        return

    deadline = time.monotonic() + 10.0
    while time.monotonic() < deadline:
        if not _pid_alive(pid):
            break
        time.sleep(0.2)
    else:
        try:
            os.killpg(os.getpgid(pid), signal.SIGKILL)
        except ProcessLookupError:
            pass

    _pid_path(spec).unlink(missing_ok=True)
    click.echo(f"{name}: stopped (pid {pid})")


# =============================================================================
# Foreground log streaming
# =============================================================================

# Per-service color used in log prefixes and the status panel.
_SERVICE_STYLES = {
    "oxigraph": "cyan",
    "api": "green",
    "dagster": "blue",
    "nexus-web": "magenta",
}


LOG_BUFFER_LINES = 2000  # per-service ring buffer cap


def _build_status_panel(
    started: list[ServiceSpec],
    ports: dict[str, int],
    focused: str,
    health_state: dict[str, dict],
) -> Table:
    """Render the status table from cached health state — no I/O here.

    `health_state[name]` should contain keys `pid`, `alive`, `ready`. The
    health probe loop refreshes it asynchronously so this stays instant.
    """
    table = Table(
        show_header=True,
        header_style="bold",
        expand=True,
        title=None,
    )
    table.add_column("#", width=3)
    table.add_column("Service")
    table.add_column("URL")
    table.add_column("PID")
    table.add_column("Health", justify="center")

    started_names = {spec.name for spec in started}
    visible = [name for name in ALL_SERVICES if name in started_names]
    for idx, name in enumerate(visible, start=1):
        port = ports[name]
        style = _SERVICE_STYLES.get(name, "white")
        state = health_state.get(name, {})
        pid = state.get("pid")
        alive = state.get("alive", False)
        ready = state.get("ready", False)

        if pid is None:
            pid_cell = Text("-", style="dim")
        elif alive:
            pid_cell = Text(str(pid))
        else:
            pid_cell = Text(f"{pid} (dead)", style="red")

        if pid is not None and not alive:
            health = Text("● crashed", style="red")
        elif ready:
            health = Text("● ready", style="green")
        else:
            health = Text("● starting", style="yellow")

        is_focus = name == focused
        marker = f"[bold]›{idx}[/bold]" if is_focus else f" {idx}"
        name_text = Text(name, style=f"bold {style}" if is_focus else style)

        table.add_row(
            marker,
            name_text,
            f"http://127.0.0.1:{port}",
            pid_cell,
            health,
        )

    return table


def _health_probe_loop(
    started: list[ServiceSpec],
    ports: dict[str, int],
    health_state: dict[str, dict],
    lock: threading.Lock,
    stop_event: threading.Event,
) -> None:
    """Background refresh of pid liveness + HTTP readiness."""
    while not stop_event.is_set():
        for spec in started:
            port = ports[spec.name]
            spec_ref = _service_spec(spec.name, port)
            pid = _read_pid(spec_ref)
            alive = pid is not None and _pid_alive(pid)
            ready = (
                _http_ready(
                    port,
                    path=SERVICE_READY_PATHS.get(spec.name, "/"),
                    timeout=0.4,
                )
                if alive
                else False
            )
            with lock:
                health_state[spec.name] = {
                    "pid": pid,
                    "alive": alive,
                    "ready": ready,
                }
            if stop_event.is_set():
                return
        # Probe cadence — short enough to feel live, long enough not to
        # hammer the API for /-route logs.
        stop_event.wait(timeout=1.5)


def _format_log_line(service_name: str, line: str) -> Text:
    """Render `[service ] line` with the service-color prefix."""
    style = _SERVICE_STYLES.get(service_name, "white")
    out = Text()
    out.append(f"[{service_name:<9}] ", style=style)
    out.append(line)
    return out


class _KeyboardReader:
    """Reads single chars in raw mode without echo. macOS / Linux only.

    Intentionally does NOT enable xterm mouse reporting — we want the
    terminal's native scrollback / text selection to keep working.
    """

    def __init__(self, on_key) -> None:
        self._on_key = on_key
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._old_settings: list | None = None
        self._fd = sys.stdin.fileno() if sys.stdin.isatty() else None

    def start(self) -> None:
        if self._fd is None:
            return
        self._old_settings = termios.tcgetattr(self._fd)
        tty.setcbreak(self._fd)
        self._thread = threading.Thread(target=self._run, daemon=True, name="keyboard")
        self._thread.start()

    def _read_csi(self) -> bytes | None:
        """Read the rest of a CSI sequence after ESC [.

        Returns the full payload after `[` (excluding the introducer), ending
        with the final byte (in the range 0x40-0x7E). Returns None on EOF or
        if the sequence doesn't arrive in time.
        """
        import select

        assert self._fd is not None
        payload = b""
        deadline = time.monotonic() + 0.1
        while time.monotonic() < deadline and len(payload) < 64:
            timeout = max(0.0, deadline - time.monotonic())
            ready, _, _ = select.select([self._fd], [], [], timeout)
            if not ready:
                if payload:
                    deadline += 0.02  # tiny grace for slow terminals
                    continue
                return None
            try:
                b = os.read(self._fd, 1)
            except OSError:
                return None
            if not b:
                return None
            payload += b
            # CSI final byte.
            if 0x40 <= b[0] <= 0x7E:
                return payload
        return payload or None

    def _decode_csi(self, payload: bytes) -> str | None:
        """Map a CSI payload (without the leading ESC [) to a logical key."""
        if payload in (b"A",):
            return "UP"
        if payload in (b"B",):
            return "DOWN"
        if payload == b"5~":
            return "PGUP"
        if payload == b"6~":
            return "PGDN"
        # SGR mouse: <btn>;<x>;<y>M|m  (we only care about press = M).
        if payload.startswith(b"<") and payload[-1:] in (b"M", b"m"):
            try:
                body = payload[1:-1].decode("ascii")
                parts = body.split(";")
                btn = int(parts[0])
            except (ValueError, IndexError):
                return None
            if payload[-1:] == b"M":
                # Buttons 64 / 65 are wheel up / wheel down. Shift/Ctrl
                # variants set the modifier bits — strip them.
                base = btn & ~0x1C  # clear shift/meta/ctrl bits
                if base == 64:
                    return "WHEELUP"
                if base == 65:
                    return "WHEELDOWN"
        return None

    def _run(self) -> None:
        import select

        assert self._fd is not None
        while not self._stop.is_set():
            ready, _, _ = select.select([self._fd], [], [], 0.2)
            if not ready:
                continue
            try:
                ch = os.read(self._fd, 1)
            except OSError:
                return
            if not ch:
                return

            if ch == b"\x1b":
                # Expect CSI introducer next.
                ready2, _, _ = select.select([self._fd], [], [], 0.05)
                if not ready2:
                    # Bare ESC — ignore.
                    continue
                try:
                    nxt = os.read(self._fd, 1)
                except OSError:
                    return
                if nxt != b"[":
                    continue
                payload = self._read_csi()
                if payload is None:
                    continue
                mapped = self._decode_csi(payload)
                if mapped is None:
                    continue
                try:
                    self._on_key(mapped)
                except Exception:
                    pass
                continue

            try:
                self._on_key(ch.decode("utf-8", errors="replace"))
            except Exception:
                pass

    def stop(self) -> None:
        self._stop.set()
        if self._fd is not None and self._old_settings is not None:
            try:
                termios.tcsetattr(self._fd, termios.TCSADRAIN, self._old_settings)
            except termios.error:
                pass
        if self._thread is not None:
            self._thread.join(timeout=0.5)


RECENT_DUMP_LINES = 30


def _stream_log_to_console(
    spec: ServiceSpec,
    buffer: collections.deque,
    focus_state: dict,
    focus_lock: threading.Lock,
    console: Console,
    stop_event: threading.Event,
) -> None:
    """Tail a service's log file, buffer every line, and print it via the
    rich Console if the current filter accepts this service.

    Printing through `console.print` while a `Live` is active makes Rich
    insert the line ABOVE the pinned region — so logs scroll naturally in
    the terminal and native scrollback / selection keep working.
    """
    log_file = _log_path(spec)
    for _ in range(50):
        if log_file.exists():
            break
        if stop_event.is_set():
            return
        time.sleep(0.1)
    try:
        fh = open(log_file, "rb")
    except OSError:
        return
    try:
        pending = b""
        while not stop_event.is_set():
            chunk = fh.read(4096)
            if not chunk:
                time.sleep(0.15)
                continue
            pending += chunk
            while b"\n" in pending:
                line_bytes, pending = pending.split(b"\n", 1)
                line = line_bytes.decode("utf-8", errors="replace")
                buffer.append(line)
                with focus_lock:
                    focused = focus_state["value"]
                if focused == "all" or focused == spec.name:
                    console.print(_format_log_line(spec.name, line), soft_wrap=False)
    finally:
        fh.close()


def _open_letter_map(started: list[ServiceSpec]) -> dict[str, str]:
    """Map first-letter shortcut → service name, skipping collisions.

    Two services starting with the same letter would race for the key, so
    drop both rather than silently bind to one of them.
    """
    seen: dict[str, str | None] = {}
    for spec in started:
        first = spec.name[:1].lower()
        if not first.isalpha():
            continue
        if first in seen:
            seen[first] = None  # mark as collision
        else:
            seen[first] = spec.name
    return {k: v for k, v in seen.items() if v is not None}


def _build_hint(
    started: list[ServiceSpec],
    focused: str,
) -> Text:
    """The keybind helper line that lives right under the status table."""
    out = Text()
    out.append("Filter:  ", style="dim")
    for i, spec in enumerate(started, start=1):
        style = _SERVICE_STYLES.get(spec.name, "white")
        active = focused == spec.name
        prefix = "[" if active else " "
        suffix = "]" if active else " "
        out.append(
            f"{prefix}{i}={spec.name}{suffix}",
            style=f"bold {style}" if active else style,
        )
        out.append(" ")
    all_active = focused == "all"
    out.append(
        " [0=all] " if all_active else "  0=all  ",
        style="bold" if all_active else "dim",
    )

    open_map = _open_letter_map(started)
    if open_map:
        out.append("    open:", style="dim")
        for letter, name in open_map.items():
            style = _SERVICE_STYLES.get(name, "white")
            out.append(f" {letter}={name}", style=style)
    out.append("    q or Ctrl+C: stop", style="dim")
    return out


def _follow_until_interrupt(started: list[ServiceSpec], ports: dict[str, int]) -> None:
    """Live status bar + hint pinned at the bottom; logs scroll above them.

    The terminal's own scrollback works (no alt-screen). Hotkeys 1/2/3 filter
    which service streams; 0 returns to interleaved.
    """
    console = Console()
    stop_event = threading.Event()
    threads: list[threading.Thread] = []

    buffers: dict[str, collections.deque] = {
        spec.name: collections.deque(maxlen=LOG_BUFFER_LINES) for spec in started
    }
    health_state: dict[str, dict] = {
        spec.name: {"pid": None, "alive": False, "ready": False} for spec in started
    }
    health_lock = threading.Lock()

    # Filter state: "all" or a service name.
    focus_state = {"value": "all"}
    focus_lock = threading.Lock()
    index_to_name = {i + 1: spec.name for i, spec in enumerate(started)}
    open_letters = _open_letter_map(started)

    live_holder: dict[str, Live | None] = {"value": None}

    def render() -> Group:
        with focus_lock:
            focused = focus_state["value"]
        with health_lock:
            snapshot = {k: dict(v) for k, v in health_state.items()}
        status = _build_status_panel(started, ports, focused, snapshot)
        hint = _build_hint(started, focused)
        return Group(status, hint)

    def force_refresh() -> None:
        live = live_holder["value"]
        if live is not None:
            try:
                live.update(render(), refresh=True)
            except Exception:
                pass

    def dump_recent(name: str) -> None:
        """Print the last RECENT_DUMP_LINES of a service to give context."""
        recent = list(buffers[name])[-RECENT_DUMP_LINES:]
        if not recent:
            return
        style = _SERVICE_STYLES.get(name, "white")
        console.print(
            Text.assemble(
                ("── recent ", "dim"),
                (name, style),
                (f" ({len(recent)} lines) ──", "dim"),
            )
        )
        for line in recent:
            console.print(_format_log_line(name, line), soft_wrap=False)

    def open_service(name: str) -> None:
        port = ports[name]
        url = f"http://127.0.0.1:{port}"
        style = _SERVICE_STYLES.get(name, "white")
        console.print(
            Text.assemble(
                ("── opening ", "dim"),
                (name, f"bold {style}"),
                (f" at {url} ──", "dim"),
            )
        )
        try:
            webbrowser.open(url)
        except Exception as exc:  # pragma: no cover - best-effort
            console.print(Text(f"   failed to open browser: {exc}", style="red"))

    def on_key(ch: str) -> None:
        if ch in ("q", "Q", "\x03"):
            os.kill(os.getpid(), signal.SIGINT)
            return
        lower = ch.lower()
        if lower in open_letters and lower not in ("q",):
            open_service(open_letters[lower])
            return
        if ch == "0":
            with focus_lock:
                if focus_state["value"] != "all":
                    focus_state["value"] = "all"
                    console.print(
                        Text("── filter cleared: showing all services ──", style="dim")
                    )
            force_refresh()
            return
        if ch.isdigit():
            idx = int(ch)
            if idx in index_to_name:
                new_focus = index_to_name[idx]
                with focus_lock:
                    if focus_state["value"] != new_focus:
                        focus_state["value"] = new_focus
                        style = _SERVICE_STYLES.get(new_focus, "white")
                        console.print(
                            Text.assemble(
                                ("── focused on ", "dim"),
                                (new_focus, f"bold {style}"),
                                (" — only its logs will follow ──", "dim"),
                            )
                        )
                        dump_recent(new_focus)
                force_refresh()
                return

    keyboard = _KeyboardReader(on_key=on_key)

    keyboard.start()
    try:
        with Live(
            render(),
            console=console,
            refresh_per_second=4,
            transient=False,
            screen=False,  # native scrollback works
        ) as live:
            live_holder["value"] = live

            for spec in started:
                t = threading.Thread(
                    target=_stream_log_to_console,
                    args=(
                        spec,
                        buffers[spec.name],
                        focus_state,
                        focus_lock,
                        console,
                        stop_event,
                    ),
                    daemon=True,
                    name=f"log-{spec.name}",
                )
                t.start()
                threads.append(t)

            probe_thread = threading.Thread(
                target=_health_probe_loop,
                args=(started, ports, health_state, health_lock, stop_event),
                daemon=True,
                name="health-probe",
            )
            probe_thread.start()
            threads.append(probe_thread)

            try:
                while True:
                    time.sleep(0.25)
                    live.update(render())
                    with health_lock:
                        any_alive = any(
                            v.get("alive", False) for v in health_state.values()
                        )
                        all_started = all(
                            v.get("pid") is not None for v in health_state.values()
                        )
                    if all_started and not any_alive:
                        break
            except KeyboardInterrupt:
                pass
    finally:
        live_holder["value"] = None
        keyboard.stop()
        stop_event.set()
        console.print(Text("── stopping services ──", style="dim"))
        for spec in reversed(started):
            _stop_service(spec.name, ports[spec.name])
        for t in threads:
            t.join(timeout=1.0)


# =============================================================================
# CLI
# =============================================================================

def _validate_services(selected: tuple[str, ...]) -> list[str]:
    if not selected:
        return list(ALL_SERVICES)
    unknown = [s for s in selected if s not in ALL_SERVICES]
    if unknown:
        raise click.BadParameter(
            f"Unknown service(s): {', '.join(unknown)}. "
            f"Choose from: {', '.join(ALL_SERVICES)}."
        )
    # Preserve canonical order (api → dagster → nexus-web).
    return [s for s in ALL_SERVICES if s in selected]


@click.group("dev")
def dev() -> None:
    """Run ABI services natively for development (no Docker)."""


@dev.command("up")
@click.option(
    "--service",
    "services",
    multiple=True,
    type=click.Choice(ALL_SERVICES),
    help="Limit to the given service(s). Repeat the flag. Default: start all.",
)
@click.option(
    "-d",
    "--detach",
    is_flag=True,
    default=False,
    help="Run in the background and return to the shell immediately.",
)
def dev_up(services: tuple[str, ...], detach: bool) -> None:
    """Start the selected dev services.

    By default this stays in the foreground and streams interleaved logs from
    every started service until you hit Ctrl+C (which stops them cleanly).
    Pass `-d/--detach` to spawn them in the background instead.
    """
    selected = _validate_services(services)
    instance = _load_or_create_instance()
    ports: dict[str, int] = instance["ports"]
    _ensure_storage_layout()

    started: list[ServiceSpec] = []
    try:
        for name in selected:
            spec = _start_service(name, ports)
            started.append(spec)
            # api & dagster connect to the oxigraph HTTP endpoint at engine
            # boot; block briefly until it answers so they don't race-crash.
            if name == "oxigraph" and any(
                n in selected for n in ("api", "dagster")
            ):
                click.echo("oxigraph: waiting for readiness...")
                if not _wait_until_ready(spec.port, max_wait=15.0, path="/health"):
                    click.echo(
                        "⚠ oxigraph did not become ready in 15s — "
                        "downstream services may fail to start. "
                        "Check `.abi/dev/logs/oxigraph.log`.",
                        err=True,
                    )
    except Exception:
        if started:
            click.echo(
                "Startup failed; stopping services that did come up...",
                err=True,
            )
            for spec in reversed(started):
                _stop_service(spec.name, ports[spec.name])
        raise

    if detach:
        click.echo()
        click.echo("ABI dev services:")
        for spec in started:
            click.echo(f"  {spec.name:<10} http://127.0.0.1:{spec.port}")
        click.echo()
        click.echo("Logs: `abi dev logs <service> -f`   Stop: `abi dev down`")
        return

    _follow_until_interrupt(started, ports)


@dev.command("down")
@click.option(
    "--service",
    "services",
    multiple=True,
    type=click.Choice(ALL_SERVICES),
    help="Limit to the given service(s). Default: stop all.",
)
def dev_down(services: tuple[str, ...]) -> None:
    """Stop the selected dev services."""
    selected = _validate_services(services)
    if not _instance_path().exists():
        click.echo("No dev instance allocated — nothing to stop.")
        return
    instance = json.loads(_instance_path().read_text())
    ports: dict[str, int] = instance["ports"]
    # Stop in reverse order so consumers (api) come down after their deps.
    for name in reversed(selected):
        _stop_service(name, ports[name])
    click.echo("Done.")


@dev.command("status")
def dev_status() -> None:
    """Show the current dev instance state."""
    if not _instance_path().exists():
        click.echo("No dev instance allocated yet. Run `abi dev up`.")
        return
    instance = json.loads(_instance_path().read_text())
    click.echo(f"Project: {instance['project_root']}")
    click.echo(f"Offset:  {instance['offset']}")
    click.echo()
    click.echo(f"{'Service':<12} {'Port':<7} {'PID':<10} {'HTTP':<13} URL")
    for name in ALL_SERVICES:
        port = instance["ports"][name]
        spec = _service_spec(name, port)
        pid = _read_pid(spec)
        if pid is None:
            pid_status = "-"
        elif _pid_alive(pid):
            pid_status = f"{pid} (alive)"
        else:
            pid_status = f"{pid} (dead)"
        http = "ready" if _http_ready(port, path=SERVICE_READY_PATHS.get(name, "/")) else "down"
        click.echo(
            f"{name:<12} {port:<7} {pid_status:<10} {http:<13} "
            f"http://127.0.0.1:{port}"
        )


@dev.command("logs")
@click.argument(
    "service",
    type=click.Choice(ALL_SERVICES),
    required=True,
)
@click.option("-f", "--follow", is_flag=True, default=False, help="Tail follow.")
@click.option(
    "-n",
    "--lines",
    type=int,
    default=100,
    show_default=True,
    help="Number of trailing lines to print.",
)
def dev_logs(service: str, follow: bool, lines: int) -> None:
    """Print (and optionally follow) a service's log file."""
    instance = json.loads(_instance_path().read_text()) if _instance_path().exists() else None
    if instance is None:
        click.echo("No dev instance allocated yet. Run `abi dev up`.")
        return
    spec = _service_spec(service, instance["ports"][service])
    log_file = _log_path(spec)
    if not log_file.exists():
        click.echo(f"No log file yet for {service}.")
        return

    if follow:
        os.execvp("tail", ["tail", "-n", str(lines), "-f", str(log_file)])
    else:
        os.execvp("tail", ["tail", "-n", str(lines), str(log_file)])


@dev.command("ports")
def dev_ports() -> None:
    """Print the ports allocated to this worktree."""
    instance = _load_or_create_instance()
    for name in ALL_SERVICES:
        click.echo(f"{name:<12} {instance['ports'][name]}")
