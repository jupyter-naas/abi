"""Login page fields of ``tenant:``, shared by mounted and standalone Nexus.

Defined once: ``naas_abi.NexusConfig`` is dumped into the Nexus ``Settings``
and both ``TenantConfig`` models refuse extra keys, so two copies that drift
apart refuse every configuration that sets the drifted fields. Both inherit
from :class:`TenantLoginConfig`.

The values reach the public login page (``/api/tenant`` needs no session), so
they are checked when the configuration loads, each error naming its field.
"""

from __future__ import annotations

from typing import Any
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, field_validator, model_validator

# The logo image's height on the login and "No workspace yet" pages, in pixels.
DEFAULT_LOGO_HEIGHT = 48
MIN_LOGO_HEIGHT = 16
MAX_LOGO_HEIGHT = 256


def _is_absolute_http_url(value: str) -> bool:
    """An http(s) URL with a host, a valid port if any, and no space or control
    character. urlsplit raises on a malformed IPv6 host, and reading ``port``
    on a port that is not a number."""
    if any(ord(ch) <= 32 for ch in value):
        return False
    try:
        parts = urlsplit(value)
        _ = parts.port
    except ValueError:
        return False
    return parts.scheme in ("http", "https") and bool(parts.hostname)


class TenantLoginConfig(BaseModel):
    """Heading, logo height and footer link of the Nexus login page."""

    model_config = ConfigDict(extra="forbid")

    # A static heading, "Sign in to continue" under it. Unset: the Welcome typewriter.
    login_heading: str | None = None
    # Height of the logo image (logo_rectangle_url or logo_url), 16 to 256 pixels.
    logo_height: int = DEFAULT_LOGO_HEIGHT
    # A link on its own line under login_footer_text, opened in a new tab.
    # Both set or both unset; the URL is an absolute http(s) URL.
    login_footer_link_label: str | None = None
    login_footer_link_url: str | None = None

    @field_validator(
        "login_heading",
        "login_footer_link_label",
        "login_footer_link_url",
        mode="before",
    )
    @classmethod
    def _blank_is_unset(cls, value: Any) -> Any:
        if isinstance(value, str):
            return value.strip() or None
        return value

    @field_validator("logo_height")
    @classmethod
    def _logo_height_in_range(cls, value: int) -> int:
        if not MIN_LOGO_HEIGHT <= value <= MAX_LOGO_HEIGHT:
            raise ValueError(
                f"tenant.logo_height is {MIN_LOGO_HEIGHT} to {MAX_LOGO_HEIGHT} "
                f"(pixels), got {value}"
            )
        return value

    @field_validator("login_footer_link_url")
    @classmethod
    def _footer_link_is_http_url(cls, value: str | None) -> str | None:
        if value is not None and not _is_absolute_http_url(value):
            raise ValueError(
                "tenant.login_footer_link_url is an absolute http(s) URL "
                "such as https://example.org/about"
            )
        return value

    @model_validator(mode="after")
    def _footer_link_label_and_url_together(self) -> TenantLoginConfig:
        if (self.login_footer_link_label is None) != (
            self.login_footer_link_url is None
        ):
            raise ValueError(
                "tenant.login_footer_link_label and tenant.login_footer_link_url "
                "are set together"
            )
        return self
