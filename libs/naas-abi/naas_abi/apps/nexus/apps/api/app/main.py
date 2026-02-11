"""
NEXUS API - Main Application Entry Point
"""

from contextlib import asynccontextmanager
from typing import AsyncGenerator
from pathlib import Path

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware

from app.api.router import api_router
from app.core.config import settings, validate_settings_on_startup
from app.core.logging import configure_logging
from app.core.database import init_db, table_exists
from app.services.ollama import ensure_ollama_ready, get_ollama_status
from app.services.websocket import init_websocket


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan handler."""
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
    
    # Auto-start Ollama and pull default model (Qwen3-VL:2b for vision demos)
    print("Checking Ollama status...")
    # Gate autostart behind config flag to avoid process management in prod
    required_model = "qwen3-vl:2b"
    if settings.enable_ollama_autostart:
        ollama_result = await ensure_ollama_ready(required_model=required_model)
    else:
        # Do not attempt to start; only report current status
        from app.services.ollama import get_installed_models, is_ollama_running
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
        print(f"Ollama: installed but not running - {ollama_result.get('error', 'not started')} (autostart={'on' if settings.enable_ollama_autostart else 'off'})")
    else:
        print("Ollama: not installed - install from https://ollama.ai for local AI")
    
    yield
    # Shutdown


app = FastAPI(
    title="NEXUS API",
    description="The coordination platform API by naas.ai, powered by ABI",
    version="0.0.1",
    docs_url="/docs" if settings.debug or settings.environment == "development" else None,
    redoc_url="/redoc" if settings.debug or settings.environment == "development" else None,
    lifespan=lifespan,
)

# CORS - allow frontend origin; local dev always includes localhost:3000
cors_origins = settings.cors_origins_list
import logging
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
                response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
            
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


app.add_middleware(SecurityHeadersMiddleware)

# Include API router
app.include_router(api_router, prefix="/api")


@app.get("/health")
async def health_check() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "healthy", "service": "nexus-api"}


@app.get("/api/ollama/status")
async def ollama_status():
    """Get current Ollama status - models, running state, etc."""
    return await get_ollama_status()


@app.post("/api/ollama/pull")
async def ollama_pull_model(model: str = "qwen3-vl:2b"):
    """Trigger a model pull. Returns immediately, pull runs in background."""
    import asyncio
    from app.services.ollama import pull_model, is_ollama_running
    
    if not await is_ollama_running():
        return {"success": False, "error": "Ollama is not running"}
    
    # Start pull in background
    asyncio.create_task(pull_model(model))
    return {"success": True, "message": f"Pulling {model} in background..."}


@app.post("/api/ollama/ensure-ready")
async def ollama_ensure_ready(model: str = "qwen3-vl:2b"):
    """Ensure Ollama is running and the requested model is available.

    Returns a lightweight status with a `ready` flag consumed by the frontend
    to decide whether to retry the pending chat request automatically.
    """
    result = await ensure_ollama_ready(required_model=model)
    ready = bool(result.get("ollama_running") and (result.get("model_available") or result.get("model_pulled")))
    return {"ready": ready, "status": result}


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
    app.mount("/organizations", StaticFiles(directory=str(org_logos_path)), name="organizations")

# Serve uploaded workspace logos
uploads_path = Path(__file__).parent.parent / "uploads"
uploads_path.mkdir(parents=True, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=str(uploads_path)), name="uploads")


# Wrap app with WebSocket support (must be LAST, after all middleware)
app = init_websocket(app)
