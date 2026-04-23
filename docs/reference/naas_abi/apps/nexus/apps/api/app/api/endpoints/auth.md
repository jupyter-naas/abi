# auth (compatibility layer)

## What it is
- A thin compatibility module that re-exports authentication-related constants, schemas, dependencies, and endpoint callables from the underlying auth adapter and service.
- Intended to provide a stable import path (`...endpoints.auth`) without duplicating implementation.

## Public API
All items below are re-exported via `__all__`:

### Constants
- `ALLOWED_AVATAR_EXTENSIONS`: Allowed avatar file extensions.
- `AVATAR_STORAGE_PREFIX`: Storage prefix/path for avatar assets.
- `MAX_AVATAR_SIZE`: Maximum avatar upload size.

### Schemas / Models
- `AuthResponse`
- `ForgotPasswordRequest`
- `MagicLinkRequest`
- `MagicLinkVerifyRequest`
- `PasswordChangeRequest`
- `RefreshTokenRequest`
- `RefreshTokenResponse`
- `ResetPasswordRequest`
- `Token`
- `User`, `UserBase`, `UserCreate`, `UserInDB`, `UserLogin`, `UserUpdate`

### Endpoint handlers / dependencies (re-exported callables)
- `router`: FastAPI router for auth-related endpoints.
- `oauth2_scheme`: OAuth2 token dependency/scheme.
- Auth flows:
  - `login`, `login_for_access_token`, `logout`
  - `register`
  - `refresh_access_token`
  - `forgot_password`, `reset_password`
  - `request_magic_link`, `verify_magic_link`
  - `change_password`
- User context/access helpers:
  - `get_current_user`, `get_current_user_required`
  - `get_me`, `update_me`
  - `get_workspace_role`, `require_workspace_access`
- Avatar endpoints:
  - `get_avatar`, `upload_avatar`, `remove_avatar`
- Token utility:
  - `decode_token`

### Crypto/token utilities (from service layer)
- `create_access_token`
- `get_password_hash`
- `verify_password`

## Configuration/Dependencies
- Re-exports come from:
  - `naas_abi.apps.nexus.apps.api.app.services.auth.adapters.primary`
  - `naas_abi.apps.nexus.apps.api.app.services.auth.service`
- No configuration is defined in this module itself; behavior depends on the underlying adapter/service implementations.

## Usage
Minimal example: include the re-exported router in a FastAPI app.

```python
from fastapi import FastAPI
from naas_abi.apps.nexus.apps.api.app.api.endpoints import auth

app = FastAPI()
app.include_router(auth.router)
```

## Caveats
- This module contains no logic; it only re-exports symbols. Any runtime behavior, validation, and side effects are determined by the imported adapter/service code.
