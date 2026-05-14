"""
ModulesService: returns installed modules (from the running engine) and
the full catalog of available modules (scanned from naas_abi_marketplace).

The catalog is built via pure filesystem + regex scanning — no dynamic
imports — so it is fast and never fails due to heavy module dependencies.
"""

from __future__ import annotations

import logging
import re
from functools import lru_cache
from pathlib import Path

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

# Regex patterns to extract class-level string attributes from agent source files.
# Handles both inline:       name: str = "value"
# and parenthesised:         logo_url: str = (
#                                "https://..."
#                            )
_RE_NAME = re.compile(
    r'^\s+name\s*(?::[^=\n]*)?\s*=\s*\(?\s*["\']([^"\']+)["\']',
    re.MULTILINE,
)
_RE_DESC = re.compile(
    r'^\s+description\s*(?::[^=\n]*)?\s*=\s*\(?\s*["\']([^"\']+)["\']',
    re.MULTILINE,
)
_RE_LOGO = re.compile(
    r'^\s+logo_url\s*(?::[^=\n]*)?\s*=\s*\(?\s*["\']([^"\']+)["\']',
    re.MULTILINE,
)


def _get_category(module_path: str) -> str:
    parts = module_path.split(".")
    if parts[0] != "naas_abi_marketplace":
        return "core"
    if len(parts) >= 3:
        return _CATEGORY_MAP.get(parts[1], parts[1])
    return "core"


def _scan_agent_file(path: Path) -> tuple[str | None, str | None, str | None]:
    """Extract name/description/logo_url from an agent source file via regex."""
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return None, None, None

    name_m = _RE_NAME.search(text)
    desc_m = _RE_DESC.search(text)
    logo_m = _RE_LOGO.search(text)

    return (
        name_m.group(1) if name_m else None,
        desc_m.group(1) if desc_m else None,
        logo_m.group(1) if logo_m else None,
    )


def _fallback_name(dir_name: str) -> str:
    return dir_name.replace("-", " ").replace("_", " ").title()


@lru_cache(maxsize=1)
def _build_catalog() -> list[ModuleInfo]:
    """
    Scan naas_abi_marketplace at depth 2 using pure filesystem I/O.

    For each module, look for agent source files and extract metadata via
    regex — no imports, no side-effects, sub-second execution.
    Results are process-cached; a container restart picks up new modules.
    """
    try:
        import naas_abi_marketplace

        # naas_abi_marketplace is a namespace package — __file__ is None.
        # Use __path__ (a list of root directories) instead.
        pkg_paths = list(naas_abi_marketplace.__path__)
        if not pkg_paths:
            _log.warning("naas_abi_marketplace.__path__ is empty — catalog will be empty")
            return []
        base = Path(pkg_paths[0])
    except (ImportError, AttributeError, StopIteration):
        _log.warning("naas_abi_marketplace not available — catalog will be empty")
        return []

    catalog: list[ModuleInfo] = []

    for cat_dir in sorted(base.iterdir()):
        if not cat_dir.is_dir() or cat_dir.name.startswith("_"):
            continue
        category = _CATEGORY_MAP.get(cat_dir.name, cat_dir.name)

        for mod_dir in sorted(cat_dir.iterdir()):
            if not mod_dir.is_dir() or mod_dir.name.startswith("_"):
                continue
            # Accept both proper Python packages (__init__.py) and
            # non-identifier dirs (e.g. "account-executive") that still
            # contain an agents/ subdir or a top-level *Agent.py file.
            has_agents_dir = (mod_dir / "agents").is_dir()
            has_agent_file = any(mod_dir.glob("*Agent.py"))
            has_init = (mod_dir / "__init__.py").exists()
            if not (has_init or has_agents_dir or has_agent_file):
                continue

            module_path = f"naas_abi_marketplace.{cat_dir.name}.{mod_dir.name}"

            # Search for agent files (*Agent.py or agents/*.py)
            name: str | None = None
            description: str | None = None
            logo_url: str | None = None

            agent_candidates = list((mod_dir / "agents").glob("*.py")) if (mod_dir / "agents").is_dir() else []
            agent_candidates += list(mod_dir.glob("*Agent.py"))

            for agent_file in agent_candidates:
                if agent_file.name.startswith("_"):
                    continue
                n, d, lurl = _scan_agent_file(agent_file)
                if n:
                    name, description, logo_url = n, d, lurl
                    break

            catalog.append(
                ModuleInfo(
                    module_path=module_path,
                    name=name or _fallback_name(mod_dir.name),
                    description=description or "",
                    logo_url=logo_url,
                    category=category,
                    installed=False,
                )
            )

    _log.info("Marketplace catalog built: %d modules", len(catalog))
    return catalog


def _agent_meta(agent_cls: type) -> tuple[str | None, str | None, str | None]:
    agent_name = getattr(agent_cls, "name", None) or getattr(agent_cls, "NAME", None)
    agent_desc = getattr(agent_cls, "description", None)
    agent_logo = getattr(agent_cls, "logo_url", None)
    return (
        str(agent_name) if agent_name else None,
        str(agent_desc) if agent_desc else None,
        str(agent_logo) if agent_logo else None,
    )


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
                name = _fallback_name(module_path.split(".")[-1])

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

        # Available: full filesystem catalog, flagged with installed status
        catalog = _build_catalog()
        available: list[ModuleInfo] = [
            ModuleInfo(**{**m.model_dump(), "installed": m.module_path in installed_paths})
            for m in catalog
        ]
        available.sort(key=lambda m: (m.category, m.name.lower()))

        return ModulesResponse(installed=installed, available=available)
