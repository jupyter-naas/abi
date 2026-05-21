"""Apps FastAPI primary adapter.

Discovers apps shipped by marketplace + built-in modules, hydrates each
result with the workspace's enable state (via ``AppsService``), and exposes
both the catalog and a CRUD surface for per-workspace app configuration
over HTTP.

Routes
------
* ``GET    /api/apps/?workspace_id=…``         — catalog (with enable state)
* ``GET    /api/apps/{ws}``                    — list configs for workspace
* ``POST   /api/apps/{ws}``                    — create config
* ``GET    /api/apps/{ws}/{app_id:path}``      — get one config
* ``PATCH  /api/apps/{ws}/{app_id:path}``      — update / enable / disable
* ``DELETE /api/apps/{ws}/{app_id:path}``      — delete (reverts to default)

The filesystem-level catalog discovery lives here (rather than in the
service) because it shapes the HTTP response; the service itself only
owns per-workspace persistence.
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict
from functools import lru_cache
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from naas_abi.apps.nexus.apps.api.app.api.endpoints.auth import (
    User,
    get_current_user_required,
    require_workspace_access,
)
from naas_abi.apps.nexus.apps.api.app.services.apps.port import (
    AppConfigCreate,
    AppConfigCreateInput,
    AppConfigRecord,
    AppConfigUpdate,
    AppConfigUpdateInput,
    AppInfo,
    AppPricing,
    AppsResponse,
)
from naas_abi.apps.nexus.apps.api.app.services.apps.service import (
    AppAlreadyConfiguredError,
    AppsService,
)
from naas_abi.apps.nexus.apps.api.app.services.registry import (
    ServiceRegistry,
    get_service_registry,
)

_log = logging.getLogger(__name__)

router = APIRouter(dependencies=[Depends(get_current_user_required)])


# ---------------------------------------------------------------------------
# Catalog discovery (marketplace + built-in apps)
# ---------------------------------------------------------------------------

_CATEGORY_MAP = {
    "ai": "ai",
    "applications": "application",
    "domains": "domain",
    "alpha": "alpha",
}

# Built-in apps shipped with naas_abi itself (not via the marketplace).
# These are always considered installed.
_BUILTIN_APPS_PACKAGE = "naas_abi"
_BUILTIN_APPS_SUBPATH = "apps"


def _get_category(module_path: str) -> str:
    parts = module_path.split(".")
    if parts[0] == "naas_abi_marketplace":
        if len(parts) >= 3:
            return _CATEGORY_MAP.get(parts[1], parts[1])
        return "core"
    if parts[0] == "naas_abi":
        return "core"
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


def _scan_marketplace_apps() -> list[AppInfo]:
    """Scan ``naas_abi_marketplace`` for ``apps/<app_name>/manifest.json`` files."""
    try:
        import naas_abi_marketplace

        pkg_paths = list(naas_abi_marketplace.__path__)
        if not pkg_paths:
            _log.warning("naas_abi_marketplace.__path__ is empty")
            return []
        base = Path(pkg_paths[0])
    except (ImportError, AttributeError):
        _log.warning("naas_abi_marketplace not available")
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

    return catalog


def _scan_builtin_apps() -> list[AppInfo]:
    """Scan ``naas_abi/apps/<app_name>/manifest.json`` for built-in apps.

    Built-in apps ship with the platform (not the marketplace) and are
    always considered installed.
    """
    try:
        import naas_abi

        pkg_paths = list(naas_abi.__path__)
        if not pkg_paths:
            return []
        apps_dir = Path(pkg_paths[0]) / _BUILTIN_APPS_SUBPATH
    except (ImportError, AttributeError):
        return []

    if not apps_dir.is_dir():
        return []

    catalog: list[AppInfo] = []
    for app_dir in sorted(apps_dir.iterdir()):
        if not app_dir.is_dir() or app_dir.name.startswith("_"):
            continue
        manifest_path = app_dir / "manifest.json"
        if not manifest_path.is_file():
            continue
        manifest = _read_manifest(manifest_path)
        if manifest is None:
            continue
        module_path = f"{_BUILTIN_APPS_PACKAGE}.{_BUILTIN_APPS_SUBPATH}.{app_dir.name}"
        # Built-in apps are always installed — they ship with the platform.
        info = _build_app_info(module_path, app_dir, manifest)
        catalog.append(info.model_copy(update={"installed": True}))
    return catalog


@lru_cache(maxsize=1)
def _scan_apps_catalog() -> tuple[AppInfo, ...]:
    """Discover apps from the marketplace and naas_abi's built-in apps dir.

    Results are process-cached; restart the API to pick up new manifests.
    """
    catalog = _scan_marketplace_apps() + _scan_builtin_apps()
    _log.info("Apps catalog built: %d apps", len(catalog))
    return tuple(catalog)


def _app_exists(app_id: str) -> bool:
    return any(a.app_id == app_id for a in _scan_apps_catalog())


# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------


def get_apps_service(
    registry: ServiceRegistry = Depends(get_service_registry),
) -> AppsService:
    return registry.apps


def _serialize_record(record: AppConfigRecord) -> dict:
    data = asdict(record)
    data["created_at"] = record.created_at.isoformat()
    data["updated_at"] = record.updated_at.isoformat()
    return data


def _ensure_app_exists(app_id: str) -> None:
    if not _app_exists(app_id):
        raise HTTPException(status_code=404, detail=f"Unknown app_id: {app_id}")


class AppsFastAPIPrimaryAdapter:
    def __init__(self) -> None:
        self.router = router


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.get("/", response_model=AppsResponse)
async def list_apps(
    workspace_id: str | None = None,
    current_user: User = Depends(get_current_user_required),
    apps_service: AppsService = Depends(get_apps_service),
) -> AppsResponse:
    """Return every app discovered from marketplace + built-in manifests.

    When ``workspace_id`` is provided, results carry the workspace's enable
    state. Apps without a stored record default to ``enabled=True``.
    """
    if workspace_id:
        await require_workspace_access(current_user.id, workspace_id)

    try:
        from naas_abi import ABIModule

        engine = ABIModule.get_instance().engine
        installed_modules = engine.modules
    except Exception:
        installed_modules = {}

    catalog = _scan_apps_catalog()

    enabled_by_app_id: dict[str, bool] = (
        await apps_service.get_enabled_states(workspace_id) if workspace_id else {}
    )

    results: list[AppInfo] = []
    for app in catalog:
        installed_module = installed_modules.get(app.module_path)
        update: dict = {"enabled": enabled_by_app_id.get(app.app_id, True)}

        if installed_module is not None:
            update["installed"] = True
            # Manifest values take precedence; only fall back to runtime
            # config when the manifest omits the credential.
            cfg = getattr(installed_module, "configuration", None)
            if not app.demo_login:
                update["demo_login"] = getattr(cfg, "demo_login", None) or None
            if not app.demo_password:
                update["demo_password"] = getattr(cfg, "demo_password", None) or None

        results.append(app.model_copy(update=update))

    results.sort(key=lambda a: (a.category, a.name.lower()))
    return AppsResponse(apps=results)


@router.get("/{workspace_id}")
async def list_app_configs(
    workspace_id: str,
    current_user: User = Depends(get_current_user_required),
    apps_service: AppsService = Depends(get_apps_service),
) -> list[dict]:
    """List every stored app config for a workspace."""
    await require_workspace_access(current_user.id, workspace_id)
    records = await apps_service.list_app_configs(workspace_id)
    return [_serialize_record(r) for r in records]


@router.post("/{workspace_id}", status_code=201)
async def create_app_config(
    workspace_id: str,
    body: AppConfigCreate,
    current_user: User = Depends(get_current_user_required),
    apps_service: AppsService = Depends(get_apps_service),
) -> dict:
    """Create a new app config row (errors if one already exists)."""
    await require_workspace_access(current_user.id, workspace_id)
    _ensure_app_exists(body.app_id)
    try:
        record = await apps_service.create_app_config(
            AppConfigCreateInput(
                workspace_id=workspace_id,
                app_id=body.app_id,
                enabled=body.enabled,
            )
        )
    except AppAlreadyConfiguredError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return _serialize_record(record)


@router.get("/{workspace_id}/{app_id:path}")
async def get_app_config(
    workspace_id: str,
    app_id: str,
    current_user: User = Depends(get_current_user_required),
    apps_service: AppsService = Depends(get_apps_service),
) -> dict:
    """Get a single app config row."""
    await require_workspace_access(current_user.id, workspace_id)
    _ensure_app_exists(app_id)
    record = await apps_service.get_app_config(workspace_id, app_id)
    if record is None:
        raise HTTPException(status_code=404, detail="App config not found")
    return _serialize_record(record)


@router.patch("/{workspace_id}/{app_id:path}")
async def update_app_config(
    workspace_id: str,
    app_id: str,
    updates: AppConfigUpdate,
    current_user: User = Depends(get_current_user_required),
    apps_service: AppsService = Depends(get_apps_service),
) -> dict:
    """Update an app config (e.g. enable/disable).

    Idempotent: if no row exists yet, one is created with the supplied
    values. This lets the UI toggle simply call PATCH without a prior POST.
    """
    await require_workspace_access(current_user.id, workspace_id)
    _ensure_app_exists(app_id)

    record = await apps_service.update_app_config(
        workspace_id=workspace_id,
        app_id=app_id,
        updates=AppConfigUpdateInput(enabled=updates.enabled),
    )
    if record is None:
        # No existing row — create one. Missing fields fall back to defaults
        # (enabled=True), then we apply the requested update on top.
        enabled = True if updates.enabled is None else updates.enabled
        record = await apps_service.create_app_config(
            AppConfigCreateInput(
                workspace_id=workspace_id,
                app_id=app_id,
                enabled=enabled,
            )
        )
    return _serialize_record(record)


@router.delete("/{workspace_id}/{app_id:path}")
async def delete_app_config(
    workspace_id: str,
    app_id: str,
    current_user: User = Depends(get_current_user_required),
    apps_service: AppsService = Depends(get_apps_service),
) -> dict[str, str]:
    """Delete the app config (reverts to the default ``enabled=True``)."""
    await require_workspace_access(current_user.id, workspace_id)
    _ensure_app_exists(app_id)
    deleted = await apps_service.delete_app_config(workspace_id, app_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="App config not found")
    return {"status": "deleted"}
