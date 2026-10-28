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
    require_action,
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
            from naas_abi.apps.nexus.apps.api.app.core.config import settings
            from naas_abi.apps.nexus.apps.api.app.core.feature_flags import (
                enabled_feature_catalog,
            )
            from naas_abi.apps.nexus.apps.api.app.services.iam.sets import (
                user_feature_flags,
            )
            from naas_abi.tools.nexus_admin_tools import _workspace_service

            role = await require_member(db, user_id, workspace_id)
            if isinstance(role, dict):
                return role
            denied = await require_action(user_id, workspace_id, "GetWorkspace", id=())
            if denied is not None:
                return denied
            record = await _workspace_service(db).get_workspace(workspace_id)
            if record is None:
                return {"error": "Workspace not found."}
            # What the user may use here: IAM's, from the policies granting
            # features (no role brings one).
            flags = await user_feature_flags(
                user_id,
                [(record.organization_id, record.id)],
                enabled_feature_catalog(settings.feature_flags),
            )
            out = jsonable(record)
            out["your_role"] = role
            out["feature_flags"] = (flags or {}).get(record.id, {})
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

            denied = await require_action(user_id, workspace_id, "ListSecrets")
            if denied is not None:
                return denied
            service = SecretsService(adapter=SecretsSecondaryAdapterPostgres(db=db))
            secrets = await service.list_secrets(workspace_id)
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
