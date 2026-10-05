from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from naas_abi.skills.catalog import ModuleSkill

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
    builtin: bool = False
    when_to_use: str = ""
    # Real package paths. Postgres prompt rows leave this empty.
    files: tuple[str, ...] = ()
    source: str = "user"
    catalog_ref: str | None = None


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


class ModuleSkillCatalogPort(Protocol):
    async def list_enabled(self, workspace_id: str) -> list[ModuleSkill]:
        """Packages explicitly allowed in this workspace's configuration."""
        ...

    def read_file(self, reference: str, relative: str) -> str | None:
        """Read a file of an already authorized module skill."""
        ...
