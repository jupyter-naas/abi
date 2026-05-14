"""
ModulesService: returns installed modules (from the running engine) and
the full catalog of available modules (scanned from naas_abi_marketplace).
"""

from __future__ import annotations

import importlib
import logging
import pkgutil
from functools import lru_cache

from naas_abi.apps.nexus.apps.api.app.services.modules.schema import (
    ModuleInfo,
    ModulesResponse,
)

_log = logging.getLogger(__name__)

_CATEGORY_MAP = {
    "ai": "ai",
    "applications": "application",
    "domains": "domain",
}


def _get_category(module_path: str) -> str:
    parts = module_path.split(".")
    if parts[0] != "naas_abi_marketplace":
        return "core"
    if len(parts) >= 3:
        return _CATEGORY_MAP.get(parts[1], parts[1])
    return "core"


def _agent_meta(agent_cls: type) -> tuple[str | None, str | None, str | None]:
    agent_name = getattr(agent_cls, "name", None) or getattr(agent_cls, "NAME", None)
    agent_desc = getattr(agent_cls, "description", None)
    agent_logo = getattr(agent_cls, "logo_url", None)
    return (
        str(agent_name) if agent_name else None,
        str(agent_desc) if agent_desc else None,
        str(agent_logo) if agent_logo else None,
    )


@lru_cache(maxsize=1)
def _build_catalog() -> list[ModuleInfo]:
    """
    Walk naas_abi_marketplace at depth 2 and collect one representative
    agent per module to extract name/description/logo_url.

    Results are cached for the process lifetime (modules don't change at
    runtime).
    """
    try:
        import naas_abi_marketplace
    except ImportError:
        _log.warning("naas_abi_marketplace not available - catalog will be empty")
        return []

    catalog: dict[str, ModuleInfo] = {}

    # Iterate depth-1 categories (ai, applications, domains)
    for _cat_finder, cat_name, cat_ispkg in pkgutil.iter_modules(
        naas_abi_marketplace.__path__,
        naas_abi_marketplace.__name__ + ".",
    ):
        if not cat_ispkg or cat_name.startswith("naas_abi_marketplace.__"):
            continue

        try:
            cat_mod = importlib.import_module(cat_name)
        except Exception:
            continue

        # Iterate depth-2 modules within the category
        cat_path = getattr(cat_mod, "__path__", [])
        for _mod_finder, mod_name, mod_ispkg in pkgutil.iter_modules(
            cat_path,
            cat_name + ".",
        ):
            if not mod_ispkg:
                continue

            module_path = mod_name  # e.g. naas_abi_marketplace.ai.chatgpt
            agents_pkg = module_path + ".agents"
            name: str | None = None
            description: str | None = None
            logo_url: str | None = None

            try:
                agents_mod = importlib.import_module(agents_pkg)
                agent_path = getattr(agents_mod, "__path__", [])
                for _a_finder, agent_mod_name, _a_ispkg in pkgutil.iter_modules(
                    agent_path,
                    agents_pkg + ".",
                ):
                    if "_test" in agent_mod_name:
                        continue
                    try:
                        agent_file_mod = importlib.import_module(agent_mod_name)
                        for attr_name in dir(agent_file_mod):
                            cls = getattr(agent_file_mod, attr_name, None)
                            if (
                                cls is None
                                or not isinstance(cls, type)
                                or not hasattr(cls, "name")
                                or attr_name.startswith("_")
                            ):
                                continue
                            ag_name, ag_desc, ag_logo = _agent_meta(cls)
                            if ag_name:
                                name = ag_name
                                description = ag_desc
                                logo_url = ag_logo
                                break
                        if name:
                            break
                    except Exception:
                        continue
            except Exception:
                pass

            if not name:
                name = module_path.split(".")[-1].replace("_", " ").title()

            catalog[module_path] = ModuleInfo(
                module_path=module_path,
                name=name,
                description=description or "",
                logo_url=logo_url,
                category=_get_category(module_path),
                installed=False,
            )

    return list(catalog.values())


class ModulesService:
    @staticmethod
    async def list_modules() -> ModulesResponse:
        from naas_abi import ABIModule

        abi_module = ABIModule.get_instance()
        engine = abi_module.engine

        # Installed: modules currently loaded by the engine
        installed_paths: set[str] = set(engine.modules.keys())
        installed: list[ModuleInfo] = []

        for module_path, module_instance in engine.modules.items():
            name: str | None = None
            description: str | None = None
            logo_url: str | None = None

            for agent_cls in module_instance.agents:
                ag_name, ag_desc, ag_logo = _agent_meta(agent_cls)
                if ag_name:
                    name, description, logo_url = ag_name, ag_desc, ag_logo
                    break

            if not name:
                name = module_path.split(".")[-1].replace("_", " ").title()

            installed.append(
                ModuleInfo(
                    module_path=module_path,
                    name=name,
                    description=description or "",
                    logo_url=logo_url,
                    category=_get_category(module_path),
                    installed=True,
                )
            )

        # Available: full catalog from naas_abi_marketplace, flagged as installed
        catalog = _build_catalog()
        available: list[ModuleInfo] = [
            ModuleInfo(
                **{**m.model_dump(), "installed": m.module_path in installed_paths}
            )
            for m in catalog
        ]
        available.sort(key=lambda m: (m.category, m.name.lower()))

        return ModulesResponse(installed=installed, available=available)
