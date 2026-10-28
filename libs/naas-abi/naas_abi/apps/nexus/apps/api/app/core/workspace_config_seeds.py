"""Read-only view of the config preseeding of a workspace.

``nexus_config.organizations[].workspaces[]`` (``WorkspaceSeedConfig``) preloads
agents, apps, ontologies, graphs and Maps into a workspace on API boot, upserted
by slug (core/org_seed). Settings > General lists those seeds; they stay owned
by the config. Only the preloading fields are listed: no branding, owner or
secrets.
"""

from __future__ import annotations

from collections.abc import Sequence

from naas_abi.apps.nexus.apps.api.app.core.config import (
    OrganizationSeedConfig,
    WorkspaceSeedConfig,
)

CONFIG_ROOT = "nexus_config.organizations"


def find_workspace_seed(
    organizations: Sequence[OrganizationSeedConfig], workspace_slug: str
) -> tuple[OrganizationSeedConfig, WorkspaceSeedConfig] | None:
    """The first config entry seeding ``workspace_slug`` (slugs are global)."""
    for org_cfg in organizations:
        for workspace_cfg in org_cfg.workspaces:
            if workspace_cfg.slug == workspace_slug:
                return org_cfg, workspace_cfg
    return None


def workspace_seed_rows(
    organizations: Sequence[OrganizationSeedConfig], workspace_slug: str
) -> list[dict[str, str]]:
    """One ``{kind, value, source}`` row per item the config preseeds."""
    found = find_workspace_seed(organizations, workspace_slug)
    if found is None:
        return []
    org_cfg, ws = found
    base = f"{CONFIG_ROOT}[{org_cfg.slug}].workspaces[{ws.slug}]"
    rows: list[dict[str, str]] = []

    def add(kind: str, value: str, path: str) -> None:
        rows.append({"kind": kind, "value": value, "source": f"{base}.{path}"})

    def add_list(kind: str, values: list[str] | None, path: str) -> None:
        for index, value in enumerate(values or []):
            add(kind, value, f"{path}[{index}]")

    if ws.default_agent:
        add("default_agent", ws.default_agent, "default_agent")
    add_list("agent", ws.agents, "agents")
    add_list("app", ws.apps, "apps")
    add_list("ontology", ws.ontologies, "ontologies")
    if ws.graphs.read_all:
        add("graph_read_all", "All graphs", "graphs.read_all")
    add_list("graph_read", ws.graphs.read, "graphs.read")
    add_list("graph_write", ws.graphs.write, "graphs.write")
    if ws.maps is not None:
        add_list("map_feed", ws.maps.feeds, "maps.feeds")
        add_list("basemap", ws.maps.basemaps.custom, "maps.basemaps.custom")
    return rows
