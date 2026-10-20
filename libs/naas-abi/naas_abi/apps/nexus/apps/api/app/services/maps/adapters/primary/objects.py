"""FastAPI dependencies for the Maps hot paths: object store and engine cache."""

from __future__ import annotations

from typing import Any

from fastapi import Depends, HTTPException, Request
from naas_abi.apps.nexus.apps.api.app.services.maps.adapters.secondary.object_storage import (
    ObjectStorageMapsObjects,
)
from naas_abi.apps.nexus.apps.api.app.services.maps.cache import MapsCache
from naas_abi.apps.nexus.apps.api.app.services.maps.objects import MapsObjectStorePort


def _engine_services() -> Any | None:
    try:
        from naas_abi import ABIModule

        return ABIModule.get_instance().engine.services
    except Exception:  # noqa: BLE001 - standalone Nexus: no engine
        return None


def get_maps_cache(request: Request) -> MapsCache:
    """One per app: concurrent misses are coalesced across requests."""
    cache = getattr(request.app.state, "maps_cache", None)
    if cache is None:
        services = _engine_services()
        engine_cache = None
        try:
            # The module's services proxy has no cache_available(): read the service.
            engine_cache = services.cache if services is not None else None
        except Exception:  # noqa: BLE001 - no cache configured: no caching
            engine_cache = None
        cache = MapsCache(engine_cache)
        request.app.state.maps_cache = cache
    return cache


def get_maps_objects(
    request: Request, cache: MapsCache = Depends(get_maps_cache)
) -> MapsObjectStorePort:
    objects = getattr(request.app.state, "maps_objects", None)
    if objects is not None:
        return objects
    services = _engine_services()
    if services is None:
        raise HTTPException(status_code=503, detail="Object storage is not configured")
    objects = ObjectStorageMapsObjects(services.object_storage, cache)
    request.app.state.maps_objects = objects
    return objects
