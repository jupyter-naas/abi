from __future__ import annotations

import re
from datetime import datetime

from naas_abi.apps.nexus.apps.api.app.services.iam.authorization import (
    ensure_scope,
    ensure_workspace_access,
)
from naas_abi.apps.nexus.apps.api.app.services.iam.port import RequestContext
from naas_abi.apps.nexus.apps.api.app.services.iam.service import IAMService
from naas_abi.apps.nexus.apps.api.app.services.skills.port import (
    SKILL_SCOPES,
    SkillCreateInput,
    SkillPersistencePort,
    SkillRecord,
    SkillUpdateInput,
)

# Reserved chat commands that can never be used as skill slugs.
RESERVED_SLUGS = {"skills", "create-skill"}

_SLUG_RE = re.compile(r"[^a-z0-9-]+")


def normalize_slug(value: str) -> str:
    """Normalize a raw name/slug to a chat-command slug: lowercase, hyphenated."""
    slug = _SLUG_RE.sub("-", value.strip().lower().replace("_", "-"))
    return slug.strip("-")


class SkillValidationError(ValueError):
    pass


class SkillPermissionError(PermissionError):
    pass


class SkillService:
    def __init__(self, adapter: SkillPersistencePort, iam_service: IAMService | None = None):
        self.adapter = adapter
        self.iam_service = iam_service

    def _ensure_scope(
        self, context: RequestContext, required_scope: str, denied_message: str
    ) -> None:
        ensure_scope(
            context=context,
            required_scope=required_scope,
            denied_message=denied_message,
            iam_service=self.iam_service,
        )

    async def _ensure_workspace_access(self, context: RequestContext, workspace_id: str) -> None:
        await ensure_workspace_access(
            context=context,
            workspace_id=workspace_id,
            denied_message="Workspace access denied",
            required_scope="workspace.read",
            iam_service=self.iam_service,
            workspace_service=None,
        )

    def _ensure_can_modify(self, context: RequestContext, skill: SkillRecord) -> None:
        # User-scoped skills are private to their creator; wider scopes are
        # editable by anyone with access to the skill's workspace (checked by
        # the caller via _ensure_workspace_access).
        if skill.scope == "user" and skill.user_id != context.actor_user_id:
            raise SkillPermissionError("Only the creator can modify this skill")

    @staticmethod
    def _validate_scope(scope: str) -> None:
        if scope not in SKILL_SCOPES:
            raise SkillValidationError(
                f"Invalid scope '{scope}'. Must be one of: {', '.join(SKILL_SCOPES)}"
            )

    async def _validate_slug(
        self,
        workspace_id: str,
        user_id: str,
        slug: str,
        exclude_skill_id: str | None = None,
    ) -> str:
        normalized = normalize_slug(slug)
        if not normalized:
            raise SkillValidationError("Slug cannot be empty")
        if normalized in RESERVED_SLUGS:
            raise SkillValidationError(f"'/{normalized}' is a reserved command")
        existing = await self.adapter.get_visible_by_slug(workspace_id, user_id, normalized)
        if existing and existing.id != exclude_skill_id:
            raise SkillValidationError(f"A skill with slug '/{normalized}' already exists")
        return normalized

    async def list_visible_skills(
        self,
        context: RequestContext,
        workspace_id: str,
    ) -> list[SkillRecord]:
        self._ensure_scope(context, "skill.read", "Skill access denied")
        await self._ensure_workspace_access(context, workspace_id)
        return await self.adapter.list_visible(workspace_id, context.actor_user_id)

    async def get_skill(self, context: RequestContext, skill_id: str) -> SkillRecord | None:
        self._ensure_scope(context, "skill.read", "Skill access denied")
        skill = await self.adapter.get_by_id(skill_id)
        if skill:
            await self._ensure_workspace_access(context, skill.workspace_id)
            if skill.scope == "user" and skill.user_id != context.actor_user_id:
                raise SkillPermissionError("Skill access denied")
        return skill

    async def create_skill(self, context: RequestContext, data: SkillCreateInput) -> SkillRecord:
        self._ensure_scope(context, "skill.create", "Skill access denied")
        await self._ensure_workspace_access(context, data.workspace_id)
        self._validate_scope(data.scope)
        data.slug = await self._validate_slug(data.workspace_id, data.user_id, data.slug)
        if not data.name.strip():
            raise SkillValidationError("Name cannot be empty")
        if not data.prompt.strip():
            raise SkillValidationError("Prompt cannot be empty")
        return await self.adapter.create(data)

    async def update_skill(
        self,
        context: RequestContext,
        skill_id: str,
        updates: SkillUpdateInput,
    ) -> SkillRecord | None:
        self._ensure_scope(context, "skill.update", "Skill access denied")
        existing = await self.adapter.get_by_id(skill_id)
        if not existing:
            return None
        await self._ensure_workspace_access(context, existing.workspace_id)
        self._ensure_can_modify(context, existing)
        if updates.scope is not None:
            self._validate_scope(updates.scope)
        if updates.slug is not None:
            updates.slug = await self._validate_slug(
                existing.workspace_id,
                context.actor_user_id,
                updates.slug,
                exclude_skill_id=skill_id,
            )
        return await self.adapter.update(skill_id, updates)

    async def mark_skill_used(
        self,
        context: RequestContext,
        skill_id: str,
        now: datetime,
    ) -> SkillRecord | None:
        self._ensure_scope(context, "skill.read", "Skill access denied")
        existing = await self.adapter.get_by_id(skill_id)
        if not existing:
            return None
        await self._ensure_workspace_access(context, existing.workspace_id)
        return await self.adapter.mark_used(skill_id, now)

    async def delete_skill(self, context: RequestContext, skill_id: str) -> bool:
        self._ensure_scope(context, "skill.delete", "Skill access denied")
        existing = await self.adapter.get_by_id(skill_id)
        if not existing:
            return False
        await self._ensure_workspace_access(context, existing.workspace_id)
        self._ensure_can_modify(context, existing)
        return await self.adapter.delete(skill_id)
