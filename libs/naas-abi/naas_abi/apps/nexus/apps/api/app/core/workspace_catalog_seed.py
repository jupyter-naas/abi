"""Resolve per-workspace app, agent, ontology, and graph seed lists from Nexus settings."""

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


def _graph_slug(uri: str) -> str:
    text = (uri or "").strip().rstrip("/")
    if not text:
        return ""
    return text.split("/")[-1].split("#")[-1]


def graph_catalog_aliases(uri: str, graph_id: str = "") -> set[str]:
    """Ids that may appear in ``WorkspaceSeedConfig.graphs`` for this named graph."""
    slug = _graph_slug(uri)
    aliases = {uri, uri.lower(), slug, slug.lower()}
    if graph_id:
        aliases.add(graph_id)
        aliases.add(graph_id.lower())
    return aliases


def graph_matches_seed(uri: str, seed_refs: Sequence[str], graph_id: str = "") -> bool:
    """True when ``uri`` is named in the seed. schema and nexus are not implied."""
    aliases = graph_catalog_aliases(uri, graph_id)
    for raw in seed_refs:
        ref = (raw or "").strip()
        if not ref:
            continue
        if ref in aliases or ref.lower() in aliases:
            return True
        if uri.rstrip("/") == ref.rstrip("/"):
            return True
    return False


def filter_graph_catalog(
    items: Sequence[Any],
    seed_refs: Sequence[str] | None,
) -> list[Any]:
    """Restrict named-graph rows to the seed list.

    ``None`` keeps the full store listing (existing deployments). An empty
    list returns nothing. A non-empty list is exclusive: listed on, others
    off. schema and nexus are not added.
    """
    if seed_refs is None:
        return list(items)
    if not seed_refs:
        return []
    return [
        item
        for item in items
        if graph_matches_seed(item.uri, seed_refs, getattr(item, "id", "") or "")
    ]


def filter_graph_packs(
    packs: Sequence[Any],
    seed_refs: Sequence[str] | None,
) -> list[Any]:
    """Filter packed graph lists and drop empty role groups."""
    if seed_refs is None:
        return list(packs)
    filtered: list[Any] = []
    for pack in packs:
        graphs = filter_graph_catalog(getattr(pack, "graphs", []) or [], seed_refs)
        if not graphs:
            continue
        if hasattr(pack, "__dataclass_fields__"):
            filtered.append(type(pack)(role_label=pack.role_label, graphs=graphs))
        else:
            pack.graphs = graphs
            filtered.append(pack)
    return filtered


def filter_ontology_catalog(
    items: Sequence[Any],
    seed_refs: Sequence[str] | None,
) -> list[Any]:
    """Restrict catalog rows to the seed list.

    ``None`` keeps the full engine listing (existing deployments). An empty
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
