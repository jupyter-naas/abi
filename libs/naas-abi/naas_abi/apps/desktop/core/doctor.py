"""Setup health checks for ABI Desktop first-run doctor.

Pure functions return structured check results; :func:`run_doctor` aggregates
them. No ``naas_abi`` / ``naas_abi_core`` imports.
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import Any, Protocol, TypedDict

import httpx

from ..config.desktop_config import COMMON_API_KEYS, merged_env_keys, resolve_env_files
from .integrations import OLLAMA_HINT, probe_ollama

OPENCODE_INSTALL_HINT = (
    "Install opencode and ensure it is on your PATH — https://opencode.ai/docs/install"
)


class DoctorCheck(TypedDict):
    id: str
    status: str  # ok | warn | error
    message: str
    fix: str


class DoctorReport(TypedDict):
    checks: list[DoctorCheck]
    ready: bool


class OpencodeProbe(Protocol):
    def is_running(self) -> bool: ...


def _harness(settings: dict[str, str]) -> str:
    return (settings.get("harness") or "opencode").strip().lower()


def check_opencode_binary(
    settings: dict[str, str],
    which: Any | None = None,
) -> DoctorCheck:
    if which is None:
        which = shutil.which
    if _harness(settings) != "opencode":
        return {
            "id": "opencode_binary",
            "status": "ok",
            "message": "pi harness selected; opencode binary not required",
            "fix": "",
        }

    bin_name = settings.get("opencode_bin") or "opencode"
    if "/" in bin_name or bin_name.startswith("."):
        path = Path(bin_name).expanduser()
        found = path.is_file() and os.access(path, os.X_OK)
        location = str(path)
    else:
        resolved = which(bin_name)
        found = resolved is not None
        location = resolved or bin_name

    if found:
        return {
            "id": "opencode_binary",
            "status": "ok",
            "message": f"opencode binary found ({location})",
            "fix": "",
        }
    return {
        "id": "opencode_binary",
        "status": "error",
        "message": f"opencode binary not found ({bin_name})",
        "fix": OPENCODE_INSTALL_HINT,
    }


def check_opencode_reachable(
    settings: dict[str, str],
    opencode: OpencodeProbe,
) -> DoctorCheck:
    if _harness(settings) != "opencode":
        return {
            "id": "opencode_reachable",
            "status": "ok",
            "message": "pi harness selected; opencode server not required",
            "fix": "",
        }

    if opencode.is_running():
        return {
            "id": "opencode_reachable",
            "status": "ok",
            "message": "opencode server is reachable",
            "fix": "",
        }
    return {
        "id": "opencode_reachable",
        "status": "error",
        "message": "opencode server is not running or not reachable",
        "fix": (
            "Start opencode from the workspace (e.g. `opencode serve`) or fix the "
            "opencode binary path in Settings, then retry."
        ),
    }


def check_api_keys(workspace_root: str) -> DoctorCheck:
    files = resolve_env_files(workspace_root)
    merged = merged_env_keys(workspace_root)

    present = [key for key in COMMON_API_KEYS if merged.get(key)]
    missing = [key for key in COMMON_API_KEYS if key not in merged or not merged[key]]
    any_env_file = any(entry["exists"] for entry in files)

    if not any_env_file:
        return {
            "id": "api_keys",
            "status": "warn",
            "message": (
                "No workspace .env or .env.remote file found — cloud models need "
                "provider keys; pick an Ollama model or add keys to your workspace"
            ),
            "fix": (
                "Create .env or .env.remote in your workspace root with provider keys "
                f"(e.g. {', '.join(COMMON_API_KEYS[:3])}), set Workspace root in "
                "Settings to that project folder, or select an Ollama model in chat."
            ),
        }

    if present:
        parts = [f"present: {', '.join(present)}"]
        if missing:
            parts.append(f"missing or empty: {', '.join(missing)}")
        return {
            "id": "api_keys",
            "status": "ok" if present else "warn",
            "message": "; ".join(parts),
            "fix": (
                ""
                if not missing
                else f"Add missing keys to .env or .env.remote: {', '.join(missing)}"
            ),
        }

    return {
        "id": "api_keys",
        "status": "warn",
        "message": (
            "Workspace env files exist but no common provider API keys were found "
            f"({', '.join(COMMON_API_KEYS[:4])}, ...)"
        ),
        "fix": (
            "Add at least one provider API key to .env or .env.remote, or configure "
            "Ollama for local models."
        ),
    }


def check_workspace(workspace_root: str) -> DoctorCheck:
    path = Path(workspace_root).expanduser()
    if not path.exists():
        return {
            "id": "workspace",
            "status": "error",
            "message": f"Workspace does not exist ({path})",
            "fix": "Choose an existing folder in Settings or let ABI Desktop create one.",
        }
    if not os.access(path, os.W_OK):
        return {
            "id": "workspace",
            "status": "error",
            "message": f"Workspace is not writable ({path})",
            "fix": "Fix directory permissions or pick a writable workspace in Settings.",
        }
    if not (path / ".git").exists():
        return {
            "id": "workspace",
            "status": "error",
            "message": "Workspace is missing a .git directory (opencode project root)",
            "fix": (
                f"Run `git init` in {path} or restart ABI Desktop to auto-initialize."
            ),
        }
    return {
        "id": "workspace",
        "status": "ok",
        "message": f"Workspace is ready ({path})",
        "fix": "",
    }


async def check_ollama(
    settings: dict[str, str],
    transport: httpx.AsyncBaseTransport | None = None,
) -> DoctorCheck:
    base_url = str(settings.get("ollama_base_url") or "").strip()
    if not base_url:
        return {
            "id": "ollama",
            "status": "ok",
            "message": "Ollama not configured (optional)",
            "fix": "",
        }

    probe = await probe_ollama(base_url, transport=transport)
    if probe["connected"]:
        count = len(probe["models"])
        names = ", ".join(m["name"] for m in probe["models"][:3])
        suffix = f" ({names})" if names else ""
        return {
            "id": "ollama",
            "status": "ok",
            "message": f"Ollama reachable at {base_url} — {count} model(s){suffix}",
            "fix": "",
        }
    return {
        "id": "ollama",
        "status": "warn",
        "message": f"Ollama unreachable at {base_url}",
        "fix": OLLAMA_HINT,
    }


def check_data_dirs(
    data_dir: Path,
    db_path: Path,
    graph_dir: Path,
) -> DoctorCheck:
    issues: list[str] = []
    for label, path in (
        ("Data directory", data_dir),
        ("Graph directory", graph_dir),
        ("Database parent", db_path.parent),
    ):
        if not path.exists():
            issues.append(f"{label} missing ({path})")
        elif not os.access(path, os.W_OK):
            issues.append(f"{label} not writable ({path})")

    if issues:
        return {
            "id": "data_dirs",
            "status": "error",
            "message": "; ".join(issues),
            "fix": (
                f"Ensure {data_dir} exists and is writable, or set ABI_DESKTOP_HOME "
                "to a writable location."
            ),
        }
    return {
        "id": "data_dirs",
        "status": "ok",
        "message": f"Data directory ready ({data_dir})",
        "fix": "",
    }


async def run_doctor(
    *,
    settings: dict[str, str],
    opencode: OpencodeProbe,
    data_dir: Path,
    db_path: Path,
    graph_dir: Path,
    transport: httpx.AsyncBaseTransport | None = None,
) -> DoctorReport:
    checks: list[DoctorCheck] = [
        check_opencode_binary(settings),
        check_opencode_reachable(settings, opencode),
        check_api_keys(settings.get("workspace_root") or ""),
        check_workspace(settings.get("workspace_root") or ""),
        await check_ollama(settings, transport=transport),
        check_data_dirs(data_dir, db_path, graph_dir),
    ]
    ready = all(c["status"] != "error" for c in checks)
    return {"checks": checks, "ready": ready}
