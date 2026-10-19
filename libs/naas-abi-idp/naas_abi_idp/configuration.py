"""The provider's configuration.

``IdPConfiguration`` is the module's ``Configuration``: ``python -m naas_abi_idp``
builds it from the environment (``from_environment``), ``naas_abi_sdk.module_runner``
from a JSON file. Nothing here is a secret except a client's ``secret``, which
the provider hashes when it seeds the client and never stores in clear.
"""

from __future__ import annotations

import json
import os
import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlsplit

from naas_abi_sdk.module import ModuleConfiguration

# The access and ID tokens of a provider live ten minutes at most (RFC §9).
MAX_TOKEN_SECONDS = 600
CLIENT_ID = re.compile(r"^[A-Za-z0-9._-]{1,64}$")
GRANT_TYPES = ("authorization_code", "refresh_token", "client_credentials")
DEFAULT_SCOPES = ("openid", "email", "profile", "groups", "offline_access")


@dataclass
class Branding:
    """How the login page and the mail look. Every field is optional text; the
    page escapes it, and only ``https`` (or same-origin) images load."""

    app_name: str = "ABI"
    primary_color: str = "#22c55e"
    background_color: str = "#f5f5f5"
    card_color: str = "#ffffff"
    text_color: str = "#1a1a1a"
    border_radius: int = 12
    logo_url: str | None = None
    footer_text: str = ""
    tab_title: str | None = None

    def __post_init__(self) -> None:
        for name in ("primary_color", "background_color", "card_color", "text_color"):
            if not re.fullmatch(r"#[0-9a-fA-F]{3,8}", getattr(self, name)):
                raise ValueError(f"branding.{name} is a hex color such as #22c55e")
        if not 0 <= int(self.border_radius) <= 48:
            raise ValueError("branding.border_radius is 0 to 48")
        if self.logo_url is not None:
            scheme = urlsplit(self.logo_url).scheme
            if scheme not in ("https", "http", ""):
                raise ValueError("branding.logo_url is an http(s) URL or a path")

    @classmethod
    def of(
        cls, value: Mapping[str, Any] | None, base: Branding | None = None
    ) -> Branding:
        fields = dict((base or cls()).__dict__)
        fields.update(value or {})
        return cls(**fields)


@dataclass
class ClientConfiguration:
    """A relying party the provider seeds at start (ABI itself, for one)."""

    client_id: str
    # Plain secret; None makes a public client (PKCE only). Hashed when seeded.
    secret: str | None = field(default=None, repr=False)
    redirect_uris: list[str] = field(default_factory=list)
    grant_types: list[str] = field(
        default_factory=lambda: ["authorization_code", "refresh_token"]
    )
    scopes: list[str] = field(default_factory=lambda: list(DEFAULT_SCOPES))
    name: str = ""

    def __post_init__(self) -> None:
        if not CLIENT_ID.match(self.client_id):
            raise ValueError(f"Invalid client id {self.client_id!r}")
        unknown = sorted(set(self.grant_types) - set(GRANT_TYPES))
        if unknown:
            raise ValueError(f"Unknown grant types {unknown}")
        if "authorization_code" in self.grant_types and not self.redirect_uris:
            raise ValueError(f"Client {self.client_id}: redirect_uris are required")
        if "client_credentials" in self.grant_types and not self.secret:
            raise ValueError(
                f"Client {self.client_id}: client_credentials needs a secret"
            )


@dataclass
class IdPConfiguration(ModuleConfiguration):
    # The public issuer URL, path included: https://<host>/idp. Stable: it is
    # in every token and in the configuration of every relying party.
    issuer: str = ""
    clients: list[ClientConfiguration] = field(default_factory=list)
    branding: Branding = field(default_factory=Branding)
    # Overrides by email domain, shown once the address is known (an organization's
    # people see their organization's page).
    domain_branding: dict[str, Branding] = field(default_factory=dict)
    from_email: str = "no-reply@abi.local"
    from_name: str | None = None

    # Sign-in codes.
    code_length: int = 6
    code_ttl_seconds: int = 900
    max_attempts: int = 5  # wrong guesses per address, across every active code
    max_active_codes: int = 5
    # Failures per address and per client IP, and the window they count in.
    rate_limit_window_seconds: int = 300
    rate_limit_email_sends: int = 5
    rate_limit_ip_attempts: int = 20
    # Self-registration with just an email (Nexus's magic_link_allow_signup).
    signup_enabled: bool = False
    password_login_enabled: bool = False

    # Tokens and sessions.
    access_token_seconds: int = MAX_TOKEN_SECONDS
    id_token_seconds: int = MAX_TOKEN_SECONDS
    refresh_token_days: int = 30
    session_hours: int = 8
    authorization_code_seconds: int = 60
    authorization_request_seconds: int = 900
    key_rotation_days: int = 30
    groups_claim: str = "groups"
    # The request header Nexus sets to the client's address, which it
    # determined itself (the trusted route overwrites any a browser sends).
    client_ip_header: str = "x-abi-client-ip"

    def __post_init__(self) -> None:
        self.clients = [
            c if isinstance(c, ClientConfiguration) else ClientConfiguration(**c)
            for c in self.clients
        ]
        if isinstance(self.branding, Mapping):
            self.branding = Branding.of(self.branding)
        self.domain_branding = {
            domain.lower(): b
            if isinstance(b, Branding)
            else Branding.of(b, self.branding)
            for domain, b in self.domain_branding.items()
        }
        if self.issuer:
            parts = urlsplit(self.issuer)
            local = parts.hostname in ("localhost", "127.0.0.1", "::1")
            if parts.scheme != "https" and not (parts.scheme == "http" and local):
                raise ValueError("issuer is an https URL (http on localhost only)")
            if parts.query or parts.fragment or self.issuer.endswith("/"):
                raise ValueError("issuer is a bare URL without a trailing slash")
        for name in ("access_token_seconds", "id_token_seconds"):
            if not 60 <= getattr(self, name) <= MAX_TOKEN_SECONDS:
                raise ValueError(f"{name} is 60 to {MAX_TOKEN_SECONDS}")
        if not 4 <= self.code_length <= 10:
            raise ValueError("code_length is 4 to 10")
        if self.max_attempts < 1 or self.max_active_codes < 1:
            raise ValueError("max_attempts and max_active_codes are at least 1")

    def branding_for(self, email: str | None) -> Branding:
        domain = email.rsplit("@", 1)[-1].lower() if email and "@" in email else ""
        return self.domain_branding.get(domain, self.branding)

    @classmethod
    def from_environment(cls, env: Mapping[str, str] | None = None) -> IdPConfiguration:
        """Read ``ABI_IDP_*`` (and ``ABI_IDP_CONFIG``, a JSON file of any field).

        ``ABI_IDP_ISSUER`` is required; ``ABI_IDP_CLIENT_ID`` with
        ``ABI_IDP_CLIENT_SECRET`` and ``ABI_IDP_REDIRECT_URIS`` (comma-separated)
        seed the client ABI signs in with.
        """
        env = os.environ if env is None else env
        data: dict[str, Any] = {}
        path = env.get("ABI_IDP_CONFIG", "").strip()
        if path:
            with open(path, encoding="utf-8") as file:
                data = json.load(file)
        if env.get("ABI_IDP_ISSUER"):
            data["issuer"] = env["ABI_IDP_ISSUER"].strip()
        client_id = env.get("ABI_IDP_CLIENT_ID", "").strip()
        if client_id:
            uris = [u.strip() for u in env.get("ABI_IDP_REDIRECT_URIS", "").split(",")]
            data.setdefault("clients", []).append(
                {
                    "client_id": client_id,
                    "secret": env.get("ABI_IDP_CLIENT_SECRET") or None,
                    "redirect_uris": [u for u in uris if u],
                    "name": env.get("ABI_IDP_CLIENT_NAME", "ABI"),
                }
            )
        for key, cast in (
            ("ABI_IDP_FROM_EMAIL", ("from_email", str)),
            ("ABI_IDP_FROM_NAME", ("from_name", str)),
            ("ABI_IDP_SIGNUP", ("signup_enabled", _flag)),
            ("ABI_IDP_PASSWORD_LOGIN", ("password_login_enabled", _flag)),
        ):
            if env.get(key):
                name, convert = cast
                data[name] = convert(env[key])
        if env.get("ABI_IDP_APP_NAME"):
            data.setdefault("branding", {})["app_name"] = env["ABI_IDP_APP_NAME"]
        if not data.get("issuer"):
            raise ValueError("ABI_IDP_ISSUER (the public issuer URL) is required")
        return cls(**data)


def _flag(value: str) -> bool:
    return value.strip().lower() in ("1", "true", "yes", "on")
