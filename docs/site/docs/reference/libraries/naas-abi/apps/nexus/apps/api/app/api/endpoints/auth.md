# `auth` (Authentication API endpoints)

## What it is
- A FastAPI router implementing authentication and account-management endpoints:
  - Registration/login and JWT access token issuance
  - Refresh token rotation
  - Logout (access token revocation)
  - Password change + session invalidation
  - Password reset flow (token generation/consumption)
  - Avatar upload and profile updates
- Uses async SQLAlchemy sessions (`AsyncSession`) for most DB access, plus direct async engine SQL for some dependency lookups.

## Public API

### FastAPI router
- `router: APIRouter` - mountable router exposing the endpoints below.

### Dependencies (for other endpoints to reuse)
- `get_current_user(token=Depends(oauth2_scheme)) -> User | None`
  - Decodes JWT, checks revocation (by `jti`), returns user or `None`.
- `get_current_user_required(token=Depends(oauth2_scheme)) -> User`
  - Same as above but raises `401 Not authenticated` if missing/invalid.
- `get_workspace_role(user_id: str, workspace_id: str) -> str | None`
  - Returns workspace role, `"owner"` if user owns workspace, else `None`.
- `require_workspace_access(user_id: str, workspace_id: str) -> str`
  - Returns role or raises `403` if user has no access.

### Helper functions
- `verify_password(plain_password: str, hashed_password: str) -> bool` - bcrypt password verification.
- `get_password_hash(password: str) -> str` - bcrypt password hashing.
- `create_access_token(data: dict, expires_delta: timedelta | None = None) -> tuple[str, str]`
  - Creates HS256 JWT with `exp` and a generated `jti`. Returns `(token, jti)`.
- `decode_token(token: str) -> dict | None` - decodes JWT, returns payload or `None`.

### Pydantic schemas
- Request/response models:
  - `UserCreate`, `UserLogin`, `UserUpdate`
  - `Token`, `RefreshTokenRequest`, `RefreshTokenResponse`
  - `AuthResponse`
  - `PasswordChangeRequest`
  - `ForgotPasswordRequest`, `ResetPasswordRequest`
  - `User`, `UserBase` (plus internal `UserInDB`)

### HTTP endpoints (paths are relative to where the router is included)
- `POST /register` → `AuthResponse`
  - Creates user, personal workspace, membership, then returns access+refresh tokens.
  - Applies rate limiting via `check_rate_limit(...)`.
- `POST /login` → `AuthResponse`
  - Email/password login; returns access+refresh tokens.
  - Applies rate limiting.
- `POST /token` → `Token`
  - OAuth2-compatible token endpoint using `OAuth2PasswordRequestForm` (`username` = email).
- `GET /me` → `User`
  - Returns the current authenticated user.
- `PATCH /me` → `User`
  - Updates profile fields (name/email/company/role/bio). Enforces unique email.
- `POST /logout` → `{"status": "logged out"}`
  - Revokes the current access token (by `jti` and `exp`) if present in token payload.
- `POST /refresh` → `RefreshTokenResponse`
  - Validates refresh token, issues new access token + new refresh token, revokes old refresh token.
- `POST /change-password` → status dict
  - Verifies current password, updates password, revokes all user refresh tokens, inserts a row in `password_changes`.
- `POST /forgot-password` → success dict
  - Creates a 1-hour reset token (marks previous unused tokens as used). Always returns success.
  - Logs reset link to server logs (email sending is TODO).
- `POST /reset-password` → success dict
  - Validates reset token (unused, not expired), sets new password, marks token used, revokes all refresh tokens.
- `POST /upload-avatar` → `{"avatar_url": ..., "filename": ...}`
  - Uploads and stores avatar file under `uploads/avatars/`, updates user avatar, deletes prior local avatar.

## Configuration/Dependencies
- Settings (from `naas_abi...core.config.settings`):
  - `settings.secret_key` - HS256 signing key for JWT.
  - `settings.access_token_expire_minutes` - access token TTL (minutes); used to compute `expires_in`.
- Database:
  - `get_db` provides an `AsyncSession`.
  - `async_engine` used directly for some SQL operations (`_get_user_by_id`, workspace role checks, password change insert).
- External services/modules used:
  - `naas_abi...services.refresh_token`: `create_refresh_token`, `validate_refresh_token`, `revoke_refresh_token`, `revoke_access_token`, `revoke_all_user_tokens`, `is_access_token_revoked`
  - `naas_abi...services.rate_limit`: `check_rate_limit`, `get_rate_limit_identifier`
  - `naas_abi...services.audit`: `log_register`, `log_login`, `log_logout`, `log_token_refresh`, `log_password_change`
- File storage:
  - Avatar files stored locally in `uploads/avatars/`
  - Allowed extensions: `.png`, `.jpg`, `.jpeg`, `.gif`, `.webp`
  - Max size: 2MB

## Usage

### Mount the router in FastAPI
```python
from fastapi import FastAPI
from naas_abi.apps.nexus.apps.api.app.api.endpoints import auth

app = FastAPI()
app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
```

### Call login and use the token (example with `requests`)
```python
import requests

base = "http://localhost:8000/api/auth"

r = requests.post(f"{base}/login", json={"email": "user@example.com", "password": "password123"})
r.raise_for_status()
tokens = r.json()

me = requests.get(f"{base}/me", headers={"Authorization": f"Bearer {tokens['access_token']}"})
print(me.json())
```

## Caveats
- `POST /forgot-password` does not send email; it logs a reset link to the server logs and always returns success.
- `POST /logout` revokes the access token only if the JWT payload includes both `jti` and `exp`.
- `POST /upload-avatar` reads the entire upload into memory to enforce the 2MB size limit.
- Avatar storage is local filesystem (`uploads/avatars/`); you must ensure that path is writable and served if clients need to fetch `/uploads/avatars/...`.
- Some DB operations bypass ORM sessions and use raw SQL via `async_engine`, so required tables/columns must match the SQL queries (`users`, `workspace_members`, `workspaces`, `password_changes`).
