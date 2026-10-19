"""Where the drafts of a workspace's app projects live, and whose they are.

Drafts are objects under ``nexus/app-projects/<workspace>/``. IAM places that
prefix in the workspace, so a member's role reaches it (and a viewer's does not
write): the kernel checks the user on every draft access, besides the route.
"""

from __future__ import annotations

from collections.abc import Iterable

from naas_abi.apps.nexus.apps.api.app.models import WorkspaceModel
from naas_abi.apps.nexus.apps.api.app.services.apps.projects.adapters.secondary.object_storage import (
    DEFAULT_ROOT,
)
from naas_abi.apps.nexus.apps.api.app.services.apps.projects.port import (
    AppProjectError,
    workspace_segment,
)
from naas_abi.apps.nexus.apps.api.app.services.iam.placements import (
    Placement,
    on_workspace_created,
    placement_source,
)
from naas_abi_core.services.iam.names import path_parts
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


def draft_placement(workspace_id: str) -> Placement:
    """The drafts prefix of ``workspace_id``, placed in it."""
    return Placement(
        "object_storage",
        (*path_parts(DEFAULT_ROOT), workspace_segment(workspace_id)),
        workspace_id,
        prefix=True,
    )


@placement_source
async def workspace_drafts(db: AsyncSession) -> Iterable[Placement]:
    """Every workspace's drafts prefix."""
    found: list[Placement] = []
    for (workspace_id,) in (await db.execute(select(WorkspaceModel.id))).all():
        try:
            found.append(draft_placement(workspace_id))
        except AppProjectError:
            continue  # an id with no usable path segment has no drafts
    return found


@on_workspace_created
async def new_workspace_drafts(db: AsyncSession, workspace_id: str) -> Iterable[Placement]:
    try:
        return [draft_placement(workspace_id)]
    except AppProjectError:
        return []  # an id with no usable path segment has no drafts
