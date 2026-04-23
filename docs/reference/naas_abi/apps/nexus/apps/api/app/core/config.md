# Settings (Nexus API configuration)

## What it is
- Centralized application configuration built with **pydantic-settings** (Pydantic v2).
- Loads defaults and optionally overrides via environment variables and a `.env` file.
- Provides structured sub-configs for tenant branding, feature flags, and startup seed data.
- Includes a startup validator that refuses to run in non-development environments with an insecure `SECRET_KEY`.

## Public API
### Models
- `TenantConfig`
  - Tenant branding values surfaced to the browser (title, colors, logos, login page styling).
  - `apps: list[ExternalAppConfig]` for external app shortcuts.
- `ExternalAppConfig`
  - Defines an external app shortcut displayed in the Apps page (`name`, `url`, optional description/icon).
- `FeatureFlagsConfig`
  - Feature access policy exposed to the frontend:
    - `enabled_features`
    - `role_baseline` (role → allowed features)
    - `workspace_overrides` (workspace → per-feature enable/disable)
- `UserSeedConfig`
  - User seed definition upserted on startup by email.
- `OrganizationMemberSeedConfig`
  - Seed for organization member assignment (role: `owner|admin|member`).
- `WorkspaceMemberSeedConfig`
  - Seed for workspace member assignment (role: `owner|admin|member|viewer`).
- `WorkspaceSeedConfig`
  - Workspace seed definition upserted on startup by slug, with optional branding.
- `OrganizationSeedConfig`
  - Organization seed definition upserted on startup by slug, with members/workspaces and branding options.
- `Settings` (`BaseSettings`)
  - Main settings container. Key fields:
    - App: `app_name`, `debug`, `environment`, `nexus_env`
    - API: `api_prefix`, `api_url`, `frontend_url`, `websocket_path`
    - Storage: `database_url` (PostgreSQL async), `redis_url`
    - Auth: `secret_key`, token/magic-link settings, SMTP settings
    - Rate limiting: `rate_limit_enabled`, thresholds
    - Seeding: `auto_seed_demo_data`
    - Security headers: `enable_security_headers`, `content_security_policy`
    - Integrations: `abi_api_url`, `abi_api_key`, `openai_api_key`, `anthropic_api_key`, Cloudflare Workers AI tokens
    - Local AI: `enable_ollama_autostart`
  - Post-init behavior (`model_post_init`):
    - Disables rate limiting when `environment == "development"` **or** `nexus_env == "local"`.
    - Forces `enable_ollama_autostart = False` and `auto_seed_demo_data = False` unless development/local.

### Functions / Globals
- `get_settings() -> Settings`
  - Returns a cached singleton `Settings()` instance (`@lru_cache`).
- `settings`
  - Module-level singleton: `settings = get_settings()`.
- `validate_settings_on_startup() -> None`
  - Validates `settings.secret_key` against known-insecure values.
  - In non-development environments: prints a fatal message and exits with code `1`.
  - In development: prints a warning.

## Configuration/Dependencies
- Depends on:
  - `pydantic` (v2) and `pydantic-settings`
- Settings loading behavior:
  - `.env` file is read by default (`env_file=".env"`, UTF-8).
  - Environment variable names are **case-insensitive** (`case_sensitive=False`).
  - Extra env vars are ignored (`extra="ignore"`).
- Several models use `extra="forbid"` to reject unknown fields in structured configs (tenant, seeds, feature flags).

## Usage
```python
from naas_abi.apps.nexus.apps.api.app.core.config import (
    get_settings,
    validate_settings_on_startup,
)

# Validate critical config (typically called during app startup/lifespan)
validate_settings_on_startup()

s = get_settings()
print(s.api_url)
print(s.database_url)
print(s.tenant.tab_title)
```

## Caveats
- `validate_settings_on_startup()` will **terminate the process** (`sys.exit(1)`) if `SECRET_KEY` is default/empty and `environment != "development"`.
- `model_post_init` mutates some fields after load:
  - Rate limiting is automatically disabled in development/local.
  - `enable_ollama_autostart` and `auto_seed_demo_data` are forced off outside development/local, even if set.
