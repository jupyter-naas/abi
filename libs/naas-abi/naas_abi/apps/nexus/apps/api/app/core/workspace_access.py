"""Effective workspace role: one query shape for every adapter that needs it.

A user's role on a workspace is the highest of:

- the explicit ``workspace_members`` row;
- ``owner`` when the user is ``workspaces.owner_id``;
- the role inherited from the workspace's organization: org owners
  (``organizations.owner_id`` or an ``owner`` membership) get ``owner`` and org
  admins get ``admin`` on every workspace of that organization.

Organization members with role ``member`` inherit nothing, so their access
still comes from workspace rows. Inheritance never crosses organizations.
"""

from __future__ import annotations

from naas_abi.apps.nexus.apps.api.app.models import (
    OrganizationMemberModel,
    OrganizationModel,
    WorkspaceMemberModel,
    WorkspaceModel,
)
from sqlalchemy import Select, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

ROLE_RANK: dict[str, int] = {"viewer": 0, "member": 1, "admin": 2, "owner": 3}

# Organization role -> workspace role granted on every workspace of the org.
INHERITED_FROM_ORG: dict[str, str] = {"owner": "owner", "admin": "admin"}


def max_role(*roles: str | None) -> str | None:
    """Highest-ranked role, ignoring ``None`` and unknown values."""
    known = [role for role in roles if role in ROLE_RANK]
    if not known:
        return None
    return max(known, key=ROLE_RANK.__getitem__)


def _roles_at_least(min_role: str | None) -> list[str]:
    floor = ROLE_RANK[min_role] if min_role else -1
    return [role for role, rank in ROLE_RANK.items() if rank >= floor]


async def resolve_organization_role(db: AsyncSession, user_id: str, org_id: str) -> str | None:
    member_role = (
        await db.execute(
            select(OrganizationMemberModel.role)
            .where(OrganizationMemberModel.organization_id == org_id)
            .where(OrganizationMemberModel.user_id == user_id)
        )
    ).scalar_one_or_none()
    owner_id = (
        await db.execute(select(OrganizationModel.owner_id).where(OrganizationModel.id == org_id))
    ).scalar_one_or_none()
    return max_role(member_role, "owner" if owner_id == user_id else None)


async def resolve_workspace_role(db: AsyncSession, user_id: str, workspace_id: str) -> str | None:
    workspace = (
        await db.execute(
            select(WorkspaceModel.owner_id, WorkspaceModel.organization_id).where(
                WorkspaceModel.id == workspace_id
            )
        )
    ).one_or_none()
    if workspace is None:
        return None

    explicit = (
        await db.execute(
            select(WorkspaceMemberModel.role)
            .where(WorkspaceMemberModel.workspace_id == workspace_id)
            .where(WorkspaceMemberModel.user_id == user_id)
        )
    ).scalar_one_or_none()

    inherited: str | None = None
    if workspace.organization_id:
        org_role = await resolve_organization_role(db, user_id, workspace.organization_id)
        inherited = INHERITED_FROM_ORG.get(org_role or "")

    return max_role(explicit, "owner" if workspace.owner_id == user_id else None, inherited)


def accessible_workspace_ids(user_id: str, *, min_role: str | None = None) -> Select:
    """``SELECT workspaces.id`` the user reaches with at least ``min_role``.

    Use as ``WorkspaceModel.id.in_(accessible_workspace_ids(user_id))``.
    """
    allowed = _roles_at_least(min_role)
    inheriting_org_roles = [
        org_role for org_role, ws_role in INHERITED_FROM_ORG.items() if ws_role in allowed
    ]

    conditions = [
        WorkspaceModel.id.in_(
            select(WorkspaceMemberModel.workspace_id)
            .where(WorkspaceMemberModel.user_id == user_id)
            .where(WorkspaceMemberModel.role.in_(allowed))
        ),
        WorkspaceModel.organization_id.in_(
            select(OrganizationMemberModel.organization_id)
            .where(OrganizationMemberModel.user_id == user_id)
            .where(OrganizationMemberModel.role.in_(inheriting_org_roles))
        ),
    ]
    if "owner" in allowed:
        conditions.append(WorkspaceModel.owner_id == user_id)
        conditions.append(
            WorkspaceModel.organization_id.in_(
                select(OrganizationModel.id).where(OrganizationModel.owner_id == user_id)
            )
        )
    return select(WorkspaceModel.id).where(or_(*conditions))
