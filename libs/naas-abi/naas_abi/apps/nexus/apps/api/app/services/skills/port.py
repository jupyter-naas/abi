from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime

SKILL_SCOPES = ("user", "workspace", "organization")


@dataclass
class SkillRecord:
    id: str
    workspace_id: str
    organization_id: str | None
    user_id: str
    name: str
    slug: str
    description: str
    prompt: str
    scope: str
    enabled: bool
    last_used_at: datetime | None
    created_at: datetime
    updated_at: datetime


@dataclass
class SkillCreateInput:
    workspace_id: str
    user_id: str
    name: str
    slug: str
    prompt: str
    description: str | None = None
    scope: str = "user"
    enabled: bool = True


@dataclass
class SkillUpdateInput:
    name: str | None = None
    slug: str | None = None
    description: str | None = None
    prompt: str | None = None
    scope: str | None = None
    enabled: bool | None = None


class SkillPersistencePort(ABC):
    @abstractmethod
    async def list_visible(self, workspace_id: str, user_id: str) -> list[SkillRecord]:
        """Skills visible to ``user_id`` in ``workspace_id``: their own user-scoped
        skills, the workspace's workspace-scoped skills, and organization-scoped
        skills of the workspace's organization."""

    @abstractmethod
    async def get_by_id(self, skill_id: str) -> SkillRecord | None:
        pass

    @abstractmethod
    async def get_visible_by_slug(
        self, workspace_id: str, user_id: str, slug: str
    ) -> SkillRecord | None:
        pass

    @abstractmethod
    async def create(self, data: SkillCreateInput) -> SkillRecord:
        pass

    @abstractmethod
    async def update(self, skill_id: str, updates: SkillUpdateInput) -> SkillRecord | None:
        pass

    @abstractmethod
    async def mark_used(self, skill_id: str, now: datetime) -> SkillRecord | None:
        pass

    @abstractmethod
    async def delete(self, skill_id: str) -> bool:
        pass
