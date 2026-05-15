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

# Regex patterns to extract metadata from agent source files.
# Supports three conventions used across the codebase:
#
#   Class attributes (with optional type annotation, inline or parenthesised):
#     name: str = "Accountant"
#     logo_url: str = (
#         "https://..."
#     )
#
#   Module-level constants (used by most domain/app agents):
#     NAME = "Accountant"
#     AVATAR_URL = "https://..."
#     DESCRIPTION = "..."
#
# Each pattern tries the class-attribute form first (indented), then the
# module-level constant form (no indentation).
_RE_NAME = re.compile(
    r'(?:^\s+name\s*(?::[^=\n]*)?\s*=\s*\(?\s*|^NAME\s*=\s*)["\']([^"\']+)["\']',
    re.MULTILINE,
)
_RE_DESC = re.compile(
    r'(?:^\s+description\s*(?::[^=\n]*)?\s*=\s*\(?\s*|^DESCRIPTION\s*=\s*)["\']([^"\']+)["\']',
    re.MULTILINE,
)
_RE_LOGO = re.compile(
    r'(?:^\s+logo_url\s*(?::[^=\n]*)?\s*=\s*\(?\s*|^AVATAR_URL\s*=\s*)["\']([^"\']+)["\']',
    re.MULTILINE,
)
_RE_MODEL = re.compile(
    r'(?:^\s+model\s*(?::[^=\n]*)?\s*=\s*\(?\s*|^MODEL\s*=\s*)["\']([^"\']+)["\']',
    re.MULTILINE,
)
_RE_SLUG = re.compile(r'^SLUG\s*=\s*["\']([^"\']+)["\']', re.MULTILINE)
_RE_AGENT_TYPE = re.compile(r'^TYPE\s*=\s*["\']([^"\']+)["\']', re.MULTILINE)
# Triple-quoted system prompts (class attr or module constant)
_RE_SYSTEM_PROMPT = re.compile(
    r'(?:^SYSTEM_PROMPT|^\s+system_prompt\s*(?::[^=\n]*)?)\s*=\s*"""(.*?)"""',
    re.MULTILINE | re.DOTALL,
)
_NOT_FUNCTIONAL_RE = re.compile(r'NOT FUNCTIONAL', re.IGNORECASE)
# Marketplace metadata (optional, set by agent author)
_RE_TIER = re.compile(r'^TIER\s*=\s*["\']([^"\']+)["\']', re.MULTILINE)
_RE_MAINTAINER = re.compile(r'^MAINTAINER\s*=\s*["\']([^"\']+)["\']', re.MULTILINE)
_RE_STRIPE_URL = re.compile(r'^STRIPE_URL\s*=\s*["\']([^"\']+)["\']', re.MULTILINE)

_SYSTEM_PROMPT_PREVIEW_LEN = 280


def _get_category(module_path: str) -> str:
    parts = module_path.split(".")
    if parts[0] != "naas_abi_marketplace":
        return "core"
    if len(parts) >= 3:
        return _CATEGORY_MAP.get(parts[1], parts[1])
    return "core"


def _trim_prompt(raw: str) -> str | None:
    """Return the first meaningful paragraph of a system prompt, trimmed."""
    text = raw.strip()
    if not text:
        return None
    # Strip leading markdown headers / role lines
    lines = [ln for ln in text.splitlines() if ln.strip() and not ln.strip().startswith("#")]
    clean = " ".join(lines)
    if len(clean) > _SYSTEM_PROMPT_PREVIEW_LEN:
        clean = clean[:_SYSTEM_PROMPT_PREVIEW_LEN].rsplit(" ", 1)[0] + "…"
    return clean or None


AgentMeta = tuple[
    str | None,  # name
    str | None,  # description
    str | None,  # logo_url
    str | None,  # model
    str | None,  # slug
    str | None,  # agent_type
    str | None,  # system_prompt_preview
    bool,        # functional
    str | None,  # tier
    str | None,  # maintainer
    str | None,  # stripe_url
]


def _scan_agent_file(path: Path) -> AgentMeta:
    """Extract all agent metadata from a source file via regex (no imports)."""
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return None, None, None, None, None, None, None, True, None, None, None

    def _m(pattern: re.Pattern[str]) -> str | None:
        m = pattern.search(text)
        return m.group(1) if m else None

    prompt_raw = _m(_RE_SYSTEM_PROMPT)
    return (
        _m(_RE_NAME),
        _m(_RE_DESC),
        _m(_RE_LOGO),
        _m(_RE_MODEL),
        _m(_RE_SLUG),
        _m(_RE_AGENT_TYPE),
        _trim_prompt(prompt_raw) if prompt_raw else None,
        not bool(_NOT_FUNCTIONAL_RE.search(text)),
        _m(_RE_TIER),
        _m(_RE_MAINTAINER),
        _m(_RE_STRIPE_URL),
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
            model: str | None = None
            slug: str | None = None
            agent_type: str | None = None
            system_prompt_preview: str | None = None
            functional: bool = True
            tier: str | None = None
            maintainer: str | None = None
            stripe_url: str | None = None

            agent_candidates = list((mod_dir / "agents").glob("*.py")) if (mod_dir / "agents").is_dir() else []
            agent_candidates += list(mod_dir.glob("*Agent.py"))

            for agent_file in agent_candidates:
                if agent_file.name.startswith("_"):
                    continue
                n, d, lurl, mdl, slg, atype, spp, func, tr, maint, surl = _scan_agent_file(agent_file)
                if n:
                    name, description, logo_url = n, d, lurl
                    model, slug, agent_type = mdl, slg, atype
                    system_prompt_preview, functional = spp, func
                    tier, maintainer, stripe_url = tr, maint, surl
                    break

            catalog.append(
                ModuleInfo(
                    module_path=module_path,
                    name=name or _fallback_name(mod_dir.name),
                    description=description or "",
                    logo_url=logo_url,
                    category=category,
                    installed=False,
                    model=model,
                    slug=slug,
                    agent_type=agent_type,
                    system_prompt_preview=system_prompt_preview,
                    functional=functional,
                    tier=tier,
                    maintainer=maintainer,
                    stripe_url=stripe_url,
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
