from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime


@dataclass
class WorkspaceRecord:
    id: str
    name: str
    slug: str
    owner_id: str
    organization_id: str | None = None
    logo_url: str | None = None
    logo_emoji: str | None = None
    primary_color: str | None = "#22c55e"
    accent_color: str | None = None
    background_color: str | None = None
    sidebar_color: str | None = None
    font_family: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    organization_logo_url: str | None = None
    organization_logo_rectangle_url: str | None = None


@dataclass
class WorkspaceCreateInput:
    name: str
    slug: str
    owner_id: str
    organization_id: str | None = None
    logo_url: str | None = None
    logo_emoji: str | None = None
    primary_color: str | None = "#22c55e"
    accent_color: str | None = None
    background_color: str | None = None
    sidebar_color: str | None = None
    font_family: str | None = None


@dataclass
class WorkspaceUpdateInput:
    name: str | None = None
    logo_url: str | None = None
    logo_emoji: str | None = None
    primary_color: str | None = None
    accent_color: str | None = None
    background_color: str | None = None
    sidebar_color: str | None = None
    font_family: str | None = None


@dataclass
class WorkspaceStatsRecord:
    nodes: int
    edges: int
    conversations: int
    agents: int


@dataclass
class WorkspaceMemberRecord:
    id: str
    workspace_id: str
    user_id: str
    role: str
    email: str | None = None
    name: str | None = None
    created_at: datetime | None = None


@dataclass
class UserRecord:
    id: str
    email: str


@dataclass
class InferenceServerRecord:
    id: str
    workspace_id: str
    name: str
    type: str
    endpoint: str
    description: str | None = None
    enabled: bool = True
    api_key: str | None = None
    health_path: str | None = None
    models_path: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


@dataclass
class InferenceServerCreateInput:
    id: str
    workspace_id: str
    name: str
    type: str
    endpoint: str
    description: str | None = None
    enabled: bool = True
    api_key: str | None = None
    health_path: str | None = None
    models_path: str | None = None


@dataclass
class InferenceServerUpdateInput:
    name: str | None = None
    endpoint: str | None = None
    description: str | None = None
    enabled: bool | None = None
    api_key: str | None = None
    health_path: str | None = None
    models_path: str | None = None


class WorkspacePermissionPort(ABC):
    @abstractmethod
    async def get_workspace_role(self, user_id: str, workspace_id: str) -> str | None:
        raise NotImplementedError

    @abstractmethod
    async def list_workspaces_for_user(self, user_id: str) -> list[WorkspaceRecord]:
        raise NotImplementedError

    @abstractmethod
    async def get_workspace_by_id(self, workspace_id: str) -> WorkspaceRecord | None:
        raise NotImplementedError

    @abstractmethod
    async def get_workspace_by_slug(self, slug: str) -> WorkspaceRecord | None:
        raise NotImplementedError

    @abstractmethod
    async def workspace_slug_exists(self, slug: str) -> bool:
        raise NotImplementedError

    @abstractmethod
    async def create_workspace(self, workspace: WorkspaceCreateInput) -> WorkspaceRecord:
        raise NotImplementedError

    @abstractmethod
    async def delete_workspace(self, workspace_id: str) -> bool:
        raise NotImplementedError

    @abstractmethod
    async def update_workspace(
        self, workspace_id: str, updates: WorkspaceUpdateInput
    ) -> WorkspaceRecord | None:
        raise NotImplementedError

    @abstractmethod
    async def get_workspace_stats(self, workspace_id: str) -> WorkspaceStatsRecord | None:
        raise NotImplementedError

    @abstractmethod
    async def list_workspace_members(self, workspace_id: str) -> list[WorkspaceMemberRecord]:
        raise NotImplementedError

    @abstractmethod
    async def get_user_by_email(self, email: str) -> UserRecord | None:
        raise NotImplementedError

    @abstractmethod
    async def is_workspace_member(self, workspace_id: str, user_id: str) -> bool:
        raise NotImplementedError

    @abstractmethod
    async def add_workspace_member(
        self, workspace_id: str, user_id: str, role: str
    ) -> WorkspaceMemberRecord:
        raise NotImplementedError

    @abstractmethod
    async def remove_workspace_member(self, workspace_id: str, user_id: str) -> bool:
        raise NotImplementedError

    @abstractmethod
    async def update_workspace_member_role(
        self, workspace_id: str, user_id: str, role: str
    ) -> bool:
        raise NotImplementedError

    @abstractmethod
    async def list_inference_servers(self, workspace_id: str) -> list[InferenceServerRecord]:
        raise NotImplementedError

    @abstractmethod
    async def create_inference_server(
        self, server: InferenceServerCreateInput
    ) -> InferenceServerRecord:
        raise NotImplementedError

    @abstractmethod
    async def update_inference_server(
        self, workspace_id: str, server_id: str, updates: InferenceServerUpdateInput
    ) -> InferenceServerRecord | None:
        raise NotImplementedError

    @abstractmethod
    async def delete_inference_server(self, workspace_id: str, server_id: str) -> bool:
        raise NotImplementedError

    @abstractmethod
    async def set_workspace_logo(self, workspace_id: str, logo_url: str) -> WorkspaceRecord | None:
        raise NotImplementedError
