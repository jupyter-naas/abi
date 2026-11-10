"""``/api/iam/view-as``: start, list and stop a view of another person.

* ``GET    /workspaces?principal_id=`` the workspaces of the person where IAM accepts a
  view by the caller.
* ``POST   /`` (``principal_id``, ``workspace_id``) start a view: IAM's ``iam:ViewAs``
  decides (403 with its message), audited first.
* ``DELETE /`` stop the view.

Session only (``/api/iam/``): an API key never starts or carries a view, and neither
does a bearer session token: the view is kept on the browser's cookie session. Who may
view as whom is IAM's; there is no role check here.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from naas_abi.apps.nexus.apps.api.app.core.database import get_db
from naas_abi.apps.nexus.apps.api.app.services.auth.adapters.primary.auth__primary_adapter__dependencies import (  # noqa: E501
    get_current_user_required,
)
from naas_abi.apps.nexus.apps.api.app.services.iam.guards import declares
from naas_abi.apps.nexus.apps.api.app.services.oidc.service import ActiveSession
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.resources import AuditUnavailable
from naas_abi.apps.nexus.apps.api.app.services.view_as import runtime
from naas_abi.apps.nexus.apps.api.app.services.view_as.port import ViewAsError, Viewer
from naas_abi.apps.nexus.apps.api.app.services.view_as.service import ViewAsService
from naas_abi.apps.nexus.apps.api.app.services.view_as.views import view_json, workspace_json
from naas_abi_core.services.iam.IAMPorts import PermissionDeniedError
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(dependencies=[Depends(get_current_user_required)])


class StartBody(BaseModel):
    principal_id: str = Field(min_length=1, max_length=255)
    workspace_id: str = Field(min_length=1, max_length=255)


def _session(request: Request) -> ActiveSession:
    """The browser session the view is kept on (the viewer's, also during a view)."""
    session = getattr(request.state, "nexus_session", None)
    if session is None:
        raise HTTPException(
            status_code=403, detail="A view starts from a signed-in browser session"
        )
    return session


def _viewer(request: Request) -> Viewer:
    return runtime.viewer_of(_session(request))


def _service(db: AsyncSession = Depends(get_db)) -> ViewAsService:
    return runtime.RUNTIME.service(db)


@router.get("/workspaces", dependencies=[declares("iam:ViewAs")])
async def viewable_workspaces(
    request: Request,
    principal_id: str = Query(min_length=1, max_length=255),
    service: ViewAsService = Depends(_service),
) -> list[dict]:
    found = await service.workspaces(_viewer(request), principal_id)
    return [workspace_json(workspace) for workspace in found]


@router.post("", dependencies=[declares("iam:ViewAs")])
async def start_view(
    request: Request, body: StartBody, service: ViewAsService = Depends(_service)
) -> dict:
    try:
        record = await service.start(_viewer(request), body.principal_id, body.workspace_id)
    except PermissionDeniedError as exc:  # IAM's refusal: ``ViewAsRefused`` says why
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ViewAsError as exc:
        raise HTTPException(status_code=exc.status, detail=str(exc)) from exc
    except AuditUnavailable as exc:
        raise HTTPException(status_code=503, detail=f"No view started: {exc}") from exc
    return view_json(record)


@router.delete("")
async def stop_view(request: Request, service: ViewAsService = Depends(_service)) -> dict:
    """Ends the view of the session. It needs no right of its own: it only gives up one."""
    ended = await service.stop(_session(request).id)
    return {"stopped": ended is not None}
