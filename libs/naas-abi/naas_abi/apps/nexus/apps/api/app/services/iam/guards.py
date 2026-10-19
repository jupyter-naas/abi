"""Authorization declared on the route (RFC §6.5, §10.2).

A route names the action it performs, once, in its decorator::

    @router.put("/{workspace_id}/files/{drive}/{path:path}",
                dependencies=[guard("PutFile", id=("drive", "path"), feature="files")])

``guard`` is a FastAPI dependency: it runs before the request body is
validated, asks IAM (``authz.require``) as ``api`` on behalf of the signed-in
user, and answers 401/403/404 itself. Because it is declared, the matrix test
(``route_matrix_test``) reads every route's action and proves viewers can read
and not write.

The workspace (or organization) and the id parts of the resource are the names
of the request's path or query parameters. When the resource can only be named
after loading it (a conversation's owner, a project's kind), or the workspace is
in the body, the route calls ``authz.require`` itself and declares the action
with ``declares`` so the matrix still sees it.
"""

# No ``from __future__ import annotations``: FastAPI reads the annotations of
# ``Guard.__call__`` from the instance, which has no module globals to resolve strings in.
from collections.abc import Sequence
from dataclasses import dataclass

from fastapi import Depends, HTTPException, Request
from naas_abi.apps.nexus.apps.api.app.services.auth.adapters.primary.auth__primary_adapter__dependencies import (  # noqa: E501
    get_current_user_required,
)
from naas_abi.apps.nexus.apps.api.app.services.iam import authz as authz_module


def _param(request: Request, name: str) -> str:
    value = request.path_params.get(name)
    if value is None:
        value = request.query_params.get(name)
    if value is None or value == "":
        raise HTTPException(status_code=422, detail=f"Missing {name}")
    return str(value)


@dataclass(frozen=True)
class Guard:
    """The dependency ``guard`` builds: callable, and readable by the matrix."""

    action: str
    workspace: str | None = "workspace_id"
    org: str | None = None
    id: tuple[str, ...] = ()
    feature: str | None = None
    # Fixed id parts placed after the named ones (``-`` for a list).
    literal: tuple[str, ...] = ()
    # What a caller who sees the resource but may not do this is told.
    denied: str | None = None

    async def __call__(self, request: Request, user=Depends(get_current_user_required)) -> None:
        parts = [_param(request, name) for name in self.id]
        # ``literal`` parts are fixed strings placed after the named ones.
        parts += list(self.literal)
        await authz_module.AUTHZ.require(
            self.action,
            user=user,
            workspace=_param(request, self.workspace) if self.workspace else None,
            org=_param(request, self.org) if self.org else None,
            id=parts if len(parts) != 1 else parts[0],
            feature=self.feature,
            denied=self.denied,
        )


@dataclass(frozen=True)
class Declared:
    """A no-op dependency naming the action a route authorizes inline."""

    action: str

    async def __call__(self) -> None:
        return None


def guard(
    action: str,
    *,
    workspace: str | None = "workspace_id",
    org: str | None = None,
    id: str | Sequence[str] = (),
    literal: str | Sequence[str] = (),
    feature: str | None = None,
    denied: str | None = None,
):
    """A route dependency: ``dependencies=[guard("GetWorkspace")]``.

    ``workspace``/``org``: the request parameter holding the id (``workspace``
    defaults to ``workspace_id``; pass ``None`` for platform actions).
    ``id``: the request parameters whose values form the resource id, in order.
    ``literal``: fixed id parts appended after them (``"-"`` for a list).
    ``denied``: the message of a 403 for a caller who sees the resource.
    """
    return Depends(
        Guard(
            action=action,
            workspace=workspace if org is None else None,
            org=org,
            id=(id,) if isinstance(id, str) else tuple(id),
            literal=(literal,) if isinstance(literal, str) else tuple(literal),
            feature=feature,
            denied=denied,
        )
    )


def declares(action: str):
    """``dependencies=[declares("SendMessage")]``: the route authorizes ``action``
    itself (inline), and says so for the matrix."""
    return Depends(Declared(action))
