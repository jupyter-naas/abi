from __future__ import annotations

import re
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime

from naas_abi.apps.nexus.apps.api.app.services.skills.port import (
    MAX_PROMPT_CHARS,
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


def suggest_skill_slug(slug: str | None, name: str) -> str:
    """Pick a non-reserved slug, remapping drafts that echo `/create-skill`."""
    for candidate in (slug or "", name, f"{name}-task", "custom-skill"):
        normalized = normalize_slug(candidate)
        if normalized and normalized not in RESERVED_SLUGS:
            return normalized
    return "custom-skill"


class SkillValidationError(ValueError):
    pass


class SkillPermissionError(PermissionError):
    pass


@dataclass(frozen=True)
class RequestContext:
    """Who is asking: a user-scoped skill is private to its user. Authorization is
    IAM's, decided by the router."""

    actor_user_id: str


# ``await may_manage(user_id, org_id)``: whether the user administers the organization.
OrganizationGate = Callable[[str, str], Awaitable[bool]]

ORGANIZATION = "organization"


async def _organization_admin(user_id: str, org_id: str) -> bool:
    """An organization skill is part of every chat of the organization: making,
    changing or deleting one is the organization's administrators' to do."""
    from naas_abi.apps.nexus.apps.api.app.services.iam.authz import AUTHZ

    return await AUTHZ.allowed("UpdateOrganization", user=user_id, org=org_id)


class SkillService:
    """Skills of a workspace.

    Who may do what in a workspace is decided by IAM at the route
    (``UpdateSkill``...). The context only names the caller: a user-scoped skill is
    private to its creator, whatever role anyone holds. An organization skill
    reaches every workspace of the organization, so creating one, widening a skill
    to it, and changing or deleting one also need the organization's
    administration (``may_manage``).
    """

    def __init__(self, adapter: SkillPersistencePort, may_manage: OrganizationGate | None = None):
        self.adapter = adapter
        self._may_manage = may_manage or _organization_admin

    async def _require_organization(self, user_id: str, org_id: str | None) -> None:
        if not org_id:
            raise SkillValidationError("This workspace belongs to no organization")
        if not await self._may_manage(user_id, org_id):
            raise SkillPermissionError(
                "Only the organization's admins and owners manage its skills"
            )

    @staticmethod
    def _validate_prompt(prompt: str) -> None:
        if not prompt.strip():
            raise SkillValidationError("Prompt cannot be empty")
        if len(prompt) > MAX_PROMPT_CHARS:
            raise SkillValidationError(f"Prompt is longer than {MAX_PROMPT_CHARS} characters")

    def _ensure_can_modify(self, context: RequestContext, skill: SkillRecord) -> None:
        # User-scoped skills are private to their creator; wider scopes are
        # editable by anyone IAM lets update skills in the skill's workspace.
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
        return await self.adapter.list_visible(workspace_id, context.actor_user_id)

    async def get_skill(self, context: RequestContext, skill_id: str) -> SkillRecord | None:
        skill = await self.adapter.get_by_id(skill_id)
        if skill and skill.scope == "user" and skill.user_id != context.actor_user_id:
            raise SkillPermissionError("Skill access denied")
        return skill

    async def create_skill(self, data: SkillCreateInput) -> SkillRecord:
        self._validate_scope(data.scope)
        if not data.name.strip():
            raise SkillValidationError("Name cannot be empty")
        self._validate_prompt(data.prompt)
        if data.scope == ORGANIZATION:
            await self._require_organization(
                data.user_id, await self.adapter.organization_of(data.workspace_id)
            )
        # Models often set slug to "create-skill" because that was the slash
        # command that started the draft. Remap before validation.
        data.slug = await self._validate_slug(
            data.workspace_id,
            data.user_id,
            suggest_skill_slug(data.slug, data.name),
        )
        return await self.adapter.create(data)

    async def update_skill(
        self,
        context: RequestContext,
        skill_id: str,
        updates: SkillUpdateInput,
    ) -> SkillRecord | None:
        existing = await self.adapter.get_by_id(skill_id)
        if not existing:
            return None
        self._ensure_can_modify(context, existing)
        if updates.scope is not None:
            self._validate_scope(updates.scope)
        if updates.prompt is not None:
            self._validate_prompt(updates.prompt)
        if ORGANIZATION in (existing.scope, updates.scope):
            org_id = existing.organization_id or await self.adapter.organization_of(
                existing.workspace_id
            )
            await self._require_organization(context.actor_user_id, org_id)
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
        existing = await self.adapter.get_by_id(skill_id)
        if not existing:
            return None
        if existing.scope == "user" and existing.user_id != context.actor_user_id:
            raise SkillPermissionError("Skill access denied")
        return await self.adapter.mark_used(skill_id, now)

    async def delete_skill(self, context: RequestContext, skill_id: str) -> bool:
        existing = await self.adapter.get_by_id(skill_id)
        if not existing:
            return False
        self._ensure_can_modify(context, existing)
        # Its creator may take an organization skill back; anyone else administers
        # the organization.
        if existing.scope == ORGANIZATION and existing.user_id != context.actor_user_id:
            org_id = existing.organization_id or await self.adapter.organization_of(
                existing.workspace_id
            )
            await self._require_organization(context.actor_user_id, org_id)
        return await self.adapter.delete(skill_id)

    async def set_enabled_in(
        self, context: RequestContext, skill_id: str, workspace_id: str, enabled: bool
    ) -> SkillRecord | None:
        """Turn an organization skill on or off in ``workspace_id``, one of its
        organization's workspaces. The route checked that the caller administers
        that workspace."""
        existing = await self.adapter.get_by_id(skill_id)
        if not existing or existing.scope != ORGANIZATION or not existing.organization_id:
            return None
        if await self.adapter.organization_of(workspace_id) != existing.organization_id:
            return None
        await self.adapter.set_enabled_in(skill_id, workspace_id, enabled, context.actor_user_id)
        found = await self.adapter.list_visible(workspace_id, context.actor_user_id)
        return next((s for s in found if s.id == skill_id), None)
