"""The workspace a remote app opens in.

Apps are enabled per workspace, as the catalog shows them. A remote app's grant
names one workspace that the user can open and where the app is enabled, and
the module gets it with each request (``scope["abi"]["workspace_id"]``), so
its backend can keep each workspace's data apart.
"""

from __future__ import annotations

from typing import Any
from uuid import uuid4

from fastapi import HTTPException
from naas_abi.apps.nexus.apps.api.app.core.workspace_catalog_seed import (
    resolve_app_enabled,
    workspace_seed_for_slug,
)
from naas_abi.apps.nexus.apps.api.app.services.workspaces import WorkspacePermissionError


async def enabled_in(registry: Any, workspace: Any, app_id: str) -> bool:
    """Whether the workspace enables the app: its stored state, else its seed."""
    states = await registry.apps.get_enabled_states(workspace.id)
    seed = workspace_seed_for_slug(getattr(workspace, "slug", None))
    seed_apps = {
        str(app).strip() for app in (getattr(seed, "apps", None) or ()) if str(app).strip()
    }
    return resolve_app_enabled(app_id, states, seed_apps)


async def choose_workspace(
    registry: Any, user_id: str, app_id: str, workspace_id: str | None
) -> str:
    """``workspace_id`` when the user can open it and it enables the app; with
    none named (an old link), the first of the user's workspaces that does."""
    if workspace_id:
        try:
            await registry.workspaces.require_workspace_access(
                user_id=user_id, workspace_id=workspace_id
            )
        except WorkspacePermissionError as exc:
            raise HTTPException(
                status_code=403, detail="You do not have access to this workspace"
            ) from exc
        workspace = await registry.workspaces.get_workspace(workspace_id)
        if workspace is not None and await enabled_in(registry, workspace, app_id):
            return workspace.id
        raise HTTPException(status_code=403, detail="This app is not enabled in this workspace")
    for workspace in await registry.workspaces.list_workspaces(user_id):
        if await enabled_in(registry, workspace, app_id):
            return workspace.id
    raise HTTPException(status_code=403, detail="This app is not enabled in any of your workspaces")


async def remote_app_workspace(user_id: str, app_id: str, workspace_id: str | None) -> str:
    """``choose_workspace`` on the service registry, in a database session."""
    from naas_abi.apps.nexus.apps.api.app.core.database import AsyncSessionLocal
    from naas_abi.apps.nexus.apps.api.app.core.postgres_session_registry import (
        PostgresSessionRegistry,
    )
    from naas_abi.apps.nexus.apps.api.app.services.registry import ServiceRegistry

    async with AsyncSessionLocal() as db:
        sessions = PostgresSessionRegistry.instance()
        session_id = f"sess-{uuid4().hex}"
        sessions.bind(session_id=session_id, db=db)
        token = sessions.set_current_session(session_id)
        try:
            return await choose_workspace(ServiceRegistry.instance(), user_id, app_id, workspace_id)
        finally:
            sessions.reset_current_session(token)
            sessions.unbind(session_id)
