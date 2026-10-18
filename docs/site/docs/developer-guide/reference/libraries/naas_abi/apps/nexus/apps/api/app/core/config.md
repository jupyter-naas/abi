# Settings

## What it is
- Centralized configuration for the Nexus API using **pydantic-settings** (Pydantic v2).
- Loads defaults and optionally overrides via environment variables and a `.env` file.
- Provides structured configs for:
  - Tenant branding (UI metadata)
  - Feature flags
  - Marketplace pricing metadata
  - Seed template sources (Slides/Documents/Sheets)
  - Startup seed data (users/organizations/workspaces)
- Includes startup validation to prevent running with an insecure `SECRET_KEY` outside development.

## Public API

### Models / Config objects
- `TenantConfig`
  - Tenant branding values exposed to the browser (titles, colors, logos, login page styling).
  - `apps: list[ExternalAppConfig]` external app shortcuts.
- `ExternalAppConfig`
  - External app shortcut entry (`name`, `url`, optional `description`, `icon_emoji`).

- `SlidesTemplateSourceConfig`
  - Declares an additional directory of Slides seed templates.
  - Validates `namespace` format and rejects reserved namespace `abi`.
- `DocumentsTemplateSourceConfig`
  - Declares an additional directory of Documents seed templates.
  - Validates `namespace` format and rejects reserved namespace `abi`.
- `SheetsTemplateSourceConfig`
  - Declares an additional directory of Sheets seed templates.
  - Validates `namespace` format and rejects reserved namespace `abi`.

- `ModelPricingEntry`
  - Token pricing metadata for a model (`input_per_million`, `output_per_million`, `label`).
- `MarketplaceUsageTier`
  - Usage scenario for cost estimation (`label`, `interactions`, `avg_tokens`, `description`).
- `MarketplacePricingConfig`
  - Marketplace maintenance fee settings and pricing UI metadata.
- `MarketplaceConfig`
  - Full marketplace configuration surfaced to the frontend; includes defaults for usage tiers and model pricing.

- `FeatureFlagsConfig`
  - Feature access policy exposed to the frontend:
    - `enabled_features`
    - `role_baseline` (role → allowed features)
    - `workspace_overrides` (workspace → per-feature enable/disable)
    - `organization_overrides` (org id → role overlays)

- `UserSeedConfig`
  - Startup user seed entry (upsert by `email`).
- `OrganizationMemberSeedConfig`
  - Startup organization membership seed (`role`: `owner|admin|member`).
- `WorkspaceMemberSeedConfig`
  - Startup workspace membership seed (`role`: `owner|admin|member|viewer`).
- `WorkspaceSeedConfig`
  - Startup workspace seed (upsert by `slug`), includes branding and initial `graphs` policy (`WorkspaceGraphPolicyConfig`).
- `OrganizationSeedConfig`
  - Startup organization seed (upsert by `slug`), includes members, workspaces, and branding overrides.

- `Settings` (`BaseSettings`)
  - Main settings container. Key groups:
    - Branding/Policy: `tenant`, `feature_flags`, `marketplace`
    - Template sources: `slides_template_sources`, `documents_template_sources`, `documents_default_template_id`, `documents_hidden_template_ids`, `sheets_template_sources`
    - Seeds: `users`, `organizations`
    - App/API: `app_name`, `debug`, `environment`, `nexus_env`, `api_prefix`, `api_url`, `frontend_url`, `websocket_path`
    - Graph caching: `graph_query_cache_ttl_seconds`
    - Coding workspaces: `coding_*`
    - Auth/security: `secret_key`, magic-link/OTP settings, token lifetimes, optional Pages SSO, app submission settings
    - Email metadata: `email_from_address`, `email_from_name`
    - Rate limiting: `rate_limit_*`
    - Security headers: `enable_security_headers`, `content_security_policy`
    - Integrations: `abi_api_url`, `abi_api_key`, `openai_api_key`, `anthropic_api_key`, `cloudflare_*`
    - Local AI: `enable_ollama_autostart`
  - Post-init hook:
    - Forces `enable_ollama_autostart = False` unless `environment == "development"` or `nexus_env == "local"`.

### Functions / globals
- `get_settings() -> Settings`
  - Returns a cached singleton `Settings()` (`@lru_cache`).
- `settings: Settings`
  - Module-level singleton instance (`settings = get_settings()`).
- `current_secret_key() -> str`
  - Returns `settings.secret_key` at call time (to avoid stale imported `settings` references).
- `validate_settings_on_startup() -> None`
  - If `settings.secret_key` is known-insecure:
    - Non-development: prints a fatal message and terminates the process via `sys.exit(1)`.
    - Development: prints a warning.

## Configuration/Dependencies
- Dependencies:
  - `pydantic` (v2) and `pydantic-settings`
  - `naas_abi.apps.nexus.apps.api.app.core.secret_key.INSECURE_SECRET_KEYS`
  - `naas_abi.apps.nexus.graph_policy_config.WorkspaceGraphPolicyConfig`
- Settings loading behavior (`Settings.model_config`):
  - Reads `.env` by default (`env_file=".env"`, UTF-8).
  - Environment variable names are case-insensitive (`case_sensitive=False`).
  - Unknown environment variables are ignored (`extra="ignore"`).
- Many nested models reject unknown fields (`extra="forbid"`).
- Reserved template namespace:
  - `"abi"` is reserved for ABI-shipped seeds; configuration sources cannot use it for `namespace`.

## Usage
```python
from naas_abi.apps.nexus.apps.api.app.core.config import (
    get_settings,
    validate_settings_on_startup,
    current_secret_key,
)

validate_settings_on_startup()

s = get_settings()
print(s.api_url)
print(current_secret_key())
print(s.tenant.tab_title)
```

## Caveats
- `validate_settings_on_startup()` can **terminate the process** (`sys.exit(1)`) when `SECRET_KEY` is insecure and `environment != "development"`.
- `Settings.model_post_init` may override configuration:
  - `enable_ollama_autostart` is forced `False` unless in development or `nexus_env == "local"`.
- Template source `namespace` must match the configured regex and cannot be `"abi"`.
