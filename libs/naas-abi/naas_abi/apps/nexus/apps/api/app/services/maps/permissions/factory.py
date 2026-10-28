"""One Maps access policy per process, shared by the layer, basemap and permission routes."""

from __future__ import annotations

from functools import lru_cache

from naas_abi.apps.nexus.apps.api.app.services.maps.permissions.adapters.secondary.postgres import (
    PostgresMapsGrantStore,
)
from naas_abi.apps.nexus.apps.api.app.services.maps.permissions.service import MapsAccess


@lru_cache(maxsize=1)
def postgres_maps_access() -> MapsAccess:
    return MapsAccess(PostgresMapsGrantStore())
