"""Apps FastAPI primary adapter.

Discovers apps shipped by every module the engine has loaded, hydrates
each result with the workspace's enable state (via ``AppsService``), and
exposes both the catalog and a CRUD surface for per-workspace app
configuration over HTTP.

Routes
------
* ``GET    /api/apps/?workspace_id=…``         — catalog (with enable state)
* ``GET    /api/apps/{ws}``                    — list configs for workspace
* ``POST   /api/apps/{ws}``                    — create config
* ``GET    /api/apps/{ws}/{app_id:path}``      — get one config
* ``PATCH  /api/apps/{ws}/{app_id:path}``      — update / enable / disable
* ``DELETE /api/apps/{ws}/{app_id:path}``      — delete (reverts to default)

Discovery mirrors the pattern used by the agents adapter
(``agents__primary_adapter__FastAPI._get_agent_class_registry``): we walk
every module loaded by ``ABIModule.get_instance().engine`` (plus the root
``ABIModule`` itself) and read each module's ``apps/<app_name>/manifest.json``
files. The ``category`` field is sourced from the manifest — there is no
hard-coded category map.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Iterator
from dataclasses import asdict
from functools import lru_cache
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from naas_abi.apps.nexus.apps.api.app.api.endpoints.auth import (
    User,
    get_current_user_required,
    require_workspace_access,
)
from naas_abi.apps.nexus.apps.api.app.core.workspace_catalog_seed import (
    resolve_app_enabled,
    workspace_seed_for_slug,
)
from naas_abi.apps.nexus.apps.api.app.services.apps.app_html_access import (
    mint_app_html_access_token,
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
from naas_abi.apps.nexus.apps.api.app.utils.public_urls import public_modules_url
from pydantic import BaseModel, Field
from sqlalchemy import select

_log = logging.getLogger(__name__)

router = APIRouter(dependencies=[Depends(get_current_user_required)])


# ---------------------------------------------------------------------------
# Catalog discovery (driven by loaded engine modules)
# ---------------------------------------------------------------------------


async def _workspace_slug(workspace_id: str) -> str | None:
    from naas_abi.apps.nexus.apps.api.app.core.database import AsyncSessionLocal
    from naas_abi.apps.nexus.apps.api.app.models import WorkspaceModel

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(WorkspaceModel.slug).where(WorkspaceModel.id == workspace_id)
        )
        return result.scalar_one_or_none()


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


def _resolve_manifest_url(raw_url: str | None, module_path: str, app_name: str) -> str | None:
    """Resolve ``html:<filename>`` shorthand to the canonical /app-html/ path.

    The module dotted path is converted to slash-separated URL segments so
    ``naas_abi_marketplace.ai.chatgpt`` becomes
    ``naas_abi_marketplace/ai/chatgpt`` in the URL.
    """
    if raw_url and raw_url.startswith("html:"):
        filename = raw_url[len("html:"):]
        module_path_url = module_path.replace(".", "/")
        return f"/app-html/{module_path_url}/{app_name}/{filename}"
    return raw_url


def _resolve_avatar_url(avatar_url: str | None) -> str | None:
    """Rewrite module-served avatar paths to absolute public API URLs.

    Manifests may declare either:
    * ``/modules/<mod>/assets/public/...`` — already under the ``/modules`` mount
    * ``<mod>/assets/public/...`` — agent-style module-relative path

    Both are only reachable on ``public_api_host`` (e.g.
    ``https://api.localhost/modules/report/assets/public/avatar.png``). Absolute
    ``http(s)`` URLs are left untouched. Falls back to the raw value when the
    ABIModule instance is not initialized (unit tests).
    """
    if not avatar_url:
        return None
    if avatar_url.startswith(("http://", "https://")):
        return avatar_url

    stripped = avatar_url.lstrip("/")
    try:
        if stripped.startswith("modules/"):
            return public_modules_url(stripped[len("modules/") :])
        # Agent-style module-relative path (e.g. report/assets/public/avatar.png)
        if "/assets/public/" in f"/{stripped}":
            return public_modules_url(stripped)
    except Exception:
        _log.debug(
            "Could not resolve avatar_url against public_api_host; leaving relative",
            exc_info=True,
        )
    return avatar_url


def _build_app_info(
    module_path: str,
    app_dir: Path,
    manifest: dict,
) -> AppInfo:
    pricing_raw = manifest.get("pricing")
    pricing = AppPricing(**pricing_raw) if isinstance(pricing_raw, dict) else None

    url = _resolve_manifest_url(manifest.get("url"), module_path, app_dir.name)

    return AppInfo(
        module_path=module_path,
        module_name=_module_name_from_path(module_path),
        app_name=app_dir.name,
        app_id=f"{module_path}:{app_dir.name}",
        category=manifest.get("category", "unknown"),
        name=manifest.get("name") or _fallback_name(app_dir.name),
        description=manifest.get("description") or "",
        url=url,
        avatar_url=_resolve_avatar_url(manifest.get("avatar_url")),
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


def _iter_loaded_modules() -> Iterator[Any]:
    """Yield every module the engine has loaded, starting with the root ABIModule.

    Same discovery shape as ``agents__primary_adapter__FastAPI``: the root
    ``ABIModule`` first, then each engine-loaded module (deduped against
    the root in case it also appears in the engine's module map).
    """
    from naas_abi import ABIModule

    abi_module = ABIModule.get_instance()
    yield abi_module
    for module in abi_module.engine.modules.values():
        if module is abi_module:
            continue
        yield module


def _scan_module_apps(module: Any) -> list[AppInfo]:
    """Discover apps under ``<module_root_path>/apps/<app_name>/manifest.json``."""
    module_root = getattr(module, "module_root_path", None)
    if not module_root:
        return []
    apps_dir = Path(module_root) / "apps"
    if not apps_dir.is_dir():
        return []

    module_path = module.__class__.__module__

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
        catalog.append(_build_app_info(module_path, app_dir, manifest))
    return catalog


@lru_cache(maxsize=1)
def _scan_apps_catalog() -> tuple[AppInfo, ...]:
    """Discover apps from every loaded module's ``apps/`` directory.

    Everything we discover lives inside an already-loaded module, so all
    results are flagged ``installed=True``. Results are process-cached;
    restart the API to pick up new manifests.
    """
    catalog: list[AppInfo] = []
    for module in _iter_loaded_modules():
        for info in _scan_module_apps(module):
            catalog.append(info.model_copy(update={"installed": True}))
    _log.info("Apps catalog built: %d apps", len(catalog))
    return tuple(catalog)


_APP_ASSET_SUFFIXES = {
    ".css",
    ".gif",
    ".html",
    ".ico",
    ".jpeg",
    ".jpg",
    ".js",
    ".mjs",
    ".png",
    ".svg",
    ".webp",
    ".woff",
    ".woff2",
}


@lru_cache(maxsize=1)
def _scan_apps_html_paths() -> dict[str, str]:
    """Build a URL map for safe browser assets under app directories.

    HTML entry points commonly import colocated scripts, styles, fonts, and
    images. Serve those assets from the same authenticated ``/app-html/``
    namespace while excluding source, configuration, and dataset files.
    """
    html_map: dict[str, str] = {}
    for module in _iter_loaded_modules():
        module_root = getattr(module, "module_root_path", None)
        if not module_root:
            continue
        module_path = module.__class__.__module__
        module_path_url = module_path.replace(".", "/")
        apps_dir = Path(module_root) / "apps"
        if not apps_dir.is_dir():
            continue
        for app_dir in apps_dir.iterdir():
            if not app_dir.is_dir() or app_dir.name.startswith("_"):
                continue
            manifest_path = app_dir / "manifest.json"
            if not manifest_path.is_file():
                continue
            for asset_file in app_dir.rglob("*"):
                if (
                    not asset_file.is_file()
                    or asset_file.suffix.lower() not in _APP_ASSET_SUFFIXES
                ):
                    continue
                rel = asset_file.relative_to(app_dir).as_posix()
                url_key = f"{module_path_url}/{app_dir.name}/{rel}"
                html_map[url_key] = str(asset_file.resolve())
    _log.info("Apps browser asset map built: %d entries", len(html_map))
    return html_map


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


class AppHtmlAccessTokenRequest(BaseModel):
    """Mint a short-lived JWT for ``/app-html/`` (Bearer or ``?token=``)."""

    expires_minutes: int | None = Field(
        default=None,
        ge=1,
        le=24 * 60,
        description="Lifetime; defaults to app_html_access_token_expire_minutes",
    )
    path_prefix: str | None = Field(
        default=None,
        description="Optional path lock, e.g. /app-html/axi/devops/",
    )


class AppHtmlAccessTokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    path_prefix: str | None = None


@router.post("/access-token", response_model=AppHtmlAccessTokenResponse)
async def create_app_html_access_token(
    body: AppHtmlAccessTokenRequest,
    current_user: User = Depends(get_current_user_required),
) -> AppHtmlAccessTokenResponse:
    """Issue a time-limited JWT accepted by ``/app-html/`` (alongside ABI_API_KEY)."""
    try:
        token, expires_in = mint_app_html_access_token(
            user_id=current_user.id,
            expires_minutes=body.expires_minutes,
            path_prefix=body.path_prefix,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return AppHtmlAccessTokenResponse(
        access_token=token,
        expires_in=expires_in,
        path_prefix=body.path_prefix,
    )


@router.get("/", response_model=AppsResponse)
async def list_apps(
    request: Request,
    workspace_id: str | None = None,
    current_user: User = Depends(get_current_user_required),
    apps_service: AppsService = Depends(get_apps_service),
) -> AppsResponse:
    """Return every app discovered from loaded-module manifests.

    When ``workspace_id`` is provided, results carry the workspace's enable
    state. Apps without a stored record default to ``enabled=False``.
    """
    if workspace_id:
        await require_workspace_access(current_user.id, workspace_id)

    try:
        from naas_abi import ABIModule

        loaded_modules = ABIModule.get_instance().engine.modules
    except Exception:
        loaded_modules = {}

    catalog = _scan_apps_catalog()
    workspace_slug: str | None = None
    if workspace_id:
        workspace_slug = await _workspace_slug(workspace_id)

    enabled_by_app_id: dict[str, bool] = (
        await apps_service.get_enabled_states(workspace_id) if workspace_id else {}
    )
    seed_apps: set[str] = set()
    if workspace_id:
        seed = workspace_seed_for_slug(workspace_slug)
        if seed is not None and seed.apps:
            seed_apps = {
                str(app_id).strip() for app_id in seed.apps if str(app_id).strip()
            }

    results: list[AppInfo] = []
    for app in catalog:
        update: dict = {
            "enabled": resolve_app_enabled(app.app_id, enabled_by_app_id, seed_apps)
        }

        # Manifest values take precedence; only fall back to runtime config
        # when the manifest omits the credential.
        loaded_module = loaded_modules.get(app.module_path)
        if loaded_module is not None:
            cfg = getattr(loaded_module, "configuration", None)
            if not app.demo_login:
                update["demo_login"] = getattr(cfg, "demo_login", None) or None
            if not app.demo_password:
                update["demo_password"] = getattr(cfg, "demo_password", None) or None

        # Bundled HTML apps are proxied by the Nexus web app (/app-html/ rewrite)
        # so iframes load same-origin. Keep API-relative paths here.
        if app.url and app.url.startswith("/app-html/"):
            update["url"] = app.url

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
        # No existing row: create one. Missing fields fall back to defaults
        # (enabled=False), then we apply the requested update on top.
        enabled = False if updates.enabled is None else updates.enabled
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
    """Delete the app config (reverts to the default ``enabled=False``)."""
    await require_workspace_access(current_user.id, workspace_id)
    _ensure_app_exists(app_id)
    deleted = await apps_service.delete_app_config(workspace_id, app_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="App config not found")
    return {"status": "deleted"}
