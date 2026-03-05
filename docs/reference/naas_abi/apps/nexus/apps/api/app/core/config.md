# Settings

## What it is
- Pydantic-based application configuration for the Nexus API.
- Loads settings from environment variables (and an optional `.env` file) and exposes:
  - Tenant/branding configuration
  - Seed data definitions (users/organizations/workspaces)
  - API/CORS settings
  - Database/Redis/auth/rate-limiting/security header settings
- Includes a startup validator to refuse running with an insecure `SECRET_KEY` outside development.

## Public API
- `class TenantConfig(BaseModel)`
  - Tenant branding surfaced to the browser (title, favicon, colors, login page styling).
- `class UserSeedConfig(BaseModel)`
  - User definition applied on startup (upsert by email).
- `class OrganizationMemberSeedConfig(BaseModel)`
  - Organization membership assignment (`role`: `owner|admin|member`).
- `class WorkspaceMemberSeedConfig(BaseModel)`
  - Workspace membership assignment (`role`: `owner|admin|member|viewer`).
- `class WorkspaceSeedConfig(BaseModel)`
  - Workspace definition applied on startup (upsert by `slug`).
- `class OrganizationSeedConfig(BaseModel)`
  - Organization definition applied on startup (upsert by `slug`), includes workspaces.
- `class Settings(BaseSettings)`
  - Main settings container loaded from environment / `.env`.
  - `cors_origins_list -> list[str]` (property): resolves and merges CORS origins from:
    - `cors_origins_str` (comma-separated)
    - `cors_origins` (JSON array string)
    - plus localhost defaults when `environment == "development"` or `nexus_env == "local"`.
  - `model_post_init(...)`: post-load adjustments:
    - Disables rate limiting in development/local.
    - Forces `enable_ollama_autostart = False` and `auto_seed_demo_data = False` when not development/local.
- `get_settings() -> Settings`
  - Returns a cached `Settings` instance (`@lru_cache`).
- `settings: Settings`
  - Module-level singleton settings instance (`settings = get_settings()`).
- `validate_settings_on_startup() -> None`
  - Validates critical settings:
    - If `SECRET_KEY` is a known-insecure value and `environment != "development"`, prints a fatal message and exits the process (`sys.exit(1)`).
    - Warns (prints) when insecure `SECRET_KEY` is used in development.

## Configuration/Dependencies
- Dependencies:
  - `pydantic` (`BaseModel`, `Field`, `EmailStr`)
  - `pydantic_settings` (`BaseSettings`, `SettingsConfigDict`)
- `.env` loading:
  - `Settings.model_config` reads `.env` (UTF-8), case-insensitive keys, ignores unknown env vars.
- Notable environment variables (map to `Settings` fields):
  - App/API: `APP_NAME`, `DEBUG`, `ENVIRONMENT`, `NEXUS_ENV`, `API_PREFIX`, `API_URL`, `FRONTEND_URL`, `WEBSOCKET_PATH`
  - CORS: `CORS_ORIGINS_STR` (comma-separated), `CORS_ORIGINS` (JSON array string)
  - DB/Redis: `DATABASE_URL`, `REDIS_URL`
  - Auth: `SECRET_KEY`, `ACCESS_TOKEN_EXPIRE_MINUTES`, `REFRESH_TOKEN_EXPIRE_DAYS`
  - Rate limiting: `RATE_LIMIT_ENABLED`, `RATE_LIMIT_LOGIN_ATTEMPTS`, `RATE_LIMIT_WINDOW_SECONDS`
  - Seeding: `AUTO_SEED_DEMO_DATA`, plus structured `TENANT`, `USERS`, `ORGANIZATIONS` if provided via supported pydantic-settings mechanisms
  - AI/backends: `ABI_API_URL`, `ABI_API_KEY`, `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `CLOUDFLARE_API_TOKEN`, `CLOUDFLARE_ACCOUNT_ID`
  - Ollama: `ENABLE_OLLAMA_AUTOSTART`
  - Security headers: `ENABLE_SECURITY_HEADERS`, `CONTENT_SECURITY_POLICY`

## Usage
```python
from naas_abi.apps.nexus.apps.api.app.core.config import get_settings, validate_settings_on_startup

settings = get_settings()

# Optional: validate early during app startup/lifespan
validate_settings_on_startup()

print(settings.api_url)
print(settings.cors_origins_list)
```

## Caveats
- `validate_settings_on_startup()` will terminate the process (`sys.exit(1)`) in non-development environments if `secret_key` is empty or matches a known insecure default.
- In non-development/non-local environments, `model_post_init` forces:
  - `enable_ollama_autostart = False`
  - `auto_seed_demo_data = False`
- `cors_origins_list` always includes localhost origins in development/local, even if not provided in env.
