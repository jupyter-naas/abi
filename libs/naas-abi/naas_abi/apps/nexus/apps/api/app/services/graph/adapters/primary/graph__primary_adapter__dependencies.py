from __future__ import annotations

from fastapi import Depends
from naas_abi.apps.nexus.apps.api.app.services.graph.service import GraphService
from naas_abi.apps.nexus.apps.api.app.services.registry import ServiceRegistry, get_service_registry


def get_graph_service(
    registry: ServiceRegistry = Depends(get_service_registry),
) -> GraphService:
    return registry.graph
