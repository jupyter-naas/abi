"""Loaded module assets and the workspace's explicit config allowlist."""

import logging
from collections.abc import Callable
from typing import Any

from naas_abi.apps.nexus.apps.api.app.core.workspace_catalog_seed import live_settings
from naas_abi.apps.nexus.apps.api.app.models import OrganizationModel, WorkspaceModel
from naas_abi.apps.nexus.apps.api.app.services.skills.adapters.secondary.postgres import (
    AsyncSessionGetter,
)
from naas_abi.skills.catalog import ModuleSkill, load_module_skills, read_directory_file
from sqlalchemy import select

logger = logging.getLogger(__name__)


def loaded_modules() -> dict[str, Any]:
    from naas_abi import ABIModule

    abi = ABIModule.get_instance()
    return {"naas_abi": abi, **abi.engine.modules}


class ModuleSkillCatalog:
    def __init__(
        self,
        db_getter: AsyncSessionGetter,
        modules_getter: Callable[[], dict[str, Any]] = loaded_modules,
    ):
        self.db_getter = db_getter
        self.modules_getter = modules_getter

    async def list_enabled(self, workspace_id: str) -> list[ModuleSkill]:
        db = self.db_getter()
        if db is None:
            raise RuntimeError("No database session bound for skills catalog")
        identity = (
            await db.execute(
                select(WorkspaceModel.slug, OrganizationModel.slug)
                .outerjoin(
                    OrganizationModel, WorkspaceModel.organization_id == OrganizationModel.id
                )
                .where(WorkspaceModel.id == workspace_id)
            )
        ).one_or_none()
        if identity is None:
            return []
        matches = [
            ws
            for org in getattr(live_settings(), "organizations", []) or []
            if org.slug == identity[1]
            for ws in org.workspaces
            if ws.slug == identity[0]
        ]
        if len(matches) > 1:
            raise ValueError("Ambiguous workspace skill configuration")
        refs = list(dict.fromkeys(getattr(matches[0], "skills", None) or [])) if matches else []
        if not refs:
            return []
        catalog = load_module_skills(self.modules_getter())
        for ref in refs:
            if ref not in catalog:
                logger.warning(
                    "Configured skill %s is unavailable in workspace %s", ref, workspace_id
                )
        return [catalog[ref] for ref in refs if ref in catalog]

    def read_file(self, reference: str, relative: str) -> str | None:
        item = load_module_skills(self.modules_getter()).get(reference)
        return read_directory_file(item.root, relative) if item else None
