# refresh_token (Refresh Token Service)

## What it is
- Async service functions to:
  - Generate and store long-lived refresh tokens (stored as SHA-256 hashes).
  - Validate refresh tokens and track last use.
  - Revoke refresh tokens (single token or all for a user).
  - Revoke access tokens by inserting them into a blacklist table.
  - Periodically delete expired refresh/revoked tokens.

## Public API
- `generate_refresh_token() -> str`
  - Generates a cryptographically secure refresh token (URL-safe).
- `hash_token(token: str) -> str`
  - SHA-256 hash used for storing/looking up refresh tokens.
- `create_refresh_token(user_id: str, access_token_jti: str | None = None, user_agent: str | None = None, ip_address: str | None = None) -> str`
  - Creates a refresh token record in `refresh_tokens` and returns the **plaintext** token to return to the client.
- `validate_refresh_token(token: str) -> str`
  - Validates a refresh token (exists, not revoked, not expired), updates `last_used_at`, and returns `user_id`.
  - Raises `fastapi.HTTPException(401)` for invalid/revoked/expired tokens.
- `revoke_refresh_token(token: str, reason: str = "user_requested") -> None`
  - Marks a refresh token as revoked (`revoked_at`, `revoked_reason`) by token hash.
- `revoke_all_user_tokens(user_id: str, reason: str = "password_change") -> None`
  - Revokes all non-revoked refresh tokens for a user.
- `revoke_access_token(jti: str, user_id: str, expires_at: datetime, reason: str = "logout") -> None`
  - Inserts an access token into `revoked_tokens` (blacklist) for immediate revocation.
- `is_access_token_revoked(jti: str) -> bool`
  - Checks `revoked_tokens` for the given `jti`.
- `cleanup_expired_tokens() -> None`
  - Deletes expired rows from `refresh_tokens` and `revoked_tokens`.

## Configuration/Dependencies
- **Settings**
  - `settings.refresh_token_expire_days`: used to compute refresh token expiration (`now + timedelta(days=...)`).
- **Database**
  - Uses `async_engine` and raw SQL (`sqlalchemy.text`) with `async_engine.begin()`.
  - Expected tables/columns:
    - `refresh_tokens`: `id`, `user_id`, `token_hash`, `access_token_jti`, `expires_at`, `created_at`, `user_agent`, `ip_address`, `last_used_at`, `revoked_at`, `revoked_reason`
    - `revoked_tokens`: `jti`, `user_id`, `revoked_at`, `revoked_reason`, `expires_at`
- **Time handling**
  - Uses `datetime.now(UTC).replace(tzinfo=None)` (naive UTC timestamps).

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
- Refresh tokens are **returned in plaintext** only at creation time; only hashes are stored. Persist the plaintext token client-side if needed.
- Validation raises `HTTPException(401)` for invalid, revoked, or expired tokens.
- Timestamps are stored/compared as **naive** datetimes derived from UTC (`tzinfo` removed); database and application must agree on this convention.
