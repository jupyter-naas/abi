"""Authorization of a route that is about the caller, not a workspace.

Speech and the OpenAI-compatible gateway take no workspace: a client calls them
as a user. IAM's actions are still a workspace's (``abi:<org>:<ws>:nexus:...``),
so the call is allowed when the workspace the client names allows the action
(``?workspace_id=``), or, when it names none, when any workspace the caller holds
a role in does. The decision is IAM's either way, and a caller with no
workspace is refused.
"""

# No ``from __future__ import annotations``: FastAPI resolves the annotations of the
# dependency below from the function, as ``guards`` does.
from collections.abc import Sequence

from fastapi import Depends, Request
from naas_abi.apps.nexus.apps.api.app.services.auth.adapters.primary.auth__primary_adapter__dependencies import (  # noqa: E501
    get_current_user_required,
)
from naas_abi.apps.nexus.apps.api.app.services.iam import authz as authz_module
from naas_abi.apps.nexus.apps.api.app.services.iam.authz import AuthzDenied
from naas_abi.apps.nexus.apps.api.app.services.iam.memberships import MEMBERSHIPS


async def require_in_any_workspace(
    action: str,
    *,
    user,
    workspace: str | None = None,
    id: str | Sequence[str] = (),
    feature: str | None = None,
) -> None:
    """Raise ``AuthzDenied`` unless ``workspace`` (or, with none, one of the
    caller's workspaces) allows ``action`` on ``id``."""
    if workspace:
        await authz_module.AUTHZ.require(
            action, user=user, workspace=workspace, id=id, feature=feature
        )
        return
    candidates = await MEMBERSHIPS.workspaces_of(authz_module.Authz.user_id(user) or "")
    if await authz_module.AUTHZ.allowed_in_any(
        action, user=user, workspaces=candidates, id=id, feature=feature
    ):
        return
    raise AuthzDenied(403, detail="You do not have permission to do this")


def allowed_in_any_workspace(
    action: str, *, id: str | Sequence[str] = (), feature: str | None = None
):
    """A route dependency (pair it with ``declares(action)`` for the matrix):
    ``workspace_id`` of the query, when the client sends one, else any workspace."""

    async def dependency(request: Request, user=Depends(get_current_user_required)) -> None:
        await require_in_any_workspace(
            action,
            user=user,
            workspace=request.query_params.get("workspace_id"),
            id=id,
            feature=feature,
        )

    return Depends(dependency)
