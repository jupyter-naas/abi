"""``guard`` for a project of the office routers (slides, documents, sheets).

A project is ``project/<kind>/<slug>``: the kind comes first, so a policy can
name every slide deck (``project/slides/*``). ``guard`` appends fixed id parts
after the named ones, so the kind is a prefix this guard puts in front.
"""

# No ``from __future__ import annotations``: see ``guards.Guard``.
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, TypeVar

from fastapi import Depends, Request
from naas_abi.apps.nexus.apps.api.app.services.auth.adapters.primary.auth__primary_adapter__dependencies import (  # noqa: E501
    get_current_user_required,
)
from naas_abi.apps.nexus.apps.api.app.services.iam import authz as authz_module
from naas_abi.apps.nexus.apps.api.app.services.iam.guards import Guard, _param
from naas_abi.apps.nexus.apps.api.app.services.iam.names import nexus_resource

KINDS = ("slides", "documents", "sheets")
_P = TypeVar("_P")


@dataclass(frozen=True)
class ProjectGuard(Guard):
    """The ``guard`` of a route on ``project/<kind>/<id parts>``."""

    kind: str = ""

    async def __call__(self, request: Request, user=Depends(get_current_user_required)) -> None:
        parts = [self.kind, *(_param(request, name) for name in self.id), *self.literal]
        await authz_module.AUTHZ.require(
            self.action,
            user=user,
            workspace=_param(request, self.workspace) if self.workspace else None,
            id=parts,
            feature=self.feature,
        )


def project_guard(
    action: str,
    kind: str,
    *,
    id: str | Sequence[str] = "slug",
    literal: str | Sequence[str] = (),
):
    """``dependencies=[project_guard("GetProject", "slides")]``: the workspace is
    the ``workspace_id`` parameter and the project's slug the ``slug`` one
    (``id=()`` and ``literal="-"`` for a list)."""
    assert kind in KINDS, kind
    return Depends(
        ProjectGuard(
            action=action,
            id=(id,) if isinstance(id, str) else tuple(id),
            literal=(literal,) if isinstance(literal, str) else tuple(literal),
            feature=kind,
            kind=kind,
        )
    )


async def readable_projects(
    projects: Sequence[_P], *, kind: str, workspace_id: str, user: Any
) -> list[_P]:
    """The projects of a list the user may read (RFC §5.5): a policy may deny one
    deck of a workspace whose others the role reaches."""
    org = await authz_module.AUTHZ.org_of(workspace_id)
    if org is None:
        return []
    return await authz_module.AUTHZ.filter(
        "GetProject",
        projects,
        user=user,
        resource_of=lambda project: nexus_resource(
            "project", org=org, workspace=workspace_id, id=(kind, project.slug)
        ),
    )
