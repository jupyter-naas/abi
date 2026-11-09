"""The workspace a remote app opens in.

A remote app's grant names one workspace where IAM lets the user open the app
(its module scope, ``module:OpenApp``, ``services/apps/scopes.py``), and the
module gets it with each request (``scope["abi"]["workspace_id"]``), so its
backend can keep each workspace's data apart. IAM alone decides: a workspace
keeps no on/off state of its own for an app.
"""

from __future__ import annotations

from typing import Any
from uuid import uuid4

from fastapi import HTTPException
from naas_abi.apps.nexus.apps.api.app.services.apps.scopes import app_scope
from naas_abi.apps.nexus.apps.api.app.services.iam import authz


async def choose_workspace(
    registry: Any, user_id: str, app_id: str, workspace_id: str | None
) -> str:
    """``workspace_id`` when IAM lets the user open the app there; with none named
    (an old link), the first of the user's workspaces that does, by slug (then
    id), so a link always opens the same one."""
    scope = app_scope(app_id)
    if scope is None:
        raise HTTPException(status_code=404, detail="Unknown app")
    if workspace_id:
        await authz.require_scope(scope, user=user_id, workspace=workspace_id)
        return workspace_id
    workspaces = await registry.workspaces.list_workspaces(user_id)
    for workspace in sorted(workspaces, key=lambda w: (getattr(w, "slug", "") or "", w.id)):
        if await authz.allowed_scope(scope, user=user_id, workspace=workspace.id):
            return workspace.id
    raise HTTPException(
        status_code=403, detail="You may not open this app in any of your workspaces"
    )


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
