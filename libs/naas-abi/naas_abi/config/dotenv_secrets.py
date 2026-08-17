"""Read/write engine-facing secrets in the project `.env` file."""

from __future__ import annotations

import os
import re
from pathlib import Path

from dotenv import set_key
from naas_abi.config.module_enable import resolve_config_file

_PLACEHOLDER_VALUES = frozenset(
    {
        "",
        "placeholder",
        "secret_ref",
        "your-github-token-here",
        "changeme",
        "xxx",
        "todo",
        "none",
        "null",
    }
)

_GITHUB_TOKEN_PREFIXES = ("ghp_", "gho_", "ghu_", "ghs_", "ghr_", "github_pat_")


def resolve_dotenv_path(config_file: str | None = None) -> Path:
    """Resolve the dotenv path from config.yaml secret adapter settings."""
    target = config_file or resolve_config_file()
    if os.path.exists(target):
        import yaml

        with open(target, encoding="utf-8") as handle:
            config = yaml.safe_load(handle) or {}
        services = config.get("services")
        if isinstance(services, dict):
            secret = services.get("secret")
            if isinstance(secret, dict):
                adapters = secret.get("secret_adapters")
                if isinstance(adapters, list):
                    for adapter in adapters:
                        if not isinstance(adapter, dict):
                            continue
                        if adapter.get("adapter") != "dotenv":
                            continue
                        cfg = adapter.get("config")
                        if isinstance(cfg, dict):
                            path = cfg.get("path", ".env")
                            if isinstance(path, str) and path.strip():
                                return Path(path)
    return Path(".env")


def write_dotenv_secret(key: str, value: str, *, config_file: str | None = None) -> Path:
    """Persist a secret to `.env` for the engine dotenv adapter."""
    path = resolve_dotenv_path(config_file)
    if not path.exists():
        path.write_text("", encoding="utf-8")
    set_key(str(path), key, value)
    os.environ[key] = value
    return path


def clear_dotenv_secret(key: str, *, config_file: str | None = None) -> Path:
    """Remove a secret from `.env` and the process environment."""
    path = resolve_dotenv_path(config_file)
    if path.exists():
        lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
        pattern = re.compile(rf"^\s*{re.escape(key)}\s*=")
        kept = [line for line in lines if not pattern.match(line)]
        path.write_text("".join(kept), encoding="utf-8")
    os.environ.pop(key, None)
    return path


def is_usable_secret_value(value: str | None) -> bool:
    """Return True when a secret looks like a real credential, not a template stub."""
    if value is None:
        return False
    cleaned = str(value).strip()
    if cleaned.lower() in _PLACEHOLDER_VALUES:
        return False
    if "your-" in cleaned.lower() or cleaned.lower().endswith("-here"):
        return False
    if cleaned.startswith(_GITHUB_TOKEN_PREFIXES):
        return True
    return len(cleaned) >= 20


def engine_secret_configured(key: str) -> bool:
    """Return True when the engine secret service has a non-empty usable value."""
    try:
        from naas_abi import ABIModule

        secret = ABIModule.get_instance().engine.services.secret.get(key)
    except Exception:  # noqa: BLE001 - engine may be unavailable in unit tests
        return False
    return is_usable_secret_value(secret if secret is None else str(secret))
