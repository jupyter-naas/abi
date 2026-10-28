"""Workspace instance catalog for create UI and persisted ``catalog_seed``."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from naas_abi.apps.nexus.apps.api.app.core.config import (
    OrganizationSeedConfig,
    WorkspaceSeedConfig,
)
from naas_abi.apps.nexus.apps.api.app.core.workspace_catalog_seed import live_settings
from naas_abi.apps.nexus.apps.api.app.core.workspace_config_seeds import find_workspace_seed


@dataclass(frozen=True)
class CatalogOption:
    id: str
    label: str
    kind: str


def parse_catalog_seed(raw: str | None) -> dict[str, Any] | None:
    if raw is None:
        return None
    try:
        data = json.loads(raw)
    except (TypeError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def dump_catalog_seed(seed: Mapping[str, Any] | None) -> str | None:
    if seed is None:
        return None
    return json.dumps(seed, sort_keys=True)


def _yaml_seed(slug: str | None) -> WorkspaceSeedConfig | None:
    if not slug:
        return None
    found = find_workspace_seed(getattr(live_settings(), "organizations", None) or [], slug)
    return found[1] if found else None


def effective_seed_agents(
    slug: str | None,
    catalog_seed: dict[str, Any] | None,
) -> list[str] | None:
    """Agent roster refs for sync; ``None`` means unseeded wildcard guard applies."""
    if catalog_seed is not None and "agents" in catalog_seed:
        agents = catalog_seed.get("agents")
        if agents is None:
            return None
        return [str(item).strip() for item in agents if str(item).strip()]
    yaml_ws = _yaml_seed(slug)
    if yaml_ws is not None and yaml_ws.agents is not None:
        return list(yaml_ws.agents)
    return None


def effective_seed_default_agent(
    slug: str | None,
    catalog_seed: dict[str, Any] | None,
) -> str | None:
    if catalog_seed and catalog_seed.get("default_agent"):
        return str(catalog_seed["default_agent"]).strip() or None
    yaml_ws = _yaml_seed(slug)
    if yaml_ws and yaml_ws.default_agent:
        return yaml_ws.default_agent
    return None


def effective_seed_apps(slug: str | None, catalog_seed: dict[str, Any] | None) -> set[str]:
    if catalog_seed is not None and "apps" in catalog_seed:
        apps = catalog_seed.get("apps") or []
        return {str(app_id).strip() for app_id in apps if str(app_id).strip()}
    yaml_ws = _yaml_seed(slug)
    if yaml_ws and yaml_ws.apps:
        return {str(app_id).strip() for app_id in yaml_ws.apps if str(app_id).strip()}
    return set()


def workspace_seed_apps(workspace: Any) -> set[str]:
    """The apps a workspace record's seed turns on (``effective_seed_apps``: its
    stored ``catalog_seed`` first, then the config's), as the catalog and the
    visibility read them."""
    raw = getattr(workspace, "catalog_seed", None)
    catalog_seed = raw if isinstance(raw, dict) or raw is None else parse_catalog_seed(raw)
    return effective_seed_apps(getattr(workspace, "slug", None), catalog_seed)


def _unique_sorted(values: Sequence[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for value in values:
        text = value.strip()
        if not text or text in seen:
            continue
        seen.add(text)
        out.append(text)
    return sorted(out, key=str.lower)


def _collect_from_config(organizations: Sequence[OrganizationSeedConfig]) -> dict[str, list[str]]:
    agents: list[str] = []
    apps: list[str] = []
    ontologies: list[str] = []
    map_feeds: list[str] = []
    basemaps: list[str] = []
    for org in organizations:
        for ws in org.workspaces:
            agents.extend(ws.agents or [])
            apps.extend(ws.apps or [])
            ontologies.extend(ws.ontologies or [])
            if ws.maps:
                map_feeds.extend(ws.maps.feeds or [])
                basemaps.extend(ws.maps.basemaps.custom or [])
    return {
        "agents": _unique_sorted(agents),
        "apps": _unique_sorted(apps),
        "ontologies": _unique_sorted(ontologies),
        "map_feeds": _unique_sorted(map_feeds),
        "basemaps": _unique_sorted(basemaps),
    }


def build_workspace_seed_catalog() -> dict[str, list[CatalogOption]]:
    """Deployment-wide options for the create-workspace instance picker."""
    from naas_abi.agents.feature.registry import feature_office_agent_specs

    collected = _collect_from_config(getattr(live_settings(), "organizations", None) or [])
    options: dict[str, list[CatalogOption]] = {
        "agents": [CatalogOption(id=ref, label=ref, kind="agent") for ref in collected["agents"]],
        "apps": [CatalogOption(id=ref, label=ref, kind="app") for ref in collected["apps"]],
        "ontologies": [
            CatalogOption(id=ref, label=ref, kind="ontology") for ref in collected["ontologies"]
        ],
        "map_feeds": [
            CatalogOption(id=ref, label=ref, kind="map_feed") for ref in collected["map_feeds"]
        ],
        "basemaps": [
            CatalogOption(id=ref, label=ref, kind="basemap") for ref in collected["basemaps"]
        ],
    }
    office_refs = {spec.roster_ref for spec in feature_office_agent_specs()}
    options["agents"] = [
        CatalogOption(id=ref, label=ref, kind="agent")
        for ref in _unique_sorted([o.id for o in options["agents"]] + list(office_refs))
    ]
    try:
        from naas_abi.apps.nexus.apps.api.app.services.apps.adapters.primary.apps__primary_adapter__FastAPI import (
            apps_catalog,
        )

        app_ids = _unique_sorted([app.app_id for app in apps_catalog()])
        options["apps"] = [
            CatalogOption(id=app_id, label=app_id, kind="app")
            for app_id in _unique_sorted([o.id for o in options["apps"]] + app_ids)
        ]
    except Exception:
        pass
    return options


def catalog_seed_rows(catalog_seed: dict[str, Any] | None) -> list[dict[str, str]]:
    """Seed rows for Settings → configuration (database-owned instances)."""
    if not catalog_seed:
        return []
    rows: list[dict[str, str]] = []
    base = "workspaces.catalog_seed"

    def add(kind: str, value: str, path: str) -> None:
        rows.append({"kind": kind, "value": value, "source": f"{base}.{path}"})

    if catalog_seed.get("default_agent"):
        add("default_agent", str(catalog_seed["default_agent"]), "default_agent")
    for index, value in enumerate(catalog_seed.get("agents") or []):
        add("agent", str(value), f"agents[{index}]")
    for index, value in enumerate(catalog_seed.get("apps") or []):
        add("app", str(value), f"apps[{index}]")
    for index, value in enumerate(catalog_seed.get("ontologies") or []):
        add("ontology", str(value), f"ontologies[{index}]")
    maps = catalog_seed.get("maps") or {}
    for index, value in enumerate(maps.get("feeds") or []):
        add("map_feed", str(value), f"maps.feeds[{index}]")
    basemaps = (maps.get("basemaps") or {}).get("custom") or []
    for index, value in enumerate(basemaps):
        add("basemap", str(value), f"maps.basemaps.custom[{index}]")
    return rows
