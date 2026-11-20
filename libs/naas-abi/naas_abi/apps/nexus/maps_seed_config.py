"""Workspace Maps setup shared by mounted and standalone Nexus configuration."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class WorkspaceMapsBasemapsSeedConfig(BaseModel):
    """Basemaps of a workspace's Maps. Built-in basemaps are always enabled."""

    model_config = ConfigDict(extra="forbid")

    # Custom basemap ids enabled at first; other custom basemaps start disabled.
    custom: list[str] = Field(default_factory=list)


class WorkspaceMapsCameraConfig(BaseModel):
    """Where the map opens. Read on each catalog load, not copied into Settings.

    Absent: the map opens on the world view, and the first pins fit the frame.
    Set: the map opens here, and those first pins leave the view where it is.
    """

    model_config = ConfigDict(extra="forbid")

    lat: float = Field(ge=-90, le=90)
    lng: float = Field(ge=-180, le=180)
    zoom: float = Field(ge=0, le=22)


class WorkspaceMapsSeedConfig(BaseModel):
    """Initial Maps setup of a workspace, applied once per id (Settings → Maps wins after).

    Listed feeds start enabled and show when the map opens; every other feed
    starts disabled, as does every feed of a workspace without this block.
    ``camera`` is not part of that seed: it is the launch view whenever the
    catalog is read.
    """

    model_config = ConfigDict(extra="forbid")

    feeds: list[str] = Field(default_factory=list)
    basemaps: WorkspaceMapsBasemapsSeedConfig = Field(
        default_factory=WorkspaceMapsBasemapsSeedConfig
    )
    camera: WorkspaceMapsCameraConfig | None = None
