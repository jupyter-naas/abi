from __future__ import annotations

from typing import TYPE_CHECKING

from naas_abi.apps.nexus.apps.api.app.services.iam.port import RequestContext
from naas_abi.apps.nexus.apps.api.app.services.iam.service import IAMPermissionError, IAMService

if TYPE_CHECKING:
    from naas_abi.apps.nexus.apps.api.app.services.workspaces.service import WorkspaceService


def resolve_iam_service(explicit_iam_service: IAMService | None = None) -> IAMService | None:
    if explicit_iam_service is not None:
        return explicit_iam_service
    try:
        from naas_abi.apps.nexus.apps.api.app.core.postgres_session_registry import (
            PostgresSessionRegistry,
        )
        from naas_abi.apps.nexus.apps.api.app.services.registry import ServiceRegistry

        if PostgresSessionRegistry.instance().current_session() is None:
            return None
        return ServiceRegistry.instance().iam
    except Exception:
        return None


def resolve_workspace_service(
    explicit_workspace_service: WorkspaceService | None = None,
) -> WorkspaceService | None:
    if explicit_workspace_service is not None:
        return explicit_workspace_service
    try:
        from naas_abi.apps.nexus.apps.api.app.core.postgres_session_registry import (
            PostgresSessionRegistry,
        )
        from naas_abi.apps.nexus.apps.api.app.services.registry import ServiceRegistry

        if PostgresSessionRegistry.instance().current_session() is None:
            return None
        return ServiceRegistry.instance().workspaces
    except Exception:
        return None


def ensure_scope(
    context: RequestContext,
    required_scope: str,
    denied_message: str,
    iam_service: IAMService | None = None,
) -> None:
    resolved_iam_service = resolve_iam_service(iam_service)
    if not resolved_iam_service:
        return
    try:
        resolved_iam_service.ensure(
            token_data=context.token_data,
            required_scope=required_scope,
        )
    except IAMPermissionError as exc:
        raise PermissionError(denied_message) from exc


async def ensure_workspace_access(
    context: RequestContext,
    workspace_id: str,
    denied_message: str = "Workspace access denied",
    required_scope: str = "workspace.read",
    iam_service: IAMService | None = None,
    workspace_service: WorkspaceService | None = None,
) -> str | None:
    ensure_scope(
        context=context,
        required_scope=required_scope,
        denied_message=denied_message,
        iam_service=iam_service,
    )

    resolved_workspace_service = resolve_workspace_service(workspace_service)
    if not resolved_workspace_service:
        return None

    try:
        return await resolved_workspace_service.require_workspace_access(
            user_id=context.actor_user_id,
            workspace_id=workspace_id,
        )
    except PermissionError as exc:
        raise PermissionError(denied_message) from exc
