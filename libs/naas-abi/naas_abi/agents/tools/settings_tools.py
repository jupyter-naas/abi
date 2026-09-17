"""SettingsAgent tools for Nexus Settings (workspace + organization admin).

Membership, invitations, roles, workspaces, and profile edits reuse
``nexus_admin_tools`` (the same tools Abi owns). These add the read side the
Settings pages show: the workspace record and theme, the caller's role, the
effective feature flags (``core/feature_flags.build_feature_flags``, same
inputs as ``GET /api/workspaces/{id}``), and secret *names*. Secret values,
masked or not, never reach the model.
"""

from __future__ import annotations

from typing import Any

from langchain_core.tools import BaseTool, tool
from naas_abi.agents.feature.runtime import (
    guarded,
    jsonable,
    request_context,
    require_member,
    run_db,
    tool_context,
)

_FEATURE = "Settings"


def settings_tools() -> list[BaseTool]:
    @tool
    def get_workspace_settings() -> Any:
        """This workspace's settings: name, slug, organization, theme colors,
        drives, and, for the signed-in user asking, their role (your_role)
        and effective feature flags. Use it for "what is my role?"."""
        ctx = tool_context()
        if isinstance(ctx, dict):
            return ctx
        user_id, workspace_id = ctx

        async def _run(db: Any) -> Any:
            from naas_abi.agents.tools.nexus_admin_tools import (
                _organization_service,
                _workspace_service,
            )
            from naas_abi.apps.nexus.apps.api.app.core.config import settings
            from naas_abi.apps.nexus.apps.api.app.core.feature_flags import (
                build_feature_flags,
            )

            role = await require_member(db, user_id, workspace_id)
            if isinstance(role, dict):
                return role
            record = await _workspace_service(db).get_workspace(workspace_id)
            if record is None:
                return {"error": "Workspace not found."}
            override = None
            if record.organization_id:
                stored = await _organization_service(db).get_role_features(
                    org_id=record.organization_id
                )
                override = stored.role_baseline if stored is not None else None
            flags = build_feature_flags(
                role=role,
                feature_flags_config=settings.feature_flags,
                workspace_slug=record.slug,
                workspace_id=record.id,
                organization_id=record.organization_id,
                organization_override=override,
            )
            out = jsonable(record)
            out["your_role"] = role
            out["feature_flags"] = flags
            out["organization_role_override"] = override is not None
            return out

        return guarded(_FEATURE, lambda: run_db(_run))

    @tool
    def list_workspace_secret_names() -> Any:
        """Names, categories, and descriptions of this workspace's secrets.

        Values are never returned. Use it to check whether a key (for example
        an API key a module needs) is configured.
        """
        ctx = tool_context()
        if isinstance(ctx, dict):
            return ctx
        user_id, workspace_id = ctx

        async def _run(db: Any) -> Any:
            from naas_abi.apps.nexus.apps.api.app.services.secrets.adapters.secondary.postgres import (
                SecretsSecondaryAdapterPostgres,
            )
            from naas_abi.apps.nexus.apps.api.app.services.secrets.service import (
                SecretsService,
            )

            role = await require_member(db, user_id, workspace_id)
            if isinstance(role, dict):
                return role
            service = SecretsService(adapter=SecretsSecondaryAdapterPostgres(db=db))
            secrets = await service.list_secrets(request_context(user_id), workspace_id)
            return {
                "total": len(secrets),
                "secrets": [
                    {
                        "key": s.key,
                        "category": s.category,
                        "description": s.description,
                        "updated_at": jsonable(s.updated_at),
                    }
                    for s in secrets
                ],
            }

        return guarded(_FEATURE, lambda: run_db(_run))

    return [get_workspace_settings, list_workspace_secret_names]
