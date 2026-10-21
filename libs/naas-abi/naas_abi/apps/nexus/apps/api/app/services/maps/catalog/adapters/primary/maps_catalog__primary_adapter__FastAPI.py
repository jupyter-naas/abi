"""``GET /api/maps/catalog``: everything Settings → Maps and the sidebar need, in one read.

Feeds (SPARQL and API feeds) and their layers, basemaps, what is hidden and the layer
colors for the workspace. Writes stay on ``/api/maps/layouts`` and
``/api/maps/basemaps``. Module graph layers are listed by ``/api/maps/layers``
(they need the graph scope); built-in feeds are drawn by the web app and only
appear here through their hidden flag and color.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query, Request, Response
from naas_abi.apps.nexus.apps.api.app.api.endpoints.auth import get_current_user_required
from naas_abi.apps.nexus.apps.api.app.services.iam import authz
from naas_abi.apps.nexus.apps.api.app.services.iam.guards import guard
from naas_abi.apps.nexus.apps.api.app.services.maps.adapters.primary.workspace_defaults import (
    graph_feed_ids,
    maps_workspace_defaults,
)
from naas_abi.apps.nexus.apps.api.app.services.maps.basemaps.adapters.primary.maps_basemaps__primary_adapter__FastAPI import (  # noqa: E501
    basemap_seed_revisions,
    basemap_seeds,
    get_maps_basemap_service,
)
from naas_abi.apps.nexus.apps.api.app.services.maps.basemaps.builtin import DEFAULT_BASEMAP_ID
from naas_abi.apps.nexus.apps.api.app.services.maps.basemaps.service import MapsBasemapService
from naas_abi.apps.nexus.apps.api.app.services.maps.feed_layers.adapters.primary.maps_feed_layers__primary_adapter__FastAPI import (  # noqa: E501
    feed_layer_seed_revisions,
    feed_layer_seeds,
)
from naas_abi.apps.nexus.apps.api.app.services.maps.feed_layers.dependencies import (
    get_maps_feed_layer_service,
)
from naas_abi.apps.nexus.apps.api.app.services.maps.feed_layers.service import (
    MapsFeedLayerService,
)
from naas_abi.apps.nexus.apps.api.app.services.maps.layouts.adapters.primary.maps_layouts__primary_adapter__FastAPI import (  # noqa: E501
    get_maps_layout_service,
    layout_seed_revisions,
    layout_seeds,
)
from naas_abi.apps.nexus.apps.api.app.services.maps.layouts.service import MapsLayoutService
from naas_abi.apps.nexus.apps.api.app.services.maps.workspace_config import WorkspaceMapsDefaults

router = APIRouter()


@router.get("", dependencies=[guard("GetMapsCatalog")])
async def get_catalog(
    request: Request,
    response: Response,
    workspace_id: str = Query(..., min_length=1),
    current_user=Depends(get_current_user_required),
    layouts: MapsLayoutService = Depends(get_maps_layout_service),
    basemaps: MapsBasemapService = Depends(get_maps_basemap_service),
    feed_layers: MapsFeedLayerService = Depends(get_maps_feed_layer_service),
    defaults: WorkspaceMapsDefaults = Depends(maps_workspace_defaults),
) -> dict[str, Any]:
    response.headers["Cache-Control"] = "no-store"
    listed_layouts = await layouts.list(
        workspace_id,
        seeds=layout_seeds(request),
        revisions=layout_seed_revisions(request),
        enabled_feeds=defaults.feeds,
        extra_feed_ids=graph_feed_ids(request),
    )
    listed_layers = await feed_layers.list(
        workspace_id,
        seeds=feed_layer_seeds(request),
        revisions=feed_layer_seed_revisions(request),
    )
    listed_basemaps = await basemaps.list(
        workspace_id,
        seeds=basemap_seeds(request),
        revisions=basemap_seed_revisions(request),
        enabled_custom=defaults.custom_basemaps,
    )
    can_edit = await authz.allowed(
        "UpdateLayout", user=current_user, workspace=workspace_id, id="-"
    )
    return {
        # Feeds (data sources) and the layers drawn from them.
        "layouts": [layout.to_dict() for layout in listed_layouts.layouts],
        "feed_layers": [layer.to_dict() for layer in listed_layers],
        "hidden_layouts": sorted(listed_layouts.hidden),
        "hidden_feeds": sorted(listed_layouts.hidden_feeds),
        "layer_colors": listed_layouts.colors,
        "basemaps": [basemap.to_dict() for basemap in listed_basemaps.basemaps],
        "hidden_basemaps": sorted(listed_basemaps.hidden),
        "default_basemap_id": DEFAULT_BASEMAP_ID,
        "can_edit": can_edit,
    }
