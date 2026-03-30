from __future__ import annotations

from fastapi import Depends
from naas_abi.apps.nexus.apps.api.app.services.registry import ServiceRegistry, get_service_registry
from naas_abi.apps.nexus.apps.api.app.services.search.service import SearchService


def get_search_service(
    registry: ServiceRegistry = Depends(get_service_registry),
) -> SearchService:
    return registry.search
