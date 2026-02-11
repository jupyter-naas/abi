"""
Application configuration using pydantic-settings.
"""

import json
import sys
from functools import lru_cache
from typing import Any

from pydantic import PostgresDsn, validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Known-insecure secret keys that must be rejected
_INSECURE_SECRETS = frozenset({
    "",
    "change-me-in-production",
    "change-me-in-production-use-a-long-random-string",
    "secret",
    "password",
    "changeme",
})


class Settings(BaseSettings):
    """Application settings."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",  # Ignore extra environment variables
    )

    # App
    app_name: str = "NEXUS API"
    debug: bool = False
    environment: str = "development"
    nexus_env: str = "local"  # Environment name (local, cloudflare, staging)

    # API
    api_prefix: str = "/api"
    api_url: str = "http://localhost:8000"
    frontend_url: str = "http://localhost:3000"
    websocket_path: str = "/ws/socket.io"

    # CORS - accept comma-separated (CORS_ORIGINS_STR) or JSON array (CORS_ORIGINS)
    cors_origins_str: str = "http://localhost:3000,http://127.0.0.1:3000"
    cors_origins: str | None = None  # Optional JSON array e.g. '["http://localhost:3000"]'

    @property
    def cors_origins_list(self) -> list[str]:
        """Resolved CORS origins: from env, merged; local dev always includes localhost."""
        origins: set[str] = set()
        # From comma-separated string
        for o in self.cors_origins_str.split(","):
            o = o.strip()
            if o:
                origins.add(o)
        # From JSON array (CORS_ORIGINS in .env)
        if self.cors_origins:
            try:
                parsed = json.loads(self.cors_origins) if isinstance(self.cors_origins, str) else self.cors_origins
                if isinstance(parsed, list):
                    for o in parsed:
                        if isinstance(o, str) and o.strip():
                            origins.add(o.strip())
            except (json.JSONDecodeError, TypeError):
                pass
        # In development, always allow localhost so frontend never gets blocked
        if self.environment == "development" or self.nexus_env == "local":
            origins.add("http://localhost:3000")
            origins.add("http://127.0.0.1:3000")
            origins.add("http://localhost:3042")
            origins.add("http://127.0.0.1:3042")
        return list(origins)

    # Database
    database_url: str = "postgresql+asyncpg://nexus:nexus@localhost:5432/nexus"  # PostgreSQL only

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # Authentication
    secret_key: str = "change-me-in-production"
    access_token_expire_minutes: int = 30  # 30 minutes (short-lived)
    refresh_token_expire_days: int = 30  # 30 days (long-lived)
    
    # Rate Limiting
    rate_limit_enabled: bool = True
    rate_limit_login_attempts: int = 5  # Max login attempts per window
    rate_limit_window_seconds: int = 300  # 5-minute window
    
    # Demo data seeding (idempotent startup check)
    # When enabled, startup seeds demo data only if users table is empty.
    auto_seed_demo_data: bool = True
    
    def model_post_init(self, __context: Any) -> None:
        """Adjust settings based on environment after initialization (pydantic v2 hook)."""
        # Disable rate limiting in development to avoid blocking during hot reload
        if self.environment == "development" or self.nexus_env == "local":
            self.rate_limit_enabled = False
        # Make Ollama autostart opt-in and local-only
        # - Enable by setting ENABLE_OLLAMA_AUTOSTART=true
        # - Force OFF unless environment is development or nexus_env is local
        if not (self.environment == "development" or self.nexus_env == "local"):
            self.enable_ollama_autostart = False
            self.auto_seed_demo_data = False
    
    # Security Headers
    enable_security_headers: bool = True
    content_security_policy: str | None = None  # Set in production

    # ABI Engine
    abi_api_url: str = "http://localhost:8001"
    abi_api_key: str | None = None

    # OpenAI (for embeddings/fallback)
    openai_api_key: str | None = None

    # Anthropic (Claude)
    anthropic_api_key: str | None = None

    # Cloudflare Workers AI
    cloudflare_api_token: str | None = None
    cloudflare_account_id: str | None = None

    # Local AI (Ollama) autostart
    # Default OFF; enabled automatically in local development.
    enable_ollama_autostart: bool = False
    

@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


settings = get_settings()





def validate_settings_on_startup() -> None:
    """Validate critical settings before the app starts serving requests.
    
    Called during app lifespan startup. Refuses to start if SECRET_KEY
    is a known-insecure value in non-development environments.
    """
    if settings.secret_key in _INSECURE_SECRETS:
        if settings.environment != "development":
            print(
                "\n"
                "=" * 60 + "\n"
                "FATAL: SECRET_KEY is insecure.\n"
                "\n"
                "You are running in a non-development environment with a\n"
                "default or empty SECRET_KEY. This allows anyone to forge\n"
                "authentication tokens.\n"
                "\n"
                "Generate a secure key:\n"
                "  python -c \"import secrets; print(secrets.token_urlsafe(64))\"\n"
                "\n"
                "Set it in your .env file:\n"
                "  SECRET_KEY=<your-generated-key>\n"
                "=" * 60 + "\n"
            )
            sys.exit(1)
        else:
            print(
                "WARNING: Using insecure default SECRET_KEY. "
                "This is acceptable for local development only. "
                "Set SECRET_KEY in .env before deploying."
            )
