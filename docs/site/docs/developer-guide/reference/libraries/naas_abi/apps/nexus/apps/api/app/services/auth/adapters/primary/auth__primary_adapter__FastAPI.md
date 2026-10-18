# AuthFastAPIPrimaryAdapter

## What it is
- A FastAPI **primary adapter** exposing authentication and profile endpoints via an `APIRouter`.
- Handles:
  - Password-based auth (register/login/oauth token, password change/reset)
  - Magic-link auth (request/verify)
  - Session/token refresh and logout
  - User profile read/update
  - Avatar upload, retrieval, and removal backed by object storage

## Public API
### Module-level router
- `router: fastapi.APIRouter`
  - Contains all auth-related routes.

### FastAPI endpoints (registered on `router`)
- `POST /register` → `AuthResponse`
  - Register user (requires `settings.auth_password_enabled`); rate-limited; logs register.
- `POST /login` → `AuthResponse`
  - Password login (requires `settings.auth_password_enabled`); rate-limited; logs login success/failure.
- `POST /token` → `Token`
  - OAuth2 password flow token endpoint (requires `settings.auth_password_enabled`).
- `GET /me` → `User`
  - Return current authenticated user.
- `PATCH /me` → `User`
  - Update current user profile fields; errors on email conflict / missing user.
- `POST /logout` → `{"status": "logged out"}`
  - Logout current user (revokes provided bearer token if present); logs logout.
- `POST /refresh` → `RefreshTokenResponse`
  - Refresh tokens using a refresh token; logs token refresh when user can be resolved.
- `POST /change-password` → dict
  - Change password (requires `settings.auth_password_enabled`); logs password change.
- `POST /forgot-password` → dict
  - Initiate password reset flow (requires `settings.auth_password_enabled`).
- `POST /reset-password` → dict
  - Reset password using reset token (requires `settings.auth_password_enabled`).
- `POST /magic-link/request` → dict
  - Request a magic link; rate-limited; sends email only if SMTP enabled and service returns a token.
- `POST /magic-link/verify` → `AuthResponse`
  - Verify magic link token and issue auth tokens; logs login with `method=magic_link`.
- `POST /upload-avatar` → dict
  - Upload avatar image for current user; validates extension and max size (2MB); stores in object storage; updates user avatar URL.
- `GET /avatar/{filename}` → `fastapi.responses.Response`
  - Fetch avatar bytes from object storage; sets media type by file extension.
- `DELETE /avatar` → `{"status": "ok"}`
  - Remove avatar for current user; deletes old avatar object from storage when applicable.

### Adapter class
- `class AuthFastAPIPrimaryAdapter`
  - `__init__(self) -> None`: exposes `self.router` (the module router) for inclusion into a FastAPI app.

## Configuration/Dependencies
### Settings (from `naas_abi...core.config.settings`)
Used behaviors depend on:
- `settings.auth_password_enabled` (gate password-based flows)
- SMTP / magic-link email:
  - `settings.smtp_enabled`, `smtp_host`, `smtp_port`, `smtp_username`, `smtp_password`, `smtp_use_tls`, `smtp_use_ssl`
  - `smtp_from_email`, `smtp_from_name`
  - `frontend_url`, `magic_link_path`, `magic_link_expire_minutes`
  - `magic_link_email_app_name`
  - `magic_link_email_subject_template`, `magic_link_email_text_template`, `magic_link_email_html_template`

### Injected FastAPI dependencies
- `get_auth_service` → provides `AuthService`
- `get_current_user_required` → provides current `User` (authentication required)
- `oauth2_scheme` → extracts bearer token (optional in logout)
- Rate limiting:
  - `get_rate_limit_identifier(request)`
  - `check_rate_limit(identifier, route_key)`

### Object storage dependency
- `_get_object_storage(request: Request) -> ObjectStorageService`
  - Uses `request.app.state.object_storage` if set.
  - Otherwise attempts to resolve via `naas_abi.ABIModule.get_instance().engine.services.object_storage`.
  - Raises `HTTPException(500)` if not initialized.

### Avatar constraints (constants)
- Storage prefix: `nexus/avatars`
- Allowed extensions: `.png`, `.jpg`, `.jpeg`, `.gif`, `.webp`
- Max size: `2 * 1024 * 1024` bytes (2MB)

## Usage
Minimal inclusion into a FastAPI app:

```python
from fastapi import FastAPI
from naas_abi.apps.nexus.apps.api.app.services.auth.adapters.primary.auth__primary_adapter__FastAPI import (
    AuthFastAPIPrimaryAdapter,
)

app = FastAPI()
auth_adapter = AuthFastAPIPrimaryAdapter()
app.include_router(auth_adapter.router, prefix="/api/auth", tags=["auth"])
```

If you want to supply object storage explicitly (so `_get_object_storage` uses it):

```python
from fastapi import FastAPI
from naas_abi_core.services.object_storage.ObjectStorageService import ObjectStorageService

app = FastAPI()
app.state.object_storage = ObjectStorageService(...)  # configured instance
```

## Caveats
- Password-based endpoints return **HTTP 410** when `settings.auth_password_enabled` is `False`.
- Magic-link email sending is skipped when `settings.smtp_enabled` is `False`.
- Avatar upload:
  - Validates by **file extension** and size; content type is not validated beyond extension mapping.
  - Files are stored under `nexus/avatars`; old avatar deletion is best-effort (errors ignored).
- Object storage must be initialized (via `app.state.object_storage` or `ABIModule`) or avatar operations will return **HTTP 500**.
