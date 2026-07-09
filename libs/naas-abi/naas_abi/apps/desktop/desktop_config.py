"""Configuration and filesystem layout for ABI Desktop.

Everything lives under a single data directory (default ``~/.abi-desktop``)
so the app stays fully local and self-contained:

- ``desktop.db``   SQLite database (chats, messages, settings)
- ``graph/``       embedded Oxigraph triple store
- ``workspace/``   default code workspace handed to opencode
"""

from __future__ import annotations

import os
import shlex
from pathlib import Path
from typing import Any, TypedDict

APP_NAME = "ABI Desktop"
APP_ID = "abi-desktop"

DATA_DIR = Path(os.environ.get("ABI_DESKTOP_HOME", str(Path.home() / ".abi-desktop")))
DB_PATH = DATA_DIR / "desktop.db"
GRAPH_DIR = DATA_DIR / "graph"
DEFAULT_WORKSPACE = DATA_DIR / "workspace"

# Workspace env files are always resolved relative to ``workspace_root`` (never
# a separate setting). ``.env.remote`` is sourced before ``.env`` so local
# overrides win, matching the Nexus / opencode workflow.
ENV_FILE_NAMES: tuple[str, ...] = (".env.remote", ".env")

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


DEFAULT_SETTINGS: dict[str, str] = {
    "workspace_root": str(DEFAULT_WORKSPACE),
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
}


def ensure_dirs() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    GRAPH_DIR.mkdir(parents=True, exist_ok=True)
    ensure_workspace(DEFAULT_WORKSPACE)


def ensure_workspace(path: Path) -> None:
    """Create the workspace and make it a git repo.

    opencode resolves its project root by walking up to the nearest
    ``.git``; without one it roots at ``/`` and file tools fail on the
    read-only filesystem.
    """
    path.mkdir(parents=True, exist_ok=True)
    if not (path / ".git").exists():
        import subprocess

        subprocess.run(
            ["git", "init", "-q"],
            cwd=str(path),
            check=False,
            capture_output=True,
        )
