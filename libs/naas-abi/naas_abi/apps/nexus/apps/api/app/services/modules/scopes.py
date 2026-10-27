"""Every module with what it exposes, as module scopes: for the policy builder
and the module × workspace page.

Each module (an engine module by its configured path, a remote one by its id)
lists its agents, apps, workflows and pipelines (core ``module_scopes``: the
``module`` catalog, ``abi:<org>:<ws>:module:<type>/<module>/<name>``) with
their display name, description and icon, and the catalog it declares (its
own service, resource types and actions). ``resource`` is the pattern a policy
names, placed at the scope it is attached to (``${scope}``).

``build`` is the pure part; ``gather`` reads the engine, discovery, the jobs
and IAM, each source on its own: one that fails leaves its part out.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any

from naas_abi_core.services.iam import module_scopes
from naas_abi_core.services.iam.catalog import ActionCatalog

_log = logging.getLogger(__name__)

PLURAL = {
    module_scopes.AGENT: "agents",
    module_scopes.APP: "apps",
    module_scopes.WORKFLOW: "workflows",
    module_scopes.PIPELINE: "pipelines",
}


@dataclass(frozen=True)
class Exposed:
    """One agent, app, workflow or pipeline of a module."""

    type: str
    module: str
    name: str
    display_name: str = ""
    description: str = ""
    icon: str | None = None


@dataclass
class ModuleScopes:
    module: str
    items: dict[str, list[Exposed]] = field(default_factory=dict)
    catalog: ActionCatalog | None = None


def _actions(type_name: str) -> list[str]:
    actions = [module_scopes.USE_ACTION[type_name]]
    if type_name in module_scopes.RUNS_ACTION:
        actions.append(module_scopes.RUNS_ACTION[type_name])
    return [f"{module_scopes.SERVICE}:{a}" for a in actions]


def _item_view(item: Exposed) -> dict[str, Any]:
    resource = module_scopes.scope_resource(item.type, item.module, item.name)
    return {
        "name": item.name,
        "display_name": item.display_name or item.name,
        "description": item.description,
        "icon": item.icon,
        "resource": "${scope}:" + resource.split(":", 3)[3],
        "actions": _actions(item.type),
    }


def _catalog_view(catalog: ActionCatalog) -> dict[str, Any]:
    return {
        "service": catalog.service,
        "version": catalog.version,
        "resource_types": [
            {
                "name": t.name,
                "description": t.description,
                "resource": f"${{scope}}:{catalog.service}:{t.name}/*",
            }
            for t in catalog.resource_types
        ],
        "actions": [
            {
                "action": catalog.qualified(a.name),
                "level": a.level,
                "resource_types": list(a.resource_types),
                "description": a.description,
            }
            for a in catalog.actions
        ],
    }


def build(
    exposed: Iterable[Exposed],
    catalogs: Iterable[ActionCatalog] = (),
    modules: Iterable[str] = (),
) -> list[dict[str, Any]]:
    """The modules, sorted, each with its items by type (sorted, one entry per
    name) and its declared catalog. ``modules`` are listed even with nothing."""
    found: dict[str, ModuleScopes] = {m: ModuleScopes(m) for m in modules}
    for item in exposed:
        entry = found.setdefault(item.module, ModuleScopes(item.module))
        same = entry.items.setdefault(item.type, [])
        if all(other.name != item.name for other in same):
            same.append(item)
    for catalog in catalogs:
        if catalog.module:
            found.setdefault(catalog.module, ModuleScopes(catalog.module)).catalog = catalog
    return [
        {
            "module": entry.module,
            **{
                PLURAL[t]: [
                    _item_view(i)
                    for i in sorted(entry.items.get(t, []), key=lambda i: i.name.lower())
                ]
                for t in module_scopes.TYPES
            },
            "declared": _catalog_view(entry.catalog) if entry.catalog else None,
        }
        for entry in sorted(found.values(), key=lambda e: e.module)
    ]


# -- sources ---------------------------------------------------------------------------


def _text(value: Any) -> str:
    return value if isinstance(value, str) else ""


def engine_modules() -> list[str]:
    try:
        from naas_abi import ABIModule

        return list(ABIModule.get_instance().engine.modules)
    except Exception:  # noqa: BLE001 - no engine loaded
        _log.debug("No engine modules", exc_info=True)
        return []


def engine_agents() -> list[Exposed]:
    from naas_abi.apps.nexus.apps.api.app.services.agents.adapters.primary import (
        agents__primary_adapter__FastAPI as agents_api,
    )
    from naas_abi.apps.nexus.apps.api.app.services.agents.scopes import class_scope

    classes = agents_api._get_agent_class_registry()
    module_of = agents_api.agent_class_modules()
    found: list[Exposed] = []
    for key, cls in classes.items():
        scope = class_scope(key, cls, module_of)
        if scope is None:
            continue
        found.append(
            Exposed(
                scope.type,
                scope.module,
                scope.name,
                display_name=scope.name,
                description=_text(getattr(cls, "description", None))
                or _text(getattr(cls, "DESCRIPTION", None)),
                icon=_text(getattr(cls, "logo_url", None))
                or _text(getattr(cls, "AVATAR_URL", None))
                or None,
            )
        )
    return found


async def remote_agents() -> list[Exposed]:
    from naas_abi.apps.nexus.apps.api.app.services.agents.remote.factory import (
        get_remote_agent_directory,
    )

    return [
        Exposed(module_scopes.AGENT, a.module_id, a.name, a.name, a.description)
        for a in await get_remote_agent_directory().list_agents()
    ]


async def apps() -> list[Exposed]:
    from naas_abi.apps.nexus.apps.api.app.services.apps.adapters.primary import (
        apps__primary_adapter__FastAPI as apps_api,
    )
    from naas_abi.apps.nexus.apps.api.app.services.apps.scopes import app_scope

    found: list[Exposed] = []
    for app in (*apps_api._scan_apps_catalog(), *await apps_api._remote_apps_catalog()):
        scope = app_scope(app.app_id)
        if scope is not None:
            found.append(
                Exposed(
                    scope.type,
                    scope.module,
                    scope.name,
                    app.name,
                    app.description,
                    app.avatar_url or app.icon_emoji,
                )
            )
    return found


async def workflows() -> list[Exposed]:
    """The workflows and pipelines the jobs catalogs list, then the engine's
    own (when the jobs are not reachable, or not hosted here)."""
    from naas_abi.apps.nexus.apps.api.app.services.agents.scopes import engine_process_scopes
    from naas_abi.apps.nexus.apps.api.app.services.workflows.factory import (
        get_workflows_service,
    )
    from naas_abi.apps.nexus.apps.api.app.services.workflows.scopes import workflow_scope

    found: list[Exposed] = []
    try:
        listed = await get_workflows_service().list()
    except Exception:  # noqa: BLE001 - no broker, no jobs: the engine's own below
        _log.debug("Jobs catalogs unavailable for module scopes", exc_info=True)
    else:
        for d in listed.workflows:
            scope = workflow_scope(d.module_id, d.name)
            found.append(Exposed(scope.type, scope.module, scope.name, d.name, d.description))
    for scope in engine_process_scopes():
        found.append(Exposed(scope.type, scope.module, scope.name, scope.name))
    return found


def declared_catalogs() -> list[ActionCatalog]:
    from naas_abi.apps.nexus.apps.api.app.services.iam import runtime

    registry = getattr(runtime.iam(), "catalogs", None)
    return [c for c in registry.all() if c.module] if registry is not None else []


async def gather() -> list[dict[str, Any]]:
    """Every module with its scopes, from every source that answers."""
    exposed: list[Exposed] = []

    async def collect(name: str, source: Any) -> Any:
        try:
            result = source()
            return await result if hasattr(result, "__await__") else result
        except Exception:  # noqa: BLE001 - one source down leaves its part out
            _log.warning("Module scopes: %s unavailable", name, exc_info=True)
            return []

    # The engine's sources read in process; discovery and the jobs are NATS calls,
    # which run at once.
    *parts, catalogs = await asyncio.gather(
        collect("engine agents", engine_agents),
        collect("remote agents", remote_agents),
        collect("apps", apps),
        collect("workflows", workflows),
        collect("declared catalogs", declared_catalogs),
    )
    for part in parts:
        exposed.extend(part)
    return build(exposed, catalogs, engine_modules())
