"""Bootstrap Engine for one-off CLIs inside Docker (non-interactive secrets)."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import dotenv_values
from naas_abi_core.engine.Engine import Engine
from naas_abi_core.engine.engine_configuration.EngineConfiguration import (
    EngineConfiguration,
)


def resolve_config_path(explicit: Path | None) -> Path | None:
    """Same file pick as ``EngineConfiguration.load_configuration(None)``."""
    if explicit is not None:
        path = explicit.expanduser().resolve()
        return path if path.is_file() else None
    env = os.getenv("ENV")
    if env:
        candidate = Path(f"config.{env}.yaml")
        if candidate.is_file():
            return candidate.resolve()
    default = Path("config.yaml")
    return default.resolve() if default.is_file() else None


def preload_dotenv_for_config(config_path: Path) -> None:
    """Mirror bootstrap dotenv into ``os.environ`` so Jinja ``secret.*`` resolves."""
    base_dir = str(config_path.parent)
    content = config_path.read_text(encoding="utf-8")
    adapter = EngineConfiguration._load_bootstrap_dotenv_adapter_from_yaml_content(  # noqa: SLF001
        content, base_dir=base_dir
    )
    if adapter is not None:
        env_path = Path(adapter.path)
        if not env_path.is_absolute():
            env_path = Path(base_dir) / env_path
    else:
        env_path = Path(base_dir) / ".env"
    if not env_path.is_file():
        return
    for key, value in dotenv_values(env_path).items():
        if value is not None and key not in os.environ:
            os.environ[key] = str(value)


def load_engine(config_path: Path | None = None) -> Engine:
    """Load Engine the same way long-running ABI does (with dotenv preloaded)."""
    resolved = resolve_config_path(config_path)
    if resolved is None:
        raise SystemExit(
            "No ABI config found. Pass --config or set ENV and ship config.{ENV}.yaml."
        )
    preload_dotenv_for_config(resolved)
    if config_path is None:
        return Engine(configuration=None)
    return Engine(configuration=resolved.read_text(encoding="utf-8"))
