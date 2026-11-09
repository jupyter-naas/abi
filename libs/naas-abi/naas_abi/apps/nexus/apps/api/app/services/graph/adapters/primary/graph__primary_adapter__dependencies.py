from __future__ import annotations

from fastapi import Depends
from naas_abi.apps.nexus.apps.api.app.services.graph.service import GraphService
from naas_abi.apps.nexus.apps.api.app.services.registry import ServiceRegistry, get_service_registry


def get_graph_service(
    registry: ServiceRegistry = Depends(get_service_registry),
) -> GraphService:
    return registry.graph


async def workspace_graph_service(
    graph_service: GraphService,
    user_id: str,
    workspace_id: str,
    *,
    feature: str | None = None,
) -> GraphService:
    """The graph service bound to the workspace's view of the graphs for this user.

    The graphs themselves are the kernel's to authorize, call by call; the view
    only narrows them to the workspace. A route of a flagged section names it
    as ``feature`` (``UseFeature`` is asked first, so a caller who sees nothing
    of the workspace is refused here), or authorizes the section itself.
    """
    from fastapi import HTTPException
    from naas_abi.apps.nexus.apps.api.app.core.database import AsyncSessionLocal
    from naas_abi.apps.nexus.apps.api.app.services.graph.adapters.secondary.workspace_policy import (
        load_workspace_scope,
    )
    from naas_abi.apps.nexus.apps.api.app.services.graph.graph__schema import GraphAccessError
    from naas_abi.apps.nexus.apps.api.app.services.iam import authz

    if feature is not None:
        await authz.require("UseFeature", user=user_id, workspace=workspace_id, id=feature)
    try:
        async with AsyncSessionLocal() as db:
            scope = await load_workspace_scope(
                db, graph_service._get_catalog_store(), workspace_id, user_id
            )
        return graph_service.for_scope(scope)
    except GraphAccessError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc


async def graph_section_service(
    graph_service: GraphService, user_id: str, workspace_id: str
) -> GraphService:
    """``workspace_graph_service`` for the routes of the ``graph`` section."""
    return await workspace_graph_service(graph_service, user_id, workspace_id, feature="graph")
