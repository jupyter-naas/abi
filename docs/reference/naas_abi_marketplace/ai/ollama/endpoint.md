# `endpoint` (Ollama endpoint resolution)

## What it is
- Utilities to locate a reachable **local Ollama server** across macOS, Linux, and Windows **WSL**.
- Builds an ordered list of candidate base URLs and optionally **probes** them via `GET /api/tags`.
- Provides helpers to find the `ollama` binary and print platform-specific installation/troubleshooting hints.

## Public API
- `DEFAULT_PORT = 11434`
- `DEFAULT_BASE_URL = "http://localhost:11434"`
- `BASE_URL_ENV_VAR = "ABI_OLLAMA_BASE_URL"`: ABI-specific endpoint override (checked before `OLLAMA_HOST`).
- `OLLAMA_HOST_ENV_VAR = "OLLAMA_HOST"`: Ollama’s own host/bind setting.

### Functions
- `normalize_base_url(value: str, default_port: int = 11434) -> str`
  - Normalizes Ollama-style host specs (e.g. `11434`, `127.0.0.1`, `:11434`, `http://...`) into `scheme://host:port`.
  - Converts wildcard bind hosts (`0.0.0.0`, `::`, `*`) to `localhost` for dialing.

- `is_wsl(*, environ: Mapping[str, str] | None = None, proc_version_path: str = "/proc/version") -> bool`
  - Detects WSL via env (`WSL_DISTRO_NAME`/`WSL_INTEROP`) or `/proc/version` containing `microsoft`.

- `in_container(*, dockerenv_path: str = "/.dockerenv", containerenv_path: str = "/run/.containerenv", cgroup_path: str = "/proc/1/cgroup") -> bool`
  - Detects Docker/Podman-like container environments using sentinel files and cgroup content.

- `wsl_host_addresses(resolv_conf_path: str = "/etc/resolv.conf") -> list[str]`
  - Returns potential Windows-host addresses reachable from WSL:
    - Nameserver IPs from `/etc/resolv.conf`
    - Plus `host.docker.internal`

- `candidate_base_urls(configured: str | None = None, *, environ: Mapping[str, str] | None = None, wsl: bool | None = None, resolv_conf_path: str = "/etc/resolv.conf") -> list[str]`
  - Produces an ordered, de-duplicated list of candidate base URLs:
    1. `configured`
    2. `ABI_OLLAMA_BASE_URL`
    3. `OLLAMA_HOST`
    4. `http://localhost:11434`
    5. (WSL only) `http://<wsl_host_address>:11434` for each host address

- `probe_base_url(base_url: str, timeout: float = 0.75) -> bool`
  - Probes `{base_url}/api/tags` and returns `True` on any 2xx response.

- `resolve_base_url(configured: str | None = None, *, environ: Mapping[str, str] | None = None, wsl: bool | None = None, resolv_conf_path: str = "/etc/resolv.conf", timeout: float = 0.75, probe: bool = True) -> tuple[str, bool]`
  - Returns `(base_url, reachable)`.
  - If an **explicit** endpoint is provided (`configured` or `ABI_OLLAMA_BASE_URL`), it is honored and **never** falls back to other candidates (probing only reports reachability).
  - Otherwise, tries candidates in order and returns the first reachable; if none reachable, returns the first candidate with `reachable=False`.

- `find_ollama_binary(*, system: str | None = None, path_exists: Callable[[str], bool] | None = None) -> str | None`
  - Locates the `ollama` executable via `shutil.which` and extra platform-specific paths (notably macOS `.app` and Homebrew locations).

- `install_hint(*, system: str | None = None, wsl: bool | None = None, container: bool | None = None) -> str`
  - Returns platform-appropriate instructions when Ollama is not reachable.
  - Special-cases Linux containers (bind address issue) and WSL (VM boundary/topology).

## Configuration/Dependencies
- Environment variables:
  - `ABI_OLLAMA_BASE_URL`: preferred override for ABI (checked before `OLLAMA_HOST`)
  - `OLLAMA_HOST`: Ollama host/bind spec (normalized to a URL)
  - `WSL_DISTRO_NAME`, `WSL_INTEROP`: used for WSL detection
- Network probe:
  - HTTP `GET` to `/_api/tags` (actually `/api/tags`) via `urllib.request`
- Files consulted (defaults):
  - `/proc/version` (WSL detection fallback)
  - `/.dockerenv`, `/run/.containerenv`, `/proc/1/cgroup` (container detection)
  - `/etc/resolv.conf` (WSL host IP discovery)

## Usage
```python
from naas_abi_marketplace.ai.ollama.endpoint import resolve_base_url, install_hint

base_url, reachable = resolve_base_url()

if not reachable:
    print(install_hint())
else:
    print("Using:", base_url)
```

## Caveats
- `resolve_base_url()` will not auto-fallback past an explicitly configured endpoint (`configured` or `ABI_OLLAMA_BASE_URL`), even if it is unreachable.
- Probing uses a short default timeout (`0.75s`) and only checks `GET /api/tags`.
- Wildcard bind hosts in `OLLAMA_HOST` (e.g. `0.0.0.0`) are normalized to `localhost` for dialing.
