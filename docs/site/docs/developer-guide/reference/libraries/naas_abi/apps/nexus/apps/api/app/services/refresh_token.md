# refresh_token

## What it is
- Service module for managing long-lived refresh tokens and access-token revocation.
- Provides:
  - Refresh token generation and hashing for storage.
  - Refresh token creation, validation (with last-used tracking), and revocation.
  - Access token blacklist insert/check.
  - Cleanup of expired refresh/revoked tokens.

## Public API
- `generate_refresh_token() -> str`
  - Generate a cryptographically secure, URL-safe refresh token (plaintext).
- `hash_token(token: str) -> str`
  - SHA-256 hash of a refresh token for storage/lookup.
- `hash_otp_code(code: str) -> str`
  - HMAC-SHA256 of an OTP code using the current server secret.
- `create_refresh_token(user_id: str, access_token_jti: str | None = None, user_agent: str | None = None, ip_address: str | None = None) -> str`
  - Inserts a refresh token row into `refresh_tokens` and returns the plaintext token.
- `validate_refresh_token(token: str) -> str`
  - Validates existence, non-revocation, and non-expiration; updates `last_used_at`; returns `user_id`.
  - Raises `fastapi.HTTPException(401)` when invalid/revoked/expired.
- `revoke_refresh_token(token: str, reason: str = "user_requested") -> None`
  - Marks a refresh token as revoked (`revoked_at`, `revoked_reason`) by token hash.
- `revoke_all_user_tokens(user_id: str, reason: str = "password_change") -> None`
  - Revokes all non-revoked refresh tokens for a user and calls `revoke_remote_app_grants(user_id)`.
- `revoke_access_token(jti: str, user_id: str, expires_at: datetime, reason: str = "logout") -> None`
  - Inserts a row into `revoked_tokens` to blacklist an access token until `expires_at`.
- `is_access_token_revoked(jti: str) -> bool`
  - Returns `True` if `jti` exists in `revoked_tokens`.
- `cleanup_expired_tokens() -> None`
  - Deletes expired rows from `refresh_tokens` and `revoked_tokens` based on `expires_at`.

## Configuration/Dependencies
- **Settings**
  - `settings.refresh_token_expire_days`: controls refresh token lifetime via `timedelta(days=...)`.
- **Secret key**
  - `current_secret_key()`: used by `hash_otp_code()` for HMAC.
- **Database**
  - Uses `async_engine.begin()` and raw SQL via `sqlalchemy.text`.
  - Expected tables/columns:
    - `refresh_tokens`: `id`, `user_id`, `token_hash`, `access_token_jti`, `expires_at`, `created_at`, `user_agent`, `ip_address`, `last_used_at`, `revoked_at`, `revoked_reason`
    - `revoked_tokens`: `jti`, `user_id`, `revoked_at`, `revoked_reason`, `expires_at`
- **Time**
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
    token = await create_refresh_token(
        user_id="user_123",
        user_agent="cli",
        ip_address="127.0.0.1",
    )

    user_id = await validate_refresh_token(token)
    print(user_id)

    await revoke_refresh_token(token, reason="logout")

asyncio.run(main())
```

## Caveats
- Refresh tokens are only returned **in plaintext** by `create_refresh_token()`; only the SHA-256 hash is stored.
- `validate_refresh_token()` raises `HTTPException(401)` for invalid, revoked, or expired tokens.
- Timestamps are stored/compared as **naive** datetimes derived from UTC; database/application must follow the same convention.
- `revoke_all_user_tokens()` performs an additional side effect: it calls `revoke_remote_app_grants(user_id)` after revoking tokens.
