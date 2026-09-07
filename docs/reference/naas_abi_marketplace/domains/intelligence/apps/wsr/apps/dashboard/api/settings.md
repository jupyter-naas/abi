# Settings

## What it is
- A Pydantic `BaseSettings` configuration module for the dashboard API.
- Loads configuration from environment variables and an optional `.env` file.
- Exposes a singleton `settings` instance for use across the app.

## Public API
- `class Settings(BaseSettings)`
  - Holds configuration fields for external APIs and CORS.
- `settings: Settings`
  - Module-level instantiated settings object.

### Settings fields
- `opensky_client_id: str` — OAuth2 client ID for newer OpenSky accounts.
- `opensky_client_secret: str` — OAuth2 client secret for newer OpenSky accounts.
- `opensky_username: str` — Legacy OpenSky username (basic auth).
- `opensky_password: str` — Legacy OpenSky password (basic auth).
- `openwebcamdb_api_key: str` — API key for OpenWebcamDB.
- `tfl_app_key: str` — Optional TfL app key (higher rate limits).
- `allowed_origins: list[str]` — Allowed CORS origins; defaults to `["*"]`.

## Configuration/Dependencies
- Depends on:
  - `pydantic_settings.BaseSettings`
  - `pydantic_settings.SettingsConfigDict`
- Settings model configuration:
  - Reads from `.env` (UTF-8): `env_file=".env"`, `env_file_encoding="utf-8"`
  - Ignores unknown environment variables: `extra="ignore"`

## Usage
```python
from naas_abi_marketplace.domains.intelligence.apps.wsr.apps.dashboard.api.settings import settings

print(settings.allowed_origins)
print(settings.opensky_client_id)
```

Example `.env`:
```dotenv
OPENSKY_CLIENT_ID=your_id
OPENSKY_CLIENT_SECRET=your_secret
ALLOWED_ORIGINS=["https://example.com"]
```

## Caveats
- All fields default to empty strings (or `["*"]` for `allowed_origins`); missing env values will not raise validation errors.
- Unknown environment variables are ignored due to `extra="ignore"`.
