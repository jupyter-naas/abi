"""Configuration and filesystem layout for ABI Desktop.

Everything lives under a single data directory (default ``~/.abi-desktop``)
so the app stays fully local and self-contained:

- ``desktop.db``   SQLite database (chats, messages, settings)
- ``graph/``       embedded Oxigraph triple store
- ``workspace/``   default code workspace handed to opencode
"""

from __future__ import annotations

import json
import os
import shlex
from pathlib import Path
from typing import Any, TypedDict

from ..core.templates import ensure_templates
from ..core.workspace_layout import DEFAULT_MODEL, DEFAULT_ORG, ensure_default_context

APP_NAME = "ABI Desktop"
APP_ID = "abi-desktop"
DEFAULT_SERVER_PORT = 54242

DESKTOP_PACKAGE_DIR = Path(__file__).resolve().parent.parent
BUNDLED_ONTOLOGY_DIR = DESKTOP_PACKAGE_DIR / "ontology"

# System ontology TTL files loaded into the embedded graph before org/model
# context. Prefer repo paths when developing; bundled copies ship with PyInstaller.
BFO7_BUCKETS_PROCESS_TTL = (
    "ontologies/imports/domain-level/BFO7BucketsProcessOntology.ttl"
)
BFO7_BUCKETS_TTL = "apps/nexus/ontology/BFO7Buckets.ttl"
DESKTOP_ROUTING_TTL = "apps/desktop/ontology/desktop-routing.ttl"

DATA_DIR = Path(os.environ.get("ABI_DESKTOP_HOME", str(Path.home() / ".abi-desktop")))
DB_PATH = DATA_DIR / "desktop.db"
GRAPH_DIR = DATA_DIR / "graph"
DEFAULT_WORKSPACE = DATA_DIR / "workspace"

# Workspace env files are always resolved relative to ``workspace_root`` (never
# a separate setting). ``.env.remote`` is sourced before ``.env`` so local
# overrides win, matching the Nexus / opencode workflow.
ENV_FILE_NAMES: tuple[str, ...] = (".env.remote", ".env")

# Workspace config files surfaced in the Code explorer at the project root.
WORKSPACE_ROOT_VISIBLE: tuple[str, ...] = (
    ".env",
    ".env.remote",
    ".env.example",
    "opencode.json",
    "AGENTS.md",
    "desktop.md",
)

OPENCODE_CONFIG_TEMPLATE: dict[str, Any] = {
    "$schema": "https://opencode.ai/config.json",
    "provider": {
        "ollama": {
            "name": "Ollama (local)",
            "npm": "@ai-sdk/openai-compatible",
            "options": {
                "baseURL": "http://localhost:11434/v1",
            },
            "models": {},
        }
    },
}

ENV_EXAMPLE_TEMPLATE = """# Workspace provider keys for ABI Desktop / opencode.
# Copy to .env or .env.remote and fill in values (never commit secrets).

# OPENAI_API_KEY=
# ANTHROPIC_API_KEY=
# GOOGLE_API_KEY=
"""

DESKTOP_MD_TEMPLATE = """# ABI Desktop workspace

This folder is the ABI Desktop workspace root. The app reads config from here.

## Files

| File | Purpose |
|---|---|
| `opencode.json` | opencode provider + model config (Ollama models sync here) |
| `.env` / `.env.remote` | Provider API keys (`.env.remote` is sourced first) |
| `.env.example` | Template for required keys (no secrets) |
| `desktop.md` | This guide |

## Local models (Ollama)

ABI Desktop uses opencode agents, which require **tool-capable** models.
Examples: `qwen2.5-coder`, `llama3.1`, `deepseek-r1`.

Models like `phi` do not support agent tools and are excluded from chat.

```bash
ollama pull qwen2.5-coder:7b
```

Then open **Settings → Servers** to sync Ollama models into `opencode.json`.
"""

COMMON_API_KEYS: tuple[str, ...] = (
    "OPENAI_API_KEY",
    "ANTHROPIC_API_KEY",
    "GOOGLE_API_KEY",
    "GEMINI_API_KEY",
    "MISTRAL_API_KEY",
    "DEEPSEEK_API_KEY",
    "XAI_API_KEY",
    "OPENROUTER_API_KEY",
)


class EnvFileStatus(TypedDict):
    name: str
    path: str
    exists: bool
    keys: list[str]


def _parse_env_keys(path: Path) -> dict[str, bool]:
    """Return key -> has_nonempty_value without exposing secret values."""
    found: dict[str, bool] = {}
    if not path.is_file():
        return found
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].strip()
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if not key:
            continue
        value = value.strip().strip('"').strip("'")
        found[key] = bool(value)
    return found


def resolve_env_files(workspace_root: str | Path) -> list[EnvFileStatus]:
    """List standard workspace env files and non-empty key names (never values)."""
    root = Path(workspace_root).expanduser().resolve()
    results: list[EnvFileStatus] = []
    for name in ENV_FILE_NAMES:
        path = root / name
        keys = sorted(key for key, present in _parse_env_keys(path).items() if present)
        results.append(
            {
                "name": name,
                "path": str(path),
                "exists": path.is_file(),
                "keys": keys,
            }
        )
    return results


def merged_env_keys(workspace_root: str | Path) -> dict[str, bool]:
    """Merge keys from ``.env.remote`` then ``.env`` (later files override)."""
    merged: dict[str, bool] = {}
    root = Path(workspace_root).expanduser().resolve()
    for name in ENV_FILE_NAMES:
        for key, has_value in _parse_env_keys(root / name).items():
            if has_value or key not in merged:
                merged[key] = merged.get(key, False) or has_value
    return merged


def build_shell_env_source(workspace_root: str | Path) -> str:
    """Shell snippet that exports workspace env files with ``set -a``."""
    root = Path(workspace_root).expanduser().resolve()
    parts = [
        "source ~/.bashrc >/dev/null 2>&1;",
        "set -a;",
    ]
    for name in ENV_FILE_NAMES:
        path = shlex.quote(str(root / name))
        parts.append(f"[ -f {path} ] && source {path};")
    parts.append("set +a;")
    return " ".join(parts)


def workspace_env_report(workspace_root: str | Path) -> dict[str, Any]:
    """API-friendly summary of workspace env files and provider key presence."""
    files = resolve_env_files(workspace_root)
    merged = merged_env_keys(workspace_root)
    provider_keys = [key for key in COMMON_API_KEYS if merged.get(key)]
    missing_provider_keys = [
        key for key in COMMON_API_KEYS if key not in merged or not merged[key]
    ]
    return {
        "workspace_root": str(Path(workspace_root).expanduser().resolve()),
        "files": files,
        "provider_keys": provider_keys,
        "missing_provider_keys": missing_provider_keys,
        "has_provider_keys": bool(provider_keys),
    }


def _naas_abi_root() -> Path:
    """Package root ``naas_abi/`` (parent of ``apps/desktop``)."""
    return DESKTOP_PACKAGE_DIR.parent.parent


def default_system_ontology_candidates() -> tuple[Path, ...]:
    """Candidate TTL paths for the BFO7 system ontology base."""
    root = _naas_abi_root()
    return (
        root / BFO7_BUCKETS_PROCESS_TTL,
        root / BFO7_BUCKETS_TTL,
        BUNDLED_ONTOLOGY_DIR / "BFO7BucketsProcessOntology.ttl",
        BUNDLED_ONTOLOGY_DIR / "BFO7Buckets.ttl",
    )


def resolve_system_ontology_paths() -> list[Path]:
    """Return existing system ontology TTL paths for graph bootstrap.

    Resolution order:

    1. ``ABI_DESKTOP_SYSTEM_ONTOLOGY_PATHS`` (``os.pathsep``-separated files)
    2. Bundled ``desktop-routing.ttl`` plus the first available BFO7 TTL
    3. Repo-relative Nexus / naas_abi ontology paths when developing from source
    """
    env = os.environ.get("ABI_DESKTOP_SYSTEM_ONTOLOGY_PATHS", "").strip()
    if env:
        explicit = [
            Path(part).expanduser().resolve()
            for part in env.split(os.pathsep)
            if part.strip()
        ]
        return [path for path in explicit if path.is_file()]

    paths: list[Path] = []
    routing = BUNDLED_ONTOLOGY_DIR / "desktop-routing.ttl"
    if routing.is_file():
        paths.append(routing)

    seen: set[Path] = set()
    for candidate in default_system_ontology_candidates():
        resolved = candidate.expanduser().resolve()
        if resolved.is_file() and resolved not in seen:
            paths.append(resolved)
            seen.add(resolved)
            if resolved.name == "BFO7BucketsProcessOntology.ttl":
                break
    return paths


def detect_preferred_workspace() -> Path | None:
    """Discover a git workspace with env files (e.g. ``~/abi``)."""
    candidates: list[Path] = []
    abi_home = Path.home() / "abi"
    if abi_home.is_dir():
        candidates.append(abi_home)
    cwd = Path.cwd()
    if cwd.is_dir() and cwd.resolve() not in {c.resolve() for c in candidates}:
        candidates.append(cwd)
    for root in candidates:
        resolved = root.expanduser().resolve()
        if not (resolved / ".git").exists():
            continue
        if any((resolved / name).is_file() for name in ENV_FILE_NAMES):
            return resolved
    return None


MAX_RECENT_WORKSPACES = 10


def parse_recent_workspaces(raw: str | None) -> list[str]:
    """Parse the ``recent_workspaces`` JSON settings value."""
    if not raw:
        return []
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return []
    if not isinstance(data, list):
        return []
    return [str(item).strip() for item in data if isinstance(item, str) and item.strip()]


def serialize_recent_workspaces(paths: list[str]) -> str:
    """Serialize recent workspace paths for SQLite settings storage."""
    cleaned: list[str] = []
    seen: set[str] = set()
    for item in paths:
        resolved = str(Path(item).expanduser().resolve())
        if resolved in seen:
            continue
        seen.add(resolved)
        cleaned.append(resolved)
        if len(cleaned) >= MAX_RECENT_WORKSPACES:
            break
    return json.dumps(cleaned)


def add_recent_workspace(recent: list[str], path: str | Path) -> list[str]:
    """Move *path* to the front of *recent*, dedupe, and cap length."""
    resolved = str(Path(path).expanduser().resolve())
    updated = [resolved]
    for item in recent:
        if str(Path(item).expanduser().resolve()) == resolved:
            continue
        updated.append(str(Path(item).expanduser().resolve()))
        if len(updated) >= MAX_RECENT_WORKSPACES:
            break
    return updated


def workspace_display_name(path: str | Path) -> str:
    """Basename used in the workspace switcher (IDE semantics)."""
    resolved = Path(path).expanduser().resolve()
    return resolved.name or str(resolved)


def workspace_entry(path: str | Path) -> dict[str, Any]:
    """API-friendly workspace descriptor."""
    resolved = Path(path).expanduser().resolve()
    return {
        "path": str(resolved),
        "name": workspace_display_name(resolved),
        "exists": resolved.is_dir(),
    }


def validate_workspace_dir(path: str | Path) -> Path:
    """Ensure *path* is an existing writable directory."""
    resolved = Path(path).expanduser().resolve()
    if not resolved.is_dir():
        raise ValueError(f"Not a directory: {resolved}")
    if not os.access(resolved, os.W_OK):
        raise ValueError(f"Workspace is not writable: {resolved}")
    return resolved


def seed_recent_workspaces(store: Any) -> None:
    """Ensure the active workspace appears in ``recent_workspaces``."""
    settings = store.get_settings()
    root = settings.get("workspace_root") or ""
    if not root:
        return
    recent = parse_recent_workspaces(settings.get("recent_workspaces"))
    updated = add_recent_workspace(recent, root)
    if updated != recent:
        store.update_settings(
            {"recent_workspaces": serialize_recent_workspaces(updated)}
        )


def maybe_upgrade_workspace_setting(store: Any) -> None:
    """Point workspace at a discovered project when still on the factory default."""
    settings = store.get_settings()
    current = Path(settings["workspace_root"]).expanduser().resolve()
    if current != DEFAULT_WORKSPACE.resolve():
        seed_recent_workspaces(store)
        return
    preferred = detect_preferred_workspace()
    if preferred is None:
        seed_recent_workspaces(store)
        return
    recent = add_recent_workspace(
        parse_recent_workspaces(settings.get("recent_workspaces")),
        preferred,
    )
    store.update_settings(
        {
            "workspace_root": str(preferred),
            "recent_workspaces": serialize_recent_workspaces(recent),
        }
    )


DEFAULT_SETTINGS: dict[str, str] = {
    "workspace_root": str(DEFAULT_WORKSPACE),
    # Active org/model context under workspace_root (see workspace_layout.py).
    "active_org": DEFAULT_ORG,
    "active_model": DEFAULT_MODEL,
    # AI harness backing the chat/code sections: "opencode" | "pi".
    "harness": "opencode",
    "opencode_bin": "opencode",
    "pi_bin": "pi",
    "default_model": "",
    # opencode agent used for each section. "plan" is read-only (chat),
    # "build" can edit files (code).
    "chat_agent": "plan",
    "code_agent": "build",
    # Local Ollama server used by the Integrations section.
    "ollama_base_url": "http://localhost:11434",
    # First-run doctor overlay dismissed by the user.
    "doctor_dismissed": "false",
    # When true, send uses the top /api/router/suggest model when none is set.
    "router_auto_apply": "false",
    # JSON list of recently opened workspace folder paths (max 10).
    "recent_workspaces": "[]",
}


def ensure_dirs() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    GRAPH_DIR.mkdir(parents=True, exist_ok=True)
    ensure_workspace(DEFAULT_WORKSPACE)


def seed_workspace_templates(path: Path) -> None:
    """Create starter workspace config files when missing."""
    opencode_path = path / "opencode.json"
    if not opencode_path.exists():
        opencode_path.write_text(
            json.dumps(OPENCODE_CONFIG_TEMPLATE, indent=2) + "\n",
            encoding="utf-8",
        )

    env_example = path / ".env.example"
    if not env_example.exists():
        env_example.write_text(ENV_EXAMPLE_TEMPLATE, encoding="utf-8")

    desktop_md = path / "desktop.md"
    if not desktop_md.exists():
        desktop_md.write_text(DESKTOP_MD_TEMPLATE, encoding="utf-8")


def ensure_workspace(path: Path) -> None:
    """Create the workspace and make it a git repo.

    opencode resolves its project root by walking up to the nearest
    ``.git``; without one it roots at ``/`` and file tools fail on the
    read-only filesystem.
    """
    path.mkdir(parents=True, exist_ok=True)
    seed_workspace_templates(path)
    ensure_templates(path)
    ensure_default_context(path)
    if not (path / ".git").exists():
        import subprocess

        subprocess.run(
            ["git", "init", "-q"],
            cwd=str(path),
            check=False,
            capture_output=True,
        )
