"""FastAPI dependencies for the workspace's initial Maps setup (``config.*.yaml``)."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import Depends, Query, Request
from naas_abi.apps.nexus.apps.api.app.core.config import settings
from naas_abi.apps.nexus.apps.api.app.services.maps.layouts.layouts__schema import (
    BUILTIN_LAYOUT_IDS,
)
from naas_abi.apps.nexus.apps.api.app.services.maps.seeds import maps_seed_registry
from naas_abi.apps.nexus.apps.api.app.services.maps.workspace_config import (
    WorkspaceMapsDefaults,
    unknown_workspace_map_ids,
    workspace_maps_defaults,
)
from naas_abi.apps.nexus.apps.api.app.services.workspaces.adapters.primary.workspaces__primary_adapter__FastAPI import (  # noqa: E501
    get_workspace_service,
)
from naas_abi.apps.nexus.apps.api.app.services.workspaces.service import WorkspaceService

logger = logging.getLogger(__name__)


async def maps_workspace_defaults(
    workspace_id: str = Query(..., min_length=1),
    workspaces: WorkspaceService = Depends(get_workspace_service),
) -> WorkspaceMapsDefaults:
    """The ``maps`` block of the workspace's config entry (matched by slug)."""
    workspace = await workspaces.get_workspace(workspace_id=workspace_id)
    slug = workspace.slug if workspace is not None else None
    return workspace_maps_defaults(settings.organizations, slug)


def graph_feed_ids(request: Request) -> list[str]:
    """Graph layers registered by modules: one-layer feeds without a record."""
    catalog = getattr(request.app.state, "maps_catalog", None)
    return list(getattr(catalog, "layers", {}) or {})


def report_unknown_workspace_map_ids(app: Any) -> dict[str, list[str]]:
    """Log the config's feed and basemap ids nothing in the deployment provides.

    Run at startup, once every module registered its seeds. Unknown ids are an
    error in the config, but one workspace's typo must not stop the API.
    """
    registry = maps_seed_registry(app)
    catalog = getattr(app.state, "maps_catalog", None)
    known_feeds = (
        set(registry.layouts)
        | (BUILTIN_LAYOUT_IDS - {"all"})
        | set(getattr(catalog, "layers", {}) or {})
    )
    unknown = unknown_workspace_map_ids(settings.organizations, known_feeds, registry.basemaps)
    for slug, ids in sorted(unknown.items()):
        logger.error(
            "config: workspace %r lists Maps ids no module provides: %s", slug, ", ".join(ids)
        )
    return unknown
