"""``/api/workspaces/{workspace_id}/feature-access``: Workspace settings > General ›
Features.

Reading it is reading the workspace's configuration (``GetWorkspaceConfiguration``,
as ``/configuration``). Saving is IAM's own writes made as the caller (create the
feature's policy, attach it, detach it), each audited first and decided by IAM:
the route declares them for the matrix; the checks are IAM's, inside the calls.
"""

from __future__ import annotations

from collections.abc import Awaitable
from typing import Any, Literal, TypeVar

from fastapi import APIRouter, Depends, HTTPException
from naas_abi.apps.nexus.apps.api.app.services.auth.adapters.primary.auth__primary_adapter__dependencies import (  # noqa: E501
    get_current_user_required,
)
from naas_abi.apps.nexus.apps.api.app.services.auth.adapters.primary.auth__primary_adapter__schemas import (  # noqa: E501
    User,
)
from naas_abi.apps.nexus.apps.api.app.services.feature_access.port import FeatureChange
from naas_abi.apps.nexus.apps.api.app.services.feature_access.runtime import (
    get_feature_access_service,
)
from naas_abi.apps.nexus.apps.api.app.services.feature_access.service import (
    FeatureAccessService,
)
from naas_abi.apps.nexus.apps.api.app.services.iam.guards import declares, guard
from naas_abi.apps.nexus.apps.api.app.services.iam_admin.port import IamUnavailableError
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.resources import AuditUnavailable
from naas_abi_core.services.iam.IAMPorts import (
    IAMConflictError,
    IAMNotFoundError,
    PermissionDeniedError,
)
from pydantic import BaseModel, Field

router = APIRouter()
T = TypeVar("T")

# The IAM writes a save makes as the caller.
WRITES = ("iam:CreatePolicy", "iam:AttachPolicy", "iam:DetachPolicy")


async def _call(call: Awaitable[T]) -> T:
    try:
        return await call
    except ValueError as exc:
        raise HTTPException(422, detail=str(exc)) from exc
    except PermissionDeniedError as exc:
        raise HTTPException(403, detail=str(exc)) from exc
    except IAMNotFoundError as exc:
        raise HTTPException(404, detail=str(exc)) from exc
    except IAMConflictError as exc:
        raise HTTPException(409, detail=str(exc)) from exc
    except AuditUnavailable as exc:
        raise HTTPException(503, detail=f"No change made: {exc}") from exc
    except IamUnavailableError as exc:
        raise HTTPException(503, detail=str(exc)) from exc


Service = Depends(get_feature_access_service)
Signed = Depends(get_current_user_required)


class ChangeBody(BaseModel):
    feature: str = Field(min_length=1, max_length=64)
    choice: Literal["everyone", "only", "nobody"]
    # Only…: the IAM ids of the members (usr_…) and groups (grp_…) who may use it.
    principals: list[str] = Field(default_factory=list, max_length=100)


class SaveBody(BaseModel):
    changes: list[ChangeBody] = Field(min_length=1, max_length=50)


@router.get(
    "/{workspace_id}/feature-access",
    dependencies=[
        guard(
            "GetWorkspaceConfiguration",
            denied="Only admins can view the workspace configuration",
        )
    ],
)
async def read_feature_access(
    workspace_id: str,
    user: User = Signed,
    service: FeatureAccessService = Service,
) -> dict[str, Any]:
    """Each enabled feature: who may use it here (Everyone, Only…, Nobody), the
    other policies naming it, whether the workspace offers it, and whether the caller
    may change it."""
    return await _call(service.read(user, workspace_id))


@router.put(
    "/{workspace_id}/feature-access",
    dependencies=[declares(action) for action in WRITES],
)
async def save_feature_access(
    workspace_id: str,
    body: SaveBody,
    user: User = Signed,
    service: FeatureAccessService = Service,
) -> dict[str, Any]:
    """Several features at once, each as the caller; ``errors`` names those IAM (or
    the row's rules) refused, the others are saved. Answers the state after."""
    changes = [
        FeatureChange(c.feature, c.choice, tuple(dict.fromkeys(c.principals))) for c in body.changes
    ]
    return await _call(service.save(user, workspace_id, changes))
