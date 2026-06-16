"""
NEXUS API - Main Application Entry Point
"""

import asyncio
import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path

import uvicorn
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from naas_abi.apps.nexus.apps.api.app.api.router import api_router
from naas_abi.apps.nexus.apps.api.app.core.config import settings, validate_settings_on_startup
from naas_abi.apps.nexus.apps.api.app.core.database import init_db
from naas_abi.apps.nexus.apps.api.app.core.logging import configure_logging
from naas_abi.apps.nexus.apps.api.app.services.chat.chat_ingestion_worker import (
    start_chat_ingestion_consumer,
)
from naas_abi.apps.nexus.apps.api.app.services.exceptions import (
    register_service_exception_handlers,
)
from naas_abi.apps.nexus.apps.api.app.services.ollama import ensure_ollama_ready, get_ollama_status
from naas_abi.apps.nexus.apps.api.app.services.websocket import init_websocket
from starlette.middleware.base import BaseHTTPMiddleware


async def _prefetch_modules_catalog() -> None:
    """Warm up the marketplace module catalog in a thread-pool worker.

    The catalog scans naas_abi_marketplace via filesystem I/O which is
    synchronous.  Running it via run_in_executor keeps the event loop free.
    """
    _log = logging.getLogger(__name__)
    try:
        from naas_abi.apps.nexus.apps.api.app.services.modules.service import (
            _build_catalog,
        )

        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, _build_catalog)
        _log.info("✓ Marketplace catalog pre-populated at startup")
    except Exception:
        _log.exception("Background modules catalog pre-fetch failed (non-fatal)")


async def _sync_model_catalog() -> None:
    """Reconcile the on-disk AI model catalog into the Postgres store.

    Picks up new models and source-side property changes (e.g. a new
    description) on every boot. Properties a user edited in the frontend are
    preserved and a warning is logged when the source diverges from them.
    """
    _log = logging.getLogger(__name__)
    try:
        from naas_abi.apps.nexus.apps.api.app.core.database import AsyncSessionLocal
        from naas_abi.apps.nexus.apps.api.app.services.providers.adapters.secondary.providers__secondary_adapter__postgres import (  # noqa: E501
            ModelCatalogSecondaryAdapterPostgres,
        )
        from naas_abi.apps.nexus.apps.api.app.services.providers.service import (
            ProviderService,
        )

        async with AsyncSessionLocal() as session:
            service = ProviderService(store=ModelCatalogSecondaryAdapterPostgres(session))
            warnings = await service.sync_models()
        _log.info(
            "✓ Model catalog synced at startup (%d override divergence warning(s))",
            len(warnings),
        )
    except Exception:
        _log.exception("Background model catalog sync failed (non-fatal)")


async def _prefetch_agent_class_registry() -> None:
    """Warm up the agent class registry in a thread-pool worker.

    The registry build triggers dynamic imports of all ~160 agent modules, which
    is synchronous and CPU/IO-bound.  Running it via run_in_executor keeps the
    event loop free during startup while ensuring the cache is hot before the
    first GET /agents/ request arrives.
    """
    _log = logging.getLogger(__name__)
    try:
        from naas_abi.apps.nexus.apps.api.app.services.agents.adapters.primary.agents__primary_adapter__FastAPI import (
            _get_agent_class_registry,
        )

        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, _get_agent_class_registry)
        _log.info("✓ Agent class registry pre-populated at startup")
    except Exception:
        _log.exception("Background agent registry pre-fetch failed (non-fatal)")


async def _startup(app: FastAPI) -> None:
    """Application startup handler."""
    configure_logging()

    from naas_abi.apps.nexus.apps.api.app.services.registry_bootstrap import (
        initialize_nexus_service_registry,
    )

    initialize_nexus_service_registry()

    # Validate critical security settings
    validate_settings_on_startup()

    # Initialize database (run migrations) with retry logic
    try:
        await init_db()
        print("✓ Database ready")
    except ConnectionError as e:
        print(f"✗ Database initialization failed: {e}")
        print("  API will not start without database connection.")
        raise

    # Apply config-driven user/org/workspace seeds from config.yaml.
    from naas_abi.apps.nexus.apps.api.app.core.org_seed import apply_configuration_seeds

    await apply_configuration_seeds(getattr(app.state, "secret_service", None))

    try:
        start_chat_ingestion_consumer(app)
    except Exception:
        logging.getLogger(__name__).exception("Unable to start chat ingestion consumer")

    # Relay platform LogProcess events to the Socket.IO admin_events room
    # for the superadmin live event stream UI.
    try:
        from naas_abi.apps.nexus.apps.api.app.services.websocket.admin_events import (
            start_admin_event_relay,
        )

        start_admin_event_relay()
    except Exception:
        logging.getLogger(__name__).exception("Unable to start admin event relay")

    # Pre-populate the agent class registry in the background so the first
    # GET /agents/ request returns instantly from cache instead of waiting
    # for all agent modules to be imported.  create_task returns immediately.
    asyncio.create_task(_prefetch_agent_class_registry())

    # Pre-populate the marketplace catalog so first GET /modules/ is instant.
    asyncio.create_task(_prefetch_modules_catalog())

    # Reconcile the AI model catalog into Postgres (new models + source changes),
    # preserving any frontend property overrides.
    asyncio.create_task(_sync_model_catalog())

    # # Auto-start Ollama and pull default model (Qwen3-VL:2b for vision demos)
    # print("Checking Ollama status...")
    # # Gate autostart behind config flag to avoid process management in prod
    # required_model = "qwen3-vl:2b"
    # if settings.enable_ollama_autostart:
    #     ollama_result = await ensure_ollama_ready(required_model=required_model)
    # else:
    #     # Do not attempt to start; only report current status
    #     from naas_abi.apps.nexus.apps.api.app.services.ollama import (
    #         get_installed_models,
    #         is_ollama_running,
    #     )
    #     running = await is_ollama_running()
    #     models = await get_installed_models() if running else []
    #     ollama_result = {
    #         "ollama_installed": running or bool(models),
    #         "ollama_running": running,
    #         "ollama_started_by_nexus": False,
    #         "model_available": any(required_model in m for m in models),
    #         "model_pulled": False,
    #         "models": models,
    #         "error": None,
    #     }
    # app.state.ollama_status = ollama_result
    # if ollama_result["ollama_running"]:
    #     started_msg = " (started by NEXUS)" if ollama_result.get("ollama_started_by_nexus") else ""
    #     print(f"Ollama: running{started_msg} - models: {ollama_result['models']}")
    # elif ollama_result["ollama_installed"]:
    #     print(
    #         "Ollama: installed but not running - "
    #         f"{ollama_result.get('error', 'not started')} "
    #         f"(autostart={'on' if settings.enable_ollama_autostart else 'off'})"
    #     )
    # else:
    #     print("Ollama: not installed - install from https://ollama.ai for local AI")


async def _shutdown(app: FastAPI) -> None:
    """Application shutdown handler."""


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan handler."""
    await _startup(app)
    yield
    await _shutdown(app)


# Security Headers Middleware
class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add security headers to all responses."""

    async def dispatch(self, request: Request, call_next):
        # Skip security headers for WebSocket upgrade requests
        if request.url.path.startswith("/ws/") or request.headers.get("upgrade") == "websocket":
            return await call_next(request)

        response: Response = await call_next(request)

        if settings.enable_security_headers:
            # Prevent MIME type sniffing
            response.headers["X-Content-Type-Options"] = "nosniff"

            # Prevent clickjacking — allow /app-html/ assets to be embedded in iframes
            if request.url.path.startswith("/app-html/"):
                ancestors = ["'self'"]
                frontend = str(getattr(settings, "frontend_url", "") or "").rstrip("/")
                if frontend:
                    ancestors.append(frontend)
                for origin in getattr(request.app.state, "abi_cors_origins", ()):
                    origin = str(origin).rstrip("/")
                    if origin and origin not in ancestors:
                        ancestors.append(origin)
                # Allow the embedding page even when it is not listed in config
                # (e.g. http://localhost:3042 during local dev).
                for header in (request.headers.get("origin"), request.headers.get("referer")):
                    if not header:
                        continue
                    try:
                        from urllib.parse import urlparse

                        ref_origin = f"{urlparse(header).scheme}://{urlparse(header).netloc}".rstrip("/")
                        if ref_origin and ref_origin not in ancestors:
                            ancestors.append(ref_origin)
                    except Exception:
                        pass
                response.headers["Content-Security-Policy"] = (
                    f"frame-ancestors {' '.join(ancestors)};"
                )
            else:
                response.headers["X-Frame-Options"] = "DENY"

            # Referrer policy
            response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

            # Permissions policy (restrict features)
            response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"

            # HSTS (only in production)
            if settings.environment == "production":
                response.headers["Strict-Transport-Security"] = (
                    "max-age=31536000; includeSubDomains"
                )

            # CSP (if configured) — skip bundled app HTML; embed CSP set above.
            if not request.url.path.startswith("/app-html/"):
                if settings.content_security_policy:
                    response.headers["Content-Security-Policy"] = settings.content_security_policy
                elif settings.environment == "production":
                    # Strict default CSP for production (no 'unsafe-*').
                    # Generate a per-response nonce in case any HTML is ever served via this app.
                    import secrets

                    nonce = secrets.token_urlsafe(16)
                    csp = (
                        "default-src 'self'; "
                        "base-uri 'self'; "
                        "frame-ancestors 'none'; "
                        "object-src 'none'; "
                        f"script-src 'self' 'nonce-{nonce}'; "
                        "style-src 'self'; "
                        "img-src 'self' data: https:; "
                        "font-src 'self' data:; "
                        "connect-src 'self' https:; "
                        "upgrade-insecure-requests"
                    )
                    response.headers["Content-Security-Policy"] = csp
                    # Expose nonce for any upstream that may render templates (informational only)
                    response.headers["X-CSP-Nonce"] = nonce

        return response


async def health_check() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "healthy", "service": "nexus-api"}


async def ollama_status():
    """Get current Ollama status - models, running state, etc."""
    return await get_ollama_status()


async def ollama_pull_model(model: str = "qwen3-vl:2b"):
    """Trigger a model pull. Returns immediately, pull runs in background."""
    import asyncio

    from naas_abi.apps.nexus.apps.api.app.services.ollama import is_ollama_running, pull_model

    if not await is_ollama_running():
        return {"success": False, "error": "Ollama is not running"}

    # Start pull in background
    asyncio.create_task(pull_model(model))
    return {"success": True, "message": f"Pulling {model} in background..."}


async def ollama_ensure_ready(model: str = "qwen3-vl:2b"):
    """Ensure Ollama is running and the requested model is available.

    Returns a lightweight status with a `ready` flag consumed by the frontend
    to decide whether to retry the pending chat request automatically.
    """
    result = await ensure_ollama_ready(required_model=model)
    ready = bool(
        result.get("ollama_running")
        and (result.get("model_available") or result.get("model_pulled"))
    )
    return {"ready": ready, "status": result}


def _register_startup_handlers(app: FastAPI) -> None:
    async def on_startup() -> None:
        await _startup(app)

    async def on_shutdown() -> None:
        await _shutdown(app)

    app.add_event_handler("startup", on_startup)
    app.add_event_handler("shutdown", on_shutdown)


def _configure_middleware(app: FastAPI) -> None:
    cors_origins = list(getattr(app.state, "abi_cors_origins", [settings.frontend_url]))
    logger = logging.getLogger(__name__)
    cors_kwargs = {
        "allow_origins": cors_origins,
        "allow_credentials": True,
        "allow_methods": ["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        "allow_headers": ["Authorization", "Content-Type", "Accept", "X-Requested-With"],
        "expose_headers": ["Content-Length", "Content-Range"],
    }
    # In local development the web dev server can bind any free port (the allocator bumps
    # to the next port when one is still in TIME_WAIT after a restart), so accept any
    # localhost origin to avoid CORS breakage on every restart. Never enabled outside local/dev.
    if settings.nexus_env == "local" or settings.environment == "development":
        cors_kwargs["allow_origin_regex"] = r"https?://(localhost|127\.0\.0\.1)(:\d+)?"
    logger.info(f"[CORS] Configured origins: {cors_origins} (regex: {cors_kwargs.get('allow_origin_regex')})")
    app.add_middleware(CORSMiddleware, **cors_kwargs)
    app.add_middleware(SecurityHeadersMiddleware)

    # Per-actor HTTP activity log. Reads ActivityLogService from
    # app.state.activity_log_service (wired by the engine); if absent,
    # the middleware is a no-op.
    from naas_abi.apps.nexus.apps.api.app.services.activity_log.HttpActivityLogMiddleware import (
        HttpActivityLogMiddleware,
    )

    app.add_middleware(HttpActivityLogMiddleware)


async def serve_app_html(path: str) -> FileResponse:
    """Serve an HTML asset from any loaded module's apps directory.

    Resolution uses the pre-built html-path map from the apps catalog scan
    so no module lookup is needed at request time.
    """
    from naas_abi.apps.nexus.apps.api.app.services.apps.adapters.primary.apps__primary_adapter__FastAPI import (
        _scan_apps_html_paths,
    )

    html_map = _scan_apps_html_paths()
    file_path = html_map.get(path)
    if not file_path:
        raise HTTPException(status_code=404, detail=f"App HTML not found: {path}")

    if not Path(file_path).is_file():
        raise HTTPException(status_code=404, detail="File not found on disk")

    return FileResponse(file_path)


async def serve_provider_logo(provider_id: str) -> FileResponse:
    """Serve a marketplace AI provider's logo from disk.

    Public (no auth) so plain ``<img>`` tags can load it, and
    config-independent so logos render for providers that aren't enabled —
    matching the provider catalog, which lists every module regardless of state.
    """
    from naas_abi.apps.nexus.apps.api.app.services.providers.model_catalog import (
        resolve_provider_logo_for_id,
    )

    file_path = resolve_provider_logo_for_id(provider_id)
    if file_path is None:
        raise HTTPException(
            status_code=404, detail=f"No logo for provider {provider_id!r}"
        )
    return FileResponse(file_path)


def _register_routes(app: FastAPI) -> None:
    # Include API router
    app.include_router(api_router, prefix="/api")

    app.add_api_route("/health", health_check, methods=["GET"])
    app.add_api_route("/api/ollama/status", ollama_status, methods=["GET"])
    app.add_api_route("/api/ollama/pull", ollama_pull_model, methods=["POST"])
    app.add_api_route("/api/ollama/ensure-ready", ollama_ensure_ready, methods=["POST"])
    app.add_api_route("/app-html/{path:path}", serve_app_html, methods=["GET"])
    app.add_api_route("/provider-logos/{provider_id}", serve_provider_logo, methods=["GET"])


def _mount_static_assets(app: FastAPI) -> None:
    # Serve static assets (logos, avatars)
    logos_path = Path(__file__).parent.parent / "public" / "logos"
    if logos_path.exists():
        app.mount("/logos", StaticFiles(directory=str(logos_path)), name="logos")

    avatars_path = Path(__file__).parent.parent / "public" / "avatars"
    if avatars_path.exists():
        app.mount("/avatars", StaticFiles(directory=str(avatars_path)), name="avatars")

    # Serve organization logos
    org_logos_path = Path(__file__).parent.parent / "public" / "organizations"
    if org_logos_path.exists():
        app.mount(
            "/organizations", StaticFiles(directory=str(org_logos_path)), name="organizations"
        )

    # Serve uploaded workspace logos
    uploads_path = Path(__file__).parent.parent / "uploads"
    uploads_path.mkdir(parents=True, exist_ok=True)
    app.mount("/uploads", StaticFiles(directory=str(uploads_path)), name="uploads")



def create_app(app: FastAPI | None = None):
    """Create or patch a FastAPI app with NEXUS configuration."""
    if app is None:
        app = FastAPI(
            title="NEXUS API",
            description="The coordination platform API by naas.ai, powered by ABI",
            version="0.0.1",
            docs_url="/docs" if settings.debug or settings.environment == "development" else None,
            redoc_url="/redoc" if settings.debug or settings.environment == "development" else None,
            lifespan=lifespan,
        )
        attach_startup_handlers = False
    else:
        attach_startup_handlers = True

    existing_asgi = getattr(app.state, "_nexus_asgi_app", None)
    if existing_asgi is not None:
        return existing_asgi

    if not getattr(app.state, "_nexus_api_patched", False):
        if attach_startup_handlers:
            _register_startup_handlers(app)
        register_service_exception_handlers(app)
        _configure_middleware(app)
        _register_routes(app)
        _mount_static_assets(app)
        app.state._nexus_api_patched = True

    # Wrap app with WebSocket support (must be LAST, after all middleware)
    asgi_app = init_websocket(app)
    app.state._nexus_asgi_app = asgi_app
    return asgi_app


app = create_app()


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=9879, reload_dirs=["src", "libs"], reload=True)  # nosec B104 - dev entrypoint only (__main__), not reachable in production
