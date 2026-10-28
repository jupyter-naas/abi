"""The workspace a remote app opens in.

Apps are enabled per workspace, as the catalog shows them. A remote app's grant
names one workspace where IAM lets the user open the app (its module scope,
``module:OpenApp``, ``services/apps/scopes.py``) and
where the app is enabled, and
the module gets it with each request (``scope["abi"]["workspace_id"]``), so
its backend can keep each workspace's data apart.
"""

from __future__ import annotations

from typing import Any
from uuid import uuid4

from fastapi import HTTPException
from naas_abi.apps.nexus.apps.api.app.core.workspace_catalog_seed import resolve_app_enabled
from naas_abi.apps.nexus.apps.api.app.core.workspace_seed_catalog import workspace_seed_apps
from naas_abi.apps.nexus.apps.api.app.services.apps.scopes import app_scope
from naas_abi.apps.nexus.apps.api.app.services.iam import authz


async def enabled_in(registry: Any, workspace: Any, app_id: str) -> bool:
    """Whether the workspace enables the app: its stored state, else its seed (its
    stored catalog seed first, as the catalog reads it)."""
    states = await registry.apps.get_enabled_states(workspace.id)
    return resolve_app_enabled(app_id, states, workspace_seed_apps(workspace))


async def choose_workspace(
    registry: Any, user_id: str, app_id: str, workspace_id: str | None
) -> str:
    """``workspace_id`` when IAM lets the user use the app there and it enables
    it; with none named (an old link), the first of the user's workspaces that
    does, by slug (then id), so a link always opens the same one."""
    scope = app_scope(app_id)
    if scope is None:
        raise HTTPException(status_code=404, detail="Unknown app")
    if workspace_id:
        await authz.require_scope(scope, user=user_id, workspace=workspace_id)
        workspace = await registry.workspaces.get_workspace(workspace_id)
        if workspace is not None and await enabled_in(registry, workspace, app_id):
            return workspace.id
        raise HTTPException(status_code=403, detail="This app is not enabled in this workspace")
    workspaces = await registry.workspaces.list_workspaces(user_id)
    for workspace in sorted(workspaces, key=lambda w: (getattr(w, "slug", "") or "", w.id)):
        if await authz.allowed_scope(
            scope, user=user_id, workspace=workspace.id
        ) and await enabled_in(registry, workspace, app_id):
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
