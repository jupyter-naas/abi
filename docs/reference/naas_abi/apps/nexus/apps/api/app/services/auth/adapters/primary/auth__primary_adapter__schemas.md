# `auth__primary_adapter__schemas`

## What it is
- A collection of **Pydantic models** (schemas) for the auth API layer.
- Defines request/response payload shapes for user auth flows (login, signup, tokens, password reset, profile update).

## Public API
### Models
- `UserBase`
  - Base user fields: `email`, `name`.
- `UserCreate`
  - Signup/create payload: `email`, `password` (8–128 chars), `name` (1–200 chars).
- `UserLogin`
  - Login payload: `email`, `password` (1–128 chars).
- `MagicLinkRequest`
  - Request a magic link: `email`.
- `MagicLinkVerifyRequest`
  - Verify a magic link: `token` (min length 1).
- `User` (extends `UserBase`)
  - User response model: `id`, `created_at`, optional `avatar`, `company`, `role`, `bio`.
- `UserInDB` (extends `User`)
  - User persistence model: adds `hashed_password`.
- `Token`
  - Simple access token response: `access_token`, `token_type` (default `"bearer"`).
- `RefreshTokenResponse`
  - Refresh response: `access_token`, `refresh_token`, `token_type` (default `"bearer"`), `expires_in`.
- `AuthResponse`
  - Auth response with user + tokens: `user`, `access_token`, `refresh_token`, `token_type` (default `"bearer"`), `expires_in`.
- `UserUpdate`
  - Partial user update payload (all optional): `name`, `email`, `company`, `role`, `bio` with length constraints.
- `RefreshTokenRequest`
  - Refresh request payload: `refresh_token` (has description `"Refresh token"`).
- `PasswordChangeRequest`
  - Password change payload: `current_password` (1–128), `new_password` (8–128).
- `ForgotPasswordRequest`
  - Forgot-password payload: `email`.
- `ResetPasswordRequest`
  - Reset-password payload: `token` (min length 1), `new_password` (8–128).

## Configuration/Dependencies
- Depends on:
  - `pydantic.BaseModel`, `pydantic.Field`, `pydantic.EmailStr`
  - `datetime.datetime`
- Uses Python 3.10+ union syntax (`str | None`).

## Usage
```python
from datetime import datetime
from pydantic import ValidationError

# Import the models from your package/module path
# from naas_abi.apps.nexus.apps.api.app.services.auth.adapters.primary.auth__primary_adapter__schemas import (
#     UserCreate, AuthResponse, User
# )

# Example: validate a signup payload
from pydantic import BaseModel, EmailStr, Field

class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)
    name: str = Field(..., min_length=1, max_length=200)

try:
    user_create = UserCreate(email="user@example.com", password="supersecret", name="Alice")
    print(user_create.model_dump())
except ValidationError as e:
    print(e)
```

## Caveats
- Field validation is enforced by Pydantic constraints:
  - Password minimum lengths differ by context (`UserLogin.password` allows min 1; create/reset require min 8).
- `UserInDB` includes `hashed_password` and is intended for internal use (do not expose directly in API responses).
