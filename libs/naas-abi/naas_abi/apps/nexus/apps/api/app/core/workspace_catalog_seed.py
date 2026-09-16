"""Resolve per-workspace app, agent, and ontology seed lists from Nexus settings."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
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


def _posix(path: str) -> str:
    return path.replace("\\", "/")


def _module_key(module_name: str) -> str:
    return module_name.replace(" ", "_").strip().lower()


def normalize_ontology_ref(raw: str) -> str:
    """Canonical form for a seed id: ``module:filename.ttl``, filename, or path."""
    text = _posix((raw or "").strip())
    if not text:
        return ""
    if "://" in text:
        return text
    if ":" in text and not text.startswith("/"):
        module, _, filename = text.partition(":")
        return f"{_module_key(module)}:{filename.strip().lower()}"
    if "/" not in text:
        return text.lower()
    return text


def ontology_catalog_aliases(path: str, module_name: str) -> set[str]:
    """Ids that may appear in ``WorkspaceSeedConfig.ontologies`` for this file."""
    posix = _posix(path)
    filename = Path(posix).name
    module_key = _module_key(module_name)
    return {
        path,
        posix,
        filename,
        filename.lower(),
        f"{module_key}:{filename.lower()}",
    }


def ontology_matches_seed(path: str, module_name: str, seed_refs: Sequence[str]) -> bool:
    """True when ``path`` is named in the seed. Imports are not implied."""
    aliases = ontology_catalog_aliases(path, module_name)
    normalized_aliases = {normalize_ontology_ref(alias) for alias in aliases}
    posix = _posix(path)
    for raw in seed_refs:
        ref = (raw or "").strip()
        if not ref:
            continue
        normalized = normalize_ontology_ref(ref)
        if normalized in aliases or normalized in normalized_aliases:
            return True
        if posix.endswith(_posix(ref)) or path.endswith(ref):
            return True
    return False


def ontology_catalog_id(path: str, module_name: str) -> str:
    """Stable ``ontology_configs.ontology_id`` for a catalog file.

    ``module:filename.ttl`` rather than the raw path: absolute paths differ
    between a container (``/app/libs/...``) and a checkout, so a path-keyed
    row would silently stop matching after a deploy. This is also the form
    ``WorkspaceSeedConfig.ontologies`` already uses, so a YAML entry and a
    stored row name the same file.
    """
    return f"{_module_key(module_name)}:{Path(_posix(path)).name.lower()}"


def ontology_config_lookup_ids(path: str, module_name: str) -> list[str]:
    """Ids a stored row may use for this file, most canonical first.

    The catalog always advertises ``ontology_catalog_id``, but
    ``_seed_workspace_ontologies`` stores whatever form the YAML used (bare
    filename, ``module:filename.ttl``, or a full path), so accept those too.
    """
    canonical = ontology_catalog_id(path, module_name)
    aliases = {
        normalize_ontology_ref(alias)
        for alias in ontology_catalog_aliases(path, module_name)
    }
    aliases.discard(canonical)
    aliases.discard("")
    return [canonical, *sorted(aliases)]


def resolve_ontology_enabled(
    path: str,
    module_name: str,
    enabled_by_id: Mapping[str, bool],
    seed_refs: Sequence[str] | None,
) -> bool:
    """DB row wins; otherwise the seed list; otherwise off.

    Same precedence as :func:`resolve_app_enabled`: ontologies are opt-in,
    so a file named by neither source stays disabled.
    """
    for ontology_id in ontology_config_lookup_ids(path, module_name):
        if ontology_id in enabled_by_id:
            return enabled_by_id[ontology_id]
    if seed_refs:
        return ontology_matches_seed(path, module_name, seed_refs)
    return False


@dataclass(frozen=True)
class OntologyCatalogScope:
    """Per-workspace enablement view over the engine ontology catalog.

    ``enabled_by_id`` holds this workspace's ``ontology_configs`` rows and
    wins outright; ``seed_refs`` is ``WorkspaceSeedConfig.ontologies`` and
    only pre-enables files that have no row yet.
    """

    enabled_by_id: Mapping[str, bool] = field(default_factory=dict)
    seed_refs: Sequence[str] | None = None

    def allows(self, path: str, module_name: str) -> bool:
        return resolve_ontology_enabled(
            path, module_name, self.enabled_by_id, self.seed_refs
        )


def filter_ontology_catalog(
    items: Sequence[Any],
    scope: OntologyCatalogScope | None,
) -> list[Any]:
    """Restrict catalog rows to the ontologies enabled for a workspace.

    ``None`` keeps the full engine listing and is only reached when a
    request carries no workspace context. With a scope every file is off
    unless a stored row or the seed list turns it on. owl:imports are not
    added: they follow their parent file's access.
    """
    if scope is None:
        return list(items)
    return [item for item in items if scope.allows(item.path, item.module_name)]
