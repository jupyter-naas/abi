"""``/api/workspaces/{workspace_id}/platform-files`` (Workspace settings > General ›
Platform Files): Off, Read, or Read and write (``platform_files``, #1590).

Reading is reading the workspace's configuration (``GetWorkspaceConfiguration``, as
``/feature-access``). Changing it is IAM's own writes made as the caller (a group made
at the platform, a platform policy attached to it): IAM decides, and only the platform
admin holds them. The route declares them for the matrix; the check is IAM's, inside
the call.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, Literal, TypeVar

from fastapi import APIRouter, Depends, HTTPException
from naas_abi.apps.nexus.apps.api.app.services.auth.adapters.primary.auth__primary_adapter__dependencies import (  # noqa: E501
    get_current_user_required,
)
from naas_abi.apps.nexus.apps.api.app.services.auth.adapters.primary.auth__primary_adapter__schemas import (  # noqa: E501
    User,
)
from naas_abi.apps.nexus.apps.api.app.services.iam import platform_files
from naas_abi.apps.nexus.apps.api.app.services.iam import runtime as iam_runtime
from naas_abi.apps.nexus.apps.api.app.services.iam.authz import AUTHZ
from naas_abi.apps.nexus.apps.api.app.services.iam.guards import declares, guard
from naas_abi_core.engine.call_context import use_call_context
from naas_abi_core.services.iam.IAMPorts import IAMNotFoundError, PermissionDeniedError
from pydantic import BaseModel
from starlette.concurrency import run_in_threadpool

router = APIRouter()
T = TypeVar("T")

# The IAM writes a change makes as the caller.
WRITES = ("iam:CreateGroup", "iam:AttachPolicy")


async def _as_caller(user: User, work: Callable[[Any], T]) -> T:
    """``work(iam)`` in a worker thread, as the caller (Nexus on their behalf)."""
    context = AUTHZ.context(user)

    def run() -> T:
        with use_call_context(context):
            return work(iam_runtime.iam())

    try:
        return await run_in_threadpool(run)
    except ValueError as exc:
        raise HTTPException(422, detail=str(exc)) from exc
    except PermissionDeniedError as exc:
        raise HTTPException(403, detail=str(exc)) from exc
    except IAMNotFoundError as exc:
        raise HTTPException(404, detail=str(exc)) from exc
    except iam_runtime.IAMUnavailableError as exc:
        raise HTTPException(503, detail=str(exc)) from exc


def _state(iam: Any, workspace_id: str) -> dict[str, Any]:
    return {
        "workspace_id": workspace_id,
        "mode": platform_files.workspace_platform_files(iam, workspace_id),
        "can_change": platform_files.may_set(iam),
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
async def read_platform_files(workspace_id: str, user: User = Depends(get_current_user_required)):
    """``{workspace_id, mode, can_change}``: what the workspace gives its people of
    Platform Files (``off``, ``read``, ``write``), and whether the caller may change it."""
    return await _as_caller(user, lambda iam: _state(iam, workspace_id))


@router.put(
    "/{workspace_id}/platform-files",
    dependencies=[declares(action) for action in WRITES],
)
async def save_platform_files(
    workspace_id: str,
    body: PlatformFilesBody,
    user: User = Depends(get_current_user_required),
):
    """Give the workspace's people Platform Files, as the caller: 403 unless a
    platform admin. Answers the state after."""

    def change(iam: Any) -> dict[str, Any]:
        platform_files.set_workspace_platform_files(iam, workspace_id, body.mode)
        return _state(iam, workspace_id)

    return await _as_caller(user, change)
