from __future__ import annotations

import os
import re
from dataclasses import replace
from datetime import datetime
from pathlib import Path

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
from naas_abi.skills.catalog import (
    BundledSkill,
    bundled_by_id,
    list_directory_files,
    list_package_files,
    load_bundled_skills,
    load_user_skills,
    read_directory_file,
    read_package_file,
)

# In-memory rows only. Bundled skills are not inserted into Postgres.
_BUNDLED_EPOCH = datetime(2026, 1, 1)
_BUNDLED_USER = "bundled"

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


def bundled_skill_record(skill: BundledSkill, workspace_id: str) -> SkillRecord:
    """One built-in skill as a list row. The prompt is the SKILL.md body."""
    return SkillRecord(
        id=skill.record_id,
        workspace_id=workspace_id,
        organization_id=None,
        user_id=_BUNDLED_USER,
        name=skill.name,
        slug=skill.slug,
        description=skill.description,
        prompt=skill.body,
        scope="builtin",
        enabled=True,
        last_used_at=None,
        created_at=_BUNDLED_EPOCH,
        updated_at=_BUNDLED_EPOCH,
        builtin=True,
        when_to_use=skill.when_to_use,
        files=list_package_files(skill.slug),
    )


def user_package_record(
    skill: BundledSkill,
    workspace_id: str,
    files: tuple[str, ...],
) -> SkillRecord:
    """A SKILL.md the user asked to write. Not a Postgres row and not builtin."""
    return SkillRecord(
        id=f"pkg.{workspace_id}.{skill.slug}",
        workspace_id=workspace_id,
        organization_id=None,
        user_id=_BUNDLED_USER,
        name=skill.name,
        slug=skill.slug,
        description=skill.description,
        prompt=skill.body,
        scope="user",
        enabled=True,
        last_used_at=None,
        created_at=_BUNDLED_EPOCH,
        updated_at=_BUNDLED_EPOCH,
        builtin=False,
        when_to_use=skill.when_to_use,
        files=files,
    )


def parse_user_package_id(skill_id: str) -> tuple[str, str] | None:
    """``pkg.{workspace_id}.{slug}`` or None. The slug is the final segment."""
    if not skill_id.startswith("pkg."):
        return None
    rest = skill_id[4:]
    if "." not in rest:
        return None
    workspace_id, slug = rest.rsplit(".", 1)
    if not workspace_id or not slug:
        return None
    return workspace_id, slug


def merge_bundled_skills(
    stored: list[SkillRecord],
    workspace_id: str,
    user_skills: tuple[BundledSkill, ...] = (),
    user_files: dict[str, tuple[str, ...]] | None = None,
) -> list[SkillRecord]:
    """Shipped skills, then user packages, then Postgres rows.

    A saved slug hides a package with the same slug. A user package hides
    the shipped skill with the same slug. Postgres rows carry no file tree.
    """
    taken = {skill.slug.lower() for skill in stored}
    files_by_slug = user_files or {}
    user_rows = [
        user_package_record(
            skill,
            workspace_id,
            files_by_slug.get(skill.slug, ()),
        )
        for skill in user_skills
        if skill.slug.lower() not in taken
    ]
    taken.update(skill.slug.lower() for skill in user_rows)
    bundled = [
        bundled_skill_record(skill, workspace_id)
        for skill in load_bundled_skills()
        if skill.slug.lower() not in taken
    ]
    return bundled + user_rows + list(stored)


def default_user_skills_root() -> Path:
    """Directory of user skill packages. Override with ``NAAS_USER_SKILLS_DIR``."""
    raw = os.environ.get("NAAS_USER_SKILLS_DIR", "").strip()
    if raw:
        return Path(raw)
    return Path.home() / ".naas" / "skills"


class SkillService:
    def __init__(
        self,
        adapter: SkillPersistencePort,
        iam_service: IAMService | None = None,
        user_skills_root: Path | None = None,
    ):
        self.adapter = adapter
        self.iam_service = iam_service
        self.user_skills_root = user_skills_root

    def _user_skills_dir(self, workspace_id: str) -> Path:
        base = (
            self.user_skills_root
            if self.user_skills_root is not None
            else default_user_skills_root()
        )
        return base / workspace_id

    def _load_user_packages(
        self, workspace_id: str
    ) -> tuple[tuple[BundledSkill, ...], dict[str, tuple[str, ...]]]:
        root = self._user_skills_dir(workspace_id)
        skills = load_user_skills(root)
        files = {
            skill.slug: list_directory_files(root / skill.slug) for skill in skills
        }
        return skills, files

    def _with_package_files(self, skill: SkillRecord) -> SkillRecord:
        """Attach files from the workspace package directory when a row has none.

        A Postgres skill hides the package row with the same slug. The Contents
        tree still reads that directory.
        """
        if skill.builtin or skill.files or not skill.workspace_id or not skill.slug:
            return skill
        files = list_directory_files(self._user_skills_dir(skill.workspace_id) / skill.slug)
        if not files:
            return skill
        return replace(skill, files=files)

    def write_requested_skill_package(
        self,
        workspace_id: str,
        *,
        slug: str,
        name: str,
        description: str,
        when_to_use: str,
        body: str,
        files: list[dict[str, str]] | None = None,
    ) -> Path:
        """Write a SKILL.md because the user asked. Not an agent tool."""
        from naas_abi.skills.writer import write_skill_package

        return write_skill_package(
            self._user_skills_dir(workspace_id),
            slug=slug,
            name=name,
            description=description,
            when_to_use=when_to_use,
            body=body,
            files=files,
        )

    def read_skill_package_file(self, skill: SkillRecord, relative: str) -> str | None:
        """Text of one real package file. Postgres rows read the package dir."""
        if not skill.files or relative not in skill.files:
            return None
        if skill.builtin:
            return read_package_file(skill.slug, relative)
        parsed = parse_user_package_id(skill.id)
        if parsed is not None:
            workspace_id, slug = parsed
            return read_directory_file(self._user_skills_dir(workspace_id) / slug, relative)
        return read_directory_file(
            self._user_skills_dir(skill.workspace_id) / skill.slug,
            relative,
        )

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
        stored = await self.adapter.list_visible(workspace_id, context.actor_user_id)
        user_skills, user_files = self._load_user_packages(workspace_id)
        merged = merge_bundled_skills(
            stored,
            workspace_id,
            user_skills=user_skills,
            user_files=user_files,
        )
        return [self._with_package_files(skill) for skill in merged]

    async def get_skill(self, context: RequestContext, skill_id: str) -> SkillRecord | None:
        self._ensure_scope(context, "skill.read", "Skill access denied")
        bundled = bundled_by_id(skill_id)
        if bundled is not None:
            return bundled_skill_record(bundled, "")
        parsed = parse_user_package_id(skill_id)
        if parsed is not None:
            workspace_id, slug = parsed
            skills, files = self._load_user_packages(workspace_id)
            match = next((item for item in skills if item.slug == slug), None)
            if match is not None:
                await self._ensure_workspace_access(context, workspace_id)
                return user_package_record(match, workspace_id, files.get(slug, ()))
        skill = await self.adapter.get_by_id(skill_id)
        if skill:
            await self._ensure_workspace_access(context, skill.workspace_id)
            if skill.scope == "user" and skill.user_id != context.actor_user_id:
                raise SkillPermissionError("Skill access denied")
            return self._with_package_files(skill)
        return skill

    async def create_skill(self, context: RequestContext, data: SkillCreateInput) -> SkillRecord:
        self._ensure_scope(context, "skill.create", "Skill access denied")
        await self._ensure_workspace_access(context, data.workspace_id)
        self._validate_scope(data.scope)
        if not data.name.strip():
            raise SkillValidationError("Name cannot be empty")
        if not data.prompt.strip():
            raise SkillValidationError("Prompt cannot be empty")
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
        self._ensure_scope(context, "skill.update", "Skill access denied")
        if bundled_by_id(skill_id) is not None:
            raise SkillPermissionError("Built-in skills cannot be edited")
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
        bundled = bundled_by_id(skill_id)
        if bundled is not None:
            # ``now`` is ignored. Built-in use is not stored.
            _ = now
            return bundled_skill_record(bundled, "")
        existing = await self.adapter.get_by_id(skill_id)
        if not existing:
            return None
        await self._ensure_workspace_access(context, existing.workspace_id)
        return await self.adapter.mark_used(skill_id, now)

    async def delete_skill(self, context: RequestContext, skill_id: str) -> bool:
        self._ensure_scope(context, "skill.delete", "Skill access denied")
        if bundled_by_id(skill_id) is not None:
            raise SkillPermissionError("Built-in skills cannot be deleted")
        existing = await self.adapter.get_by_id(skill_id)
        if not existing:
            return False
        await self._ensure_workspace_access(context, existing.workspace_id)
        self._ensure_can_modify(context, existing)
        return await self.adapter.delete(skill_id)
