"""Enable marketplace modules in config.yaml (shared by CLI and Nexus API)."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any

import yaml

# Default config blocks for known marketplace modules. Secrets use Jinja so the
# engine resolves them from .env at boot — never hard-code tokens here.
KNOWN_MODULE_DEFAULTS: dict[str, dict[str, Any]] = {
    "naas_abi_marketplace.applications.github": {
        "config": {
            "github_access_token": "{{ secret.GITHUB_ACCESS_TOKEN }}",
        },
        "secrets": ["GITHUB_ACCESS_TOKEN"],
    },
}


@dataclass(frozen=True)
class ModuleEnableResult:
    module_path: str
    config_file: str
    created: bool
    secrets_required: list[str] = field(default_factory=list)
    restart_required: bool = True

    @property
    def message(self) -> str:
        parts = [
            f"Module '{self.module_path}' enabled in {self.config_file}.",
        ]
        if self.secrets_required:
            parts.append(
                "Connect GitHub in Marketplace, then use Restart OS to apply changes."
            )
        elif self.restart_required:
            parts.append("Use Restart OS in the workspace menu to apply changes.")
        return " ".join(parts)


def resolve_config_file() -> str:
    """Pick config.yaml or config.{ENV}.yaml using the same rules as the CLI."""
    env = os.getenv("ENV")
    if not env and os.path.exists("config.yaml"):
        try:
            with open("config.yaml", encoding="utf-8") as file:
                config = yaml.safe_load(file) or {}
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
                            secret_config = adapter.get("config")
                            if not isinstance(secret_config, dict):
                                secret_config = {}
                            path = secret_config.get("path", ".env")
                            if isinstance(path, str) and path.strip():
                                from naas_abi_core.services.secret.adaptors.secondary.dotenv_secret_secondaryadaptor import (
                                    DotenvSecretSecondaryAdaptor,
                                )

                                value = DotenvSecretSecondaryAdaptor(path=path).get("ENV")
                                if value is not None:
                                    env = str(value)
                                break
        except OSError:
            pass

    if env and os.path.exists(f"config.{env}.yaml"):
        return f"config.{env}.yaml"
    return "config.yaml"


def _module_entry_key(entry: dict[str, Any]) -> str | None:
    value = entry.get("module") or entry.get("path")
    return str(value) if value else None


def enable_module_in_config(
    module_path: str,
    *,
    config_file: str | None = None,
) -> ModuleEnableResult:
    """
    Enable a module in config.yaml. Idempotent.

    Uses the ``module`` key (Engine loader expects ``module_config.module``).
    Merges known default config/secrets for marketplace integrations.
    """
    target = config_file or resolve_config_file()
    if not os.path.exists(target):
        raise FileNotFoundError(f"Configuration file not found: {target}")

    with open(target, encoding="utf-8") as handle:
        config = yaml.safe_load(handle) or {}

    if "modules" not in config or not isinstance(config["modules"], list):
        config["modules"] = []

    defaults = KNOWN_MODULE_DEFAULTS.get(module_path, {})
    default_config = defaults.get("config", {})
    secrets_required = list(defaults.get("secrets", []))

    created = False
    for entry in config["modules"]:
        if not isinstance(entry, dict):
            continue
        if _module_entry_key(entry) == module_path:
            entry["enabled"] = True
            entry.setdefault("module", module_path)
            entry.pop("path", None)
            if default_config:
                existing = entry.get("config")
                if not isinstance(existing, dict):
                    existing = {}
                merged = {**default_config, **existing}
                entry["config"] = merged
            break
    else:
        created = True
        new_entry: dict[str, Any] = {
            "module": module_path,
            "enabled": True,
        }
        if default_config:
            new_entry["config"] = dict(default_config)
        config["modules"].append(new_entry)

    config["modules"] = sorted(
        config["modules"],
        key=lambda item: (_module_entry_key(item) or "") if isinstance(item, dict) else "",
    )

    with open(target, "w", encoding="utf-8") as handle:
        yaml.dump(config, handle, default_flow_style=False, sort_keys=False)

    return ModuleEnableResult(
        module_path=module_path,
        config_file=target,
        created=created,
        secrets_required=secrets_required,
        restart_required=True,
    )
