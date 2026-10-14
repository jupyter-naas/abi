from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import shutil
from collections import Counter
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
    ModuleSkillCatalogPort,
    SkillCreateInput,
    SkillPersistencePort,
    SkillRecord,
    SkillUpdateInput,
)
from naas_abi.skills.catalog import (
    ModuleSkill,
    list_directory_files,
    read_directory_file,
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


def module_skill_id(workspace_id: str, reference: str) -> str:
    payload = json.dumps([workspace_id, reference]).encode("utf-8")
    return "module." + base64.urlsafe_b64encode(payload).decode("ascii").rstrip("=")


def parse_module_skill_id(value: str) -> tuple[str, str] | None:
    if not value.startswith("module."):
        return None
    try:
        raw = value[len("module.") :]
        parts = json.loads(base64.urlsafe_b64decode(raw + "=" * (-len(raw) % 4)))
        if (
            isinstance(parts, list)
            and len(parts) == 2
            and all(isinstance(p, str) and p for p in parts)
        ):
            return parts[0], parts[1]
    except (ValueError, UnicodeError):
        pass
    return None


def module_skill_record(
    item: ModuleSkill, workspace_id: str, *, include_body: bool = False
) -> SkillRecord:
    skill = item.skill
    return SkillRecord(
        id=module_skill_id(workspace_id, item.reference),
        workspace_id=workspace_id,
        organization_id=None,
        user_id=_BUNDLED_USER,
        name=skill.name,
        slug=skill.slug,
        description=skill.description,
        prompt=skill.body if include_body else "",
        scope="builtin",
        enabled=True,
        last_used_at=None,
        created_at=_BUNDLED_EPOCH,
        updated_at=_BUNDLED_EPOCH,
        builtin=True,
        when_to_use=skill.when_to_use,
        files=list_directory_files(item.root),
        source="module",
        catalog_ref=item.reference,
    )


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
        module_catalog: ModuleSkillCatalogPort | None = None,
    ):
        self.adapter = adapter
        self.iam_service = iam_service
        self.user_skills_root = user_skills_root
        self.module_catalog = module_catalog

    def _package_dir(self, skill: SkillRecord) -> Path:
        base = (
            self.user_skills_root
            if self.user_skills_root is not None
            else default_user_skills_root()
        )
        # IDs, rather than slugs, isolate private skills and survive renames.
        key = hashlib.sha256(skill.id.encode("utf-8")).hexdigest()
        return base / "records" / key / "package"

    def _with_package_files(self, skill: SkillRecord) -> SkillRecord:
        if skill.builtin:
            return skill
        return replace(skill, files=list_directory_files(self._package_dir(skill)))

    async def write_requested_skill_package(
        self,
        context: RequestContext,
        skill_id: str,
        *,
        when_to_use: str,
        files: list[dict[str, str]] | None = None,
    ) -> Path:
        """Attach a package to an authorized record; never create an unowned skill."""
        from naas_abi.skills.writer import write_skill_package

        self._ensure_scope(context, "skill.update", "Skill access denied")
        skill = await self.get_skill(context, skill_id)
        if skill is None:
            raise SkillValidationError("Skill not found")
        if skill.builtin:
            raise SkillPermissionError("Module skills cannot be edited")
        self._ensure_can_modify(context, skill)
        return write_skill_package(
            self._package_dir(skill).parent,
            slug="package",
            name=skill.name,
            description=skill.description or skill.name,
            when_to_use=when_to_use,
            body=skill.prompt,
            files=files,
        )

    def read_skill_package_file(self, skill: SkillRecord, relative: str) -> str | None:
        """Read files only from the package attached to this authorized record."""
        if not skill.files or relative not in skill.files:
            return None
        if skill.builtin:
            return (
                self.module_catalog.read_file(skill.catalog_ref, relative)
                if self.module_catalog and skill.catalog_ref
                else None
            )
        return read_directory_file(self._package_dir(skill), relative)

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
        items = await self.module_catalog.list_enabled(workspace_id) if self.module_catalog else []
        counts = Counter(item.skill.slug for item in items)
        taken = {row.slug for row in stored}
        module_rows = []
        for item in items:
            row = module_skill_record(item, workspace_id)
            if counts[row.slug] > 1:
                row = replace(row, slug=f"{normalize_slug(item.module_name)}-{row.slug}")
            if row.slug not in taken:
                module_rows.append(row)
                taken.add(row.slug)
        merged = module_rows + stored
        return [self._with_package_files(skill) for skill in merged]

    async def get_skill(self, context: RequestContext, skill_id: str) -> SkillRecord | None:
        self._ensure_scope(context, "skill.read", "Skill access denied")
        if skill_id.startswith("module."):
            parsed = parse_module_skill_id(skill_id)
            if parsed is None or self.module_catalog is None:
                return None
            workspace_id, reference = parsed
            await self._ensure_workspace_access(context, workspace_id)
            items = await self.module_catalog.list_enabled(workspace_id)
            match = next((item for item in items if item.reference == reference), None)
            return module_skill_record(match, workspace_id, include_body=True) if match else None
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
        if skill_id.startswith("module."):
            raise SkillPermissionError("Module skills cannot be edited")
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
        if skill_id.startswith("module."):
            return await self.get_skill(context, skill_id)
        existing = await self.adapter.get_by_id(skill_id)
        if not existing:
            return None
        await self._ensure_workspace_access(context, existing.workspace_id)
        return await self.adapter.mark_used(skill_id, now)

    async def delete_skill(self, context: RequestContext, skill_id: str) -> bool:
        self._ensure_scope(context, "skill.delete", "Skill access denied")
        if skill_id.startswith("module."):
            raise SkillPermissionError("Module skills cannot be deleted")
        existing = await self.adapter.get_by_id(skill_id)
        if not existing:
            return False
        await self._ensure_workspace_access(context, existing.workspace_id)
        self._ensure_can_modify(context, existing)
        deleted = await self.adapter.delete(skill_id)
        if deleted:
            package = self._package_dir(existing)
            if package.is_dir():
                shutil.rmtree(package)
        return deleted
