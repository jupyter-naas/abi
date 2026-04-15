from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


class UserBase(BaseModel):
    email: EmailStr
    name: str


class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)
    name: str = Field(..., min_length=1, max_length=200)


class UserLogin(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=1, max_length=128)


class MagicLinkRequest(BaseModel):
    email: EmailStr


class MagicLinkVerifyRequest(BaseModel):
    token: str = Field(..., min_length=1)


class User(UserBase):
    id: str
    created_at: datetime
    avatar: str | None = None
    company: str | None = None
    role: str | None = None
    bio: str | None = None


class UserInDB(User):
    hashed_password: str


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class RefreshTokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class AuthResponse(BaseModel):
    user: User
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class UserUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=200)
    email: str | None = Field(None, min_length=3, max_length=255)
    company: str | None = Field(None, max_length=200)
    role: str | None = Field(None, max_length=100)
    bio: str | None = Field(None, max_length=1000)


class RefreshTokenRequest(BaseModel):
    refresh_token: str = Field(..., description="Refresh token")


class PasswordChangeRequest(BaseModel):
    current_password: str = Field(..., min_length=1, max_length=128)
    new_password: str = Field(..., min_length=8, max_length=128)


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str = Field(..., min_length=1)
    new_password: str = Field(..., min_length=8, max_length=128)
