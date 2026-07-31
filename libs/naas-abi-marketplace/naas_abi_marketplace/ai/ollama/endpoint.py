"""Locate a reachable Ollama server across macOS, Linux and Windows WSL.

Ollama is a *local* server, which makes "where is it?" a platform question
rather than a config question. The three supported platforms fail differently:

* **macOS** — installed via the ``.app`` bundle, Homebrew, or the install
  script. Always on the same machine, so ``localhost`` is right.
* **Linux** — install script or distro package, often managed by systemd. Also
  same-machine, so ``localhost`` is right.
* **Windows WSL** — two distinct topologies. Either ollama runs *inside* the
  distro (``localhost`` works), or the user runs the **Ollama Windows app** on
  the host while ABI runs in the Linux VM. In that second case ``localhost``
  inside the VM reaches the VM's own loopback and finds nothing, and the
  address that does work depends on the WSL networking mode:

  - ``networkingMode=mirrored`` — the host shares the VM's loopback, so
    ``localhost`` works after all.
  - NAT (the default) — the host is a separate IP, discoverable as the
    nameserver in ``/etc/resolv.conf``.

  That is the same NAT-vs-mirrored split already documented for the dev stack
  in ``naas_abi_cli.cli.dev`` (see ``BIND_HOST``/``BROWSER_HOST``), so we take
  the same approach: a sensible default, an explicit env override, and no
  guessing where a probe can tell us the answer.

So rather than assume an address, we build an ordered candidate list and use
the first one that actually answers ``GET /api/tags``. Everything that reads
the environment is injectable, so all three platforms are testable from any
machine.
"""

from __future__ import annotations

import os
import platform
import shutil
import urllib.error
import urllib.request
from collections.abc import Callable, Mapping
from pathlib import Path

DEFAULT_PORT = 11434
DEFAULT_BASE_URL = f"http://localhost:{DEFAULT_PORT}"

# Explicit ABI-specific override, checked before ollama's own OLLAMA_HOST so a
# user can point ABI at a different server without disturbing their ollama CLI.
BASE_URL_ENV_VAR = "ABI_OLLAMA_BASE_URL"
OLLAMA_HOST_ENV_VAR = "OLLAMA_HOST"

# A wildcard bind is an accept-any address, not a connect target — same
# reasoning as ``naas_abi_cli.cli.dev.PROBE_HOST``.
_WILDCARD_HOSTS = {"0.0.0.0", "::", "[::]", "*"}  # nosec B104

_PROBE_PATH = "/api/tags"


def normalize_base_url(value: str, default_port: int = DEFAULT_PORT) -> str:
    """Turn any of ollama's accepted host spellings into a base URL.

    ``OLLAMA_HOST`` is a *bind/dial* spec, not a URL: ``11434``,
    ``127.0.0.1``, ``127.0.0.1:11434``, ``:11434`` and ``http://host:11434``
    are all legal. Normalize them all to ``scheme://host:port``.
    """
    raw = value.strip()
    if not raw:
        return DEFAULT_BASE_URL

    scheme = "http"
    if "://" in raw:
        scheme, _, raw = raw.partition("://")
        scheme = scheme or "http"

    raw = raw.rstrip("/")

    # A bare port, as ollama allows ("OLLAMA_HOST=11434").
    if raw.isdigit():
        return f"{scheme}://localhost:{raw}"

    host, port = raw, None
    if raw.startswith("["):  # bracketed IPv6, optionally with :port
        closing = raw.find("]")
        if closing != -1:
            host = raw[: closing + 1]
            remainder = raw[closing + 1 :]
            if remainder.startswith(":"):
                port = remainder[1:]
    elif raw.count(":") == 1:
        host, _, port = raw.partition(":")

    if not host:
        host = "localhost"
    if host in _WILDCARD_HOSTS:
        # Can't dial a wildcard — the intent was "listening everywhere here".
        host = "localhost"

    return f"{scheme}://{host}:{port or default_port}"


def is_wsl(
    *,
    environ: Mapping[str, str] | None = None,
    proc_version_path: str = "/proc/version",
) -> bool:
    """True when running inside a Windows Subsystem for Linux distro.

    Checked two ways because neither is universal: WSL2 sets
    ``WSL_DISTRO_NAME``, and every WSL kernel carries ``microsoft`` in
    ``/proc/version``.
    """
    env = os.environ if environ is None else environ
    if env.get("WSL_DISTRO_NAME") or env.get("WSL_INTEROP"):
        return True
    try:
        return "microsoft" in Path(proc_version_path).read_text(
            encoding="utf-8", errors="replace"
        ).lower()
    except OSError:
        return False


def in_container(
    *,
    dockerenv_path: str = "/.dockerenv",
    containerenv_path: str = "/run/.containerenv",
    cgroup_path: str = "/proc/1/cgroup",
) -> bool:
    """True when running inside a Docker/Podman container.

    Worth distinguishing because the failure it causes is specific: on Linux,
    ``host.docker.internal`` resolves to the bridge gateway, but a stock Ollama
    install listens on ``127.0.0.1`` only, so the connection is refused rather
    than the host being unreachable.
    """
    for path in (dockerenv_path, containerenv_path):
        if Path(path).exists():
            return True
    try:
        cgroups = Path(cgroup_path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return False
    return "docker" in cgroups or "containerd" in cgroups or "libpod" in cgroups


def wsl_host_addresses(resolv_conf_path: str = "/etc/resolv.conf") -> list[str]:
    """Addresses that might reach the Windows host from inside a WSL distro.

    Under NAT networking, WSL writes the host's address as the nameserver in
    ``/etc/resolv.conf``. ``host.docker.internal`` is appended because Docker
    Desktop's WSL integration publishes it and many WSL users have it.
    """
    addresses: list[str] = []
    try:
        for line in Path(resolv_conf_path).read_text(
            encoding="utf-8", errors="replace"
        ).splitlines():
            fields = line.split()
            if len(fields) >= 2 and fields[0] == "nameserver":
                if fields[1] not in addresses:
                    addresses.append(fields[1])
    except OSError:
        pass
    addresses.append("host.docker.internal")
    return addresses


def candidate_base_urls(
    configured: str | None = None,
    *,
    environ: Mapping[str, str] | None = None,
    wsl: bool | None = None,
    resolv_conf_path: str = "/etc/resolv.conf",
) -> list[str]:
    """Ordered, de-duplicated list of base URLs worth trying.

    Most specific first: explicit config, then ABI's override, then ollama's
    own ``OLLAMA_HOST``, then same-machine loopback, and finally — only under
    WSL — the Windows host addresses.
    """
    env = os.environ if environ is None else environ
    in_wsl = is_wsl(environ=env) if wsl is None else wsl

    candidates: list[str] = []

    def add(value: str | None) -> None:
        if not value:
            return
        normalized = normalize_base_url(value)
        if normalized not in candidates:
            candidates.append(normalized)

    add(configured)
    add(env.get(BASE_URL_ENV_VAR))
    add(env.get(OLLAMA_HOST_ENV_VAR))
    add(DEFAULT_BASE_URL)

    if in_wsl:
        # Covers the common WSL setup: Ollama Windows app on the host, ABI in
        # the VM. Harmless under mirrored networking, where localhost already
        # answered and we never get this far.
        for address in wsl_host_addresses(resolv_conf_path):
            add(f"http://{address}:{DEFAULT_PORT}")

    return candidates


def probe_base_url(base_url: str, timeout: float = 0.75) -> bool:
    """True when an Ollama server answers ``/api/tags`` at ``base_url``."""
    request = urllib.request.Request(
        f"{base_url.rstrip('/')}{_PROBE_PATH}",
        method="GET",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:  # nosec B310
            return 200 <= response.status < 300
    except (urllib.error.URLError, OSError, ValueError):
        return False


def resolve_base_url(
    configured: str | None = None,
    *,
    environ: Mapping[str, str] | None = None,
    wsl: bool | None = None,
    resolv_conf_path: str = "/etc/resolv.conf",
    timeout: float = 0.75,
    probe: bool = True,
) -> tuple[str, bool]:
    """Pick the base URL to talk to, and report whether anything answered.

    Returns ``(base_url, reachable)``. When nothing answers we still return the
    best candidate rather than raising: a project must be able to boot with
    ollama not yet started, and the failure then surfaces at first use with a
    clear message instead of blocking startup.

    An **explicit** endpoint — the module's ``base_url`` or
    ``ABI_OLLAMA_BASE_URL`` — is honoured as given and never fallen back past.
    Probing it only reports whether it answered. Searching on would mean that
    pointing ABI at a remote GPU box and having that box go down silently
    reroutes to whatever local server happens to be up, which is a different
    machine with a different model set and no error to say so. Auto-detection
    (loopback, WSL host) still takes the first candidate that answers, because
    there the whole point is to find one.
    """
    env = os.environ if environ is None else environ
    explicit = configured or env.get(BASE_URL_ENV_VAR)
    if explicit:
        base_url = normalize_base_url(explicit)
        return base_url, probe_base_url(base_url, timeout=timeout) if probe else False

    candidates = candidate_base_urls(
        configured, environ=environ, wsl=wsl, resolv_conf_path=resolv_conf_path
    )
    if not probe:
        return candidates[0], False

    for candidate in candidates:
        if probe_base_url(candidate, timeout=timeout):
            return candidate, True

    return candidates[0], False


def find_ollama_binary(
    *,
    system: str | None = None,
    path_exists: Callable[[str], bool] | None = None,
) -> str | None:
    """Locate the ollama executable, checking per-platform install locations.

    ``shutil.which`` covers most cases; the extra paths catch installs that
    aren't on a non-interactive shell's PATH (notably the macOS ``.app`` and
    Homebrew on Apple silicon).
    """
    found = shutil.which("ollama")
    if found:
        return found

    exists: Callable[[str], bool] = (
        (lambda candidate: Path(candidate).exists())
        if path_exists is None
        else path_exists
    )
    current = platform.system() if system is None else system

    extra_paths: list[str] = []
    if current == "Darwin":
        extra_paths = [
            "/usr/local/bin/ollama",
            "/opt/homebrew/bin/ollama",
            "/Applications/Ollama.app/Contents/Resources/ollama",
            str(Path.home() / ".ollama" / "ollama"),
        ]
    elif current == "Linux":
        extra_paths = [
            "/usr/local/bin/ollama",
            "/usr/bin/ollama",
            "/snap/bin/ollama",
            str(Path.home() / ".ollama" / "ollama"),
        ]

    for candidate in extra_paths:
        if exists(candidate):
            return candidate
    return None


def install_hint(
    *,
    system: str | None = None,
    wsl: bool | None = None,
    container: bool | None = None,
) -> str:
    """Platform-correct instructions for getting an Ollama server running.

    A generic "install from ollama.com" is useless on WSL, where the usual
    problem is not a missing install but a server on the *other* side of the
    VM boundary — and equally useless inside a Linux container, where Ollama
    is installed and running but listening only on the host's loopback.
    """
    current = platform.system() if system is None else system
    in_wsl = is_wsl() if wsl is None else wsl
    containerised = in_container() if container is None else container

    # Checked before the WSL branch: a container on Docker Desktop's WSL
    # backend is both, and the bind address is the actionable problem.
    if containerised and current == "Linux":
        return (
            "Ollama is not reachable from inside this container.\n"
            "On Linux, Ollama listens on 127.0.0.1 by default, so the host is\n"
            "resolvable through host.docker.internal but refuses the connection.\n"
            "Bind it where the container can reach it:\n"
            "  sudo systemctl edit ollama\n"
            '    [Service]\n'
            '    Environment="OLLAMA_HOST=0.0.0.0:11434"\n'
            "  sudo systemctl restart ollama\n"
            "Only do this on a trusted network, or restrict it to the Docker\n"
            "bridge (e.g. OLLAMA_HOST=172.17.0.1:11434) and firewall the port.\n"
            f"To use a remote server instead, set {BASE_URL_ENV_VAR}.\n"
            "Docker Desktop on macOS and Windows needs none of this."
        )
    if in_wsl:
        return (
            "Ollama is not reachable from this WSL distro. Either:\n"
            "  - install it inside the distro:  curl -fsSL https://ollama.com/install.sh | sh\n"
            "  - or run the Ollama Windows app on the host and allow it to accept\n"
            "    connections from WSL:  set OLLAMA_HOST=0.0.0.0 for the Windows app,\n"
            "    then restart it.\n"
            f"If the host address is not auto-detected, set {BASE_URL_ENV_VAR} "
            "explicitly, e.g.\n"
            f"  export {BASE_URL_ENV_VAR}=http://$(ip route show default | "
            "awk '{print $3}'):11434"
        )
    if current == "Darwin":
        return (
            "Ollama is not reachable. Install it with one of:\n"
            "  - brew install ollama && brew services start ollama\n"
            "  - download the app from https://ollama.com/download\n"
            "Then confirm it is up:  curl http://localhost:11434/api/tags"
        )
    if current == "Linux":
        return (
            "Ollama is not reachable. Install and start it:\n"
            "  curl -fsSL https://ollama.com/install.sh | sh\n"
            "  sudo systemctl enable --now ollama   # or run: ollama serve\n"
            "Then confirm it is up:  curl http://localhost:11434/api/tags"
        )
    if current == "Windows":
        return (
            "Native Windows is not a supported ABI platform — use WSL.\n"
            "Install WSL, then either install ollama inside the distro or run the\n"
            "Ollama Windows app with OLLAMA_HOST=0.0.0.0 so the distro can reach it."
        )
    return (
        "Ollama is not reachable. See https://ollama.com/download, then confirm "
        "with:  curl http://localhost:11434/api/tags"
    )
