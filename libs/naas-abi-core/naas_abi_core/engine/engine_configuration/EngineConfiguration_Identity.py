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
      provisioning: none           # builtin | zitadel | keycloak | none
      # provisioning: builtin      # the built-in IdP (naas-abi-idp): its issuer ends
      #                            # with /idp and is reached over NATS; its admin app
      #                            # creates the people an invitation names
      # provisioning: zitadel      # invitations create the user through Zitadel's API:
      # admin:
      #   token: "{{ secret.ZITADEL_PAT }}"   # a machine user's personal access token
      #   url: https://acme.zitadel.cloud     # default: the issuer
      #   org_id: "..."                       # default: the token's organization
      # provisioning: keycloak     # likewise through the realm's admin REST API:
      # admin:
      #   client_id: abi-admin                # a service-account client of the realm
      #   client_secret: "{{ secret.KC_ADMIN_SECRET }}"
      #   send_actions: true                  # Keycloak mails the verify/password link
      # provisioning: none         # users are managed in the provider: an invitation
      #                            # is a pending grant only
      # trust_email: true          # its emails are verified without email_verified (Entra ID)
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
from urllib.parse import urlsplit

from naas_abi_core.services.identity.provider_keys import check_endpoint_url
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

if TYPE_CHECKING:
    from naas_abi_core.services.iam.IAMPorts import IIAMService
    from naas_abi_core.services.identity.IdentityPorts import (
        IdentityProvider,
        OIDCHttpPort,
        ProvisioningPort,
    )
    from naas_abi_core.services.identity.IdentityService import IdentityService

PROVIDER_NAME_PATTERN = r"^[a-z0-9-]{1,32}$"
# Where Nexus serves the built-in IdP: its issuer is https://<host>/idp.
BUILTIN_IDP_PATH = "/idp"


class ProvisioningAdminConfiguration(BaseModel):
    """How ABI calls a provider's admin API to create invited people
    (``provisioning: zitadel | keycloak``)."""

    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)

    # The admin API's origin; the issuer's by default (Keycloak: the server
    # before ``/realms/<realm>``).
    url: str | None = None
    # Zitadel: a machine user's personal access token.
    token: str | None = Field(default=None, repr=False)
    org_id: str | None = None
    # Keycloak: a confidential client with the service account on.
    client_id: str | None = None
    client_secret: str | None = Field(default=None, repr=False)
    realm: str | None = None
    send_actions: bool = True

    @field_validator("url")
    @classmethod
    def _url(cls, value: str | None) -> str | None:
        if value is not None:
            check_endpoint_url(value, what="identity.providers[].admin.url")
        return value

    @field_validator("token", "client_secret")
    @classmethod
    def _secret(cls, value: str | None) -> str | None:
        return value or None


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
    # The admin API an invitation provisions through (zitadel, keycloak).
    admin: ProvisioningAdminConfiguration | None = None
    # Shown on the login page; the name when unset.
    display_name: str | None = None
    # The provider only issues emails it controls (Entra ID sends no
    # email_verified): its email then counts as verified.
    trust_email: bool = False

    @model_validator(mode="after")
    def _admin(self) -> Self:
        admin = self.admin
        if self.provisioning in ("builtin", "none"):
            if admin is not None:
                raise ValueError(
                    f"identity.providers[{self.name}].admin is for zitadel and "
                    f"keycloak: {self.provisioning} needs none"
                )
        elif self.provisioning == "zitadel":
            if admin is None or not admin.token:
                raise ValueError(
                    f"identity.providers[{self.name}]: provisioning zitadel needs "
                    "admin.token (a machine user's personal access token)"
                )
        elif admin is None or not (admin.client_id and admin.client_secret):
            raise ValueError(
                f"identity.providers[{self.name}]: provisioning keycloak needs "
                "admin.client_id and admin.client_secret"
            )
        return self

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
            trust_email=self.trust_email,
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
        builtin = [p for p in self.providers if p.provisioning == "builtin"]
        if len(builtin) > 1:
            raise ValueError(
                "identity.providers: only one provider is the built-in IdP "
                f"(provisioning: builtin): {[p.name for p in builtin]}"
            )
        for p in builtin:
            if urlsplit(p.issuer).path != BUILTIN_IDP_PATH:
                raise ValueError(
                    f"identity.providers[{p.name}]: the built-in IdP is served at "
                    f"{BUILTIN_IDP_PATH}, so its issuer ends with it "
                    f"(https://<host>{BUILTIN_IDP_PATH}), not {p.issuer!r}"
                )
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

        http: OIDCHttpPort = OIDCHttpHttpx(
            timeout_seconds=self.verifier.http_timeout_seconds
        )
        builtin = [p.issuer for p in self.providers if p.provisioning == "builtin"]
        if builtin:
            # The built-in IdP has no port: its issuer is read over NATS (the
            # serving engine attaches the app client, ``Engine.__serve``).
            from naas_abi_core.services.identity.adapters.secondary.OIDCHttpBuiltinIdP import (
                OIDCHttpBuiltinIdP,
            )

            http = OIDCHttpBuiltinIdP(http, builtin)
        provisioning = {
            p.name: adapter
            for p in self.providers
            if (adapter := _provisioning(p, self.verifier.http_timeout_seconds))
            is not None
        }
        service = IdentityService(
            [p.to_provider() for p in self.providers],
            iam,  # type: ignore[arg-type]  # the owner: resolve_idp_groups is IAMService's
            http,
            default_provider=self.default_provider,
            clock_skew_seconds=self.verifier.clock_skew_seconds,
            jwks_cache_seconds=self.verifier.jwks_cache_seconds,
            discovery_cache_seconds=self.verifier.discovery_cache_seconds,
            refetch_seconds=self.verifier.jwks_refetch_seconds,
            provisioning=provisioning,
        )
        if self.providers:
            warm_up_in_background(service)
        return service


def _provisioning(
    provider: IdentityProviderConfiguration, timeout: float
) -> ProvisioningPort | None:
    """The adapter of a provider's ``provisioning`` setting; None for ``none``."""
    from naas_abi_core.services.identity.adapters.secondary.AdminHttp import (
        AdminHttp,
        ClientCredentialsToken,
    )

    admin = provider.admin
    if provider.provisioning == "builtin":
        from naas_abi_core.services.identity.adapters.secondary.ProvisioningBuiltinIdP import (
            ProvisioningBuiltinIdP,
        )

        return ProvisioningBuiltinIdP(provider.name)
    if provider.provisioning == "zitadel" and admin is not None:
        from naas_abi_core.services.identity.adapters.secondary.ProvisioningZitadel import (
            ProvisioningZitadel,
        )

        bearer = {"Authorization": f"Bearer {admin.token}"}
        return ProvisioningZitadel(
            provider.name,
            AdminHttp(
                admin.url or provider.issuer,
                headers=lambda: bearer,
                timeout_seconds=timeout,
            ),
            org_id=admin.org_id,
        )
    if provider.provisioning == "keycloak" and admin is not None:
        from naas_abi_core.services.identity.adapters.secondary.ProvisioningKeycloak import (
            ProvisioningKeycloak,
            admin_location,
        )

        server, realm = admin_location(provider.issuer, admin.url, admin.realm)
        token = ClientCredentialsToken(
            f"{provider.issuer.rstrip('/')}/protocol/openid-connect/token",
            admin.client_id or "",
            admin.client_secret or "",
            timeout_seconds=timeout,
        )
        return ProvisioningKeycloak(
            provider.name,
            AdminHttp(server, headers=token.headers, timeout_seconds=timeout),
            realm,
            send_actions=admin.send_actions,
        )
    return None


def warm_up_in_background(service: IdentityService) -> None:
    """Read each provider's discovery document and JWKS without delaying boot;
    one that cannot be read is logged, and read again on first use."""
    import threading

    from naas_abi_core import logger

    def warm_up() -> None:
        for name, error in service.warm_up().items():
            logger.warning(f"Identity provider {name}: {error}")

    threading.Thread(target=warm_up, name="identity-warm-up", daemon=True).start()
