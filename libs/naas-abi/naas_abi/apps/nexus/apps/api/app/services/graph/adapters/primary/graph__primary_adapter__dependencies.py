from __future__ import annotations

from fastapi import Depends
from naas_abi.apps.nexus.apps.api.app.services.graph.service import GraphService
from naas_abi.apps.nexus.apps.api.app.services.registry import ServiceRegistry, get_service_registry


def get_graph_service(
    registry: ServiceRegistry = Depends(get_service_registry),
) -> GraphService:
    return registry.graph


async def workspace_graph_service(graph_service: GraphService, user_id: str, workspace_id: str) -> GraphService:
    from fastapi import HTTPException
    from naas_abi.apps.nexus.apps.api.app.core.database import AsyncSessionLocal
    from naas_abi.apps.nexus.apps.api.app.services.auth.adapters.primary.auth__primary_adapter__dependencies import (
        require_workspace_access,
    )
    from naas_abi.apps.nexus.apps.api.app.services.graph.adapters.secondary.workspace_policy import (
        load_workspace_scope,
    )
    from naas_abi.apps.nexus.apps.api.app.services.graph.graph__schema import GraphAccessError

    role = await require_workspace_access(user_id, workspace_id)
    try:
        async with AsyncSessionLocal() as db:
            scope = await load_workspace_scope(db, graph_service._get_catalog_store(), workspace_id, role)
        return graph_service.for_scope(scope)
    except GraphAccessError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
