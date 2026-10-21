from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


class User(BaseModel):
    id: str
    email: EmailStr
    name: str
    created_at: datetime
    avatar: str | None = None
    organization: str | None = None
    job_title: str | None = None
    bio: str | None = None
    is_superadmin: bool = False


class UserUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=200)
    # Accepted, never applied: the identity provider states the email.
    email: str | None = Field(None, min_length=3, max_length=255)
    organization: str | None = Field(None, max_length=200)
    job_title: str | None = Field(None, max_length=100)
    bio: str | None = Field(None, max_length=2000)
