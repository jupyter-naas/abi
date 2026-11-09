"""Users seeded from configuration, shared by mounted and standalone Nexus.

One model for both: ``naas_abi.NexusConfig`` is dumped into the Nexus
``Settings`` and both refuse extra keys, so two copies that drift apart (as
``company``/``role`` against ``organization``/``job_title`` did) refuse every
configuration that sets the drifted fields.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, EmailStr, model_validator


class UserSeedConfig(BaseModel):
    """User definition applied on startup (create by email if missing)."""

    model_config = ConfigDict(extra="forbid")

    email: EmailStr
    name: str
    avatar: str | None = None
    # The profile's free-text company and job title (users.organization and
    # users.job_title), not an organization membership or an access role.
    organization: str | None = None
    job_title: str | None = None
    bio: str | None = None
    is_superadmin: bool = False

    @model_validator(mode="before")
    @classmethod
    def _ignore_the_stored_password_setting(cls, data: Any) -> Any:
        """No password is made for a configured user any more (they sign in at the
        built-in identity provider): the old setting is accepted and ignored."""
        if isinstance(data, dict) and "store_credentials_in_secrets" in data:
            data = {
                k: v for k, v in data.items() if k != "store_credentials_in_secrets"
            }
        return data
