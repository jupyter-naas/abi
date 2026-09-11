"""AppsAgent tools for Nexus Apps.

Same data the Apps page shows (``GET /api/apps/?workspace_id=``): the module
catalog discovered from ``<module>/apps/<name>/manifest.json``, the workspace
enable state (DB row, then the config seed, then off), and the tenant's
external shortcuts. When the user has an app open (``?open=<app_id>``) the
pane sends it as the open feature resource, so tools default to that app and
the agent never asks which one.

Access mirrors the HTTP adapter: workspace membership, same as
``PATCH /api/apps/{workspace_id}/{app_id}``. Demo passwords never reach the
model; tools only say whether a demo login exists.
"""

from __future__ import annotations

from typing import Any
from urllib.parse import quote

from langchain_core.tools import BaseTool, tool
from naas_abi.agents.feature.context import active_feature_resource_id
from naas_abi.agents.tools.nexus_admin_tools import (
    _record_to_dict,
    _require_user_id,
    _run_async,
    _with_db,
    _workspace_service,
)
from naas_abi_core.services.agent.context import agent_workspace_id

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
    """Tenant shortcuts (``nexus_config.tenant.apps``). Always on, not toggleable."""
    try:
        from naas_abi.apps.nexus.apps.api.app.core import config as nexus_config

        tenant = getattr(nexus_config.settings, "tenant", None)
        return list(getattr(tenant, "apps", None) or [])
    except Exception:  # noqa: BLE001
        return []


def _apps_service(db: Any) -> Any:
    from naas_abi.apps.nexus.apps.api.app.services.apps.adapters.secondary.postgres import (
        AppSecondaryAdapterPostgres,
    )
    from naas_abi.apps.nexus.apps.api.app.services.apps.service import AppsService

    return AppsService(adapter=AppSecondaryAdapterPostgres(db=db))


def _embed_kind(url: str | None) -> str | None:
    if not url:
        return None
    return "bundled" if url.startswith("/app-html/") else "external"


def _find_app(catalog: list[Any], app_id: str) -> Any | None:
    return next(
        (a for a in catalog if a.app_id == app_id),
        next((a for a in catalog if a.module_path == app_id), None),
    )


def _summary(app: Any, enabled: bool) -> dict[str, Any]:
    return {
        "app_id": app.app_id,
        "name": app.name,
        "source": "module",
        "module": app.module_name,
        "category": app.category,
        "enabled": enabled,
        "embed": _embed_kind(app.url),
        "description": (app.description or "")[:_MAX_DESCRIPTION],
    }


def _external_summary(app: Any) -> dict[str, Any]:
    return {
        "app_id": app.url,
        "name": app.name,
        "source": "external",
        "enabled": True,
        "embed": "external",
        "url": app.url,
        "description": (getattr(app, "description", None) or "")[:_MAX_DESCRIPTION],
    }


def _detail(app: Any, enabled: bool, workspace_id: str) -> dict[str, Any]:
    out = _summary(app, enabled)
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
    workspace_id = (agent_workspace_id.get() or "").strip()
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


async def _enable_state(
    db: Any, user_id: str, workspace_id: str
) -> tuple[dict[str, bool], set[str]] | dict[str, str]:
    """(DB rows, seed list) for the workspace, after the membership check."""
    from naas_abi.apps.nexus.apps.api.app.core.workspace_catalog_seed import (
        workspace_seed_for_slug,
    )
    from naas_abi.apps.nexus.apps.api.app.services.workspaces.service import (
        WorkspacePermissionError,
    )

    workspaces = _workspace_service(db)
    try:
        await workspaces.require_workspace_access(
            user_id=user_id, workspace_id=workspace_id
        )
    except WorkspacePermissionError:
        return {"error": "You do not have access to this workspace."}
    enabled_by_app_id = await _apps_service(db).get_enabled_states(workspace_id)
    workspace = await workspaces.get_workspace(workspace_id)
    seed = workspace_seed_for_slug(getattr(workspace, "slug", None))
    seed_apps = {
        str(app_id).strip()
        for app_id in (getattr(seed, "apps", None) or [])
        if str(app_id).strip()
    }
    return enabled_by_app_id, seed_apps


def _is_enabled(app_id: str, state: tuple[dict[str, bool], set[str]]) -> bool:
    from naas_abi.apps.nexus.apps.api.app.core.workspace_catalog_seed import (
        resolve_app_enabled,
    )

    enabled_by_app_id, seed_apps = state
    return resolve_app_enabled(app_id, enabled_by_app_id, seed_apps)


def apps_tools() -> list[BaseTool]:
    @tool
    def list_workspace_apps(include_disabled: bool = True) -> Any:
        """List the apps of this workspace: module apps and external shortcuts.

        Each row has app_id, name, source (module or external), module,
        category, enabled, embed (bundled or external). The Apps page only
        shows enabled apps; set include_disabled=False to match it.
        """
        ctx = _context()
        if isinstance(ctx, dict):
            return ctx
        user_id, workspace_id = ctx
        # Read request context here: _run_async may hop to a fresh thread.
        open_id = active_feature_resource_id(APP_RESOURCE_KIND)

        async def _run(db: Any) -> Any:
            state = await _enable_state(db, user_id, workspace_id)
            if isinstance(state, dict):
                return state
            rows = [_summary(app, _is_enabled(app.app_id, state)) for app in _catalog()]
            if not include_disabled:
                rows = [row for row in rows if row["enabled"]]
            rows += [_external_summary(app) for app in _external_apps()]
            return {"workspace_id": workspace_id, "open_app_id": open_id, "apps": rows}

        try:
            return _run_async(_with_db(_run))
        except Exception as exc:  # noqa: BLE001
            return _tool_error(exc)

    @tool
    def get_app(app_id: str = "") -> Any:
        """Details of one app: manifest fields, enable state, embed kind, URL.

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
            state = await _enable_state(db, user_id, workspace_id)
            if isinstance(state, dict):
                return state
            return _detail(app, _is_enabled(app.app_id, state), workspace_id)

        try:
            return _run_async(_with_db(_run))
        except Exception as exc:  # noqa: BLE001
            return _tool_error(exc)

    @tool
    def set_app_enabled(enabled: bool, app_id: str = "") -> Any:
        """Enable or disable a module app in this workspace.

        Same rule as the Settings > Apps toggle. Omit app_id to use the open
        app. External shortcuts come from tenant config and cannot be toggled.
        """
        ctx = _context()
        if isinstance(ctx, dict):
            return ctx
        user_id, workspace_id = ctx
        resolved = _resolve_app_id(app_id)
        if isinstance(resolved, dict):
            return resolved
        if any(a.url == resolved for a in _external_apps()):
            return {
                "error": (
                    "External shortcuts come from nexus_config.tenant.apps and "
                    "are always shown. Change the config to remove one."
                )
            }
        app = _find_app(_catalog(), resolved)
        if app is None:
            return {"error": f"Unknown app_id: {resolved}. See list_workspace_apps."}

        async def _run(db: Any) -> Any:
            from naas_abi.apps.nexus.apps.api.app.services.apps.port import (
                AppConfigUpdateInput,
            )

            state = await _enable_state(db, user_id, workspace_id)
            if isinstance(state, dict):
                return state
            record = await _apps_service(db).upsert_app_config(
                workspace_id=workspace_id,
                app_id=app.app_id,
                updates=AppConfigUpdateInput(enabled=bool(enabled)),
            )
            out = _record_to_dict(record)
            out["name"] = app.name
            out["note"] = "Reload the Apps page to see the change."
            return out

        try:
            return _run_async(_with_db(_run))
        except Exception as exc:  # noqa: BLE001
            return _tool_error(exc)

    return [list_workspace_apps, get_app, set_app_enabled]
