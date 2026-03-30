from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import uuid4

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


@dataclass
class WorkspacePermissionError(PermissionError):
    workspace_id: str
    user_id: str

    def __str__(self) -> str:
        return "workspace_access_denied"


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
    def __init__(self, adapter: WorkspacePermissionPort):
        self.adapter = adapter

    async def get_workspace_role(self, user_id: str, workspace_id: str) -> str | None:
        return await self.adapter.get_workspace_role(user_id=user_id, workspace_id=workspace_id)

    async def require_workspace_access(self, user_id: str, workspace_id: str) -> str:
        role = await self.get_workspace_role(user_id=user_id, workspace_id=workspace_id)
        if role is None:
            raise WorkspacePermissionError(workspace_id=workspace_id, user_id=user_id)
        return role

    async def list_workspaces(self, user_id: str) -> list[WorkspaceRecord]:
        return await self.adapter.list_workspaces_for_user(user_id=user_id)

    async def get_workspace(self, workspace_id: str) -> WorkspaceRecord | None:
        return await self.adapter.get_workspace_by_id(workspace_id=workspace_id)

    async def get_workspace_by_slug(self, slug: str) -> WorkspaceRecord | None:
        return await self.adapter.get_workspace_by_slug(slug=slug)

    async def create_workspace(self, workspace: WorkspaceCreateInput) -> WorkspaceRecord:
        if await self.adapter.workspace_slug_exists(slug=workspace.slug):
            raise WorkspaceSlugAlreadyExistsError(slug=workspace.slug)
        return await self.adapter.create_workspace(workspace=workspace)

    async def delete_workspace(self, workspace_id: str) -> bool:
        return await self.adapter.delete_workspace(workspace_id=workspace_id)

    async def update_workspace(
        self, workspace_id: str, updates: WorkspaceUpdateInput
    ) -> WorkspaceRecord | None:
        return await self.adapter.update_workspace(workspace_id=workspace_id, updates=updates)

    async def get_workspace_stats(self, workspace_id: str) -> WorkspaceStatsRecord | None:
        return await self.adapter.get_workspace_stats(workspace_id=workspace_id)

    async def list_workspace_members(self, workspace_id: str) -> list[WorkspaceMemberRecord]:
        return await self.adapter.list_workspace_members(workspace_id=workspace_id)

    async def invite_workspace_member(
        self, workspace_id: str, email: str, role: str
    ) -> WorkspaceMemberRecord | None:
        user = await self.adapter.get_user_by_email(email=email)
        if user is None:
            return None
        if await self.adapter.is_workspace_member(workspace_id=workspace_id, user_id=user.id):
            raise WorkspaceMemberAlreadyExistsError(workspace_id=workspace_id, user_id=user.id)
        return await self.adapter.add_workspace_member(
            workspace_id=workspace_id,
            user_id=user.id,
            role=role,
        )

    async def remove_workspace_member(self, workspace_id: str, user_id: str) -> bool:
        return await self.adapter.remove_workspace_member(
            workspace_id=workspace_id, user_id=user_id
        )

    async def update_workspace_member(
        self, workspace_id: str, user_id: str, updates: dict[str, Any]
    ) -> bool:
        role = updates.get("role")
        if role not in ["admin", "member", "viewer"]:
            return False
        return await self.adapter.update_workspace_member_role(
            workspace_id=workspace_id,
            user_id=user_id,
            role=role,
        )

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
        self, workspace_id: str, logo_url: str
    ) -> WorkspaceRecord | None:
        return await self.adapter.set_workspace_logo(workspace_id=workspace_id, logo_url=logo_url)
