"""Initial Maps setup of each workspace, declared in ``config.*.yaml`` (``workspaces[].maps``).

The config gives initial values only: each feed and custom basemap is decided
once per workspace (enabled when listed, disabled otherwise), then Settings →
Maps owns it. Built-in basemaps are always enabled.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass

from naas_abi.apps.nexus.apps.api.app.core.config import OrganizationSeedConfig


@dataclass(frozen=True)
class WorkspaceMapsDefaults:
    feeds: frozenset[str] = frozenset()
    custom_basemaps: frozenset[str] = frozenset()


def workspace_maps_defaults(
    organizations: Sequence[OrganizationSeedConfig], workspace_slug: str | None
) -> WorkspaceMapsDefaults:
    """The workspace's ``maps`` block; nothing enabled when it has none."""
    for organization in organizations:
        for workspace in organization.workspaces:
            if workspace.slug == workspace_slug and workspace.maps is not None:
                return WorkspaceMapsDefaults(
                    feeds=frozenset(workspace.maps.feeds),
                    custom_basemaps=frozenset(workspace.maps.basemaps.custom),
                )
    return WorkspaceMapsDefaults()


def unknown_workspace_map_ids(
    organizations: Sequence[OrganizationSeedConfig],
    known_feeds: Iterable[str],
    known_basemaps: Iterable[str],
) -> dict[str, list[str]]:
    """Feed and basemap ids a workspace's ``maps`` block names but nothing provides."""
    feeds, basemaps = set(known_feeds), set(known_basemaps)
    unknown: dict[str, list[str]] = {}
    for organization in organizations:
        for workspace in organization.workspaces:
            if workspace.maps is None:
                continue
            missing = [f"feed {i!r}" for i in workspace.maps.feeds if i not in feeds] + [
                f"basemap {i!r}" for i in workspace.maps.basemaps.custom if i not in basemaps
            ]
            if missing:
                unknown[workspace.slug] = sorted(missing)
    return unknown
