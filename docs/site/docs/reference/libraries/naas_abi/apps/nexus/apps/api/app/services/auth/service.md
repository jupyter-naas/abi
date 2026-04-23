# AuthService

## What it is
Authentication/service layer for the Nexus API that:
- Manages password-based registration/login, OAuth password grant access tokens, magic-link login, and profile updates.
- Issues and validates JWT access tokens and rotates refresh tokens.
- Coordinates persistence through an `AuthPersistencePort` adapter and token revocation/refresh-token utilities.

## Public API

### Data models
- `AuthTokens`
  - Fields: `access_token: str`, `refresh_token: str`, `expires_in: int` (seconds)

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

### Module-level functions
- `verify_password(plain_password: str, hashed_password: str) -> bool`
  - Verifies a bcrypt-hashed password.
- `get_password_hash(password: str) -> str`
  - Produces a bcrypt hash.
- `create_access_token(data: dict, expires_delta: timedelta | None = None) -> tuple[str, str]`
  - Creates a JWT access token and returns `(token, jti)`. Adds `exp` and `jti` claims.
- `decode_token(token: str) -> dict | None`
  - Decodes a JWT using configured secret; returns payload or `None` on decode/validation errors.
- `now_utc_naive() -> datetime`
  - Returns current UTC time as a *naive* `datetime` (`tzinfo=None`).

### `AuthService(adapter: AuthPersistencePort)`
Service class; all methods are `async`.

- `register_user(email, password, name, user_agent, ip_address) -> (AuthUserRecord, AuthTokens)`
  - Creates a user (with personal workspace), then returns user + access/refresh tokens.
  - Raises: `PasswordAuthenticationDisabledError`, `EmailAlreadyRegisteredError`.
- `login_user(email, password, user_agent, ip_address) -> (AuthUserRecord, AuthTokens)`
  - Authenticates user by email/password; returns user + tokens.
  - Raises: `PasswordAuthenticationDisabledError`, `InvalidCredentialsError`.
- `create_oauth_access_token(email, password) -> str`
  - Returns only an access token for valid email/password.
  - Raises: `PasswordAuthenticationDisabledError`, `InvalidCredentialsError`.
- `get_user_from_access_token(token: str | None) -> AuthUserRecord | None`
  - Decodes JWT, checks revocation by `jti` (if present), and loads user from persistence.
- `update_profile(user_id, name, email, company, role, bio) -> AuthUserRecord`
  - Updates profile fields; normalizes email to lowercase.
  - Raises: `EmailAlreadyTakenError`, `UserNotFoundError`.
- `logout_user(user_id, token: str | None) -> None`
  - If token decodes and includes `jti`/`exp`, revokes that access token until expiry.
- `refresh_tokens(refresh_token, user_agent, ip_address) -> AuthTokens`
  - Validates refresh token, issues new access+refresh tokens, revokes old refresh token as `"rotated"`.
- `change_password(user_id, current_password, new_password, ip_address, user_agent) -> None`
  - Verifies current password, updates stored password, revokes all user tokens, records a password-change event.
  - Raises: `PasswordAuthenticationDisabledError`, `UserNotFoundError`, `CurrentPasswordInvalidError`.
- `forgot_password(email) -> str | None`
  - Generates a one-time reset token (returned in plaintext), stores only a hash, and invalidates previous unused reset tokens.
  - Returns `None` if user not found.
  - Raises: `PasswordAuthenticationDisabledError`.
- `reset_password(token, new_password) -> None`
  - Validates reset token (must exist and not be expired), updates password, marks token used, revokes all user tokens.
  - Raises: `PasswordAuthenticationDisabledError`, `InvalidResetTokenError`, `ExpiredResetTokenError`, `UserNotFoundError`.
- `update_avatar(user_id, avatar_url) -> AuthUserRecord`
  - Updates avatar URL.
  - Raises: `UserNotFoundError`.
- `request_magic_link(email) -> str | None`
  - Issues a magic-link token (returned in plaintext), stores only a hash.
  - If user does not exist: may create a new user when `settings.magic_link_allow_signup` is enabled; otherwise returns `None`.
- `verify_magic_link(token, user_agent, ip_address) -> (AuthUserRecord, AuthTokens)`
  - Validates and consumes a magic-link token, then issues access+refresh tokens.
  - Raises: `InvalidMagicLinkError`, `ExpiredMagicLinkError`, `UserNotFoundError`.

## Configuration/Dependencies

### Settings used (`naas_abi...core.config.settings`)
- `secret_key` (JWT signing key)
- `access_token_expire_minutes` (access token TTL)
- `auth_password_enabled` (gate for password-based flows)
- `magic_link_allow_signup` (allow creating users when requesting magic link for unknown email)
- `magic_link_expire_minutes` (magic-link token TTL)
- `magic_link_max_active` (used to limit active unused magic-link tokens)

### External libraries
- `bcrypt` for password hashing/verification.
- `python-jose` (`jose.jwt`) for JWT encode/decode.

### Token/refresh-token subsystem (`naas_abi...services.refresh_token`)
Used for:
- Creating refresh tokens (`create_refresh_token`)
- Hashing and validating tokens (`hash_token`, `validate_refresh_token`)
- Revocation checks and operations (`is_access_token_revoked`, `revoke_access_token`, `revoke_all_user_tokens`, `revoke_refresh_token`)

### Persistence adapter
- Requires an implementation of `AuthPersistencePort` (methods used include user CRUD, token storage/marking, and `commit()`).
- Domain records:
  - `AuthUserRecord` returned by adapter user queries/mutations.

## Usage

Minimal example showing how to instantiate the service (adapter implementation is application-specific):

```python
from naas_abi.apps.nexus.apps.api.app.services.auth.service import AuthService

# adapter must implement AuthPersistencePort (not shown here)
adapter = ...  # provide your concrete persistence adapter

auth = AuthService(adapter)

# In an async context:
# user, tokens = await auth.login_user("user@example.com", "password", user_agent=None, ip_address=None)
```

## Caveats
- Access tokens are JWTs signed with `HS256` using `settings.secret_key`; decoding returns `None` on any JWT error.
- `now_utc_naive()` returns a naive UTC datetime; persistence layer should store/compare timestamps consistently.
- Logout only revokes the presented access token if it contains both `jti` and `exp`.
- Password flows (`register_user`, `login_user`, `forgot_password`, `reset_password`, `change_password`, `create_oauth_access_token`) are disabled when `settings.auth_password_enabled` is `False`.
- `forgot_password()` and `request_magic_link()` return plaintext tokens intended to be delivered out-of-band (email); only hashes are stored.
