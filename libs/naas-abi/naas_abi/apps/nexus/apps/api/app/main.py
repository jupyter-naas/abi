"""
NEXUS API - Main Application Entry Point
"""

import logging
from collections.abc import AsyncGenerator, Awaitable, Callable
from contextlib import asynccontextmanager
from pathlib import Path
from typing import cast

import uvicorn
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from naas_abi.apps.nexus.apps.api.app.api.router import api_router
from naas_abi.apps.nexus.apps.api.app.core.config import settings, validate_settings_on_startup
from naas_abi.apps.nexus.apps.api.app.core.database import init_db
from naas_abi.apps.nexus.apps.api.app.core.logging import configure_logging
from naas_abi.apps.nexus.apps.api.app.services.ollama import ensure_ollama_ready, get_ollama_status
from naas_abi.apps.nexus.apps.api.app.services.websocket import init_websocket
from starlette.middleware.base import BaseHTTPMiddleware


async def _startup(app: FastAPI) -> None:
    """Application startup handler."""
    configure_logging()

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

    if bool(getattr(settings, "auto_seed_demo_data", True)):
        from naas_abi.apps.nexus.apps.api import seed as seed_module

        ensure_seed_fn = getattr(seed_module, "ensure_seed_data", None)
        if callable(ensure_seed_fn):
            await cast(Callable[[], Awaitable[bool]], ensure_seed_fn)()

    # Auto-start Ollama and pull default model (Qwen3-VL:2b for vision demos)
    print("Checking Ollama status...")
    # Gate autostart behind config flag to avoid process management in prod
    required_model = "qwen3-vl:2b"
    if settings.enable_ollama_autostart:
        ollama_result = await ensure_ollama_ready(required_model=required_model)
    else:
        # Do not attempt to start; only report current status
        from naas_abi.apps.nexus.apps.api.app.services.ollama import (
            get_installed_models,
            is_ollama_running,
        )

        running = await is_ollama_running()
        models = await get_installed_models() if running else []
        ollama_result = {
            "ollama_installed": running or bool(models),
            "ollama_running": running,
            "ollama_started_by_nexus": False,
            "model_available": any(required_model in m for m in models),
            "model_pulled": False,
            "models": models,
            "error": None,
        }
    app.state.ollama_status = ollama_result
    if ollama_result["ollama_running"]:
        started_msg = " (started by NEXUS)" if ollama_result.get("ollama_started_by_nexus") else ""
        print(f"Ollama: running{started_msg} - models: {ollama_result['models']}")
    elif ollama_result["ollama_installed"]:
        print(
            "Ollama: installed but not running - "
            f"{ollama_result.get('error', 'not started')} "
            f"(autostart={'on' if settings.enable_ollama_autostart else 'off'})"
        )
    else:
        print("Ollama: not installed - install from https://ollama.ai for local AI")


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

            # Prevent clickjacking
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

            # CSP (if configured)
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
    # CORS - allow frontend origin; local dev always includes localhost:3000
    cors_origins = settings.cors_origins_list
    logger = logging.getLogger(__name__)
    logger.info(f"[CORS] Configured origins: {cors_origins}")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "Accept", "X-Requested-With"],
        expose_headers=["Content-Length", "Content-Range"],
    )
    app.add_middleware(SecurityHeadersMiddleware)


def _register_routes(app: FastAPI) -> None:
    # Include API router
    app.include_router(api_router, prefix="/api")

    app.add_api_route("/health", health_check, methods=["GET"])
    app.add_api_route("/api/ollama/status", ollama_status, methods=["GET"])
    app.add_api_route("/api/ollama/pull", ollama_pull_model, methods=["POST"])
    app.add_api_route("/api/ollama/ensure-ready", ollama_ensure_ready, methods=["POST"])


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
        _configure_middleware(app)
        _register_routes(app)
        _mount_static_assets(app)
        app.state._nexus_api_patched = True

    # Wrap app with WebSocket support (must be LAST, after all middleware)
    asgi_app = init_websocket(app)
    app.state._nexus_asgi_app = asgi_app
    return asgi_app


if __name__ == "__main__":
    app = create_app()
    uvicorn.run(app, host="0.0.0.0", port=9879, reload_dirs=["src", "libs"], reload=True)
