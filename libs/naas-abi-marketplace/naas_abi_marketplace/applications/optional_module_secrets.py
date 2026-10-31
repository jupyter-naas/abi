"""Fill module configuration from the secret service at load time."""

from __future__ import annotations

from typing import Any

from naas_abi_core.module.Module import BaseModule


def hydrate_configuration_from_secrets(
    module: BaseModule[Any],
    field_map: dict[str, str],
) -> None:
    """Copy present secrets into empty config fields without YAML interpolation."""
    secret = getattr(module.engine.services, "secret", None)
    if secret is None:
        return
    cfg = module.configuration
    updates: dict[str, str] = {}
    for field, secret_name in field_map.items():
        if getattr(cfg, field, ""):
            continue
        value = secret.get(secret_name)
        if value:
            updates[field] = value
    if not updates:
        return
    module._configuration = type(cfg).model_validate({**cfg.model_dump(), **updates})
