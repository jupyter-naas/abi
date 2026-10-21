"""Workspace Maps setup shared by mounted and standalone Nexus configuration."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class WorkspaceMapsBasemapsSeedConfig(BaseModel):
    """Basemaps of a workspace's Maps. Built-in basemaps are always enabled."""

    model_config = ConfigDict(extra="forbid")

    # Custom basemap ids enabled at first; other custom basemaps start disabled.
    custom: list[str] = Field(default_factory=list)


class WorkspaceMapsSeedConfig(BaseModel):
    """Initial Maps setup of a workspace, applied once per id (Settings → Maps wins after).

    Listed feeds start enabled and show when the map opens; every other feed
    starts disabled, as does every feed of a workspace without this block.
    """

    model_config = ConfigDict(extra="forbid")

    feeds: list[str] = Field(default_factory=list)
    basemaps: WorkspaceMapsBasemapsSeedConfig = Field(
        default_factory=WorkspaceMapsBasemapsSeedConfig
    )
