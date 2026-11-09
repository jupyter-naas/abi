from __future__ import annotations

from datetime import datetime

from naas_abi.apps.nexus.apps.api.app.services.auth.profile_links import (
    normalize_github_handle,
    normalize_linkedin_profile_url,
)
from pydantic import BaseModel, EmailStr, Field, field_validator


class User(BaseModel):
    id: str
    email: EmailStr
    name: str
    created_at: datetime
    avatar: str | None = None
    organization: str | None = None
    job_title: str | None = None
    bio: str | None = None
    linkedin_url: str | None = None
    github_handle: str | None = None
    is_superadmin: bool = False


class UserUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=200)
    # Accepted, never applied: the identity provider states the email.
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

