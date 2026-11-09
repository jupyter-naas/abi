"""What the coding-environment and code-review routers share (HTTP side).

The kernel decides on repositories and environments with the user's role
(``repo_access``); this module turns its answers into HTTP:

* ``authorize_repo`` / ``authorize_environment``: 404 for what the workspace
  does not own, 403 for what the caller sees but may not do;
* ``KernelRoute``: a kernel refusal (``PermissionDeniedError`` when the caller
  sees the resource, ``ResourceNotFoundError`` when not) that a handler lets
  through is a 403 or a 404, never a 500;
* ``source_control_error``: a forge error as its status.
"""

from __future__ import annotations

from collections.abc import Callable, Coroutine
from typing import Any

from fastapi import HTTPException, Request, Response
from fastapi.concurrency import run_in_threadpool
from fastapi.routing import APIRoute
from naas_abi.apps.nexus.apps.api.app.services.coding_environment.repo_access import (
    AuthorizationUnavailable,
    EnvironmentNotInWorkspace,
    RepoAccessDenied,
    RepoNotInWorkspace,
)
from naas_abi.apps.nexus.apps.api.app.services.coding_environment.repo_access import (
    authorize_environment as _authorize_environment,
)
from naas_abi.apps.nexus.apps.api.app.services.coding_environment.repo_access import (
    authorize_repo as _authorize_repo,
)
from naas_abi_core.services.iam.IAMPorts import (
    IIAMService,
    PermissionDeniedError,
    ResourceNotFoundError,
)
from naas_abi_core.services.source_control.SourceControlPorts import (
    AccessDeniedError,
    BranchNotFoundError,
    RepoNotFoundError,
    SourceControlError,
)


def get_iam(request: Request) -> IIAMService | None:
    """The engine's IAM, or None when no engine is loaded (nothing is granted)."""
    iam = getattr(request.app.state, "iam", None)
    if iam is not None:
        return iam
    try:
        from naas_abi import ABIModule  # noqa: PLC0415

        services = ABIModule.get_instance().engine.services
        iam = services.iam if services.iam_available() else None
    except Exception:
        return None
    request.app.state.iam = iam
    return iam


async def authorize_repo(
    iam: IIAMService | None, repo_id: str, workspace_id: str, *, write: bool
) -> None:
    """``repo_access.authorize_repo`` as HTTP: 404 for a repository this
    workspace does not have, 403 for one it has but the caller may not use so."""
    try:
        await run_in_threadpool(_authorize_repo, iam, repo_id, workspace_id, write=write)
    except RepoNotInWorkspace as exc:
        raise HTTPException(status_code=404, detail="Repository not found.") from exc
    except RepoAccessDenied as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except AuthorizationUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


async def authorize_environment(
    iam: IIAMService | None, environment_id: str, workspace_id: str
) -> None:
    """``repo_access.authorize_environment`` as HTTP: 404 for an environment of
    another workspace."""
    try:
        await run_in_threadpool(_authorize_environment, iam, environment_id, workspace_id)
    except EnvironmentNotInWorkspace as exc:
        raise HTTPException(status_code=404, detail="Environment not found.") from exc
    except AuthorizationUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


def source_control_error(exc: SourceControlError) -> HTTPException:
    """A forge error as HTTP: what the caller may not see is 404, a refusal 403,
    anything else the forge's failure (502)."""
    if isinstance(exc, RepoNotFoundError | BranchNotFoundError):
        status_code = 404
    elif isinstance(exc, AccessDeniedError):
        status_code = 403
    else:
        status_code = 502
    return HTTPException(status_code=status_code, detail=str(exc) or type(exc).__name__)


class KernelRoute(APIRoute):
    """A route whose kernel refusals answer 403 (the caller sees the resource)
    or 404 (it does not), whatever the handler caught."""

    def get_route_handler(self) -> Callable[[Request], Coroutine[Any, Any, Response]]:
        handler = super().get_route_handler()

        async def guarded(request: Request) -> Response:
            try:
                return await handler(request)
            except PermissionDeniedError as exc:
                raise HTTPException(
                    status_code=403, detail="You do not have permission to do this"
                ) from exc
            except ResourceNotFoundError as exc:
                raise HTTPException(status_code=404, detail="Not found") from exc

        return guarded
