"""
AppsService: discovers web applications shipped by marketplace modules.

For each module under ``naas_abi_marketplace/<category>/<module>/``, scans
the ``apps/<app_name>/manifest.json`` files and exposes them as a flat list.

Manifest fields are the source of truth for app metadata (name, description,
icon, url, tier, maintainer, …). Per-deployment values (demo_login,
demo_password) are pulled from the installed module's runtime configuration.

The catalog is built via pure filesystem I/O (no dynamic imports), mirroring
the pattern used by ``ModulesService``.
"""

from __future__ import annotations

import json
import logging
from functools import lru_cache
from pathlib import Path

from naas_abi.apps.nexus.apps.api.app.services.apps.schema import (
    AppInfo,
    AppPricing,
    AppsResponse,
)

_log = logging.getLogger(__name__)

_CATEGORY_MAP = {
    "ai": "ai",
    "applications": "application",
    "domains": "domain",
    "alpha": "alpha",
}


def _get_category(module_path: str) -> str:
    parts = module_path.split(".")
    if parts[0] != "naas_abi_marketplace":
        return "core"
    if len(parts) >= 3:
        return _CATEGORY_MAP.get(parts[1], parts[1])
    return "core"


def _fallback_name(dir_name: str) -> str:
    return dir_name.replace("-", " ").replace("_", " ").title()


def _read_manifest(path: Path) -> dict | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        _log.warning("Failed to read manifest %s: %s", path, exc)
        return None


def _module_name_from_path(module_path: str) -> str:
    """Human-readable parent module name (last segment, underscores → spaces)."""
    last = module_path.rsplit(".", 1)[-1] if "." in module_path else module_path
    return last.replace("_", " ")


def _build_app_info(
    module_path: str,
    app_dir: Path,
    manifest: dict,
) -> AppInfo:
    pricing_raw = manifest.get("pricing")
    pricing = AppPricing(**pricing_raw) if isinstance(pricing_raw, dict) else None

    return AppInfo(
        module_path=module_path,
        module_name=_module_name_from_path(module_path),
        app_name=app_dir.name,
        app_id=f"{module_path}:{app_dir.name}",
        category=_get_category(module_path),
        name=manifest.get("name") or _fallback_name(app_dir.name),
        description=manifest.get("description") or "",
        url=manifest.get("url"),
        avatar_url=manifest.get("avatar_url"),
        icon_emoji=manifest.get("icon_emoji"),
        demo_login=manifest.get("demo_login"),
        demo_password=manifest.get("demo_password"),
        version=manifest.get("version"),
        author=manifest.get("author"),
        license=manifest.get("license"),
        keywords=list(manifest.get("keywords") or []),
        tier=manifest.get("tier"),
        maintainer=manifest.get("maintainer"),
        pricing=pricing,
        dependencies=dict(manifest.get("dependencies") or {}),
    )


@lru_cache(maxsize=1)
def _scan_apps_catalog() -> list[AppInfo]:
    """
    Scan ``naas_abi_marketplace`` for ``apps/<app_name>/manifest.json`` files.

    Results are process-cached; restart the API to pick up new manifests.
    """
    try:
        import naas_abi_marketplace

        pkg_paths = list(naas_abi_marketplace.__path__)
        if not pkg_paths:
            _log.warning("naas_abi_marketplace.__path__ is empty — apps catalog will be empty")
            return []
        base = Path(pkg_paths[0])
    except (ImportError, AttributeError):
        _log.warning("naas_abi_marketplace not available — apps catalog will be empty")
        return []

    catalog: list[AppInfo] = []

    for cat_dir in sorted(base.iterdir()):
        if not cat_dir.is_dir() or cat_dir.name.startswith("_"):
            continue

        for mod_dir in sorted(cat_dir.iterdir()):
            if not mod_dir.is_dir() or mod_dir.name.startswith("_"):
                continue

            apps_dir = mod_dir / "apps"
            if not apps_dir.is_dir():
                continue

            module_path = f"naas_abi_marketplace.{cat_dir.name}.{mod_dir.name}"

            for app_dir in sorted(apps_dir.iterdir()):
                if not app_dir.is_dir() or app_dir.name.startswith("_"):
                    continue
                manifest_path = app_dir / "manifest.json"
                if not manifest_path.is_file():
                    continue
                manifest = _read_manifest(manifest_path)
                if manifest is None:
                    continue
                catalog.append(_build_app_info(module_path, app_dir, manifest))

    _log.info("Apps catalog built: %d apps", len(catalog))
    return catalog


class AppsService:
    @staticmethod
    async def list_apps() -> AppsResponse:
        """Return all apps discovered from marketplace manifests.

        Apps whose parent module is currently loaded by the engine are flagged
        ``installed=True`` and enriched with demo credentials from the module's
        runtime configuration.
        """
        try:
            from naas_abi import ABIModule

            engine = ABIModule.get_instance().engine
            installed_modules = engine.modules
        except Exception:
            installed_modules = {}

        catalog = _scan_apps_catalog()

        results: list[AppInfo] = []
        for app in catalog:
            installed_module = installed_modules.get(app.module_path)
            if installed_module is None:
                results.append(app)
                continue

            # Manifest values take precedence; only fall back to runtime config
            # when the manifest omits the credential.
            cfg = getattr(installed_module, "configuration", None)
            update: dict = {"installed": True}
            if not app.demo_login:
                update["demo_login"] = getattr(cfg, "demo_login", None) or None
            if not app.demo_password:
                update["demo_password"] = getattr(cfg, "demo_password", None) or None
            results.append(app.model_copy(update=update))

        results.sort(key=lambda a: (a.category, a.name.lower()))
        return AppsResponse(apps=results)
