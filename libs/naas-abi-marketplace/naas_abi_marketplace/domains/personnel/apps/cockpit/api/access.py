"""Who may read the Personnel Cockpit's datasets.

In Nexus: a signed-in user who belongs to the workspace the cockpit is opened in
(``?workspace_id=``). Without Nexus (the engine alone): the engine's API key.
"""

from __future__ import annotations

import hmac
import os
from typing import Any

from fastapi import Depends, HTTPException, Query, Request, status


def _bearer(request: Request) -> str:
    header = request.headers.get("Authorization") or ""
    return header[7:].strip() if header.lower().startswith("bearer ") else ""


def _api_key_holder(request: Request) -> str:
    expected = os.environ.get("ABI_API_KEY") or ""
    token = _bearer(request)
    if not expected or not token or not hmac.compare_digest(token, expected):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return "api-key"


def _nexus() -> tuple[Any, Any] | None:
    try:
        from naas_abi.apps.nexus.apps.api.app.services.auth.adapters.primary.auth__primary_adapter__dependencies import (
            get_current_user_required,
            require_workspace_access,
        )
    except ImportError:
        return None
    return get_current_user_required, require_workspace_access


def cockpit_access() -> Any:
    """The router's dependency: a workspace member in Nexus, else the API key."""
    nexus = _nexus()
    if nexus is None:
        return _api_key_holder
    current_user_dependency, require_workspace_access = nexus

    async def workspace_member(
        workspace_id: str | None = Query(None, max_length=100),
        current_user: Any = Depends(current_user_dependency),
    ) -> str:
        if not workspace_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Open the cockpit from a workspace",
            )
        await require_workspace_access(str(current_user.id), workspace_id)
        return str(current_user.id)

    return workspace_member
