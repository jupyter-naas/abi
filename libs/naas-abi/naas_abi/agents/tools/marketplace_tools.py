"""MarketplaceAgent tools for Nexus Marketplace.

Same data as ``GET /api/modules/`` (installed engine modules plus the full
filesystem catalog) and ``GET /api/modules/config`` (pricing and usage tiers).
The catalog is read-only: a module is installed by listing it under
``modules:`` in config.yaml and restarting, so no tool pretends to install one.
The module selected on the Marketplace page arrives as the open feature
resource (kind ``module``). Demo passwords never reach the model.
"""

from __future__ import annotations

from typing import Any

from langchain_core.tools import BaseTool, tool
from naas_abi.agents.feature.context import active_feature_resource_id
from naas_abi.agents.feature.runtime import (
    check_member,
    clip,
    guarded,
    jsonable,
    matches,
    run,
    tool_context,
)

MODULE_RESOURCE_KIND = "module"
_FEATURE = "Marketplace"


def _list_modules() -> Any:
    from naas_abi.apps.nexus.apps.api.app.services.modules.service import ModulesService

    return run(ModulesService.list_modules())


def _marketplace_config() -> Any:
    from naas_abi.apps.nexus.apps.api.app.core.config import get_settings

    return get_settings().marketplace


def _summary(module: Any) -> dict[str, Any]:
    return {
        "module_path": module.module_path,
        "name": module.name,
        "category": module.category,
        "installed": module.installed,
        "tier": module.tier,
        "maintainer": module.maintainer,
        "functional": module.functional,
        "description": clip(module.description, 240),
    }


def _detail(module: Any) -> dict[str, Any]:
    out = _summary(module)
    out.update(
        {
            "description": clip(module.description, 1200),
            "agent_type": module.agent_type,
            "model": module.model,
            "app_url": module.app_url,
            "stripe_url": module.stripe_url,
            "has_demo_login": bool(module.demo_login),
            "system_prompt_preview": clip(module.system_prompt_preview, 600),
            "install": (
                "Already loaded by the engine."
                if module.installed
                else f"Add `- module: {module.module_path}` with `enabled: true` "
                "under modules: in config.yaml, then restart the API."
            ),
        }
    )
    return out


def marketplace_tools() -> list[BaseTool]:
    @tool
    def list_marketplace_modules(
        query: str = "", category: str = "", installed_only: bool = False
    ) -> Any:
        """List Marketplace modules: installed ones and the full catalog.

        Filter with query (name, path, description), category (core, ai,
        application, domain), or installed_only. Rows: module_path, name,
        category, installed, tier, maintainer.
        """
        ctx = tool_context()
        if isinstance(ctx, dict):
            return ctx
        user_id, workspace_id = ctx
        open_path = active_feature_resource_id(MODULE_RESOURCE_KIND)

        def _run() -> Any:
            role = check_member(user_id, workspace_id)
            if isinstance(role, dict):
                return role
            modules = _list_modules().available
            rows = [
                _summary(m)
                for m in modules
                if (not installed_only or m.installed)
                and (not category or m.category == category.strip().lower())
                and matches(query, m.name, m.module_path, m.description)
            ]
            return {
                "total": len(rows),
                "installed": sum(1 for m in modules if m.installed),
                "open_module": open_path,
                "modules": rows[:80],
                "truncated": len(rows) > 80,
            }

        return guarded(_FEATURE, _run)

    @tool
    def get_marketplace_module(module_path: str = "") -> Any:
        """Details of one module: description, tier, agent, app URL, how to install.

        Omit module_path to use the module selected on the Marketplace page.
        """
        ctx = tool_context()
        if isinstance(ctx, dict):
            return ctx
        user_id, workspace_id = ctx
        wanted = (module_path or "").strip() or active_feature_resource_id(
            MODULE_RESOURCE_KIND
        )
        if not wanted:
            return {
                "error": "No module is selected. Pass module_path (see list_marketplace_modules)."
            }

        def _run() -> Any:
            role = check_member(user_id, workspace_id)
            if isinstance(role, dict):
                return role
            modules = _list_modules().available
            module = next((m for m in modules if m.module_path == wanted), None)
            if module is None:
                module = next(
                    (m for m in modules if m.name.lower() == wanted.lower()), None
                )
            if module is None:
                return {
                    "error": f"Unknown module: {wanted}. See list_marketplace_modules."
                }
            return _detail(module)

        return guarded(_FEATURE, _run)

    @tool
    def get_marketplace_pricing() -> Any:
        """Marketplace configuration: pricing, usage tiers, and model token costs."""
        ctx = tool_context()
        if isinstance(ctx, dict):
            return ctx
        user_id, workspace_id = ctx

        def _run() -> Any:
            role = check_member(user_id, workspace_id)
            if isinstance(role, dict):
                return role
            return jsonable(_marketplace_config())

        return guarded(_FEATURE, _run)

    return [list_marketplace_modules, get_marketplace_module, get_marketplace_pricing]
