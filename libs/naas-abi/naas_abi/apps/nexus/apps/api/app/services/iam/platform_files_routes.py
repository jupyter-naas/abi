"""``/api/workspaces/{workspace_id}/platform-files`` (Workspace settings > General ›
Platform Files): Off, Read, or Read and write.

The setting is the ``GivenPlatformFiles`` section of the workspace's offer, "<W> access"
(``given_files``, ADR ``20261125_offer_gives_outside_resources``), read and written
through the offer service as the offer's Configuration does
(``PUT /api/workspaces/{id}/offer/files``). Reading is reading the workspace's
configuration (``GetWorkspaceConfiguration``). Changing it is a write of "<W> access" as
the caller: IAM decides, and only who holds Platform Files (the platform admin) gives
it; a workspace's admin may narrow or remove it.
"""

from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, Depends
from naas_abi.apps.nexus.apps.api.app.services.auth.adapters.primary.auth__primary_adapter__dependencies import (  # noqa: E501
    get_current_user_required,
)
from naas_abi.apps.nexus.apps.api.app.services.auth.adapters.primary.auth__primary_adapter__schemas import (  # noqa: E501
    User,
)
from naas_abi.apps.nexus.apps.api.app.services.feature_access.adapters.primary.feature_access__primary_adapter__FastAPI import (  # noqa: E501
    WRITES,
    _call,
)
from naas_abi.apps.nexus.apps.api.app.services.feature_access.runtime import (
    get_feature_access_service,
)
from naas_abi.apps.nexus.apps.api.app.services.feature_access.service import (
    FeatureAccessService,
)
from naas_abi.apps.nexus.apps.api.app.services.iam.given_files import PLATFORM_FILES
from naas_abi.apps.nexus.apps.api.app.services.iam.guards import declares, guard
from pydantic import BaseModel

router = APIRouter()


def _state(offer: dict[str, Any]) -> dict[str, Any]:
    row = next(r for r in offer["files"] if r["key"] == PLATFORM_FILES)
    return {
        "workspace_id": offer["workspace_id"],
        "mode": row["mode"],
        "can_change": row["editable"],
    }


class PlatformFilesBody(BaseModel):
    mode: Literal["off", "read", "write"]


@router.get(
    "/{workspace_id}/platform-files",
    dependencies=[
        guard(
            "GetWorkspaceConfiguration",
            denied="Only admins can view the workspace configuration",
        )
    ],
)
async def read_platform_files(
    workspace_id: str,
    user: User = Depends(get_current_user_required),
    service: FeatureAccessService = Depends(get_feature_access_service),
):
    """``{workspace_id, mode, can_change}``: what the workspace gives its people of
    Platform Files (``off``, ``read``, ``write``), and whether the caller may change it."""
    return _state(await _call(service.read_offer(user, workspace_id)))


@router.put(
    "/{workspace_id}/platform-files",
    dependencies=[declares(action) for action in WRITES],
)
async def save_platform_files(
    workspace_id: str,
    body: PlatformFilesBody,
    user: User = Depends(get_current_user_required),
    service: FeatureAccessService = Depends(get_feature_access_service),
):
    """Give the workspace's people Platform Files, as the caller: 403 unless they hold
    it (or only narrow it). Answers the state after."""
    return _state(await _call(service.set_files(user, workspace_id, {PLATFORM_FILES: body.mode})))
