# AuthService

## What it is
Authentication/service layer for the Nexus API. Provides:
- Password-based signup/login and password reset.
- JWT access token issuance/decoding and refresh token rotation.
- Magic-link login with an additional OTP challenge.
- User profile/avatar updates and session/logout revocation hooks.

## Public API

### Data models
- `AuthTokens`
  - `access_token: str` — JWT
  - `refresh_token: str` — opaque refresh token
  - `expires_in: int` — access token TTL in seconds
- `MagicLinkChallenge`
  - `token: str` — long magic-link token (send via email/link)
  - `otp_code: str` — short numeric code (user types)
  - `token_id: str` — persisted challenge id

### Exceptions (stringified error codes)
- `EmailAlreadyRegisteredError` → `"email_already_registered"`
- `EmailAlreadyTakenError` → `"email_already_taken"`
- `UserNotFoundError(user_id: str | None = None)` → `"user_not_found"`
- `InvalidCredentialsError(reason: str, user_id: str | None = None)` → `"invalid_credentials"`
- `CurrentPasswordInvalidError` → `"current_password_invalid"`
- `InvalidResetTokenError` → `"invalid_reset_token"`
- `ExpiredResetTokenError` → `"expired_reset_token"`
- `PasswordAuthenticationDisabledError` → `"password_authentication_disabled"`
- `InvalidMagicLinkError` → `"invalid_magic_link"`
- `ExpiredMagicLinkError` → `"expired_magic_link"`
- `InvalidOtpError` → `"invalid_otp"`
- `ExpiredOtpError` → `"expired_otp"`
- `SignupDisabledError` → `"signup_disabled"`
- `DefaultPasswordNotAllowedError` → `"default_password_not_allowed"`

### Module-level functions
- `generate_otp_code(length: int | None = None) -> str`
  - Generates a numeric OTP (defaults to `settings.otp_code_length`, clamped to 4–10, fallback 6).
- `verify_password(plain_password: str, hashed_password: str) -> bool`
  - Verifies bcrypt hash.
- `get_password_hash(password: str) -> str`
  - Returns bcrypt hash.
- `create_access_token(data: dict, expires_delta: timedelta | None = None) -> tuple[str, str]`
  - Creates HS256 JWT and returns `(token, jti)`. Adds `exp`, `jti`, and numeric `iat`.
- `decode_token(token: str) -> dict | None`
  - Decodes HS256 JWT; returns payload or `None` on `JWTError`.
- `is_session_token(payload: dict) -> bool`
  - Returns `True` when payload has no `"scope"` (session tokens vs scoped link tokens).
- `now_utc_naive() -> datetime`
  - Returns UTC time with `tzinfo=None`.

### `AuthService(adapter: AuthPersistencePort)`
All methods are `async`.

- `register_user(email, password, name, user_agent, ip_address) -> (AuthUserRecord, AuthTokens)`
  - Creates user + default workspace, then issues session tokens.
  - Raises: `PasswordAuthenticationDisabledError`, `SignupDisabledError`, `DefaultPasswordNotAllowedError`, `EmailAlreadyRegisteredError`.
- `login_user(email, password, user_agent, ip_address) -> (AuthUserRecord, AuthTokens)`
  - Validates credentials and issues session tokens.
  - Raises: `PasswordAuthenticationDisabledError`, `InvalidCredentialsError` (including default-password block).
- `create_oauth_access_token(email, password) -> str`
  - Returns only an access token (no refresh token).
  - Raises: `PasswordAuthenticationDisabledError`, `InvalidCredentialsError`.
- `get_user_from_access_token(token: str | None) -> AuthUserRecord | None`
  - Decodes JWT, rejects non-session tokens (`scope` present), checks revocation by `jti`, loads user.
- `update_profile(user_id, name, email, company, role, bio) -> AuthUserRecord`
  - Updates profile; email is normalized to lowercase.
  - Raises: `EmailAlreadyTakenError`, `UserNotFoundError`.
- `logout_user(user_id, token: str | None) -> None`
  - Revokes remote app grants for the user, and revokes the provided access token (when it includes `jti` and `exp`).
- `refresh_tokens(refresh_token, user_agent, ip_address) -> AuthTokens`
  - Validates refresh token, issues new access+refresh tokens, revokes old refresh token as `"rotated"`.
- `change_password(user_id, current_password, new_password, ip_address, user_agent) -> None`
  - Verifies current password, updates password, revokes all user tokens, records password-change event.
  - Raises: `PasswordAuthenticationDisabledError`, `DefaultPasswordNotAllowedError`, `UserNotFoundError`, `CurrentPasswordInvalidError`.
- `forgot_password(email) -> str | None`
  - Creates a 1-hour reset token (returns plaintext token; stores hash). Marks existing unused reset tokens used.
  - Returns `None` if user not found.
  - Raises: `PasswordAuthenticationDisabledError`.
- `reset_password(token, new_password) -> None`
  - Validates reset token and expiry, updates password, marks token used, revokes all user tokens.
  - Raises: `PasswordAuthenticationDisabledError`, `DefaultPasswordNotAllowedError`, `InvalidResetTokenError`, `ExpiredResetTokenError`, `UserNotFoundError`.
- `update_avatar(user_id, avatar_url) -> AuthUserRecord`
  - Updates avatar URL.
  - Raises: `UserNotFoundError`.
- `ensure_user_for_invite(email, *, name=None) -> (AuthUserRecord, bool)`
  - Ensures a user exists for an admin invite; creates user *without* default workspace when missing.
  - Returns `(user, created)`.
- `request_magic_link(email, *, create_if_missing=None) -> MagicLinkChallenge | None`
  - Issues a magic-link token + OTP; stores hashes; enforces max active challenges by marking older unused as used.
  - User provisioning behavior:
    - If user missing and `create_if_missing is False`: returns `None`.
    - If `create_if_missing is True`: creates user *without* default workspace.
    - Else uses `settings.magic_link_allow_signup` to decide; when allowed, creates user *with* default workspace.
- `verify_magic_link(token, user_agent, ip_address) -> (AuthUserRecord, AuthTokens)`
  - Validates/consumes magic-link token, then issues session tokens.
  - Raises: `InvalidMagicLinkError`, `ExpiredMagicLinkError`, `UserNotFoundError`.
- `invalidate_magic_link_challenge(token_id: str) -> None`
  - Marks a magic-link token/challenge as used (for challenges that were never successfully delivered).
- `verify_otp(email, code, user_agent, ip_address) -> (AuthUserRecord, AuthTokens)`
  - Validates OTP against any active (unused, unexpired) magic-link challenges for the user.
  - Increments attempt counters on mismatch; expires challenges that exceed `settings.otp_max_attempts`.
  - Raises: `InvalidOtpError`, `ExpiredOtpError`.

## Configuration/Dependencies

### Settings used (`naas_abi...core.config.settings`)
- JWT/session:
  - `access_token_expire_minutes`
- Password flows:
  - `auth_password_enabled`
  - `auth_signup_enabled`
- Magic link / OTP:
  - `magic_link_allow_signup`
  - `magic_link_expire_minutes`
  - `magic_link_max_active`
  - `otp_code_length`
  - `otp_max_attempts`

### Secret key
- `current_secret_key()` is used to sign/verify JWTs (`HS256`).

### External libraries
- `bcrypt` — password hashing/verification.
- `python-jose` (`jose.jwt`) — JWT encode/decode.
- `hmac.compare_digest` — constant-time OTP hash comparison.

### Service dependencies
- Persistence: `AuthPersistencePort` (user CRUD, profile updates, password reset + magic-link token storage, commit, etc.).
- Refresh/access token utilities (`naas_abi...services.refresh_token`):
  - `create_refresh_token`, `validate_refresh_token`
  - `hash_token`, `hash_otp_code`
  - `is_access_token_revoked`, `revoke_access_token`, `revoke_all_user_tokens`, `revoke_refresh_token`
- Logout side-effect:
  - `naas_abi...services.apps.remote.revocation.revoke_remote_app_grants`

## Usage

```python
import asyncio
from naas_abi.apps.nexus.apps.api.app.services.auth.service import AuthService

async def main():
    adapter = ...  # must implement AuthPersistencePort
    auth = AuthService(adapter)

    user, tokens = await auth.login_user(
        email="user@example.com",
        password="correct-horse-battery-staple",
        user_agent="cli",
        ip_address="127.0.0.1",
    )
    print(user.id, tokens.expires_in)

asyncio.run(main())
```

## Caveats
- Password-based endpoints are gated by `settings.auth_password_enabled`; signup is additionally gated by `settings.auth_signup_enabled`.
- Default/known passwords are explicitly rejected:
  - `register_user`, `change_password`, `reset_password` raise `DefaultPasswordNotAllowedError`.
  - `login_user`, `create_oauth_access_token` reject them as `InvalidCredentialsError(reason="default_password")`.
- `now_utc_naive()` returns naive UTC datetimes; persistence comparisons must be consistent.
- `get_user_from_access_token()` rejects tokens containing `"scope"` (non-session/scoped tokens).
- `forgot_password()` returns a plaintext token (for out-of-band delivery); the persisted value is hashed.
- OTP verification:
  - Normalizes code to digits only and requires exact `settings.otp_code_length`.
  - Counts attempts across all active challenges to avoid resetting guess budget by requesting new codes.
