from __future__ import annotations

import json
from typing import Any

from naas_abi.apps.nexus.apps.api.app.models import (
    AgentConfigModel,
    AppConfigModel,
    OrganizationMemberModel,
    OrganizationModel,
    OrganizationRoleFeaturesModel,
    UserModel,
    WorkspaceMemberModel,
    WorkspaceModel,
)
from naas_abi.apps.nexus.apps.api.app.services.identity_graph.port import (
    IdentityAgentConfig,
    IdentityAppConfig,
    IdentityMembership,
    IdentityOrganization,
    IdentityOrganizationMembership,
    IdentitySnapshot,
    IdentitySourcePort,
    IdentityUser,
    IdentityWorkspace,
)
from naas_abi_core import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

# Branding and settings columns carried into the graph as data properties.
ORGANIZATION_PROFILE_COLUMNS = (
    "logo_url",
    "logo_rectangle_url",
    "logo_emoji",
    "primary_color",
    "accent_color",
    "background_color",
    "font_family",
    "font_url",
    "login_card_max_width",
    "login_card_padding",
    "login_card_color",
    "login_text_color",
    "login_input_color",
    "login_border_radius",
    "login_bg_image_url",
    "show_terms_footer",
    "show_powered_by",
    "login_footer_text",
    "secondary_logo_url",
    "show_logo_separator",
    "default_theme",
)
WORKSPACE_SETTING_COLUMNS = (
    "logo_url",
    "logo_emoji",
    "primary_color",
    "accent_color",
    "background_color",
    "background_image_url",
    "sidebar_color",
    "font_family",
    "platform_drive_enabled",
    "system_drive_enabled",
    "coding_default_repo_id",
)


def _columns(model: Any, names: tuple[str, ...]) -> dict[str, Any]:
    return {name: getattr(model, name, None) for name in names}


class IdentitySourceSecondaryAdapterPostgres(IdentitySourcePort):
    def __init__(self, db: AsyncSession):
        self.db = db

    async def _all(self, model: Any, *order_by: Any) -> list[Any]:
        result = await self.db.execute(select(model).order_by(*order_by))
        return list(result.scalars().all())

    async def load_snapshot(self) -> IdentitySnapshot:
        users = await self._all(UserModel, UserModel.created_at, UserModel.id)
        organizations = await self._all(
            OrganizationModel, OrganizationModel.created_at, OrganizationModel.id
        )
        organization_members = await self._all(
            OrganizationMemberModel, OrganizationMemberModel.created_at, OrganizationMemberModel.id
        )
        role_features = await self._all(
            OrganizationRoleFeaturesModel, OrganizationRoleFeaturesModel.organization_id
        )
        workspaces = await self._all(WorkspaceModel, WorkspaceModel.created_at, WorkspaceModel.id)
        members = await self._all(
            WorkspaceMemberModel, WorkspaceMemberModel.created_at, WorkspaceMemberModel.id
        )
        apps = await self._all(AppConfigModel, AppConfigModel.workspace_id, AppConfigModel.app_id)
        agents = await self._all(
            AgentConfigModel, AgentConfigModel.workspace_id, AgentConfigModel.id
        )

        overlays: dict[str, dict[str, list[str]]] = {}
        for row in role_features:
            try:
                baseline = json.loads(row.role_baseline or "{}")
            except (TypeError, ValueError):
                logger.warning(
                    f"[identity-graph] unreadable role features for {row.organization_id}"
                )
                continue
            if isinstance(baseline, dict):
                overlays[row.organization_id] = {str(k): list(v or []) for k, v in baseline.items()}

        return IdentitySnapshot(
            users=[
                IdentityUser(
                    id=u.id,
                    name=u.name,
                    email=u.email,
                    created_at=u.created_at,
                    avatar=u.avatar,
                    company=u.company,
                    job_title=u.role,
                    bio=u.bio,
                    is_superadmin=bool(u.is_superadmin),
                )
                for u in users
            ],
            organizations=[
                IdentityOrganization(
                    id=o.id,
                    name=o.name,
                    slug=o.slug,
                    owner_id=o.owner_id,
                    created_at=o.created_at,
                    profile=_columns(o, ORGANIZATION_PROFILE_COLUMNS),
                )
                for o in organizations
            ],
            organization_memberships=[
                IdentityOrganizationMembership(
                    id=m.id,
                    organization_id=m.organization_id,
                    user_id=m.user_id,
                    role=m.role,
                    created_at=m.created_at,
                )
                for m in organization_members
            ],
            organization_role_features=overlays,
            workspaces=[
                IdentityWorkspace(
                    id=w.id,
                    name=w.name,
                    slug=w.slug,
                    owner_id=w.owner_id,
                    organization_id=w.organization_id,
                    created_at=w.created_at,
                    settings=_columns(w, WORKSPACE_SETTING_COLUMNS),
                )
                for w in workspaces
            ],
            memberships=[
                IdentityMembership(
                    id=m.id,
                    workspace_id=m.workspace_id,
                    user_id=m.user_id,
                    role=m.role,
                    created_at=m.created_at,
                )
                for m in members
            ],
            app_configs=[
                IdentityAppConfig(
                    workspace_id=a.workspace_id, app_id=a.app_id, enabled=bool(a.enabled)
                )
                for a in apps
            ],
            agent_configs=[
                IdentityAgentConfig(
                    id=a.id,
                    workspace_id=a.workspace_id,
                    name=a.name,
                    class_name=a.class_name,
                    module_path=a.module_path,
                    model_id=a.model_id,
                    provider=a.provider,
                    enabled=bool(a.enabled),
                    is_default=bool(a.is_default),
                )
                for a in agents
            ],
        )
