from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, EmailStr, Field, field_validator

from naas_abi.apps.nexus.apps.api.app.services.auth.profile_links import (
    normalize_github_handle,
    normalize_linkedin_profile_url,
)


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


class OtpVerifyRequest(BaseModel):
    email: EmailStr
    code: str = Field(..., min_length=4, max_length=16)


class User(UserBase):
    id: str
    created_at: datetime
    avatar: str | None = None
    organization: str | None = None
    job_title: str | None = None
    bio: str | None = None
    linkedin_url: str | None = None
    github_handle: str | None = None
    is_superadmin: bool = False


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
    organization: str | None = Field(None, max_length=200)
    job_title: str | None = Field(None, max_length=100)
    bio: str | None = Field(None, max_length=2000)
    # An empty string clears the field.
    linkedin_url: str | None = Field(None, max_length=500)
    github_handle: str | None = Field(None, max_length=100)

    @field_validator("linkedin_url")
    @classmethod
    def _linkedin_profile(cls, value: str | None) -> str | None:
        if value is None or not value.strip():
            return value if value is None else ""
        normalized = normalize_linkedin_profile_url(value)
        if normalized is None:
            raise ValueError(
                "Enter a LinkedIn profile URL, like https://www.linkedin.com/in/your-name"
            )
        return normalized

    @field_validator("github_handle")
    @classmethod
    def _github(cls, value: str | None) -> str | None:
        if value is None or not value.strip():
            return value if value is None else ""
        normalized = normalize_github_handle(value)
        if normalized is None:
            raise ValueError("Enter a GitHub username, like octocat")
        return normalized


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
