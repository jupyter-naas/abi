"""``identity``: the OIDC identity providers the engine trusts (RFC §12.1).

```yaml
identity:
  default_provider: acme           # where a login with no routed email domain goes
  providers:
    - name: acme                   # ^[a-z0-9-]{1,32}$, unique
      issuer: https://acme.okta.com
      client_id: abi
      client_secret: "{{ secret.ACME_OIDC_SECRET }}"
      groups_claim: groups         # optional: the claim IAM maps to groups
      scopes: [openid, email, profile, groups, offline_access]
      provisioning: none           # builtin | zitadel | keycloak | none (subtask 10)
  verifier:                        # optional tuning
    clock_skew_seconds: 30
    jwks_cache_seconds: 300
    jwks_refetch_seconds: 30
    http_timeout_seconds: 10
```

Validated when the configuration loads: names, unique issuers, ``https``
issuers (``http`` on localhost only), a default that names a provider, and
``openid`` among the scopes. Each provider's discovery document
(``<issuer>/.well-known/openid-configuration``) and JWKS are read when the
service loads; one that cannot be read is logged and retried on first use, so
a provider that is down does not stop the engine.

No ``identity`` block, or no providers: the engine trusts no provider, and
Nexus keeps only its own login.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal, Self

from naas_abi_core.services.identity.provider_keys import check_endpoint_url
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

if TYPE_CHECKING:
    from naas_abi_core.services.iam.IAMPorts import IIAMService
    from naas_abi_core.services.identity.IdentityPorts import IdentityProvider
    from naas_abi_core.services.identity.IdentityService import IdentityService

PROVIDER_NAME_PATTERN = r"^[a-z0-9-]{1,32}$"


class IdentityProviderConfiguration(BaseModel):
    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)

    name: str = Field(pattern=PROVIDER_NAME_PATTERN)
    issuer: str
    client_id: str = Field(min_length=1)
    # A secret reference ("{{ secret.X }}"), rendered when the config loads.
    # None for a public client (PKCE only).
    client_secret: str | None = Field(default=None, repr=False)
    groups_claim: str | None = None
    scopes: list[str] = Field(default_factory=lambda: ["openid", "email", "profile"])
    provisioning: Literal["builtin", "zitadel", "keycloak", "none"] = "none"
    # Shown on the login page; the name when unset.
    display_name: str | None = None

    @field_validator("issuer")
    @classmethod
    def _issuer(cls, value: str) -> str:
        check_endpoint_url(value, what="identity.providers[].issuer")
        if value != value.strip() or "?" in value or "#" in value:
            raise ValueError("identity.providers[].issuer is a bare URL")
        return value

    @field_validator("client_secret")
    @classmethod
    def _secret(cls, value: str | None) -> str | None:
        # An empty render ("{{ secret.MISSING }}" in a bootstrap pass) is no secret.
        return value or None

    @field_validator("scopes")
    @classmethod
    def _scopes(cls, value: list[str]) -> list[str]:
        if "openid" not in value:
            raise ValueError("identity.providers[].scopes must include openid")
        if any(not s or " " in s for s in value):
            raise ValueError("identity.providers[].scopes are single words")
        return list(dict.fromkeys(value))

    def to_provider(self) -> IdentityProvider:
        from naas_abi_core.services.identity.IdentityPorts import IdentityProvider

        return IdentityProvider(
            name=self.name,
            issuer=self.issuer,
            client_id=self.client_id,
            client_secret=self.client_secret,
            groups_claim=self.groups_claim,
            scopes=tuple(self.scopes),
            provisioning=self.provisioning,
            display_name=self.display_name,
        )


class IdentityVerifierConfiguration(BaseModel):
    model_config = ConfigDict(extra="forbid")

    clock_skew_seconds: int = Field(default=30, ge=0, le=300)
    jwks_cache_seconds: float = Field(default=300, gt=0, le=3600)
    jwks_refetch_seconds: float = Field(default=30, ge=0, le=3600)
    discovery_cache_seconds: float = Field(default=3600, gt=0, le=86400)
    http_timeout_seconds: float = Field(default=10, gt=0, le=120)


class IdentityConfiguration(BaseModel):
    model_config = ConfigDict(extra="forbid")

    default_provider: str | None = None
    providers: list[IdentityProviderConfiguration] = Field(default_factory=list)
    verifier: IdentityVerifierConfiguration = Field(
        default_factory=IdentityVerifierConfiguration
    )

    @model_validator(mode="after")
    def _check(self) -> Self:
        names = [p.name for p in self.providers]
        duplicates = sorted({n for n in names if names.count(n) > 1})
        if duplicates:
            raise ValueError(f"identity.providers: duplicate names {duplicates}")
        issuers = [p.issuer for p in self.providers]
        shared = sorted({i for i in issuers if issuers.count(i) > 1})
        if shared:
            raise ValueError(f"identity.providers: issuers used twice {shared}")
        if self.default_provider is not None and self.default_provider not in names:
            raise ValueError(
                f"identity.default_provider {self.default_provider!r} names no provider"
            )
        return self

    def load(self, iam: IIAMService) -> IdentityService:
        from naas_abi_core.services.identity.adapters.secondary.OIDCHttpHttpx import (
            OIDCHttpHttpx,
        )
        from naas_abi_core.services.identity.IdentityService import IdentityService

        service = IdentityService(
            [p.to_provider() for p in self.providers],
            iam,  # type: ignore[arg-type]  # the owner: resolve_idp_groups is IAMService's
            OIDCHttpHttpx(timeout_seconds=self.verifier.http_timeout_seconds),
            default_provider=self.default_provider,
            clock_skew_seconds=self.verifier.clock_skew_seconds,
            jwks_cache_seconds=self.verifier.jwks_cache_seconds,
            discovery_cache_seconds=self.verifier.discovery_cache_seconds,
            refetch_seconds=self.verifier.jwks_refetch_seconds,
        )
        if self.providers:
            _warm_up_in_background(service)
        return service


def _warm_up_in_background(service: IdentityService) -> None:
    """Read each provider's discovery document and JWKS without delaying boot;
    one that cannot be read is logged, and read again on first use."""
    import threading

    from naas_abi_core import logger

    def warm_up() -> None:
        for name, error in service.warm_up().items():
            logger.warning(f"Identity provider {name}: {error}")

    threading.Thread(target=warm_up, name="identity-warm-up", daemon=True).start()
