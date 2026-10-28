"""Resolve per-workspace app, agent, and ontology seed lists from Nexus settings."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
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


# The id of an ontology a remote module pushed: ``module/<module_id>/<path>``
# (services/ontology/ontology_source.py; not imported here, as that package
# imports this module).
_REMOTE_PREFIX = "module/"


def _remote_module_id(path: str) -> str | None:
    """The module id of a remote ontology id, else None for an in-engine path."""
    posix = _posix(path)
    if not posix.startswith(_REMOTE_PREFIX):
        return None
    module_id, _, rest = posix[len(_REMOTE_PREFIX) :].partition("/")
    return module_id if module_id and rest else None


def ontology_catalog_aliases(path: str, module_name: str) -> set[str]:
    """Ids that may appear in ``WorkspaceSeedConfig.ontologies`` for this file.

    A remote ontology answers only to its full id and to ``<module_id>:<file>``,
    both scoped to the module that pushed it. Its bare file name, and a suffix of
    its path, are not aliases: a workspace that enabled ``Foo.ttl`` of one module
    must not list ``Foo.ttl`` of a remote module that merely pushed the same name.
    """
    posix = _posix(path)
    filename = Path(posix).name
    remote_module = _remote_module_id(path)
    if remote_module is not None:
        return {
            path,
            posix,
            f"{_module_key(remote_module)}:{filename.lower()}",
        }
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
    is_remote = _remote_module_id(path) is not None
    for raw in seed_refs:
        ref = (raw or "").strip()
        if not ref:
            continue
        normalized = normalize_ontology_ref(ref)
        if normalized in aliases or normalized in normalized_aliases:
            return True
        if (
            not is_remote
            and "/" in _posix(ref)
            and not _posix(ref).startswith("/")
            and posix.endswith("/" + _posix(ref))
        ):
            return True
    return False


def filter_ontology_catalog(
    items: Sequence[Any],
    seed_refs: Sequence[str] | None,
) -> list[Any]:
    """Restrict catalog rows to the seed list.

    ``None`` is reserved for trusted internal enumeration. HTTP callers must
    supply an authorized workspace allowlist. An empty
    list returns nothing. A non-empty list is exclusive: listed on, others
    off. owl:imports are not added.
    """
    if seed_refs is None:
        return list(items)
    if not seed_refs:
        return []
    return [
        item
        for item in items
        if ontology_matches_seed(item.path, item.module_name, seed_refs)
    ]
