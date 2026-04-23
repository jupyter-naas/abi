# refresh_token (Refresh Token Service)

## What it is
- Async service functions for issuing, validating, and revoking **refresh tokens**, and blacklisting **access tokens**.
- Stores **hashed** refresh tokens (SHA-256) and updates usage metadata in the database.

## Public API
- `generate_refresh_token() -> str`
  - Generates a cryptographically secure refresh token (plaintext).
- `hash_token(token: str) -> str`
  - Returns SHA-256 hex digest for token storage/lookup.
- `async create_refresh_token(user_id: str, access_token_jti: str | None = None, user_agent: str | None = None, ip_address: str | None = None) -> str`
  - Creates and persists a refresh token for a user; returns the **plaintext** token to send to the client.
- `async validate_refresh_token(token: str) -> str`
  - Validates token (exists, not revoked, not expired), updates `last_used_at`, returns `user_id`.
  - Raises `fastapi.HTTPException(401)` on invalid/revoked/expired tokens.
- `async revoke_refresh_token(token: str, reason: str = "user_requested") -> None`
  - Revokes a single refresh token by setting `revoked_at` and `revoked_reason`.
- `async revoke_all_user_tokens(user_id: str, reason: str = "password_change") -> None`
  - Revokes all non-revoked refresh tokens for a user.
- `async revoke_access_token(jti: str, user_id: str, expires_at: datetime, reason: str = "logout") -> None`
  - Inserts the access token JTI into `revoked_tokens` (blacklist) until `expires_at`.
- `async is_access_token_revoked(jti: str) -> bool`
  - Returns `True` if `jti` exists in `revoked_tokens`.
- `async cleanup_expired_tokens() -> None`
  - Deletes expired rows from `refresh_tokens` and `revoked_tokens`.

## Configuration/Dependencies
- **Database**
  - Uses `naas_abi.apps.nexus.apps.api.app.core.database.async_engine` with SQLAlchemy `text()` queries.
  - Expected tables/columns (as referenced by queries):
    - `refresh_tokens`: `id`, `user_id`, `token_hash`, `access_token_jti`, `expires_at`, `created_at`, `last_used_at`, `revoked_at`, `revoked_reason`, `user_agent`, `ip_address`
    - `revoked_tokens`: `jti`, `user_id`, `revoked_at`, `revoked_reason`, `expires_at`
- **Settings**
  - `settings.refresh_token_expire_days` controls refresh token lifetime (days).
- **Time**
  - Uses `UTC` from `naas_abi.apps.nexus.apps.api.app.core.datetime_compat`.
  - Stores naive datetimes (`tzinfo` removed via `.replace(tzinfo=None)`).

## Usage
```python
import asyncio
from naas_abi.apps.nexus.apps.api.app.services.refresh_token import (
    create_refresh_token,
    validate_refresh_token,
    revoke_refresh_token,
)

async def main():
    token = await create_refresh_token(user_id="user_123", user_agent="cli", ip_address="127.0.0.1")
    user_id = await validate_refresh_token(token)
    print("Validated for user:", user_id)
    await revoke_refresh_token(token, reason="logout")

asyncio.run(main())
```

## Caveats
- `validate_refresh_token()` raises `HTTPException` with `401 Unauthorized` for invalid, revoked, or expired tokens.
- Refresh tokens are returned **plaintext** only at creation time; database stores only the **hash**.
- Datetimes are stored/compared as **naive** values (timezone info stripped).
