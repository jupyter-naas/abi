"""AppsAgent tools for Nexus Apps.

Same data the Apps page shows (``GET /api/apps/?workspace_id=``): the apps of
the module catalog discovered from ``<module>/apps/<name>/manifest.json`` that
the user may open in the workspace (IAM's ``module:OpenApp``, nothing else),
and the tenant's external shortcuts. When the user has an app open
(``?open=<app_id>``) the pane sends it as the open feature resource, so tools
default to that app and the agent never asks which one.

Demo passwords never reach the model; tools only say whether a demo login
exists. Who may use which app is set by policies (Roles & permissions), never
by these tools.
"""

from __future__ import annotations

from typing import Any
from urllib.parse import quote

from langchain_core.tools import BaseTool, tool

from naas_abi.agents.feature.context import active_feature_resource_id
from naas_abi.tools.nexus_admin_tools import (
    _require_user_id,
    _run_async,
    _with_db,
    _workspace_service,
    turn_workspace_id,
)

APP_RESOURCE_KIND = "app"
_MAX_DESCRIPTION = 300


def _tool_error(exc: BaseException) -> dict[str, str]:
    """Log the real exception; never hand DSNs or stack traces to the model."""
    logger = __import__("logging").getLogger(__name__)
    logger.exception("apps tool failed: %s", type(exc).__name__)
    return {"error": "Apps operation failed. Check server logs for details."}


def _catalog() -> list[Any]:
    from naas_abi.apps.nexus.apps.api.app.services.apps.adapters.primary.apps__primary_adapter__FastAPI import (
        apps_catalog,
    )

    return list(apps_catalog())


def _external_apps() -> list[Any]:
    """Tenant shortcuts (``nexus_config.tenant.apps``), shown to everyone."""
    try:
        from naas_abi.apps.nexus.apps.api.app.core import config as nexus_config

        tenant = getattr(nexus_config.settings, "tenant", None)
        return list(getattr(tenant, "apps", None) or [])
    except Exception:  # noqa: BLE001
        return []


def _embed_kind(url: str | None) -> str | None:
    if not url:
        return None
    return "bundled" if url.startswith("/app-html/") else "external"


def _find_app(catalog: list[Any], app_id: str) -> Any | None:
    return next(
        (a for a in catalog if a.app_id == app_id),
        next((a for a in catalog if a.module_path == app_id), None),
    )


def _summary(app: Any) -> dict[str, Any]:
    return {
        "app_id": app.app_id,
        "name": app.name,
        "source": "module",
        "module": app.module_name,
        "category": app.category,
        "embed": _embed_kind(app.url),
        "description": (app.description or "")[:_MAX_DESCRIPTION],
    }


def _external_summary(app: Any) -> dict[str, Any]:
    return {
        "app_id": app.url,
        "name": app.name,
        "source": "external",
        "embed": "external",
        "url": app.url,
        "description": (getattr(app, "description", None) or "")[:_MAX_DESCRIPTION],
    }


def _detail(app: Any, workspace_id: str) -> dict[str, Any]:
    out = _summary(app)
    out.update(
        {
            "module_path": app.module_path,
            "app_name": app.app_name,
            "manifest": f"{app.module_path}: apps/{app.app_name}/manifest.json",
            "url": app.url,
            "version": app.version,
            "author": app.author,
            "maintainer": app.maintainer,
            "license": app.license,
            "tier": app.tier,
            "keywords": list(app.keywords or []),
            "agent": getattr(app, "agent", None),
            "pricing": app.pricing.model_dump() if app.pricing else None,
            "has_demo_login": bool(app.demo_login),
            "open_in_nexus": (
                f"/workspace/{workspace_id}/apps?open={quote(app.app_id, safe='')}"
            ),
        }
    )
    return out


def _context() -> tuple[str, str] | dict[str, str]:
    user_id = _require_user_id()
    if isinstance(user_id, dict):
        return user_id
    workspace_id = turn_workspace_id()
    if not workspace_id:
        return {
            "error": "No workspace on this session. Open the chat pane from a workspace."
        }
    return user_id, workspace_id


def _resolve_app_id(app_id: str) -> str | dict[str, str]:
    explicit = (app_id or "").strip()
    if explicit:
        return explicit
    open_id = active_feature_resource_id(APP_RESOURCE_KIND)
    if open_id:
        return open_id
    return {"error": "No app is open. Pass app_id (see list_workspace_apps)."}


async def _usable(
    db: Any, user_id: str, workspace_id: str, catalog: list[Any]
) -> list[Any] | dict[str, str]:
    """The apps of ``catalog`` the user may open in the workspace, after the
    membership check: IAM's ``module:OpenApp``, as the Apps page lists them."""
    from naas_abi.apps.nexus.apps.api.app.services.apps.scopes import app_scope
    from naas_abi.apps.nexus.apps.api.app.services.iam import authz
    from naas_abi.apps.nexus.apps.api.app.services.workspaces.service import (
        WorkspacePermissionError,
    )

    try:
        await _workspace_service(db).require_workspace_access(
            user_id=user_id, workspace_id=workspace_id
        )
    except WorkspacePermissionError:
        return {"error": "You do not have access to this workspace."}
    return await authz.filter_scopes(
        catalog,
        user=user_id,
        workspace=workspace_id,
        scope_of=lambda app: app_scope(app.app_id),
    )


def apps_tools() -> list[BaseTool]:
    @tool
    def list_workspace_apps() -> Any:
        """List the apps of this workspace the user may open, and external shortcuts.

        Each row has app_id, name, source (module or external), module,
        category, embed (bundled or external). The same apps as the Apps page.
        """
        ctx = _context()
        if isinstance(ctx, dict):
            return ctx
        user_id, workspace_id = ctx
        # Read request context here: _run_async may hop to a fresh thread.
        open_id = active_feature_resource_id(APP_RESOURCE_KIND)

        async def _run(db: Any) -> Any:
            usable = await _usable(db, user_id, workspace_id, _catalog())
            if isinstance(usable, dict):
                return usable
            rows = [_summary(app) for app in usable]
            rows += [_external_summary(app) for app in _external_apps()]
            return {"workspace_id": workspace_id, "open_app_id": open_id, "apps": rows}

        try:
            return _run_async(_with_db(_run))
        except Exception as exc:  # noqa: BLE001
            return _tool_error(exc)

    @tool
    def get_app(app_id: str = "") -> Any:
        """Details of one app the user may open: manifest fields, embed kind, URL.

        Omit app_id to use the app open in the Apps page.
        """
        ctx = _context()
        if isinstance(ctx, dict):
            return ctx
        user_id, workspace_id = ctx
        resolved = _resolve_app_id(app_id)
        if isinstance(resolved, dict):
            return resolved

        external = next((a for a in _external_apps() if a.url == resolved), None)
        if external is not None:
            return _external_summary(external)
        app = _find_app(_catalog(), resolved)
        if app is None:
            return {"error": f"Unknown app_id: {resolved}. See list_workspace_apps."}

        async def _run(db: Any) -> Any:
            usable = await _usable(db, user_id, workspace_id, [app])
            if isinstance(usable, dict):
                return usable
            if not usable:
                return {"error": "You may not open this app in this workspace."}
            return _detail(app, workspace_id)

        try:
            return _run_async(_with_db(_run))
        except Exception as exc:  # noqa: BLE001
            return _tool_error(exc)

    return [list_workspace_apps, get_app]
