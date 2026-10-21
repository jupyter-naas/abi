from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import uuid4

from naas_abi.apps.nexus.apps.api.app.services.iam.authz import AUTHZ, Authz
from naas_abi.apps.nexus.apps.api.app.services.iam.memberships import (
    MEMBERSHIPS,
    ROLE_NAMES,
    Memberships,
    best,
)
from naas_abi.apps.nexus.apps.api.app.services.iam.names import (
    NO_ORG,
    nexus_resource,
    workspace_scope,
)
from naas_abi.apps.nexus.apps.api.app.services.workspaces.port import (
    InferenceServerCreateInput,
    InferenceServerRecord,
    InferenceServerUpdateInput,
    WorkspaceCreateInput,
    WorkspaceMemberRecord,
    WorkspacePermissionPort,
    WorkspaceRecord,
    WorkspaceStatsRecord,
    WorkspaceUpdateInput,
)
from naas_abi_core import logger
from naas_abi_core.services.iam.names import scope_fields


@dataclass
class WorkspacePermissionError(PermissionError):
    workspace_id: str
    user_id: str

    def __str__(self) -> str:
        return "workspace_access_denied"


@dataclass
class LastOwnerError(ValueError):
    """The change would leave the scope without an owner."""

    scope: str

    def __str__(self) -> str:
        return "last_owner"


def _member_id(workspace_id: str, user_id: str) -> str:
    return f"member-{workspace_id}-{user_id}"


@dataclass
class WorkspaceSlugAlreadyExistsError(ValueError):
    slug: str

    def __str__(self) -> str:
        return f"workspace_slug_exists:{self.slug}"


@dataclass
class WorkspaceMemberAlreadyExistsError(ValueError):
    workspace_id: str
    user_id: str

    def __str__(self) -> str:
        return "workspace_member_already_exists"


class WorkspaceService:
    """Workspaces and their members.

    Membership is IAM's: a member holds ``builtin.<role>`` at the workspace's
    scope (``services/iam/memberships``). ``by`` names the signed-in user making
    a change, whose own rights IAM checks (an admin can never touch an owner).
    """

    def __init__(
        self,
        adapter: WorkspacePermissionPort,
        memberships: Memberships = MEMBERSHIPS,
        authz: Authz | None = None,
    ):
        self.adapter = adapter
        self.memberships = memberships
        self._authz = authz or AUTHZ

    async def _scope(self, workspace_id: str) -> str | None:
        org = await self._authz.org_of(workspace_id)
        return workspace_scope(org, workspace_id) if org is not None else None

    async def get_workspace_role(self, user_id: str, workspace_id: str) -> str | None:
        """The highest role the user holds in the workspace: their own there, or the
        organization-wide role their org role (owner, admin) carries."""
        scope = await self._scope(workspace_id)
        if scope is None:
            return None
        org, _ = scope_fields(scope)
        held = await self.memberships.roles_of(user_id)
        return best([r for r in (held.get(scope), held.get(f"abi:{org}:*")) if r])

    async def effective_roles(
        self, user_id: str, workspaces: list[WorkspaceRecord]
    ) -> list[str | None]:
        """``get_workspace_role`` of each workspace, from one read of the user's roles."""
        held = await self.memberships.roles_of(user_id)
        return [
            best(
                [
                    r
                    for r in (
                        held.get(workspace_scope(row.organization_id, row.id)),
                        held.get(f"abi:{row.organization_id or NO_ORG}:*"),
                    )
                    if r
                ]
            )
            for row in workspaces
        ]

    async def require_workspace_access(self, user_id: str, workspace_id: str) -> str:
        role = await self.get_workspace_role(user_id=user_id, workspace_id=workspace_id)
        if role is None:
            raise WorkspacePermissionError(workspace_id=workspace_id, user_id=user_id)
        return role

    async def list_workspaces(self, user_id: str) -> list[WorkspaceRecord]:
        """The workspaces IAM lets the user list (``nexus:ListWorkspaces``)."""
        rows = await self.adapter.list_all_workspaces()
        return await self._authz.filter(
            "ListWorkspaces",
            rows,
            user=user_id,
            resource_of=lambda row: nexus_resource(
                "workspace", org=row.organization_id or NO_ORG, workspace=row.id
            ),
        )

    async def roles_of(self, user_id: str) -> dict[str, str]:
        """``{workspace id: role}`` the user holds directly."""
        return await self.memberships.scopes_of(user_id, level="workspace")

    async def get_workspace(self, workspace_id: str) -> WorkspaceRecord | None:
        return await self.adapter.get_workspace_by_id(workspace_id=workspace_id)

    async def get_workspace_by_slug(self, slug: str) -> WorkspaceRecord | None:
        return await self.adapter.get_workspace_by_slug(slug=slug)

    async def create_workspace(self, workspace: WorkspaceCreateInput) -> WorkspaceRecord:
        """Create a workspace and make ``owner_id`` its owner.

        The caller checked the right to create it in the organization (bug d:
        never a request field's say-so). A failure after the row exists in IAM
        removes the row again.
        """
        if await self.adapter.workspace_slug_exists(slug=workspace.slug):
            raise WorkspaceSlugAlreadyExistsError(slug=workspace.slug)
        record = await self.adapter.create_workspace(workspace=workspace)
        try:
            scope = await self.memberships.register_workspace(record.organization_id, record.id)
            await self.memberships.grant(workspace.owner_id, "owner", scope)
        except Exception:
            await self.adapter.delete_workspace(workspace_id=record.id)
            try:
                await self.memberships.drop_scope(record.organization_id or NO_ORG, record.id)
            except Exception:  # noqa: BLE001 - the original failure is what is raised
                logger.exception(f"Could not forget the scope of workspace {record.id}")
            raise
        return record

    async def delete_workspace(self, workspace_id: str) -> bool:
        record = await self.adapter.get_workspace_by_id(workspace_id=workspace_id)
        deleted = await self.adapter.delete_workspace(workspace_id=workspace_id)
        if deleted and record is not None:
            await self.memberships.drop_scope(record.organization_id or NO_ORG, workspace_id)
        return deleted

    async def update_workspace(
        self, workspace_id: str, updates: WorkspaceUpdateInput
    ) -> WorkspaceRecord | None:
        return await self.adapter.update_workspace(workspace_id=workspace_id, updates=updates)

    async def set_workspace_feature_overrides(
        self, workspace_id: str, overrides: dict[str, bool] | None
    ) -> WorkspaceRecord | None:
        return await self.adapter.set_workspace_feature_overrides(
            workspace_id=workspace_id, overrides=overrides
        )

    async def get_workspace_stats(self, workspace_id: str) -> WorkspaceStatsRecord | None:
        return await self.adapter.get_workspace_stats(workspace_id=workspace_id)

    async def list_workspace_members(self, workspace_id: str) -> list[WorkspaceMemberRecord]:
        """The workspace's members, then the owners and admins of its organization
        who reach it through their org role (``source: "organization"``, read-only:
        that access is managed in Organization > Users)."""
        scope = await self._scope(workspace_id)
        if scope is None:
            return []
        members = await self.memberships.members(scope)
        org = await self._authz.org_of(workspace_id)
        inherited = (
            await self.memberships.members(f"abi:{org}:*") if org not in (None, NO_ORG) else []
        )
        explicit_ids = {m.user_id for m in members}
        inherited = [m for m in inherited if m.user_id not in explicit_ids]
        users = await self.adapter.get_users_by_ids([m.user_id for m in members + inherited])
        records = [
            WorkspaceMemberRecord(
                id=_member_id(workspace_id, member.user_id),
                workspace_id=workspace_id,
                user_id=member.user_id,
                role=member.role,
                email=users[member.user_id].email,
                name=users[member.user_id].name,
                created_at=member.since,
            )
            for member in members
            if member.user_id in users
        ]
        records += sorted(
            (
                WorkspaceMemberRecord(
                    id=f"org:{member.user_id}",
                    workspace_id=workspace_id,
                    user_id=member.user_id,
                    role=member.role,
                    email=users[member.user_id].email,
                    name=users[member.user_id].name,
                    created_at=None,
                    source="organization",
                )
                for member in inherited
                if member.user_id in users
            ),
            key=lambda record: record.email or "",
        )
        return records

    async def invite_workspace_member(
        self, workspace_id: str, email: str, role: str, *, by: Any
    ) -> WorkspaceMemberRecord | None:
        """Give an existing user by email a role. Someone with no account is
        invited through an identity provider instead (``services/invites``).
        ``MembershipDenied`` when IAM
        refuses ``by`` this role (granting ``owner`` is the owner's)."""
        normalized_email = email.lower().strip()
        user = await self.adapter.get_user_by_email(email=normalized_email)
        if user is None:
            return None
        scope = await self._scope(workspace_id)
        if scope is None:
            return None
        if await self.memberships.role_at(user.id, scope) is not None:
            raise WorkspaceMemberAlreadyExistsError(workspace_id=workspace_id, user_id=user.id)
        await self.memberships.grant(user.id, role, scope, by=by)
        return WorkspaceMemberRecord(
            id=_member_id(workspace_id, user.id),
            workspace_id=workspace_id,
            user_id=user.id,
            role=role,
            email=user.email,
            name=user.name,
        )

    async def remove_workspace_member(self, workspace_id: str, user_id: str, *, by: Any) -> bool:
        scope = await self._scope(workspace_id)
        if scope is None:
            return False
        if await self.memberships.role_at(user_id, scope) == "owner":
            await self.memberships.check(user_id, None, scope, by=by)
            await self._keep_an_owner(scope, user_id)
        return await self.memberships.revoke(user_id, scope, by=by)

    async def update_workspace_member(
        self, workspace_id: str, user_id: str, updates: dict[str, Any], *, by: Any
    ) -> bool:
        role = updates.get("role")
        if role not in ROLE_NAMES:
            return False
        scope = await self._scope(workspace_id)
        if scope is None:
            return False
        held = await self.memberships.role_at(user_id, scope)
        if held is None:
            return False
        if held == "owner" and role != "owner":
            await self.memberships.check(user_id, role, scope, by=by)
            await self._keep_an_owner(scope, user_id)
        await self.memberships.grant(user_id, role, scope, by=by)
        return True

    async def _keep_an_owner(self, scope: str, leaving: str) -> None:
        owners = [m for m in await self.memberships.members(scope) if m.role == "owner"]
        if all(m.user_id == leaving for m in owners):
            raise LastOwnerError(scope)

    async def list_inference_servers(self, workspace_id: str) -> list[InferenceServerRecord]:
        return await self.adapter.list_inference_servers(workspace_id=workspace_id)

    async def create_inference_server(
        self,
        workspace_id: str,
        name: str,
        server_type: str,
        endpoint: str,
        description: str | None,
        enabled: bool,
        api_key: str | None,
        health_path: str | None,
        models_path: str | None,
    ) -> InferenceServerRecord:
        return await self.adapter.create_inference_server(
            InferenceServerCreateInput(
                id=str(uuid4()),
                workspace_id=workspace_id,
                name=name,
                type=server_type,
                endpoint=endpoint.rstrip("/"),
                description=description,
                enabled=enabled,
                api_key=api_key,
                health_path=health_path,
                models_path=models_path,
            )
        )

    async def update_inference_server(
        self,
        workspace_id: str,
        server_id: str,
        name: str | None,
        endpoint: str | None,
        description: str | None,
        enabled: bool | None,
        api_key: str | None,
        health_path: str | None,
        models_path: str | None,
    ) -> InferenceServerRecord | None:
        clean_endpoint = endpoint.rstrip("/") if endpoint is not None else None
        return await self.adapter.update_inference_server(
            workspace_id=workspace_id,
            server_id=server_id,
            updates=InferenceServerUpdateInput(
                name=name,
                endpoint=clean_endpoint,
                description=description,
                enabled=enabled,
                api_key=api_key,
                health_path=health_path,
                models_path=models_path,
            ),
        )

    async def delete_inference_server(self, workspace_id: str, server_id: str) -> bool:
        return await self.adapter.delete_inference_server(
            workspace_id=workspace_id,
            server_id=server_id,
        )

    async def update_workspace_logo(
        self, workspace_id: str, logo_url: str | None
    ) -> WorkspaceRecord | None:
        return await self.adapter.set_workspace_logo(workspace_id=workspace_id, logo_url=logo_url)
