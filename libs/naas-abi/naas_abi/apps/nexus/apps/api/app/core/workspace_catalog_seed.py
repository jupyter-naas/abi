"""Resolve per-workspace app and agent seed lists from Nexus settings."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from naas_abi.apps.nexus.apps.api.app.core import config as nexus_config


def live_settings() -> Any:
    """Return the live Settings object.

    ``on_initialized`` replaces ``nexus_config.settings``. Callers must not
    bind the import-time snapshot.
    """
    return nexus_config.settings


def workspace_seed_for_slug(slug: str | None) -> Any | None:
    if not slug:
        return None
    for org in getattr(live_settings(), "organizations", None) or []:
        for workspace in getattr(org, "workspaces", None) or []:
            if workspace.slug == slug:
                return workspace
    return None


def parse_agent_ref(raw: str) -> tuple[str, str] | None:
    """Split ``module AgentClass`` (same form as engine ``default_agent``)."""
    text = (raw or "").strip()
    if " " not in text:
        return None
    module_name, agent_name = text.split(" ", 1)
    module_name = module_name.strip()
    agent_name = agent_name.strip()
    if not module_name or not agent_name:
        return None
    return module_name, agent_name


def resolve_agent_ref(raw: str, registry: Mapping[str, Any]) -> str | None:
    """Return the registry key for ``module AgentClass``, or None."""
    parsed = parse_agent_ref(raw)
    if parsed is None:
        return None
    module_name, agent_name = parsed
    suffix = f"/{agent_name}"
    for class_name in registry:
        if not class_name.endswith(suffix):
            continue
        if class_name == f"{module_name}/{agent_name}" or class_name.startswith(
            f"{module_name}."
        ):
            return class_name
    matches = [key for key in registry if key.endswith(suffix)]
    if len(matches) == 1:
        return matches[0]
    return None


def resolve_agent_refs(refs: list[str] | None, registry: Mapping[str, Any]) -> set[str]:
    resolved: set[str] = set()
    for raw in refs or []:
        class_name = resolve_agent_ref(raw, registry)
        if class_name:
            resolved.add(class_name)
    return resolved


def resolve_app_enabled(
    app_id: str,
    enabled_by_app_id: Mapping[str, bool],
    seed_apps: set[str],
) -> bool:
    """DB row wins; otherwise the seed list; otherwise off."""
    if app_id in enabled_by_app_id:
        return enabled_by_app_id[app_id]
    return app_id in seed_apps
